from typing import List
from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from backend.database import get_session
from backend.models import Section

router = APIRouter(
    prefix="/sections",
    tags=["sections"],
)

@router.get("/", response_model=List[Section])
async def read_sections(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Section))
    sections = result.all()
    return sections

@router.post("/", response_model=Section)
async def create_section(section: Section, session: AsyncSession = Depends(get_session)):
    session.add(section)
    await session.commit()
    await session.refresh(section)
    return section
