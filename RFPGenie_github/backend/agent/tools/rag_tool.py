import logging
import litellm
from typing import List
from backend.database import supabase_rag
from google.adk.tools import FunctionTool
from backend.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def query_collections(query: str, collections: List[str]) -> str:
    """Queries one or more collections in the RAG database with a given query to find relevant context."""
    logger.info(f"[RAG_TOOL] Received query: '{query}' for collections: {collections}")

    if not collections:
        logger.warning("[RAG_TOOL] No collections specified. Aborting query.")
        return "No collections were specified for the query."

    try:
        # 1. Generate embedding for the query
        logger.debug("[RAG_TOOL] Generating embedding for the query...")
        embedding_response = litellm.embedding(
            model="text-embedding-3-small",
            input=[query]
        )
        query_embedding = embedding_response.data[0]['embedding']
        logger.debug("[RAG_TOOL] Embedding generated successfully.")

        # 2. Call the match_documents RPC function in Supabase
        rpc_params = {
            "query_embedding": query_embedding,
            "match_threshold": settings.RAG_MATCH_THRESHOLD,
            "match_count": 5,
            "collection_filter": collections
        }
        logger.info(f"[RAG_TOOL] Executing RPC 'match_documents' with params: {{match_threshold: {rpc_params['match_threshold']}, match_count: {rpc_params['match_count']}, collection_filter: {rpc_params['collection_filter']}}}")
        
        response = supabase_rag.rpc("match_documents", rpc_params).execute()
        data = response.data
        logger.debug(f"[RAG_TOOL] Raw response from Supabase: {data}")

        if not data:
            logger.info("[RAG_TOOL] No matching documents found in the database.")
            return "No relevant information was found in the knowledge base for the specified query and collections."

        logger.info(f"[RAG_TOOL] Found {len(data)} matching documents. Details:")
        for i, item in enumerate(data):
            similarity = item.get('similarity', 'N/A')
            source = item.get('metadata', {}).get('source', 'N/A')
            logger.info(f"  [CHUNK {i+1}] Similarity: {similarity:.4f}, Source: {source}")
            logger.info(f"  [CHUNK {i+1}] Content: {item['content'][:150]}...")

        # 3. Process and format the results
        contexts = [item['content'] for item in data]
        context_str = "\n\n---\n\n".join(contexts)
        
        logger.info(f"[RAG_TOOL] Found {len(contexts)} matching documents. Returning formatted context string.")
        logger.debug(f"[RAG_TOOL] Returning context: {context_str[:500]}...") # Log first 500 chars
        return context_str

    except Exception as e:
        logger.error(f"[RAG_TOOL] An unexpected error occurred: {e}", exc_info=True)
        return "An error occurred while trying to query the knowledge base."


# Wrap the function in a FunctionTool for the agent to use
query_collection_tool = FunctionTool(query_collections)