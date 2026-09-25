"""
tests/test_statute_relations.py
================================
Validates:
  1. CRUD lifecycle of statutory relations and preemption/amendment review queue.
  2. Filter capabilities by status ('proposed', 'confirmed', 'rejected') and legal doctrine/topic.
  3. Attorney review actions (confirm, reject, edit) setting reviewed_by and reviewed_at timestamps.
  4. Integration with resolve_controlling_law: emitting uncertainty advisories for unconfirmed links.
  5. Invariant enforcement: proposed links never silently control without attorney confirmation.
"""

import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.ingest import ingest_mock_data
from src.backend.resolver import resolve_controlling_law
from src.backend.rag import generate_legal_analysis
from src.backend.db import StatuteRelation, LawVector


class TestStatuteRelations(KruschLawTestCase):
    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_01_create_proposed_relation(self):
        """Verify creation of a proposed statutory relation edge."""
        payload = {
            "source_statute": "Stats. 2023, ch. 290 (AB 12)",
            "target_statute": "Cal. Civ. Code § 1950.5",
            "relation_type": "AMENDS",
            "scope_topic": "security_deposit",
            "confidence": 0.95,
            "status": "proposed",
            "trigger_span": "Section 1950.5 of the Civil Code is amended to read",
            "rationale": "AB 12 explicitly amends residential security deposit limits to 1 month rent."
        }
        resp = self.client.post("/api/resolver/relations", json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertIn("id", data)
        self.assertEqual(data["source_statute"], payload["source_statute"])
        self.assertEqual(data["target_statute"], payload["target_statute"])
        self.assertEqual(data["relation_type"], "AMENDS")
        self.assertEqual(data["scope_topic"], "security_deposit")
        self.assertEqual(data["status"], "proposed")
        self.assertAlmostEqual(data["confidence"], 0.95)
        self.assertIsNone(data["reviewed_by"])
        self.assertIsNone(data["reviewed_at"])
        self.assertIsNotNone(data["created_at"])

    def test_02_list_relations_and_filtering(self):
        """Verify filtering relations by status and doctrine topic."""
        # Create 1 proposed and 1 confirmed relation
        self.client.post("/api/resolver/relations", json={
            "source_statute": "Cal. Civ. Code § 1954.50 (Costa-Hawkins)",
            "target_statute": "San Francisco Rent Ordinance § 37.3",
            "relation_type": "PREEMPTS",
            "scope_topic": "rent_control",
            "confidence": 0.99,
            "status": "confirmed"
        })
        self.client.post("/api/resolver/relations", json={
            "source_statute": "Oakland Fair Chance Housing OMC § 8.25",
            "target_statute": "Cal. Health & Safety Code § 11571.1",
            "relation_type": "CARVES_OUT",
            "scope_topic": "eviction_criminal_record",
            "confidence": 0.88,
            "status": "proposed"
        })

        # List all
        resp = self.client.get("/api/resolver/relations")
        self.assertEqual(resp.status_code, 200)
        all_rels = resp.json()
        self.assertGreaterEqual(len(all_rels), 2)

        # Filter by status: proposed
        resp_prop = self.client.get("/api/resolver/relations?status=proposed")
        self.assertEqual(resp_prop.status_code, 200)
        prop_rels = resp_prop.json()
        self.assertTrue(all(r["status"] == "proposed" for r in prop_rels))
        self.assertTrue(any(r["scope_topic"] == "eviction_criminal_record" for r in prop_rels))

        # Filter by topic: rent_control
        resp_topic = self.client.get("/api/resolver/relations?topic=rent_control")
        self.assertEqual(resp_topic.status_code, 200)
        topic_rels = resp_topic.json()
        self.assertTrue(all("rent_control" in r["scope_topic"] for r in topic_rels))

    def test_03_patch_confirm_relation(self):
        """Verify attorney review workflow confirming a proposed relation."""
        create_resp = self.client.post("/api/resolver/relations", json={
            "source_statute": "Stats. 2019, ch. 597 (AB 1482)",
            "target_statute": "Cal. Civ. Code § 1946.2",
            "relation_type": "CREATES",
            "scope_topic": "just_cause_eviction",
            "confidence": 0.98,
            "status": "proposed"
        })
        rel_id = create_resp.json()["id"]

        # Confirm the relation
        patch_resp = self.client.patch(f"/api/resolver/relations/{rel_id}", json={
            "status": "confirmed",
            "reviewed_by": "attorney:krusch",
            "rationale": "Confirmed by admitted counsel: statutory foundation for just cause protections."
        })
        self.assertEqual(patch_resp.status_code, 200)
        updated = patch_resp.json()
        self.assertEqual(updated["status"], "confirmed")
        self.assertEqual(updated["reviewed_by"], "attorney:krusch")
        self.assertIsNotNone(updated["reviewed_at"])
        self.assertIn("Confirmed by admitted counsel", updated["rationale"])

    def test_04_patch_reject_relation(self):
        """Verify rejecting a spurious relation proposal."""
        create_resp = self.client.post("/api/resolver/relations", json={
            "source_statute": "False Candidate Code § 999",
            "target_statute": "Cal. Civ. Code § 1950.5",
            "relation_type": "PREEMPTS",
            "scope_topic": "security_deposit",
            "confidence": 0.35,
            "status": "proposed"
        })
        rel_id = create_resp.json()["id"]

        patch_resp = self.client.patch(f"/api/resolver/relations/{rel_id}", json={
            "status": "rejected",
            "reviewed_by": "attorney:krusch",
            "rationale": "No statutory preemption basis; spurious candidate rejected."
        })
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.json()["status"], "rejected")

    def test_05_delete_relation(self):
        """Verify deleting a relation and error handling on missing records."""
        create_resp = self.client.post("/api/resolver/relations", json={
            "source_statute": "Temp Code § 1",
            "target_statute": "Temp Code § 2",
            "relation_type": "AMENDS",
            "scope_topic": "temporary",
            "confidence": 0.5,
            "status": "proposed"
        })
        rel_id = create_resp.json()["id"]

        del_resp = self.client.delete(f"/api/resolver/relations/{rel_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json()["status"], "deleted")

        # Second delete should return 404
        del_again = self.client.delete(f"/api/resolver/relations/{rel_id}")
        self.assertEqual(del_again.status_code, 404)

    def test_06_resolver_uncertainty_warning_and_resolution(self):
        """Verify resolve_controlling_law flags uncertainty when proposed relations exist."""
        # Create a proposed relation for deposit doctrine
        self.client.post("/api/resolver/relations", json={
            "source_statute": "Stats. 2023, ch. 290 (AB 12)",
            "target_statute": "Cal. Civ. Code § 1950.5",
            "relation_type": "AMENDS",
            "scope_topic": "deposit",
            "confidence": 0.92,
            "status": "proposed",
            "trigger_span": "amended to read",
            "rationale": "Pending review: AB 12 deposit amendment."
        })

        # Resolve controlling law for deposit doctrine
        resolution = resolve_controlling_law(
            doctrine_or_topic="deposit",
            jurisdiction="California",
            as_of_date=date(2024, 8, 1),
            db=self.db
        )

        # Should detect the unconfirmed proposal and set the uncertainty advisory
        self.assertGreaterEqual(len(resolution.unconfirmed_proposals), 1)
        self.assertIsNotNone(resolution.uncertainty_warning)
        self.assertIn("CONTROLLING STATUTE UNCERTAIN", resolution.uncertainty_warning)
        self.assertIn("proposed preemption/amendment link(s) pending human attorney review", resolution.uncertainty_warning)

        # Now, simulate attorney confirmation of all proposals
        for prop in resolution.unconfirmed_proposals:
            self.client.patch(f"/api/resolver/relations/{prop['id']}", json={
                "status": "confirmed",
                "reviewed_by": "attorney:krusch"
            })

        # Re-resolve: uncertainty warning must be cleared
        res_after = resolve_controlling_law(
            doctrine_or_topic="deposit",
            jurisdiction="California",
            as_of_date=date(2024, 8, 1),
            db=self.db
        )
        self.assertEqual(len(res_after.unconfirmed_proposals), 0)
        self.assertIsNone(res_after.uncertainty_warning)

    def test_07_rag_incorporates_uncertainty_warning_in_brief(self):
        """Verify legal analysis brief output includes uncertainty warning banner when proposals exist."""
        # Create a proposed relation for habitability
        self.client.post("/api/resolver/relations", json={
            "source_statute": "Proposed City Habitability Standard § 100",
            "target_statute": "Cal. Civ. Code § 1941.1",
            "relation_type": "PREEMPTS",
            "scope_topic": "habitability",
            "confidence": 0.85,
            "status": "proposed"
        })

        mock_law = {
            "section": "Cal. Civ. Code § 1941.1",
            "title": "Characteristics of Tenable Dwelling",
            "content": "A dwelling shall be deemed untenantable if it lacks effective waterproofing and weather protection.",
            "effective_date": "2020-01-01"
        }

        from unittest.mock import patch, MagicMock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "## 1. Statutory Summary\nUnder Cal. Civ. Code § 1941.1, dwellings must have weather protection.\n\n## 2. Issue Application\nThe facts indicate defective waterproofing.\n\n## 3. Potential Defenses & Deadlines\nRepair and deduct remedy applies.\n\n## 4. Evidentiary Audit\nInspect physical premises."
        }

        with patch("httpx.Client.post", return_value=mock_response):
            brief, stats, claims = generate_legal_analysis(
                case_facts="Tenant reports defective roof and water leaks in Oakland apartment.",
                case_title="Habitability Defense",
                laws=[mock_law],
                db_session=self.db
            )

        # Brief markdown must include the uncertainty warning
        self.assertIn("CONTROLLING STATUTE UNCERTAIN", brief)
        self.assertIn("⚠️", brief)


if __name__ == "__main__":
    unittest.main()
