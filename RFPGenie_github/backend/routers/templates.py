from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.database import get_session
from backend.models import Template, Proposal
import logging

router = APIRouter(
    prefix="/templates",
    tags=["templates"],
)

logger = logging.getLogger(__name__)

@router.post("/", response_model=Template)
async def create_template(template: Template, session: AsyncSession = Depends(get_session)):
    logger.info(f"Creating template: {template.name}")
    session.add(template)
    await session.commit()
    await session.refresh(template)
    logger.info(f"Template {template.name} created successfully.")
    return template

@router.get("/", response_model=List[Template])
async def read_templates(session: AsyncSession = Depends(get_session)):
    logger.info(f"Fetching templates.")
    result = await session.exec(select(Template))
    templates = result.all()
    return templates

@router.get("/{template_id}", response_model=Template)
async def read_template(template_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"Fetching template {template_id}.")
    template = await session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.put("/{template_id}", response_model=Template)
async def update_template(template_id: int, template: Template, session: AsyncSession = Depends(get_session)):
    logger.info(f"Updating template {template_id}.")
    db_template = await session.get(Template, template_id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    template_data = template.dict(exclude_unset=True)
    for key, value in template_data.items():
        setattr(db_template, key, value)
    session.add(db_template)
    await session.commit()
    await session.refresh(db_template)
    logger.info(f"Template {template_id} updated successfully.")
    return db_template

@router.delete("/{template_id}")
async def delete_template(template_id: int, session: AsyncSession = Depends(get_session)):
    logger.info(f"Deleting template {template_id}.")
    template = await session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check for dependencies
    result = await session.exec(select(Proposal).where(Proposal.template_id == template_id))
    proposals = result.all()
    draft_proposals = [p for p in proposals if p.final_rfp_json is None]

    if draft_proposals:
        proposal_names = ", ".join([p.name for p in draft_proposals])
        raise HTTPException(
            status_code=409,
            detail=f"Template cannot be deleted as proposal(s) '{proposal_names}' are in a draft state and are using this template.",
        )

    await session.delete(template)
    await session.commit()
    logger.info(f"Template {template_id} deleted successfully.")
    return {"ok": True}