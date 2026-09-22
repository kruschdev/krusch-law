import os
import sys
import json
import tempfile
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

from src.backend.db import Base, Case, LawVector, IngestJob
from src.backend.ingest import ingest_mock_data, ingest_locus_parquet, parse_header_section_and_title, chunk_statute_content
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
        self.db.query(IngestJob).delete()
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

        oakland_law = self.db.query(LawVector).filter_by(city="Oakland").first()
        self.assertIsNotNone(oakland_law)
        self.assertEqual(oakland_law.state, "CA")
        self.assertIn("Rent Adjustment", oakland_law.title)
        self.assertEqual(oakland_law.county, "Alameda County")
        self.assertIsNotNone(oakland_law.source_hash)

    def test_case_creation_and_retrieval(self):
        payload = {
            "title": "Oakland Notice of Rent Increase",
            "matter_number": "MATTER-2026-001",
            "client_name": "Jane Doe",
            "description": "Tenant issue, 15% rent increase",
            "facts": "Tenant moved into unit in 2024. Landlord issued a 15% rent increase without providing Rent Adjustment notice."
        }

        # Create matter
        resp = self.client.post("/api/cases", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], payload["title"])
        self.assertEqual(data["matter_number"], "MATTER-2026-001")
        self.assertEqual(data["client_name"], "Jane Doe")
        self.assertIsNotNone(data["id"])

        # Fetch matters
        get_resp = self.client.get("/api/cases")
        self.assertEqual(get_resp.status_code, 200)
        cases = get_resp.json()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["title"], payload["title"])

    def test_case_patch_and_delete(self):
        payload = {
            "title": "Initial Title",
            "facts": "Initial facts statement regarding tenant eviction notice."
        }
        create_resp = self.client.post("/api/cases", json=payload)
        case_id = create_resp.json()["id"]

        # Patch facts - should trigger re-embedding
        patch_payload = {
            "title": "Updated Title",
            "facts": "Updated facts statement requiring re-embedding calculation."
        }
        patch_resp = self.client.patch(f"/api/cases/{case_id}", json=patch_payload)
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["title"], "Updated Title")

        # Verify updated values in db
        case_obj = self.db.query(Case).filter_by(id=case_id).first()
        self.assertEqual(case_obj.title, "Updated Title")
        self.assertEqual(case_obj.facts, patch_payload["facts"])

        # Soft Delete
        del_resp = self.client.delete(f"/api/cases/{case_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json()["status"], "deleted")

        # Verify excluded from active list
        get_resp = self.client.get("/api/cases")
        self.assertEqual(len(get_resp.json()), 0)

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

    def test_parse_header_and_chunking(self):
        # Test section parsing
        sec, title = parse_header_section_and_title("8.22.030 - Notice of Rent Adjustment Program.")
        self.assertEqual(sec, "Section 8.22.030")
        self.assertIn("Notice of Rent Adjustment", title)

        sec2, title2 = parse_header_section_and_title("Sec. 1.05.010 General Penalties")
        self.assertEqual(sec2, "Section 1.05.010")

        # Test chunking of long content
        long_content = "Paragraph 1: Statutory basis.\n\n" + ("Long legal text element. " * 150) + "\n\nParagraph 3: Final penalty clause."
        chunks = chunk_statute_content(
            header="Test Header",
            content=long_content,
            jurisdiction="Oakland Municipal Code",
            section="Section 8.22.030",
            max_chars=500
        )
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertIn("Oakland Municipal Code", chunks[0]["chunk_text"])
        self.assertIsNotNone(chunks[0]["source_hash"])

    def test_locus_parquet_ingestion_with_real_columns(self):
        import pandas as pd

        # Create a temporary parquet file with LOCUS-v1 columns
        test_df = pd.DataFrame([
            {
                "header": "8.22.010 - Purpose and Findings",
                "content": "This chapter is enacted to protect residential tenants from arbitrary evictions.",
                "state": "CA",
                "city": "Oakland",
                "county": "Alameda County",
                "topic": "Housing & Tenant Protections",
                "function": "Regulation",
                "is_substantive": True
            },
            {
                "header": "8.22.020 - Table of Contents",
                "content": "1. Purpose\n2. Rent limits",
                "state": "CA",
                "city": "Oakland",
                "county": "Alameda County",
                "topic": "Housing & Tenant Protections",
                "function": "TOC",
                "is_substantive": False  # Non-substantive should be skipped by default
            }
        ])

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
            test_df.to_parquet(temp_path)

        # Allow temp dir dynamically for test execution
        temp_dir = os.path.dirname(temp_path)
        src.backend.config.settings.extra_allowed_dirs.append(temp_dir)

        try:
            inserted = ingest_locus_parquet(temp_path, db=self.db, limit=10)
            # Only the substantive row should be ingested
            self.assertEqual(inserted, 1)

            # Check inserted record
            oakland_sub = self.db.query(LawVector).filter_by(section="Section 8.22.010").first()
            self.assertIsNotNone(oakland_sub)
            self.assertEqual(oakland_sub.state, "CA")
            self.assertEqual(oakland_sub.city, "Oakland")
            self.assertEqual(oakland_sub.county, "Alameda County")
            self.assertEqual(oakland_sub.topic, "Housing & Tenant Protections")
            self.assertTrue(oakland_sub.is_substantive)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_citation_and_quote_grounding_verified(self):
        from src.backend.rag import verify_citation_grounding
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with written notice of the Rent Adjustment Program."
            }
        ]
        # Grounded citations and exact verbatim quote from retrieved text
        grounded_analysis = (
            "Under Section 8.22.030 of the Oakland Municipal Code, the landlord violated the law. "
            "Specifically, \"Landlords must provide tenants with written notice of the Rent Adjustment Program.\""
        )
        is_grounded, ungrounded, notice = verify_citation_grounding(grounded_analysis, retrieved_laws)
        self.assertTrue(is_grounded)
        self.assertEqual(len(ungrounded), 0)
        self.assertIn("Citation Grounding Verified", notice)

    def test_citation_and_quote_grounding_flagged(self):
        from src.backend.rag import verify_citation_grounding
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with notice."
            }
        ]
        # Ungrounded section (Section 999.9) and fabricated 30+ char verbatim quote
        fabricated_analysis = (
            "Pursuant to Section 8.22.030 and Section 999.9, the court held that "
            "\"all tenants shall immediately receive an unconditional punitive damage award of twenty thousand dollars.\""
        )
        is_grounded, ungrounded, notice = verify_citation_grounding(fabricated_analysis, retrieved_laws)
        self.assertFalse(is_grounded)
        self.assertIn("999.9", ungrounded)
        self.assertIn("Citation & Grounding Advisory", notice)

    def test_parquet_path_traversal_rejection(self):
        disallowed_path = "/home/krusch/unauthorized_directory/sample.parquet"
        with self.assertRaises(ValueError) as ctx:
            ingest_locus_parquet(disallowed_path, db=self.db)
        self.assertIn("Security Exception", str(ctx.exception))

        resp = self.client.post("/api/ingest/parquet", json={"file_path": disallowed_path, "limit": 5})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Security Exception", resp.json()["detail"])

    def test_vector_and_lexical_similarity_ranking(self):
        from src.backend.rag import retrieve_laws

        q_vec = [0.0] * 1024
        q_vec[0] = 1.0

        close_vec = [0.0] * 1024
        close_vec[0] = 0.9

        far_vec = [0.0] * 1024
        far_vec[1] = 1.0

        law1 = LawVector(
            jurisdiction="Code A", state="CA", city="Oakland",
            title="Rent Increase Notice Requirement", section="Sec 1",
            content="Notice of rent adjustment must be served in writing.",
            embedding=close_vec, is_substantive=True
        )
        law2 = LawVector(
            jurisdiction="Code B", state="CA", city="Oakland",
            title="Unrelated Traffic Regulation", section="Sec 2",
            content="Bicycles shall yield to pedestrians in crosswalks.",
            embedding=far_vec, is_substantive=True
        )
        self.db.add_all([law1, law2])
        self.db.commit()

        # Query with both vector and lexical terms
        results = retrieve_laws(
            query_vector=q_vec,
            text_query="rent increase notice adjustment",
            limit=2,
            db_session=self.db
        )
        self.assertEqual(len(results), 2)
        # Rent statute must rank first
        self.assertEqual(results[0]["title"], "Rent Increase Notice Requirement")
        self.assertGreater(results[0]["similarity"], results[1]["similarity"])

    def test_laws_search_explorer_endpoint(self):
        law = LawVector(
            jurisdiction="Oakland Code", state="CA", city="Oakland",
            title="Relocation Assistance", section="Section 8.22.450",
            content="Landlords must pay relocation fees when withdrawing units from rental market.",
            embedding=self.mock_vector, is_substantive=True
        )
        self.db.add(law)
        self.db.commit()

        resp = self.client.get("/api/laws?q=relocation+fees&city=Oakland")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["section"], "Section 8.22.450")

    def test_async_ingest_job_dispatch(self):
        import pandas as pd

        test_df = pd.DataFrame([{
            "header": "1.01.010 - Title",
            "content": "This code shall be known as the Municipal Code.",
            "state": "CA",
            "city": "Oakland",
            "is_substantive": True
        }])

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
            test_df.to_parquet(temp_path)

        temp_dir = os.path.dirname(temp_path)
        src.backend.config.settings.extra_allowed_dirs.append(temp_dir)

        try:
            resp = self.client.post("/api/ingest/parquet/async", json={"file_path": temp_path, "limit": 10})
            self.assertEqual(resp.status_code, 202)
            job_data = resp.json()
            job_id = job_data["job_id"]
            self.assertIsNotNone(job_id)

            # Check job status endpoint
            status_resp = self.client.get(f"/api/ingest/jobs/{job_id}")
            self.assertEqual(status_resp.status_code, 200)
            self.assertIn(status_resp.json()["status"], ["pending", "running", "completed"])
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_api_key_authentication_enforcement(self):
        src.backend.config.settings.API_KEY = "test_confidential_key"
        try:
            unauth_resp = self.client.get("/api/cases")
            self.assertEqual(unauth_resp.status_code, 401)
            self.assertIn("Unauthorized", unauth_resp.json()["detail"])

            invalid_resp = self.client.get("/api/cases", headers={"X-API-Key": "wrong_key"})
            self.assertEqual(invalid_resp.status_code, 401)

            valid_resp = self.client.get("/api/cases", headers={"X-API-Key": "test_confidential_key"})
            self.assertEqual(valid_resp.status_code, 200)
        finally:
            src.backend.config.settings.API_KEY = None

    def test_mcp_initialize_and_tools_list(self):
        from src.mcp.server import process_request

        # 1. Initialize
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_resp = process_request(init_req)
        self.assertEqual(init_resp["id"], 1)
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "kruschlaw-mcp")

        # 2. Tools list
        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_resp = process_request(tools_req)
        self.assertEqual(tools_resp["id"], 2)
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
        self.assertIn("search_ordinances", tool_names)
        self.assertIn("get_section", tool_names)
        self.assertIn("log_matter", tool_names)
        self.assertIn("draft_brief", tool_names)

    @patch('src.mcp.server.generate_legal_analysis')
    def test_mcp_tool_execution(self, mock_analysis):
        from src.mcp.server import process_request

        mock_analysis.return_value = (
            "### Executive Summary\nTenant rights analysis.\n\n"
            "### Applicable Legal Authority\nOakland Municipal Code Section 8.22.030\n\n"
            "### Next Steps\nReview notice."
        )

        # 1. Ingest seed ordinances
        ingest_mock_data(self.db)

        # 2. Tool call: log_matter
        log_req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "log_matter",
                "arguments": {
                    "title": "MCP Test Matter",
                    "facts": "Tenant was issued rent increase without notice in Oakland.",
                    "matter_number": "MCP-001"
                }
            }
        }
        log_resp = process_request(log_req)
        self.assertEqual(log_resp["id"], 10)
        log_content = json.loads(log_resp["result"]["content"][0]["text"])
        self.assertEqual(log_content["status"], "created")
        case_id = log_content["case_id"]

        # 3. Tool call: search_ordinances
        search_req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "search_ordinances",
                "arguments": {
                    "query": "Rent Adjustment Program notice",
                    "city": "Oakland"
                }
            }
        }
        search_resp = process_request(search_req)
        self.assertEqual(search_resp["id"], 11)
        search_content = json.loads(search_resp["result"]["content"][0]["text"])
        self.assertGreaterEqual(search_content["total_matches"], 1)

        # 4. Tool call: get_section
        get_sec_req = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "get_section",
                "arguments": {
                    "section": "Section 8.22.030"
                }
            }
        }
        get_sec_resp = process_request(get_sec_req)
        self.assertEqual(get_sec_resp["id"], 12)
        sec_content = json.loads(get_sec_resp["result"]["content"][0]["text"])
        self.assertTrue(sec_content["found"])
        self.assertEqual(sec_content["section"], "Section 8.22.030")

        # 5. Tool call: draft_brief
        brief_req = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "draft_brief",
                "arguments": {
                    "case_id": case_id,
                    "city": "Oakland"
                }
            }
        }
        brief_resp = process_request(brief_req)
        self.assertEqual(brief_resp["id"], 13)
        brief_content = json.loads(brief_resp["result"]["content"][0]["text"])
        self.assertEqual(brief_content["staged_status"], "READY_FOR_ATTORNEY_REVIEW")
        self.assertIn("Tenant rights analysis", brief_content["brief_content"])


if __name__ == "__main__":
    unittest.main()

