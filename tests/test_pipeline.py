import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

# Force in-memory SQLite and mock Ollama endpoints before importing application modules
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OLLAMA_EMBED_HOST"] = "http://mock-ollama:11434"
os.environ["OLLAMA_BASE_URL"] = "http://mock-ollama:11434"

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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

# Import KruschLaw modules
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
from src.backend.ingest import ingest_mock_data
from src.backend.main import app, get_db


class TestKruschLawPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure in-memory SQLite engine with StaticPool for test session persistence
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.Session = sessionmaker(bind=cls.engine)

        # Wire test engine into modules
        src.backend.db.engine = cls.engine
        src.backend.db.SessionLocal = cls.Session
        src.backend.rag.SessionLocal = cls.Session
        src.backend.ingest.SessionLocal = cls.Session

        Base.metadata.create_all(cls.engine)

    def setUp(self):
        self.db = self.Session()
        self.db.query(Case).delete()
        self.db.query(LawVector).delete()
        self.db.commit()

        # Global mock for embedding generation (1024-dim vector)
        self.mock_vector = [0.05] * 1024
        self.mock_embed = MagicMock(return_value=self.mock_vector)
        src.backend.rag.get_embedding = self.mock_embed
        src.backend.ingest.get_embedding = self.mock_embed
        src.backend.main.get_embedding = self.mock_embed

        def override_get_db():
            db_session = self.Session()
            try:
                yield db_session
            finally:
                db_session.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "kruschlaw-backend")
        self.assertEqual(data["version"], "0.2.0-dev")
        self.assertIn("security", data)
        self.assertIn("auth_enabled", data["security"])
        self.assertIn("ollama_host_is_local_or_private", data["security"])
        self.assertIn("embed_host_is_local_or_private", data["security"])

    def test_mock_ordinance_ingestion(self):
        inserted = ingest_mock_data(self.db)
        self.assertGreater(inserted, 0)

        # Verify records exist in database
        laws = self.db.query(LawVector).all()
        self.assertEqual(len(laws), inserted)

        oakland_law = self.db.query(LawVector).filter_by(city_or_county="Oakland").first()
        self.assertIsNotNone(oakland_law)
        self.assertEqual(oakland_law.state, "CA")
        self.assertIn("Rent Adjustment", oakland_law.title)

    def test_case_creation_and_retrieval(self):
        payload = {
            "title": "Oakland Notice of Rent Increase",
            "description": "Tenant issue, 15% rent increase",
            "facts": "Tenant moved into unit in 2024. Landlord issued a 15% rent increase without providing Rent Adjustment notice."
        }

        # Create matter
        resp = self.client.post("/api/cases", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], payload["title"])
        self.assertIsNotNone(data["id"])

        # Fetch matters
        get_resp = self.client.get("/api/cases")
        self.assertEqual(get_resp.status_code, 200)
        cases = get_resp.json()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["title"], payload["title"])

    @patch('src.backend.main.generate_legal_analysis')
    def test_consult_pipeline(self, mock_analysis):
        mock_analysis.return_value = (
            "### Executive Summary\nThe rent increase appears defective under Oakland Rent Adjustment Program.\n\n"
            "### Applicable Legal Authority\nOakland Municipal Code Section 8.22.030\n\n"
            "### Factual Matrix Analysis\nThe landlord failed to provide the mandatory threshold notice.\n\n"
            "### Next Steps\nFile petition with Rent Adjustment Program."
        )

        # Seed ordinances
        ingest_mock_data(self.db)

        # Create matter
        matter = Case(
            title="Defective Notice Matter",
            facts="Landlord raised rent without providing the required initial tenant notice in Oakland.",
            embedding=self.mock_vector
        )
        self.db.add(matter)
        self.db.commit()

        # Consult
        resp = self.client.get(f"/api/consult?case_id={matter.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("analysis", data)
        self.assertIn("Executive Summary", data["analysis"])
        self.assertEqual(data["case"]["title"], matter.title)
        self.assertIn("disclaimer", data)
        self.assertIn("DISCLAIMER", data["disclaimer"])

    def test_consult_case_not_found(self):
        resp = self.client.get("/api/consult?case_id=99999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_mock_deduplication(self):
        # Ingest once
        first_count = ingest_mock_data(self.db)
        self.assertGreater(first_count, 0)

        # Ingest second time - should insert 0 new records because they already exist
        second_count = ingest_mock_data(self.db)
        self.assertEqual(second_count, 0)

    def test_parquet_ingestion_with_schema_mapping(self):
        import tempfile
        import pandas as pd
        from src.backend.ingest import ingest_locus_parquet

        # Create a temporary parquet file with custom columns
        test_df = pd.DataFrame([
            {
                "state_code": "CA",
                "jurisdiction_name": "Berkeley",
                "ordinance_text": "No tenant may be evicted without an owner-occupancy relocation payment.",
                "sec": "Section 13.76.130",
                "chapter": "Rent Stabilization"
            },
            {
                "state_code": "CA",
                "jurisdiction_name": "San Jose",
                "ordinance_text": "Tenant Protection Ordinance requires just cause and formal written notice.",
                "sec": "Section 17.23.1250",
                "chapter": "Tenant Protections"
            }
        ])

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
            test_df.to_parquet(temp_path)

        try:
            inserted = ingest_locus_parquet(temp_path, db=self.db, limit=10)
            self.assertEqual(inserted, 2)

            # Check inserted record
            berkeley = self.db.query(LawVector).filter_by(city_or_county="Berkeley").first()
            self.assertIsNotNone(berkeley)
            self.assertEqual(berkeley.state, "CA")
            self.assertEqual(berkeley.section, "Section 13.76.130")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_citation_grounding_verified(self):
        from src.backend.rag import verify_citation_grounding
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide notice..."
            }
        ]
        grounded_analysis = (
            "Under Section 8.22.030 of the Oakland Municipal Code, the landlord must provide statutory notice."
        )
        is_grounded, ungrounded, notice = verify_citation_grounding(grounded_analysis, retrieved_laws)
        self.assertTrue(is_grounded)
        self.assertEqual(len(ungrounded), 0)
        self.assertIn("Citation Grounding Verified", notice)

    def test_citation_grounding_hallucination_detected(self):
        from src.backend.rag import verify_citation_grounding
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide notice..."
            }
        ]
        # Analysis citing an ungrounded statutory section (Section 1942)
        hallucinated_analysis = (
            "Pursuant to Section 8.22.030, notice is required. Additionally, under Section 1942, "
            "the tenant may exercise repair-and-deduct remedies."
        )
        is_grounded, ungrounded, notice = verify_citation_grounding(hallucinated_analysis, retrieved_laws)
        self.assertFalse(is_grounded)
        self.assertIn("1942", ungrounded)
        self.assertIn("Citation Grounding Advisory", notice)
        self.assertIn("Section 1942", notice)

    def test_parquet_path_traversal_rejection(self):
        from src.backend.ingest import ingest_locus_parquet
        # Attempt to access an unauthorized path outside allowed directories
        disallowed_path = "/home/krusch/unauthorized_directory/sample.parquet"
        with self.assertRaises(ValueError) as ctx:
            ingest_locus_parquet(disallowed_path, db=self.db)
        self.assertIn("Security Exception", str(ctx.exception))

        # Test API endpoint response when path is disallowed
        resp = self.client.post("/api/ingest/parquet", json={"file_path": disallowed_path, "limit": 5})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Security Exception", resp.json()["detail"])

    def test_vector_similarity_ranking_sqlite(self):
        from src.backend.rag import retrieve_laws
        # Query vector: [1.0, 0.0, 0.0, ...]
        q_vec = [0.0] * 1024
        q_vec[0] = 1.0

        # Close vector: [0.9, 0.1, 0.0, ...]
        close_vec = [0.0] * 1024
        close_vec[0] = 0.9
        close_vec[1] = 0.1

        # Far vector: [0.0, 1.0, 0.0, ...]
        far_vec = [0.0] * 1024
        far_vec[1] = 1.0

        law1 = LawVector(
            jurisdiction="Code A", state="CA", city_or_county="Oakland",
            title="Close Statute", section="Sec 1", content="Text 1",
            embedding=close_vec
        )
        law2 = LawVector(
            jurisdiction="Code B", state="CA", city_or_county="Oakland",
            title="Far Statute", section="Sec 2", content="Text 2",
            embedding=far_vec
        )
        self.db.add_all([law1, law2])
        self.db.commit()

        results = retrieve_laws(query_vector=q_vec, limit=2, db_session=self.db)
        self.assertEqual(len(results), 2)
        # Verify ranking order: close statute must rank higher than far statute
        self.assertEqual(results[0]["title"], "Close Statute")
        self.assertEqual(results[1]["title"], "Far Statute")
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])

    def test_api_key_authentication_enforcement(self):
        # Configure API key
        src.backend.config.settings.API_KEY = "test_confidential_key"
        try:
            # 1. Unauthenticated request must fail with 401
            unauth_resp = self.client.get("/api/cases")
            self.assertEqual(unauth_resp.status_code, 401)
            self.assertIn("Unauthorized", unauth_resp.json()["detail"])

            # 2. Invalid API key must fail with 401
            invalid_resp = self.client.get("/api/cases", headers={"X-API-Key": "wrong_key"})
            self.assertEqual(invalid_resp.status_code, 401)

            # 3. Valid API key succeeds
            valid_resp = self.client.get("/api/cases", headers={"X-API-Key": "test_confidential_key"})
            self.assertEqual(valid_resp.status_code, 200)
        finally:
            src.backend.config.settings.API_KEY = None


if __name__ == "__main__":
    unittest.main()

