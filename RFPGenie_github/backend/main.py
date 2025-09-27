from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import templates, proposals, generation, sections, collections
from .database import engine, get_session
from . import models
from sqlmodel import select, delete
import logging

logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(models.SQLModel.metadata.create_all)

    async for session in get_session():
        #await session.exec(delete(models.Section))
        #await session.commit()

        result = await session.exec(select(models.Section))
        if not result.first():
            # Add the 9 specified sections
            sections_to_add = [
                models.Section(section_name="Executive Summary", description="A brief overview of the entire proposal.", category="General"),
                models.Section(section_name="Project objectives and background Information", description="The goals and context of the project.", category="General"),
                models.Section(section_name="Functional and Technical Solution", description="The proposed solution's functional and technical aspects.", category="General"),
                models.Section(section_name="Project Deliverables, Timelines and Outcome", description="What will be delivered, when, and what the expected outcomes are.", category="General"),
                models.Section(section_name="Commercials and value proposition", description="The pricing and the value offered.", category="General"),
                models.Section(section_name="Company Profile", description="Information about the company.", category="General"),
                models.Section(section_name="Client Reference and Case Studies", description="References and examples of past work.", category="General"),
                models.Section(section_name="Why Us", description="Reasons to choose us.", category="General"),
                models.Section(section_name="Appendices", description="Additional supporting documents.", category="General"),
            ]
            session.add_all(sections_to_add)
            await session.commit()

app.include_router(templates.router)
app.include_router(proposals.router)
app.include_router(generation.router)
app.include_router(sections.router)
app.include_router(collections.router)

@app.get("/")
def read_root():
    return {"Hello": "World"}
