from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.database import get_session
from backend.models import Proposal, ProposalSection, Approval
import shutil
import logging
import uuid
import os

router = APIRouter(
    prefix="/proposals",
    tags=["proposals"],
)

logger = logging.getLogger(__name__)

@router.post("/", response_model=Proposal)
async def create_proposal(
    name: str = Form(...),
    description: str = Form(...),
    client_name: str = Form(...),
    template_id: int = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    logger.info(f"Received request to create proposal: {name}")
    logger.info(f"Client: {client_name}, Template ID: {template_id}")

    _, extension = os.path.splitext(file.filename)
    secure_filename = f"{uuid.uuid4()}{extension}"
    file_path = f"backend/uploads/{secure_filename}"
    logger.info(f"Generated secure filename: {secure_filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Successfully saved uploaded file to: {file_path}")
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Could not save file.")

    proposal = Proposal(
        name=name,
        description=description,
        client_name=client_name,
        template_id=template_id,
        scope_document_path=file_path
    )
    logger.info("Proposal object created. Adding to session.")

    session.add(proposal)
    await session.commit()
    logger.info("Proposal committed to database.")
    await session.refresh(proposal)
    logger.info(f"Proposal {name} created successfully with ID: {proposal.id}")
    return proposal

@router.get("/", response_model=List[Proposal])
async def read_proposals(session: AsyncSession = Depends(get_session)):
    logger.info(f"Fetching proposals.")
    result = await session.exec(select(Proposal))
    proposals = result.all()
    return proposals

from sqlalchemy.orm import selectinload

@router.get("/{proposal_id}", response_model=Proposal)
async def read_proposal(proposal_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"Fetching proposal {proposal_id}.")
    result = await session.exec(
        select(Proposal)
        .options(selectinload(Proposal.proposal_sections).selectinload(ProposalSection.versions))
        .where(Proposal.id == proposal_id)
    )
    proposal = result.first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal

@router.put("/{proposal_id}", response_model=Proposal)
async def update_proposal(proposal_id: int, proposal: Proposal, session: AsyncSession = Depends(get_session)):
    logger.info(f"Updating proposal {proposal_id}.")
    db_proposal = await session.get(Proposal, proposal_id)
    if not db_proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal_data = proposal.dict(exclude_unset=True)
    for key, value in proposal_data.items():
        setattr(db_proposal, key, value)
    session.add(db_proposal)
    await session.commit()
    await session.refresh(db_proposal)
    logger.info(f"Proposal {proposal_id} updated successfully.")
    return db_proposal

@router.delete("/{proposal_id}")
async def delete_proposal(proposal_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"Deleting proposal {proposal_id}.")
    proposal = await session.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await session.delete(proposal)
    await session.commit()
    logger.info(f"Proposal {proposal_id} deleted successfully.")
    return {"ok": True}

from backend.models import Proposal, ProposalSection, ProposalSectionResponse
from sqlalchemy.orm import selectinload

@router.get("/{proposal_id}/sections", response_model=List[ProposalSectionResponse])
async def read_proposal_sections_with_versions(proposal_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"Fetching proposal sections with versions for proposal {proposal_id}.")
    result = await session.exec(
        select(ProposalSection)
        .options(selectinload(ProposalSection.versions))
        .where(ProposalSection.proposal_id == proposal_id)
    )
    sections = result.all()
    return sections

# --- Approval Endpoints ---
class ApprovalCreateRequest(BaseModel):
    proposal_id: int
    approved_by: str
    status: str = "pending"
    comments: str = None

@router.post("/{proposal_id}/approvals", response_model=Approval)
async def create_approval(proposal_id: int, request: ApprovalCreateRequest, session: AsyncSession = Depends(get_session)):
    proposal = await session.get(Proposal, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    approval = Approval(
        proposal_id=proposal_id,
        approved_by=request.approved_by,
        status=request.status,
        comments=request.comments
    )
    session.add(approval)
    await session.commit()
    await session.refresh(approval)
    return approval

@router.get("/{proposal_id}/approvals", response_model=List[Approval])
async def get_approvals(proposal_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Approval).where(Approval.proposal_id == proposal_id))
    return result.all()

@router.put("/approvals/{approval_id}", response_model=Approval)
async def update_approval(approval_id: int, request: ApprovalCreateRequest, session: AsyncSession = Depends(get_session)):
    approval = await session.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval.status = request.status
    approval.comments = request.comments
    approval.approved_by = request.approved_by
    session.add(approval)
    await session.commit()
    await session.refresh(approval)
    return approval

@router.delete("/approvals/{approval_id}")
async def delete_approval(approval_id: int, session: AsyncSession = Depends(get_session)):
    approval = await session.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    await session.delete(approval)
    await session.commit()
    return {"ok": True}
