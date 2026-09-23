import unittest
from tests.base import KruschLawTestCase
from src.backend.db import Case, MatterEvidence, LawVector


class TestEvidenceAPIAndIssueSpotting(KruschLawTestCase):
    """Integration tests for evidence query endpoints and issue-spotting in consult responses."""

    def test_get_matter_evidence_api_isolation(self):
        case = Case(
            title="Oakland Eviction Dispute",
            facts="Landlord locked out tenant and retained deposit."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        ev = MatterEvidence(
            matter_id=case.id,
            filename="Lease_Addendum.pdf",
            doc_type="lease",
            page_number=3,
            section_locator="Sec 12.1",
            chunk_index=0,
            content="Security deposit of $2,000 shall be held in trust.",
            embedding=self.mock_vector
        )
        self.db.add(ev)
        self.db.commit()

        # Query evidence via API
        resp = self.client.get(f"/api/cases/{case.id}/evidence?q=security+deposit")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["filename"], "Lease_Addendum.pdf")
        self.assertEqual(data[0]["matter_id"], case.id)
        self.assertEqual(data[0]["page_number"], 3)
        self.assertEqual(data[0]["section_locator"], "Sec 12.1")

        # Query evidence for nonexistent matter
        resp_404 = self.client.get("/api/cases/99999/evidence")
        self.assertEqual(resp_404.status_code, 404)

    def test_consult_matter_returns_spotted_issues(self):
        case = Case(
            title="Unlawful Lockout and Retaliation",
            facts="Landlord changed the locks, shut off the gas, and refused to return the security deposit after I reported mold."
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        # Seed statute
        statute = LawVector(
            jurisdiction="California Civil Code",
            state="CA",
            city="Statewide",
            topic="Habitability & Lockouts",
            title="Civ. Code § 789.3",
            section="Section 789.3",
            content="A landlord shall not with intent to terminate the occupancy cut off utilities or change locks.",
            embedding=self.mock_vector,
            is_substantive=True
        )
        self.db.add(statute)
        self.db.commit()

        resp = self.client.get(f"/api/consult?case_id={case.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("spotted_issues", data)
        issues = [i["issue"] for i in data["spotted_issues"]]
        # Verify self-help eviction and security deposit were spotted
        self.assertTrue(any("Self-Help Eviction" in iss for iss in issues))
        self.assertTrue(any("Security Deposit" in iss for iss in issues))


if __name__ == "__main__":
    unittest.main()
