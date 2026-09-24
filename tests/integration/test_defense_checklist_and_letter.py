"""
Integration Tests for Defense Checklists and Statutory Letter Assembly
======================================================================
Tests:
1. Generation of structured defense checklists with statutory deadlines:
   - 21-day deposit return and itemization under Cal. Civ. Code § 1950.5
   - Implied warranty of habitability under Cal. Civ. Code § 1941.1
   - 180-day retaliation presumption under Cal. Civ. Code § 1942.5(a)
   - Unlawful self-help lockouts under Cal. Civ. Code § 789.3
   - Defective 3-day notice under CCP § 1161(2) & Oakland OMC § 8.22.360(F)
2. Assembly of formal statutory letters with mandatory legal phrases:
   - Security deposit formal demand
   - Habitability repair notice
   - Defective notice to quit response
3. REST endpoints:
   - GET /api/cases/{case_id}/defense-checklist
   - POST /api/cases/{case_id}/assemble-letter
4. MCP tools:
   - get_defense_checklist
   - assemble_statutory_letter
"""

import json
import unittest

from tests.base import KruschLawTestCase
from src.backend.db import Case, MatterEvidence
from src.backend.checklist import generate_defense_checklist, assemble_statutory_letter
from src.mcp.server import process_request


class TestDefenseChecklistAndLetterIntegration(KruschLawTestCase):
    def test_01_generate_defense_checklist_security_deposit(self):
        case = Case(
            title="Oakland Security Deposit Dispute",
            matter_number="MAT-DEP-001",
            client_name="Elena Rostova",
            facts="Moved out on August 1st. Landlord kept my $2,500 security deposit with zero itemization or receipts after 35 days."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        report = generate_defense_checklist(case, as_of_date="2024-09-05", db=self.db)
        self.assertEqual(report.case_id, case.id)
        self.assertGreaterEqual(report.total_defenses_spotted, 1)

        dep_defense = next(d for d in report.defenses if "Security Deposit" in d.issue)
        self.assertIn("Civ. Code § 1950.5", dep_defense.controlling_citation)
        self.assertIn("21 calendar days", dep_defense.statutory_deadline)
        self.assertIn("twice the deposit amount", dep_defense.statutory_remedy)
        self.assertTrue(len(dep_defense.elements) >= 3)
        self.assertTrue(len(dep_defense.required_evidence) >= 2)

    def test_02_generate_defense_checklist_habitability_and_retaliation(self):
        case = Case(
            title="Mold and Broken Heater Retaliation",
            matter_number="MAT-HAB-002",
            client_name="Marcus Vance",
            facts="Reported severe toxic black mold and broken heater to landlord. Two weeks later landlord served a notice to vacate."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        report = generate_defense_checklist(case, as_of_date="2024-03-01", db=self.db)
        issues = [d.issue for d in report.defenses]

        self.assertTrue(any("Habitability" in iss for iss in issues))
        self.assertTrue(any("Retaliat" in iss for iss in issues))

        retaliation = next(d for d in report.defenses if "Retaliat" in d.issue)
        self.assertIn("180 calendar days", retaliation.statutory_deadline)
        self.assertIn("1942.5", retaliation.controlling_citation)

    def test_03_assemble_security_deposit_demand_letter(self):
        case = Case(
            title="Deposit Demand Case",
            matter_number="MAT-DEMAND-001",
            client_name="Jane Doe",
            facts="Vacated premises on July 10. Landlord withheld $3,000 security deposit without explanation."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        res = assemble_statutory_letter(
            case=case,
            letter_type="security_deposit_demand",
            recipient_name="Apex Property Management LLC",
            recipient_address="100 Grand Ave, Oakland, CA 94612",
            sender_name="Jane Doe",
            as_of_date="2024-08-15",
            db=self.db
        )

        self.assertEqual(res.letter_type, "security_deposit_demand")
        self.assertIn("Cal. Civ. Code § 1950.5(g)", res.mandatory_citations)
        self.assertIn("Granberry v. Islay Investments", res.letter_body)
        self.assertIn("1950.5(l)", res.letter_body)
        self.assertIn("ten (10) calendar days", res.letter_body)

    def test_04_assemble_habitability_and_defective_notice_letters(self):
        case = Case(
            title="Habitability and Notice Case",
            matter_number="MAT-COMBO-001",
            client_name="John Smith",
            facts="Defective plumbing and unpermitted entry."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        # Habitability Notice
        hab_res = assemble_statutory_letter(
            case=case,
            letter_type="habitability_repair_notice",
            recipient_name="Landlord Joe",
            recipient_address="200 Main St, Oakland, CA",
            db=self.db
        )
        self.assertIn("Cal. Civ. Code § 1941.1", hab_res.mandatory_citations)
        self.assertIn("180 calendar days", hab_res.letter_body)

        # Defective Notice Response
        notice_res = assemble_statutory_letter(
            case=case,
            letter_type="defective_notice_response",
            recipient_name="Landlord Joe",
            recipient_address="200 Main St, Oakland, CA",
            db=self.db
        )
        self.assertIn("Cal. Code Civ. Proc. § 1161(2)", notice_res.mandatory_citations)
        self.assertIn("Oakland Municipal Code § 8.22.360(F)", notice_res.mandatory_citations)
        self.assertIn("Rent Board", notice_res.letter_body)

    def test_05_rest_endpoints(self):
        case = Case(
            title="API Checklist Case",
            facts="Landlord changed locks and locked me out without a court order."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        # GET defense checklist
        resp = self.client.get(f"/api/cases/{case.id}/defense-checklist")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], case.id)
        self.assertGreaterEqual(data["total_defenses_spotted"], 1)
        self.assertTrue(any("Self-Help" in d["issue"] for d in data["defenses"]))

        # POST assemble letter
        letter_payload = {
            "letter_type": "security_deposit_demand",
            "recipient_name": "Property Owner",
            "recipient_address": "456 Market St, San Francisco, CA"
        }
        res_letter = self.client.post(f"/api/cases/{case.id}/assemble-letter", json=letter_payload)
        self.assertEqual(res_letter.status_code, 200)
        letter_data = res_letter.json()
        self.assertEqual(letter_data["letter_type"], "security_deposit_demand")
        self.assertIn("Cal. Civ. Code § 1950.5(g)", letter_data["mandatory_citations"])

    def test_06_mcp_tools(self):
        case = Case(
            title="MCP Checklist Matter",
            facts="Landlord served 3-day notice demanding late fees and failed to return deposit."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        # MCP tool: get_defense_checklist
        req_checklist = {
            "jsonrpc": "2.0",
            "id": "req-mcp-chk-01",
            "method": "tools/call",
            "params": {
                "name": "get_defense_checklist",
                "arguments": {
                    "case_id": case.id
                }
            }
        }
        res = process_request(req_checklist)
        self.assertNotIn("error", res)
        txt = res["result"]["content"][0]["text"]
        self.assertIn("defenses", txt)
        self.assertIn("controlling_citation", txt)

        # MCP tool: assemble_statutory_letter
        req_letter = {
            "jsonrpc": "2.0",
            "id": "req-mcp-let-01",
            "method": "tools/call",
            "params": {
                "name": "assemble_statutory_letter",
                "arguments": {
                    "case_id": case.id,
                    "letter_type": "security_deposit_demand",
                    "recipient_name": "Landlord LLC",
                    "recipient_address": "123 Main St, Oakland, CA"
                }
            }
        }
        res_let = process_request(req_letter)
        self.assertNotIn("error", res_let)
        txt_let = res_let["result"]["content"][0]["text"]
        self.assertIn("Cal. Civ. Code § 1950.5(g)", txt_let)
        self.assertIn("Granberry v. Islay Investments", txt_let)


if __name__ == "__main__":
    unittest.main()
