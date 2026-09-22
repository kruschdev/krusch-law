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
    OLLAMA_LLM_MODEL: str = os.getenv("OLLAMA_LLM_MODEL", "qwen2.5:14b")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))
    
    # Timeouts & Limits
    EMBED_TIMEOUT: float = float(os.getenv("EMBED_TIMEOUT", "30.0"))
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))
    DEFAULT_RETRIEVAL_LIMIT: int = int(os.getenv("DEFAULT_RETRIEVAL_LIMIT", "5"))

    # Security & Air-Gap Boundaries
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8505,http://127.0.0.1:8505,http://localhost:3000,http://127.0.0.1:3000"
    )
    ALLOWED_INGEST_DIRS: str = os.getenv(
        "ALLOWED_INGEST_DIRS",
        "/app/data,/app/data/ingest,/tmp"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_ingest_dirs_list(self) -> list[str]:
        return [os.path.abspath(d.strip()) for d in self.ALLOWED_INGEST_DIRS.split(",") if d.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

