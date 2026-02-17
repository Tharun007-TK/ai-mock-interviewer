"""
Application configuration using pydantic-settings.
All secrets and environment-specific values are loaded from .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """MVP configuration — extend as features grow."""

    # --- App ---
    APP_NAME: str = "AI Mock Interviewer"
    DEBUG: bool = True

    # --- Database (PostgreSQL / Supabase) ---
    # Default is useful for dev but overrides .env if precedence is unclear.
    # We'll rely on env_file to overwrite this.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mock_interview"

    # --- LLM (OpenRouter) ---
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL_QUESTION: str = "meta-llama/llama-3-8b-instruct"
    OPENROUTER_MODEL_EVALUATION: str = "openai/gpt-4o-mini"

    # --- Speech-to-Text (Deepgram) ---
    DEEPGRAM_API_KEY: str = ""

    # --- Embeddings ---
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-large-en"

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "./chroma_data"


    # --- Storage (Resumes) ---
    S3_BUCKET_NAME: str = ""
    S3_REGION: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Explicit configuration for .env loading
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
