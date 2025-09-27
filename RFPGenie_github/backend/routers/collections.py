from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
from pathlib import Path
import pypdf
import docx
import json
import litellm
import logging
from ..agent.ingestion_agent import ingestion_agent, CATEGORIES
from ..database import supabase_rag
from google.adk.models.llm_request import LlmRequest
from google.genai import types

router = APIRouter()

UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def read_document(file_path: Path) -> str:
    """Reads content from .pdf, .docx, or .txt file."""
    extension = file_path.suffix.lower()
    content = ""
    try:
        if extension == ".pdf":
            with file_path.open("rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    content += page.extract_text() or ""
        elif extension == ".docx":
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                content += para.text + "\n"
        elif extension == ".txt":
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file {file_path.name}: {e}")

@router.post("/collections/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Uploads a document, performs agentic chunking, creates embeddings,
    and stores them in the Supabase vector database.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file name provided.")

    file_path = UPLOAD_DIR / file.filename
    logger.info(f"Receiving file: {file.filename}")

    # Check if a document with this name already exists
    existing_docs_response = supabase_rag.table('documents').select('id', count='exact').eq('metadata->>source', file.filename).execute()
    if existing_docs_response.count > 0:
        raise HTTPException(status_code=409, detail=f"A document named '{file.filename}' already exists in the knowledge base.")

    try:
        logger.info(f"Saving file to: {file_path}")
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info("File saved successfully.")
    except Exception as e:
        logger.error(f"Could not save file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        file.file.close()

    try:
        # 1. Read document content
        logger.info("Reading document content.")
        document_content = read_document(file_path)
        if not document_content.strip():
            logger.warning("Document is empty or could not be read.")
            raise HTTPException(status_code=400, detail="Document is empty or could not be read.")
        logger.info(f"Document content read, length: {len(document_content)} characters.")

        # 2. Invoke Ingestion Agent for agentic chunking
        logger.info("Invoking ingestion agent for chunking.")
        prompt = f"Source: {file.filename}\n\n{document_content}"
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                system_instruction=ingestion_agent.instruction
            )
        )
        
        response_generator = ingestion_agent.model.generate_content_async(llm_request)
        
        response_text = ""
        async for response_part in response_generator:
            if response_part.content and response_part.content.parts:
                response_text += response_part.content.parts[0].text

        logger.info(f"Raw response from agent: {response_text}")

        # Clean up the response to get valid JSON
        json_response_str = response_text.strip()
        if json_response_str.startswith("```json"):
            json_response_str = json_response_str[7:]
        if json_response_str.endswith("```"):
            json_response_str = json_response_str[:-3]
        
        logger.info(f"Cleaned JSON string: {json_response_str}")

        try:
            chunks = json.loads(json_response_str)
            logger.info(f"Successfully parsed {len(chunks)} chunks from agent response.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from chunking agent: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to parse JSON response from chunking agent.")

        # 3. Create embeddings and prepare for storage
        logger.info("Creating embeddings for chunks.")
        documents_to_store = []
        for i, chunk in enumerate(chunks):
            if not all(k in chunk for k in ['collection', 'content', 'metadata']):
                logger.warning(f"Skipping malformed chunk {i+1}: {chunk}")
                continue

            logger.info(f"Generating embedding for chunk {i+1}/{len(chunks)}.")
            logger.info(f"  Collection: {chunk.get('collection')}")
            logger.info(f"  Content: {chunk.get('content')[:100]}...") # Log first 100 chars
            embedding_response = await litellm.aembedding(
                model="text-embedding-3-small",
                input=[chunk['content']]
            )
            embedding = embedding_response.data[0]['embedding']

            documents_to_store.append({
                'collection': chunk['collection'],
                'content': chunk['content'],
                'metadata': chunk['metadata'],
                'embedding': embedding,
            })

        # 4. Store in Supabase
        if documents_to_store:
            logger.info(f"Storing {len(documents_to_store)} documents in Supabase.")
            response = supabase_rag.table('documents').insert(documents_to_store).execute()
            if getattr(response, 'error', None):
                logger.error(f"Failed to store documents in Supabase: {response.error}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to store documents in Supabase: {response.error}")
            logger.info("Successfully stored documents in Supabase.")
        else:
            logger.warning("No documents to store.")

        return {"message": f"Successfully ingested {len(documents_to_store)} chunks from '{file.filename}'."}

    except Exception as e:
        logger.error(f"An error occurred during ingestion: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"An error occurred during ingestion: {str(e)}")
    finally:
        # 5. Clean up the temporary file
        if file_path.exists():
            logger.info(f"Cleaning up temporary file: {file_path}")
            file_path.unlink()

@router.get("/collections")
async def get_collections_by_source():
    """
    Retrieves documents grouped by their source metadata.
    """
    try:
        logger.info("Fetching documents grouped by source.")
        response = supabase_rag.table('documents').select('collection', 'metadata').execute()

        if not response.data:
            logger.info("No documents found.")
            return {}

        # Group collections by source
        source_collections = {}
        for item in response.data:
            source = item.get('metadata', {}).get('source')
            if not source:
                continue

            collection = item.get('collection')
            if source not in source_collections:
                source_collections[source] = {}
            
            if collection not in source_collections[source]:
                source_collections[source][collection] = 0
            source_collections[source][collection] += 1

        # Convert to list format for the frontend
        result = [
            {"source": source, "collections": collections}
            for source, collections in source_collections.items()
        ]

        logger.info(f"Found {len(result)} sources.")
        return result

    except Exception as e:
        logger.error(f"An error occurred while fetching collections by source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch collections.")

@router.delete("/collections/source/{source}")
async def delete_source(source: str):
    """
    Deletes all documents associated with a specific source.
    """
    try:
        logger.info(f"Attempting to delete all documents from source: {source}")
        response = supabase_rag.table('documents').delete().eq('metadata->>source', source).execute()

        # The response from delete() might not include a count of deleted rows.
        # We can check the status code or for an error.
        if getattr(response, 'error', None):
            logger.error(f"Error deleting source {source}: {response.error}")
            raise HTTPException(status_code=500, detail=f"Failed to delete source: {response.error}")

        # To give a more accurate response, we can't easily get the number of deleted rows
        # without another query. We'll just return a success message.
        logger.info(f"Successfully initiated deletion for source: {source}")
        return {"message": f"All documents from source '{source}' have been deleted."}

    except Exception as e:
        logger.error(f"An error occurred while deleting source {source}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred during deletion: {str(e)}")

@router.get("/collections/{source}/{collection}")
async def get_chunks(source: str, collection: str):
    """
    Retrieves all chunks for a specific source and collection.
    """
    try:
        logger.info(f"Fetching chunks for source: {source}, collection: {collection}")
        response = supabase_rag.table('documents').select('content').eq('metadata->>source', source).eq('collection', collection).execute()

        if not response.data:
            logger.info("No chunks found.")
            return []

        chunks = [item['content'] for item in response.data]
        logger.info(f"Found {len(chunks)} chunks.")
        return chunks

    except Exception as e:
        logger.error(f"An error occurred while fetching chunks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch chunks.")

@router.get("/collections/categories")
async def get_collection_categories():
    """
    Retrieves the list of possible collection categories.
    """
    return CATEGORIES