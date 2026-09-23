"""
tests/test_nexus_integration.py
===============================
Cross-repository integration test suite verifying that KruschLaw integrates cleanly
with KruschNexus as its sovereign document ingestion pipeline and citation spine.

Tests:
1. Ingesting markdown documents with section hierarchies.
2. Ingesting real DOCX documents from KruschNexus fixtures.
3. Ingesting real PDF documents from KruschNexus fixtures with page tracking.
4. Multipart file upload via POST /api/ingest/upload.
5. Hybrid retrieval and citation verification of ingested chunks.
6. Security guardrails (directory boundaries, invalid extensions).
"""

import os
import sys
import json
import io
import tempfile
import unittest
from unittest.mock import MagicMock

# Force in-memory SQLite and mock Ollama endpoints before importing application modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OLLAMA_EMBED_HOST"] = "http://mock-ollama:11434"
os.environ["OLLAMA_BASE_URL"] = "http://mock-ollama:11434"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

NEXUS_SRC = "/home/krusch/homelab/projects/krusch-nexus/src"
if NEXUS_SRC not in sys.path and os.path.isdir(NEXUS_SRC):
    sys.path.insert(0, NEXUS_SRC)

# Mock pgvector before SQLAlchemy imports so SQLite can treat Vector as JSON/TEXT
from sqlalchemy.types import UserDefinedType

class MockVector(UserDefinedType):
    def __init__(self, dim):
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

sys.modules['pgvector'] = MagicMock()
sys.modules['pgvector.sqlalchemy'] = MagicMock()
sys.modules['pgvector.sqlalchemy'].Vector = MockVector

import src.backend.config
import src.backend.db
import src.backend.rag
import src.backend.ingest
import src.backend.main

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.backend.db import Base, Case, LawVector
from src.backend.ingest import ingest_matter_document, ingest_uploaded_matter_file
from src.backend.main import app, get_db

FIXTURES_DIR = "/home/krusch/homelab/projects/krusch-nexus/tests/fixtures"


class TestNexusIntegration(unittest.TestCase):
    """Integration test suite for KruschLaw + KruschNexus ingestion pipeline."""

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        src.backend.db.SessionLocal = cls.TestingSessionLocal
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=cls.engine)

    def setUp(self):
        # Deterministic mock embeddings
        def mock_embed(text: str) -> list[float]:
            import hashlib
            h = hashlib.md5(text.encode("utf-8")).digest()
            val = (h[0] / 255.0) * 0.1
            vec = [0.01] * 1024
            vec[0] = val
            return vec

        def mock_embed_batch(texts: list[str]) -> list[list[float]]:
            return [mock_embed(t) for t in texts]

        src.backend.rag.get_embedding = mock_embed
        src.backend.rag.get_embeddings_batch = mock_embed_batch
        src.backend.ingest.get_embedding = mock_embed
        src.backend.ingest.get_embeddings_batch = mock_embed_batch
        src.backend.main.get_embedding = mock_embed

    def test_01_ingest_markdown_contract(self):
        """Verify markdown contract ingestion extracts section-aware chunks with headers."""
        doc_content = (
            "# Master Services Agreement\n\n"
            "## Section 3.1 Payment and Invoicing\n"
            "Client shall pay all undisputed invoices within thirty (30) days of receipt.\n\n"
            "## Section 3.2 Late Payment Penalties\n"
            "Any overdue payments shall accrue interest at the statutory rate of 1.5% per month.\n"
        )
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8") as f:
            f.write(doc_content)
            temp_path = f.name

        temp_dir = os.path.dirname(temp_path)
        src.backend.config.settings.extra_allowed_dirs.append(temp_dir)

        try:
            db = self.TestingSessionLocal()
            report = ingest_matter_document(
                file_path=temp_path,
                matter_id=201,
                doc_type="work_product",
                db=db
            )
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["pages_in"], 1)
            self.assertGreaterEqual(report["chunks_out"], 2)
            self.assertGreaterEqual(report["records_inserted"], 2)

            # Check database records
            records = db.query(LawVector).filter(LawVector.county == "Matter #201").all()
            self.assertGreaterEqual(len(records), 2)
            headers = [r.source_header for r in records]
            self.assertTrue(any("Section 3.1" in h for h in headers))
            self.assertTrue(any("Section 3.2" in h for h in headers))
            db.close()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_02_ingest_docx_policy_fixture(self):
        """Verify ingestion of a real DOCX fixture from KruschNexus."""
        docx_path = os.path.join(FIXTURES_DIR, "policy_manual.docx")
        if not os.path.exists(docx_path):
            self.skipTest(f"Fixture {docx_path} not found")

        src.backend.config.settings.extra_allowed_dirs.append(FIXTURES_DIR)
        db = self.TestingSessionLocal()
        try:
            report = ingest_matter_document(
                file_path=docx_path,
                matter_id=202,
                doc_type="authority",
                db=db
            )
            self.assertEqual(report["status"], "completed")
            self.assertGreaterEqual(report["pages_in"], 1)
            self.assertGreaterEqual(report["chunks_out"], 1)
            self.assertGreaterEqual(report["records_inserted"], 1)

            # Query database for policy manual records
            records = db.query(LawVector).filter(LawVector.county == "Matter #202").all()
            self.assertGreaterEqual(len(records), 1)
            self.assertEqual(records[0].title, "policy_manual.docx")
        finally:
            db.close()

    def test_03_ingest_pdf_contract_fixture(self):
        """Verify ingestion of a real PDF fixture with page tracking from KruschNexus."""
        pdf_path = os.path.join(FIXTURES_DIR, "sample_contract.pdf")
        if not os.path.exists(pdf_path):
            self.skipTest(f"Fixture {pdf_path} not found")

        src.backend.config.settings.extra_allowed_dirs.append(FIXTURES_DIR)
        db = self.TestingSessionLocal()
        try:
            report = ingest_matter_document(
                file_path=pdf_path,
                matter_id=203,
                doc_type="authority",
                db=db
            )
            self.assertEqual(report["status"], "completed")
            self.assertGreaterEqual(report["pages_in"], 1)
            self.assertGreaterEqual(report["chunks_out"], 1)
            self.assertGreaterEqual(report["records_inserted"], 1)

            records = db.query(LawVector).filter(LawVector.county == "Matter #203").all()
            self.assertGreaterEqual(len(records), 1)
            self.assertEqual(records[0].title, "sample_contract.pdf")
            self.assertIn("p.", records[0].section)
        finally:
            db.close()

    def test_04_multipart_upload_endpoint(self):
        """Verify uploading a file via POST /api/ingest/upload."""
        file_content = (
            "# Notice of Non-Renewal\n\n"
            "## Section 1 Grounds for Non-Renewal\n"
            "Tenancy shall terminate on December 31, 2026 pursuant to California Civil Code 1946.2.\n"
        ).encode("utf-8")

        resp = self.client.post(
            "/api/ingest/upload",
            files={"file": ("eviction_notice.md", io.BytesIO(file_content), "text/markdown")},
            data={"matter_id": 204, "doc_type": "matter_facts"}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["filename"], "eviction_notice.md")
        self.assertEqual(data["matter_id"], 204)
        self.assertGreaterEqual(data["chunks_out"], 1)
        self.assertGreaterEqual(data["records_inserted"], 1)

        # Verify search retrieves the uploaded content
        search_resp = self.client.get("/api/laws?q=Non-Renewal&city=Matter")
        self.assertEqual(search_resp.status_code, 200)
        hits = search_resp.json()
        self.assertGreaterEqual(len(hits), 1)
        self.assertIn("Grounds for Non-Renewal", hits[0]["content"])

    def test_05_unsupported_file_extension(self):
        """Verify security check rejects unsupported file types."""
        fake_content = b"MZ\x90\x00executable"
        resp = self.client.post(
            "/api/ingest/upload",
            files={"file": ("malware.exe", io.BytesIO(fake_content), "application/octet-stream")},
            data={"matter_id": 999}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported document format", resp.json()["detail"])

    def test_06_nonexistent_file_path(self):
        """Verify path ingestion endpoint returns 404 for missing file."""
        src.backend.config.settings.extra_allowed_dirs.append("/tmp")
        resp = self.client.post("/api/ingest/document", json={
            "file_path": "/tmp/nonexistent_file_xyz_12345.pdf",
            "matter_id": 999
        })
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
