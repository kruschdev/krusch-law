import unittest
from unittest.mock import patch
from tests.base import KruschLawTestCase
from src.backend.db import Case, LawVector, AuditLog
from src.backend.ingest import ingest_mock_data
import src.backend.config


class TestApiMattersIntegration(KruschLawTestCase):
    """Integration tests for FastAPI endpoints: matters CRUD, audit logging, purge, consult, and pagination."""

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "kruschlaw-backend")
        self.assertIn("security", data)

    def test_matter_crud_and_hard_purge(self):
        # 1. Create matter
        payload = {
            "title": "Oakland Notice of Rent Increase",
            "matter_number": "MATTER-2026-001",
            "client_name": "Jane Doe",
            "description": "Tenant issue, 15% rent increase",
            "facts": "Tenant moved into unit in 2024. Landlord issued a 15% rent increase without notice."
        }
        create_resp = self.client.post("/api/cases", json=payload)
        self.assertEqual(create_resp.status_code, 201)
        case_id = create_resp.json()["id"]

        # Check audit log for matter creation
        create_audit = self.db.query(AuditLog).filter_by(action="create_matter", matter_id=case_id).first()
        self.assertIsNotNone(create_audit)

        # 2. Patch matter
        patch_resp = self.client.patch(f"/api/cases/{case_id}", json={"title": "Updated Title"})
        self.assertEqual(patch_resp.status_code, 200)

        # 3. Soft delete
        del_resp = self.client.delete(f"/api/cases/{case_id}")
        self.assertEqual(del_resp.status_code, 200)
        case_soft = self.db.query(Case).filter_by(id=case_id).first()
        self.assertTrue(case_soft.is_deleted)

        # 4. Enterprise hard purge
        purge_resp = self.client.delete(f"/api/cases/{case_id}/purge")
        self.assertEqual(purge_resp.status_code, 200)
        self.assertEqual(purge_resp.json()["status"], "purged")

        # Verify matter completely deleted from database
        case_purged = self.db.query(Case).filter_by(id=case_id).first()
        self.assertIsNone(case_purged)

        # Verify purge action was recorded in immutable audit log
        purge_audit = self.db.query(AuditLog).filter_by(action="purge_matter", matter_id=case_id).first()
        self.assertIsNotNone(purge_audit)

    @patch('src.backend.main.generate_legal_analysis')
    def test_consult_endpoint_with_grounding_audit(self, mock_analysis):
        mock_analysis.return_value = (
            "### Executive Summary\nThe rent increase violates Oakland Rent Adjustment Program Section 8.22.030.\n\n"
            "### Applicable Legal Authority\nOakland Municipal Code Section 8.22.030\n\n"
            "### Factual Matrix Analysis\nUnder Section 8.22.030, landlords must provide tenants with written notice of the Rent Adjustment Program.\n\n"
            "### Next Steps\nFile RAP petition."
        )

        ingest_mock_data(self.db)

        matter = Case(
            title="Rent Increase Defense",
            facts="Landlord served a rent increase without providing the required RAP notice in Oakland.",
            embedding=self.mock_vector
        )
        self.db.add(matter)
        self.db.commit()

        resp = self.client.get(f"/api/consult?case_id={matter.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("analysis", data)
        self.assertTrue(data.get("review_required"))
        self.assertTrue(data.get("provisional_work_product"))
        self.assertIn("claims_audit", data)
        self.assertGreaterEqual(len(data["claims_audit"]), 1)
        self.assertIn("grounding_stats", data)
        self.assertEqual(data["grounding_stats"]["pass_rate"], 100.0)

        # Check audit log for legal consult
        consult_audit = self.db.query(AuditLog).filter_by(action="consult", matter_id=matter.id).first()
        self.assertIsNotNone(consult_audit)

    def test_pagination_on_cases_and_laws(self):
        # Create 5 cases
        for i in range(5):
            self.db.add(Case(title=f"Matter {i}", facts=f"Facts {i}", embedding=self.mock_vector))
        self.db.commit()

        # Query cases with limit 2, offset 1
        resp = self.client.get("/api/cases?limit=2&offset=1")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Matter 1")

        # Ingest mock ordinances and test pagination on /api/laws
        ingest_mock_data(self.db)
        laws_resp = self.client.get("/api/laws?city=Oakland&limit=3&offset=0")
        self.assertEqual(laws_resp.status_code, 200)
        law_items = laws_resp.json()
        self.assertLessEqual(len(law_items), 3)

    def test_api_key_authentication(self):
        src.backend.config.settings.API_KEY = "audit_secure_token"
        try:
            # Unauthorized request without key
            unauth = self.client.get("/api/cases")
            self.assertEqual(unauth.status_code, 401)

            # Authorized request with header
            auth = self.client.get("/api/cases", headers={"X-API-Key": "audit_secure_token"})
            self.assertEqual(auth.status_code, 200)
        finally:
            src.backend.config.settings.API_KEY = None

    def test_ingest_path_traversal_rejection(self):
        disallowed_path = "/home/krusch/unauthorized_directory/sample.parquet"
        resp = self.client.post("/api/ingest/parquet", json={"file_path": disallowed_path, "limit": 5})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Security Exception", resp.json()["detail"])

    def test_export_consult_docx_endpoint(self):
        payload = {
            "brief_content": "### Legal Memo\n\nUnder Section 8.22.030, notice is required.",
            "matter_title": "Oakland Notice Defense",
            "matter_number": "MATTER-2026-999",
            "client_name": "Test Client",
            "claims_audit": [
                {
                    "claim": "Under Section 8.22.030, notice is required.",
                    "status": "supported",
                    "citation": "8.22.030",
                    "source_excerpt": "Notice must be provided.",
                    "reason": "Verified"
                }
            ],
            "retrieved_laws": [
                {
                    "section": "Section 8.22.030",
                    "title": "RAP Notice",
                    "authority_class": "municipal_ordinance",
                    "effective_date": "2020-02-01"
                }
            ]
        }
        resp = self.client.post("/api/consult/export/docx", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        self.assertGreater(len(resp.content), 1000)
        # Check docx zip signature (PK\x03\x04)
        self.assertTrue(resp.content.startswith(b"PK\x03\x04"))


if __name__ == "__main__":
    unittest.main()
