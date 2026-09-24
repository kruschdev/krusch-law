import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Centralized configuration for KruschLaw backend."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    TAGGER_MODEL: str = os.getenv("TAGGER_MODEL", "qwen2.5-coder:7b")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    # Timeouts & Limits
    EMBED_TIMEOUT: float = float(os.getenv("EMBED_TIMEOUT", "30.0"))
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120.0"))
    TAGGER_TIMEOUT: float = float(os.getenv("TAGGER_TIMEOUT", "15.0"))
    DEFAULT_RETRIEVAL_LIMIT: int = int(os.getenv("DEFAULT_RETRIEVAL_LIMIT", "5"))

    # Batching & Performance
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "16"))

    # Security & Air-Gap Boundaries
    API_KEY: Optional[str] = os.getenv("API_KEY", None)
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8505,http://127.0.0.1:8505,http://localhost:3000,http://127.0.0.1:3000"
    )
    ALLOWED_INGEST_DIRS: str = os.getenv(
        "ALLOWED_INGEST_DIRS",
        "/app/data,/app/data/ingest"
    )
    extra_allowed_dirs: list[str] = []

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_ingest_dirs_list(self) -> list[str]:
        dirs = [os.path.abspath(d.strip()) for d in self.ALLOWED_INGEST_DIRS.split(",") if d.strip()]
        # Include repo local data directory if present
        local_data = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
        if local_data not in dirs:
            dirs.append(local_data)
            dirs.append(os.path.join(local_data, "ingest"))
        for extra in self.extra_allowed_dirs:
            dirs.append(os.path.abspath(extra.strip()))
        return dirs

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


def is_loopback_or_private_host(url_or_host: str) -> bool:
    """Inspect whether a configured host/URL resides strictly on loopback or private networks."""
    import ipaddress
    import urllib.parse
    if not url_or_host:
        return False
    try:
        if "://" in url_or_host:
            hostname = urllib.parse.urlparse(url_or_host).hostname or ""
        else:
            hostname = url_or_host

        hostname = hostname.strip().lower()
        if hostname in ("localhost", "127.0.0.1", "::1", "host.docker.internal", "db", "backend", "frontend"):
            return True
        ip = ipaddress.ip_address(hostname)
        return ip.is_loopback or ip.is_private
    except Exception:
        return False


settings = Settings()


