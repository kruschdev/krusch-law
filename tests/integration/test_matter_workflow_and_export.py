"""
Integration Tests for Week 4 Matter-Centric Workflow and Refusal-First Export
=============================================================================
Tests:
1. Full matter-centric workflow: Matter -> Issue Spotting -> Verification -> Human Feedback.
2. Human attorney claim feedback loop (accept/reject per claim) as local signal.
3. Refusal-first export: ungrounded/refused propositions become explicit Coverage Gaps, not prose.
4. MCP tool explain_why_not_controlling for autonomous agents.
"""

import os
import sys
import json
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.db import Case, GroundingReport, ClaimFeedback
from src.backend.export import generate_brief_docx
from src.mcp.server import process_request


class TestMatterWorkflowAndExportIntegration(KruschLawTestCase):
    def test_matter_claim_feedback_loop(self):
        """
        Attorneys can review assertion tables and record accept/reject decisions per claim.
        Decisions are persisted locally as evaluation and training signal.
        """
        # 1. Create client matter
        case = Case(
            title="Oakland Security Deposit Dispute",
            matter_number="MATTER-REVIEW-001",
            facts="Landlord retained $2,500 security deposit for 45 days with zero itemization."
        )
        self.db.add(case)
        self.db.commit()
        case_id = case.id

        # 2. Record human attorney feedback per claim
        feedback_payload = {
            "report_id": "rep-abc-123",
            "feedbacks": [
                {
                    "claim_text": "Landlord must return deposit within 21 calendar days under Section 1950.5.",
                    "citation": "Section 1950.5",
                    "decision": "accepted",
                    "attorney_notes": "Clean controlling California statute."
                },
                {
                    "claim_text": "Tenant is entitled to punitive treble damages under Section 999.99.",
                    "citation": "Section 999.99",
                    "decision": "rejected",
                    "correction": "Section 999.99 is not authoritative; statutory bad faith damages are governed by Section 1950.5(l).",
                    "attorney_notes": "Rejected hallucinated section."
                }
            ]
        }

        resp = self.client.post(f"/api/cases/{case_id}/claims/feedback", json=feedback_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "recorded")
        self.assertEqual(data["feedback_count"], 2)

        # 3. Retrieve recorded feedback
        get_resp = self.client.get(f"/api/cases/{case_id}/claims/feedback")
        self.assertEqual(get_resp.status_code, 200)
        items = get_resp.json()
        self.assertEqual(len(items), 2)

        accepted_item = next(i for i in items if i["decision"] == "accepted")
        self.assertIn("Section 1950.5", accepted_item["citation"])

        rejected_item = next(i for i in items if i["decision"] == "rejected")
        self.assertIn("Section 999.99 is not authoritative", rejected_item["correction"])

    def test_refusal_first_export_with_coverage_gaps(self):
        """
        Export generated from claims must convert refused or rejected claims into
        explicit statutory coverage gap notices rather than fluent misleading prose.
        """
        brief_text = (
            "### Executive Summary\n"
            "Under California Civil Code Section 1950.5, landlord must refund deposit within 21 days.\n\n"
            "[CLAIM REFUSED: NOT_IN_CORPUS - Cited section '999.99' does not exist in retrieved authorities.]\n\n"
            "### Statutory Defenses\n"
            "[COVERAGE GAP: Statutory exemption under Section 1946.2(e) precludes eviction defense.]"
        )

        claims_audit = [
            {
                "claim": "Landlord must refund deposit within 21 days.",
                "citation": "Section 1950.5",
                "status": "supported",
                "refused": False,
                "source_excerpt": "within 21 calendar days after tenant vacates"
            },
            {
                "claim": "Tenant entitled to automatic $10,000 fine under Section 999.99.",
                "citation": "Section 999.99",
                "status": "invented_citation",
                "verdict": "not_in_corpus",
                "refused": True,
                "reason": "Citation does not exist in retrieved authority set"
            }
        ]

        docx_bytes = generate_brief_docx(
            brief_content=brief_text,
            matter_title="Tenant Rights Assessment",
            matter_number="MAT-EXPORT-001",
            claims_audit=claims_audit
        )

        self.assertIsInstance(docx_bytes, bytes)
        self.assertGreater(len(docx_bytes), 1000)

        # Test DOCX export REST endpoint
        export_payload = {
            "brief_content": brief_text,
            "matter_title": "Tenant Rights Assessment",
            "matter_number": "MAT-EXPORT-001",
            "claims_audit": claims_audit
        }
        res = self.client.post("/api/consult/export/docx", json=export_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        self.assertIn("KruschLaw_Brief", res.headers["content-disposition"])

    def test_mcp_explain_why_not_controlling_tool(self):
        """
        Agents can invoke explain_why_not_controlling via MCP to diagnose why a law does not apply.
        """
        request_payload = {
            "jsonrpc": "2.0",
            "id": "req-mcp-explain-01",
            "method": "tools/call",
            "params": {
                "name": "explain_why_not_controlling",
                "arguments": {
                    "candidate_section": "Section 1950.5",
                    "doctrine": "Security Deposits",
                    "as_of_date": "2023-01-01"
                }
            }
        }
        response = process_request(request_payload)
        self.assertNotIn("error", response)
        content_items = response["result"]["content"]
        self.assertTrue(len(content_items) > 0)
        report_text = content_items[0]["text"]
        self.assertIn("is_controlling", report_text)
        self.assertIn("Section 1950.5", report_text)


if __name__ == "__main__":
    unittest.main()
