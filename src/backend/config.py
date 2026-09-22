import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Centralized configuration for KruschLaw backend."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://kruschlaw:kruschlaw_secret@localhost:5435/kruschlaw_db"
    )
    
    # Ollama Endpoints
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_EMBED_HOST: str = os.getenv("OLLAMA_EMBED_HOST", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    
    # Models
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-large")
    OLLAMA_LLM_MODEL: str = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5-coder:14b")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))
    
    # Timeouts & Limits
    EMBED_TIMEOUT: float = float(os.getenv("EMBED_TIMEOUT", "30.0"))
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))
    DEFAULT_RETRIEVAL_LIMIT: int = int(os.getenv("DEFAULT_RETRIEVAL_LIMIT", "5"))

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
