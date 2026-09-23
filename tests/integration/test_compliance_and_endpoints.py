"""
tests/integration/test_compliance_and_endpoints.py
==================================================
Validates:
  1. Manually curated statute-to-code traceability table (California residential housing doctrine).
  2. Companion context bridge endpoints: /api/laws/search and /api/laws/section.
  3. Standalone assertion verification endpoint: /api/verify/assertions.
  4. Grounded brief drafting endpoint with hard assertion grounding gate: /api/cases/brief.
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.ingest import ingest_mock_data
from src.backend.db import StatuteCodeTraceability


class TestComplianceAndEndpoints(KruschLawTestCase):
    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_01_code_traceability_registry(self):
        """Verify curated statute-to-code traceability registry for CA residential housing doctrine."""
        response = self.client.get("/api/compliance/traceability")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 5, "Must contain at least 5 curated statutory bindings.")

        statute_ids = [d["statute_id"] for d in data]
        self.assertIn("Cal. Civ. Code § 1950.5(c)", statute_ids)
        self.assertIn("Cal. Civ. Code § 1946.2", statute_ids)
        self.assertIn("Oakland Municipal Code § 8.22.030", statute_ids)

        for item in data:
            self.assertEqual(item["status"], "manually_verified")
            self.assertEqual(item["reviewed_by"], "attorney:krusch")
            self.assertIsNotNone(item["reviewed_at"])
            self.assertTrue(len(item["statutory_digest"]) > 0)

        # Test filtering by doctrine
        dep_resp = self.client.get("/api/compliance/traceability?doctrine=Security+Deposits")
        self.assertEqual(dep_resp.status_code, 200)
        dep_data = dep_resp.json()
        self.assertTrue(all(d["doctrine"] == "Security Deposits" for d in dep_data))

    def test_02_laws_search_and_section_endpoints(self):
        """Verify bridge search and section lookup endpoints consumed by KruschContext MCP."""
        # /api/laws/search
        search_resp = self.client.get("/api/laws/search?q=security+deposit+itemized&limit=3")
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.json()
        self.assertIn("results", search_data)
        self.assertGreaterEqual(len(search_data["results"]), 1)

        # /api/laws/section
        sec_resp = self.client.get("/api/laws/section?section=Section 1950.5(b)")
        self.assertEqual(sec_resp.status_code, 200)
        sec_data = sec_resp.json()
        self.assertEqual(sec_data["section"], "Section 1950.5(b)")
        self.assertIn("bad faith", sec_data["body"].lower())
        self.assertEqual(sec_data["authority_weight"], 1.0)

    def test_03_verify_assertions_endpoint(self):
        """Verify two-pass claim verifier over HTTP API."""
        # Supported claim
        payload_valid = {
            "draft_text": "Pursuant to Section 1950.5, the landlord shall furnish an itemized statement within 21 calendar days after vacating."
        }
        resp = self.client.post("/api/verify/assertions", json=payload_valid)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_grounded"])
        self.assertEqual(data["claims"][0]["verdict"], "entailed")
        self.assertFalse(data["claims"][0]["refused"])

        # Contradicted / polar inversion claim
        payload_contradicted = {
            "draft_text": "Under Section 1950.5, a landlord may arbitrarily confiscate the deposit without itemization."
        }
        resp_bad = self.client.post("/api/verify/assertions", json=payload_contradicted)
        self.assertEqual(resp_bad.status_code, 200)
        data_bad = resp_bad.json()
        self.assertFalse(data_bad["is_grounded"])
        self.assertEqual(data_bad["claims"][0]["verdict"], "contradicted")
        self.assertTrue(data_bad["claims"][0]["refused"])
        self.assertIn("[CLAIM REFUSED: CONTRADICTED", data_bad["verified_draft"])

    def test_04_brief_draft_hard_gate_and_refusal(self):
        """Verify brief drafting enforces assertion grounding as a hard gate."""
        payload = {
            "facts": "Tenant in Oakland was served a 3-day notice to quit for non-payment of rent without prior notice of the RAP program.",
            "title": "Oakland Eviction Defense Brief",
            "city": "Oakland",
            "state": "CA"
        }
        resp = self.client.post("/api/cases/brief", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("brief_markdown", data)
        self.assertIn("grounding_audit", data)

        # Refusal when authorities are missing
        payload_missing = {
            "facts": "Tenant in Anchorage Alaska commercial dispute over snow plowing permits.",
            "city": "Anchorage",
            "state": "AK"
        }
        resp_missing = self.client.post("/api/cases/brief", json=payload_missing)
        self.assertEqual(resp_missing.status_code, 200)
        data_missing = resp_missing.json()
        self.assertEqual(data_missing["status"], "CANNOT_DRAFT_WITHOUT_AUTHORITIES")


if __name__ == "__main__":
    unittest.main()
