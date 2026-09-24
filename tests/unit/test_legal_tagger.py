import unittest
from src.backend.tagger import heuristic_tag_chunk, tag_legal_chunk


class TestLegalChunkTagger(unittest.TestCase):
    """Unit tests for KruschLaw legal semantic chunk tagger."""

    def test_security_deposit_tagging(self):
        text = "Tenant shall pay an initial security deposit of $1,500. Landlord must provide itemized accounting under CC 1950.5."
        result = heuristic_tag_chunk(text, filename="Lease_Standard.pdf", locator="p. 2 § 4.1")
        self.assertEqual(result["doctrine"], "Security Deposits")
        self.assertIn("security-deposit", result["tags"])
        self.assertTrue(len(result["summary"]) > 0)

    def test_habitability_tagging(self):
        text = "The tenant reported persistent black mold, broken heating, and lack of waterproofing on the roof under 1941.1."
        result = heuristic_tag_chunk(text, filename="Notice_Defects.txt")
        self.assertEqual(result["doctrine"], "Habitability")
        self.assertIn("habitability", result["tags"])
        self.assertIn("substandard-housing", result["tags"])

    def test_just_cause_tagging(self):
        text = "Landlord served a 60-day notice to quit citing owner move-in under California Civil Code 1946.2 (AB 1482)."
        result = heuristic_tag_chunk(text, filename="Notice_To_Quit.pdf")
        self.assertEqual(result["doctrine"], "Just Cause")
        self.assertIn("just-cause", result["tags"])
        self.assertIn("notice-to-quit", result["tags"])

    def test_self_help_eviction_tagging(self):
        text = "Landlord turned off the gas supply and performed an illegal lockout changing the front door locks."
        result = heuristic_tag_chunk(text, filename="Incident_Report.docx")
        self.assertEqual(result["doctrine"], "Self-Help Eviction")
        self.assertIn("self-help-eviction", result["tags"])
        self.assertIn("lockout", result["tags"])

    def test_tag_legal_chunk_heuristic_fallback(self):
        text = "Rent shall increase by 10% effective next month pursuant to Oakland Rent Board rules."
        result = tag_legal_chunk(text, filename="Rent_Notice.pdf", use_llm=False)
        self.assertEqual(result["doctrine"], "Rent Control")
        self.assertIn("rent-control", result["tags"])


if __name__ == "__main__":
    unittest.main()
