import json
import unittest
from unittest.mock import patch
from tests.base import KruschLawTestCase
from src.backend.db import Case, LawVector, StatuteCodeTraceability
from src.backend.ingest import ingest_mock_data
from src.mcp.server import process_request


class TestMcpGuardrailsIntegration(KruschLawTestCase):
    """Integration tests for MCP server: tools listing, drafting guardrails, and grounding report retrieval."""

    def test_mcp_initialize_and_tools_list(self):
        init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        init_resp = process_request(init_req)
        self.assertEqual(init_resp["id"], 1)
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "kruschlaw-mcp")

        tools_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        tools_resp = process_request(tools_req)
        self.assertEqual(tools_resp["id"], 2)
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]

        expected_tools = [
            "search_ordinances",
            "get_section",
            "log_matter",
            "draft_brief",
            "list_matters",
            "get_grounding_report",
            "get_code_traceability"
        ]
        for tool in expected_tools:
            self.assertIn(tool, tool_names)

    def test_mcp_log_matter_and_list_matters(self):
        # 1. Log matter
        log_req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "log_matter",
                "arguments": {
                    "title": "MCP Eviction Case",
                    "facts": "Tenant facing unlawful detainer after requesting heat repairs in Oakland.",
                    "matter_number": "MCP-100"
                }
            }
        }
        log_resp = process_request(log_req)
        self.assertEqual(log_resp["id"], 10)
        log_content = json.loads(log_resp["result"]["content"][0]["text"])
        self.assertEqual(log_content["status"], "created")
        case_id = log_content["case_id"]

        # 2. List matters
        list_req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "list_matters",
                "arguments": {"limit": 10}
            }
        }
        list_resp = process_request(list_req)
        self.assertEqual(list_resp["id"], 11)
        list_content = json.loads(list_resp["result"]["content"][0]["text"])
        self.assertGreaterEqual(list_content["total_matters"], 1)
        found = any(m["id"] == case_id for m in list_content["matters"])
        self.assertTrue(found)

    def test_mcp_draft_brief_refuses_when_authorities_absent(self):
        # Create matter without any relevant authorities in database
        matter = Case(
            title="Isolated Obscure Matter",
            facts="Completely unindexed non-existent subject matter in Antarctica.",
            embedding=self.mock_vector
        )
        self.db.add(matter)
        self.db.commit()

        # Database has no laws matching this
        brief_req = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "draft_brief",
                "arguments": {
                    "case_id": matter.id,
                    "city": "Antarctica"
                }
            }
        }
        brief_resp = process_request(brief_req)
        self.assertEqual(brief_resp["id"], 20)
        content = json.loads(brief_resp["result"]["content"][0]["text"])
        self.assertEqual(content["error"], "CANNOT_DRAFT_WITHOUT_AUTHORITIES")
        self.assertTrue(content["review_required"])
        self.assertIn("refused", content["message"].lower())

    @patch('src.mcp.server.generate_legal_analysis')
    def test_mcp_draft_brief_and_get_grounding_report(self, mock_analysis):
        mock_analysis.return_value = (
            "### Executive Summary\nThe rent increase notice is defective under Oakland OMC Section 8.22.030.\n\n"
            "### Applicable Legal Authority\nOakland Municipal Code Section 8.22.030\n\n"
            "### Analysis\nUnder Section 8.22.030, landlords must provide tenants with written notice of the Rent Adjustment Program.\n\n"
            "### Next Steps\nFile petition."
        )

        ingest_mock_data(self.db)

        matter = Case(
            title="Oakland RAP Defense",
            facts="Landlord increased rent without RAP notice in Oakland.",
            embedding=self.mock_vector
        )
        self.db.add(matter)
        self.db.commit()

        # Draft brief
        draft_req = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "draft_brief",
                "arguments": {
                    "case_id": matter.id,
                    "city": "Oakland"
                }
            }
        }
        draft_resp = process_request(draft_req)
        self.assertEqual(draft_resp["id"], 30)
        draft_content = json.loads(draft_resp["result"]["content"][0]["text"])
        self.assertEqual(draft_content["staged_status"], "READY_FOR_ATTORNEY_REVIEW")
        self.assertTrue(draft_content["review_required"])
        self.assertIn("claims_audit", draft_content)

        # Retrieve grounding report via MCP tool
        report_req = {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {
                "name": "get_grounding_report",
                "arguments": {
                    "case_id": matter.id
                }
            }
        }
        report_resp = process_request(report_req)
        self.assertEqual(report_resp["id"], 31)
        report_content = json.loads(report_resp["result"]["content"][0]["text"])
        self.assertTrue(report_content["found"])
        self.assertEqual(report_content["case_id"], matter.id)
        self.assertIn("claims", report_content)

    def test_mcp_get_code_traceability(self):
        trace = StatuteCodeTraceability(
            statute_id="Cal. Civ. Code § 1950.5(c)",
            symbol_id="deposit_validator.validate_deposit_cap",
            repository="krusch-law",
            file_path="src/backend/rag.py",
            doctrine="Security Deposits",
            status="manually_verified",
            reviewed_by="attorney:krusch",
            statutory_digest="Strict 1-month cap.",
            notes="Verified against Stats. 2023, ch. 290."
        )
        self.db.add(trace)
        self.db.commit()

        req = {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "get_code_traceability",
                "arguments": {
                    "doctrine": "Security Deposits"
                }
            }
        }
        resp = process_request(req)
        self.assertEqual(resp["id"], 40)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertGreaterEqual(content["total"], 1)
        item = content["mappings"][0]
        self.assertEqual(item["statute_id"], "Cal. Civ. Code § 1950.5(c)")
        self.assertEqual(item["doctrine"], "Security Deposits")
        self.assertEqual(item["status"], "manually_verified")


if __name__ == "__main__":
    unittest.main()
