import unittest
from tests.base import KruschLawTestCase
from src.backend.db import MatterEvidence, LawVector
from src.backend.rag import expand_legal_query, retrieve_laws, retrieve_matter_evidence


class TestQueryExpansionAndEvidence(KruschLawTestCase):
    """Unit tests for automated legal issue-spotting expansion and matter evidence isolation."""

    def test_expand_legal_query_rent_increase(self):
        facts = "My landlord sent a text stating my rent was increased by 15% with no notice of rent adjustment program."
        expanded, spotted = expand_legal_query(facts)

        self.assertIn("OMC 8.22.030", expanded)
        self.assertIn("Notice of Rent Adjustment Program", expanded)
        self.assertTrue(any("Rent Adjustment Program" in s["issue"] for s in spotted))

    def test_expand_legal_query_security_deposit(self):
        facts = "Tenant moved out 35 days ago. Landlord withheld the security deposit and never sent an itemized statement."
        expanded, spotted = expand_legal_query(facts)

        self.assertIn("Cal Civ Code 1950.5", expanded)
        self.assertTrue(any("Security Deposit" in s["issue"] for s in spotted))

    def test_expand_legal_query_habitability(self):
        facts = "The apartment has black mold on the walls, no hot water, and a broken heater in the winter."
        expanded, spotted = expand_legal_query(facts)

        self.assertIn("1941.1", expanded)
        self.assertTrue(any("Habitability" in s["issue"] for s in spotted))

    def test_expand_legal_query_unlawful_lockout(self):
        facts = "The landlord changed the locks while I was at work and shut off the electricity without going to court."
        expanded, spotted = expand_legal_query(facts)

        self.assertIn("789.3", expanded)
        self.assertTrue(any("Self-Help Eviction" in s["issue"] for s in spotted))

    def test_expand_legal_query_non_legal_query(self):
        text = "Meeting with the client tomorrow afternoon at 2 PM in the office."
        expanded, spotted = expand_legal_query(text)

        self.assertEqual(expanded, text)
        self.assertEqual(len(spotted), 0)

    def test_retrieve_matter_evidence_isolation(self):
        """Verify retrieve_matter_evidence returns records strictly belonging to the requested matter."""
        ev1 = MatterEvidence(
            matter_id=101,
            filename="Lease_Agreement_101.pdf",
            doc_type="lease",
            page_number=1,
            section_locator="Clause 4",
            chunk_index=0,
            content="Tenant agrees to pay $2,200 per month on the first day of each month.",
            embedding=self.mock_vector
        )
        ev2 = MatterEvidence(
            matter_id=102,
            filename="Notice_To_Vacate_102.pdf",
            doc_type="notice",
            page_number=2,
            section_locator="Paragraph 2",
            chunk_index=0,
            content="Notice to quit premise within 3 days due to alleged non-payment.",
            embedding=self.mock_vector
        )
        self.db.add_all([ev1, ev2])
        self.db.commit()

        # Query matter 101
        res101 = retrieve_matter_evidence(matter_id=101, text_query="rent pay", db_session=self.db)
        self.assertEqual(len(res101), 1)
        self.assertEqual(res101[0]["matter_id"], 101)
        self.assertEqual(res101[0]["filename"], "Lease_Agreement_101.pdf")

        # Query matter 102
        res102 = retrieve_matter_evidence(matter_id=102, text_query="notice quit", db_session=self.db)
        self.assertEqual(len(res102), 1)
        self.assertEqual(res102[0]["matter_id"], 102)
        self.assertEqual(res102[0]["filename"], "Notice_To_Vacate_102.pdf")

        # Query nonexistent matter
        res999 = retrieve_matter_evidence(matter_id=999, text_query="rent", db_session=self.db)
        self.assertEqual(len(res999), 0)

    def test_retrieve_laws_excludes_matter_corpus(self):
        """Verify that general statutory retrieval does not leak client matter evidence chunks."""
        statute = LawVector(
            jurisdiction="California Civil Code",
            state="CA",
            city="Statewide",
            topic="Tenancy & Security Deposits",
            title="Civil Code § 1950.5",
            section="Section 1950.5",
            content="Governing California security deposit statute.",
            embedding=self.mock_vector,
            is_substantive=True
        )
        matter_chunk = LawVector(
            jurisdiction="Matter Corpus",
            state="Local",
            city="Matter",
            topic="matter_facts",
            title="Confidential_Client_Intake.txt",
            section="Client Memo",
            content="Confidential statement by tenant detailing rent increase.",
            embedding=self.mock_vector,
            is_substantive=True
        )
        self.db.add_all([statute, matter_chunk])
        self.db.commit()

        # General search without city filter should NOT return Matter Corpus
        results = retrieve_laws(text_query="security deposit rent", limit=10, db_session=self.db)
        sections_found = [r["section"] for r in results]
        jurisdictions = [r["jurisdiction"] for r in results]

        self.assertIn("Section 1950.5", sections_found)
        self.assertNotIn("Matter Corpus", jurisdictions)
        self.assertNotIn("Client Memo", sections_found)


if __name__ == "__main__":
    unittest.main()
