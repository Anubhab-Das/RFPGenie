from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SUPABASE_RAG_URL: str
    SUPABASE_RAG_KEY: str
    OPENAI_API_KEY: str
    GOOGLE_API_KEY: str
    VITE_TINYMCE_API_KEY: str
    FINAL_GENERATION_MODEL: str = "gpt-4-turbo"
    RAG_MATCH_THRESHOLD: float = 0.3

    class Config:
        pass

settings = Settings(_env_file=".env")
