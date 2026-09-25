import os
import sys
import json
import unittest
from unittest.mock import MagicMock

# Force in-memory SQLite and mock Ollama endpoints before importing application modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OLLAMA_EMBED_HOST"] = "http://mock-ollama:11434"
os.environ["OLLAMA_BASE_URL"] = "http://mock-ollama:11434"
os.environ["ENVIRONMENT"] = "test"

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock pgvector before SQLAlchemy imports so SQLite can treat Vector as JSON/TEXT
from sqlalchemy.types import UserDefinedType

class MockVector(UserDefinedType):
    def __init__(self, dim=1024):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"
    def bind_processor(self, dialect):
        def process(value):
            if isinstance(value, list):
                return json.dumps(value)
            return value
        return process
    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value
        return process

if 'pgvector' not in sys.modules:
    sys.modules['pgvector'] = MagicMock()
    sys.modules['pgvector.sqlalchemy'] = MagicMock()
    sys.modules['pgvector.sqlalchemy'].Vector = MockVector

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import src.backend.config
import src.backend.db
import src.backend.rag
import src.backend.ingest
import src.backend.main
import src.mcp.server

from src.backend.db import (
    Base, Case, LawVector, IngestJob, GroundingReport, AuditLog,
    StatuteCodeTraceability, MatterEvidence, ClaimFeedback, StatuteRelation
)
from src.backend.main import app, get_db


class KruschLawTestCase(unittest.TestCase):
    """Shared base test case setting up SQLite memory DB, mocks, and FastAPI test client."""
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.Session = sessionmaker(bind=cls.engine)

        src.backend.db.engine = cls.engine
        src.backend.db.SessionLocal = cls.Session
        src.backend.rag.SessionLocal = cls.Session
        src.backend.ingest.SessionLocal = cls.Session
        src.mcp.server.SessionLocal = cls.Session

        Base.metadata.create_all(cls.engine)

    def setUp(self):
        self.db = self.Session()
        self.db.query(AuditLog).delete()
        self.db.query(GroundingReport).delete()
        self.db.query(Case).delete()
        self.db.query(LawVector).delete()
        self.db.query(IngestJob).delete()
        self.db.query(MatterEvidence).delete()
        self.db.query(ClaimFeedback).delete()
        self.db.query(StatuteCodeTraceability).delete()
        self.db.query(StatuteRelation).delete()
        self.db.commit()

        # Global mock for embedding generation (1024-dim vector)
        self.mock_vector = [0.05] * 1024
        self.mock_embed = MagicMock(return_value=self.mock_vector)
        self.mock_embed_batch = MagicMock(side_effect=lambda texts: [self.mock_vector] * len(texts))

        src.backend.rag.get_embedding = self.mock_embed
        src.backend.rag.get_embeddings_batch = self.mock_embed_batch
        src.backend.ingest.get_embedding = self.mock_embed
        src.backend.ingest.get_embeddings_batch = self.mock_embed_batch
        src.backend.main.get_embedding = self.mock_embed

        src.mcp.server.get_embedding = self.mock_embed
        src.mcp.server.get_embeddings_batch = self.mock_embed_batch
        src.mcp.server.SessionLocal = self.Session

        def override_get_db():
            db_session = self.Session()
            try:
                yield db_session
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        src.backend.config.settings.extra_allowed_dirs = []
        self.db.close()
