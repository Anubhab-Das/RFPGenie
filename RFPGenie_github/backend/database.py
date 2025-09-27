from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client
from .config import settings

# Supabase client for RAG database
supabase_rag: Client = create_client(settings.SUPABASE_RAG_URL, settings.SUPABASE_RAG_KEY)

# SQLModel engine
engine = create_async_engine(settings.DATABASE_URL, echo=True, future=True)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
