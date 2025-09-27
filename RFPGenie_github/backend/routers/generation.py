from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.database import get_session
from backend.models import Proposal, Template, ProposalSection, SectionVersion
from backend.agent.main_agent import initial_draft_agent, final_proposal_agent
from backend.agent.regeneration_agent import regeneration_agent
from pydantic import BaseModel
from typing import List, Dict
import logging
import json
import re
import os
from pypdf import PdfReader
from docx import Document
from backend.agent.tools.rag_tool import query_collection_tool
from backend.config import settings
import litellm
from sqlmodel import select, func
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix="/generation",
    tags=["generation"],
)

logger = logging.getLogger(__name__)

class InitialDraftRequest(BaseModel):
    proposal_id: int

class FinalProposalRequest(BaseModel):
    proposal_id: int
    selected_versions: Dict[int, str]

class RegenerateSectionRequest(BaseModel):
    source_content: str

class UpdateVersionContentRequest(BaseModel):
    content: str

@router.put("/section_versions/{version_id}", response_model=SectionVersion)
async def update_section_version_content(
    version_id: int,
    request: UpdateVersionContentRequest,
    session: AsyncSession = Depends(get_session)
):
    logger.info(f"Request to update content for version ID: {version_id}")

    section_version = await session.get(SectionVersion, version_id)
    if not section_version:
        raise HTTPException(status_code=404, detail="SectionVersion not found")

    section_version.content = request.content
    session.add(section_version)
    await session.commit()
    await session.refresh(section_version)

    logger.info(f"Successfully updated content for version ID: {version_id}")
    return section_version


@router.post("/generate_initial_draft")
async def generate_initial_draft(request: InitialDraftRequest, session: AsyncSession = Depends(get_session)):
    logger.info(f"Received request to generate initial draft for proposal ID: {request.proposal_id}")
    
    proposal = await session.get(Proposal, request.proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    template = await session.get(Template, proposal.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        _, extension = os.path.splitext(proposal.scope_document_path)
        scope_document = ""
        if extension.lower() == ".pdf":
            reader = PdfReader(proposal.scope_document_path)
            for page in reader.pages:
                scope_document += page.extract_text()
        elif extension.lower() == ".docx":
            doc = Document(proposal.scope_document_path)
            for para in doc.paragraphs:
                scope_document += para.text + "\n"
        else:
            with open(proposal.scope_document_path, 'r', encoding='utf-8', errors='ignore') as f:
                scope_document = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading scope document: {e}")

    try:
        from google.genai import types
        from google.adk.models.llm_request import LlmRequest

        prompt = f"scope_document: {scope_document}\n\nsections: {template.sections}"
        llm_request = LlmRequest(
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(system_instruction=initial_draft_agent.instruction)
        )
        response_generator = initial_draft_agent.model.generate_content_async(llm_request)
        full_response_text = "".join([part.content.parts[0].text async for part in response_generator if part.content and part.content.parts])

        if not full_response_text:
            raise Exception("Agent returned an empty response.")

        match = re.search(r"```json\s*(.*?)\s*```", full_response_text, re.DOTALL)
        json_string = match.group(1).strip() if match else full_response_text
        
        initial_draft = json.loads(json_string)

        for section_name, content in initial_draft.items():
            proposal_section = ProposalSection(proposal_id=proposal.id, section_name=section_name)
            session.add(proposal_section)
            await session.flush() # Flush to get the ID for the proposal_section
            
            section_version = SectionVersion(
                proposal_section_id=proposal_section.id,
                version_number=1,
                content=content
            )
            session.add(section_version)
        
        await session.commit()
        return {"message": "Initial draft generated successfully."}

    except Exception as e:
        logger.error(f"Error during initial draft generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate initial draft.")

@router.post("/section/{section_id}/regenerate", response_model=SectionVersion)
async def regenerate_section(section_id: int, request: RegenerateSectionRequest, session: AsyncSession = Depends(get_session)):
    logger.info(f"[REGEN_SECTION] Request for section ID: {section_id}")

    proposal_section = await session.get(ProposalSection, section_id)
    if not proposal_section:
        raise HTTPException(status_code=404, detail="ProposalSection not found")

    try:
        prompt = f"""
        Source Content:
        {request.source_content}

        Collection Mappings:
        {json.dumps(proposal_section.collection_mappings, indent=2)}

        Custom Prompt:
        {proposal_section.custom_prompt}
        """

        rag_tool_schema = {
            "type": "function",
            "function": {
                "name": "query_collections",
                "description": "Queries one or more collections in the RAG database...",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "collections": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["query", "collections"]
                }
            }
        }
        
        messages = [
            {"role": "system", "content": regeneration_agent.instruction},
            {"role": "user", "content": prompt},
        ]

        full_response_text = ""
        # Simplified loop for single-section regeneration
        for _ in range(3): # Max 3 turns
            response = await litellm.acompletion(model=settings.FINAL_GENERATION_MODEL, messages=messages, tools=[rag_tool_schema])
            response_message = response.choices[0].message
            messages.append(response_message)

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_result = query_collection_tool.func(**tool_args)
                    messages.append({"role": "tool", "content": tool_result, "tool_call_id": tool_call.id})
                continue
            
            full_response_text = response_message.content
            break
        
        if not full_response_text:
            raise Exception("Regeneration Agent returned an empty response.")

        # Get the highest current version number
        result = await session.exec(
            select(func.max(SectionVersion.version_number))
            .where(SectionVersion.proposal_section_id == section_id)
        )
        max_version = result.one_or_none() or 0

        new_version = SectionVersion(
            proposal_section_id=section_id,
            version_number=max_version + 1,
            content=full_response_text
        )
        session.add(new_version)
        await session.commit()
        await session.refresh(new_version)

        return new_version

    except Exception as e:
        logger.error(f"[REGEN_SECTION] An error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to regenerate section.")


@router.post("/generate_final_proposal")
async def generate_final_proposal(request: FinalProposalRequest, session: AsyncSession = Depends(get_session)):
    logger.info(f"[PROPOSAL_GEN] Final proposal generation request for proposal ID: {request.proposal_id}.")
    
    result = await session.exec(select(Proposal).options(selectinload(Proposal.proposal_sections)).where(Proposal.id == request.proposal_id))
    proposal = result.one_or_none()

    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    try:
        # Use the user-selected versions from the request body
        initial_draft_dict = request.selected_versions
        logger.info(f"[PROPOSAL_GEN] Using the following user-selected versions for generation: {json.dumps(initial_draft_dict, indent=2)}")
        
        mappings = [{
            "section_name": section.section_name,
            "collection_mappings": section.collection_mappings,
            "custom_prompt": section.custom_prompt,
        } for section in proposal.proposal_sections]

        prompt = f"""
        Proposal Name: {proposal.name}
        Initial Draft (from user selected versions):
        {json.dumps(initial_draft_dict, indent=2)}

        Mappings:
        {json.dumps(mappings, indent=2)}
        """

        rag_tool_schema = {
            "type": "function",
            "function": {
                "name": "query_collections",
                "description": "Queries one or more collections in the RAG database...",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "collections": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["query", "collections"]
                }
            }
        }

        messages = [
            {"role": "system", "content": final_proposal_agent.instruction},
            {"role": "user", "content": prompt},
        ]

        full_response_text = ""
        for i in range(7):
            response = await litellm.acompletion(model=settings.FINAL_GENERATION_MODEL, messages=messages, tools=[rag_tool_schema])
            response_message = response.choices[0].message
            messages.append(response_message)

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    tool_args = json.loads(tool_call.function.arguments)
                    tool_result = query_collection_tool.func(**tool_args)
                    messages.append({"role": "tool", "content": tool_result, "tool_call_id": tool_call.id})
                continue
            
            full_response_text = response_message.content
            break
        else:
            raise Exception("Agent exceeded maximum turns.")

        if not full_response_text:
            raise Exception("Agent returned an empty final response.")

        match = re.search(r"```html\s*(.*?)\s*```", full_response_text, re.DOTALL)
        final_html = match.group(1).strip() if match else full_response_text

        body_match = re.search(r"<body.*?>(.*?)</body>", final_html, re.DOTALL)
        if body_match:
            final_html = body_match.group(1).strip()

        final_html = re.sub(r'\s*style="[^"]*"', '', final_html)

        proposal.final_rfp_json = final_html
        session.add(proposal)
        await session.commit()
        
        return {"rfp_content": final_html}
    except Exception as e:
        logger.error(f"[PROPOSAL_GEN] An error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate final proposal.")