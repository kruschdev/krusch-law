import unittest
from tests.base import KruschLawTestCase
from src.backend.rag import (
    extract_propositional_claims,
    verify_assertion_grounding,
    verify_citation_grounding,
    embedding_cache
)


class TestAssertionGrounding(KruschLawTestCase):
    """Unit tests for assertion-level grounding, failure mode taxonomy, and embedding cache."""

    def test_extract_propositional_claims(self):
        text = (
            "Under Cal. Civ. Code § 1950.5(b), security deposits are strictly capped at one month's rent. "
            "Pursuant to OMC § 8.22.030, landlords must provide the written RAP notice. "
            "In Green v. Superior Court, the warranty of habitability was recognized."
        )
        claims = extract_propositional_claims(text)
        self.assertGreaterEqual(len(claims), 3)

        # Cal. Civ. Code § 1950.5(b) claim should not be fragmented at periods
        cal_claim = next((c for c in claims if "1950.5(b)" in c), None)
        self.assertIsNotNone(cal_claim)
        self.assertIn("1950.5(b)", cal_claim)

        # OMC § 8.22.030 claim
        omc_claim = next((c for c in claims if "8.22.030" in c), None)
        self.assertIsNotNone(omc_claim)
        self.assertIn("8.22.030", omc_claim)

    def test_failure_mode_invented_citation(self):
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with written notice of the Rent Adjustment Program.",
                "repealed": False
            }
        ]
        # Text cites a fabricated section 999.99
        analysis = "Pursuant to OMC Section 999.99, tenants are entitled to an immediate $10,000 refund."
        is_grounded, claims, notice, stats = verify_assertion_grounding(analysis, retrieved_laws)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "invented_citation")
        self.assertIn("999.99", claims[0]["reason"])
        self.assertEqual(stats["pass_rate"], 0.0)

    def test_failure_mode_wrong_proposition(self):
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Notice",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with written notice of the Rent Adjustment Program at inception.",
                "repealed": False
            }
        ]
        # Cites real section Section 8.22.030, but asserts an eviction defense proposition not supported by the text
        analysis = "Under Section 8.22.030, a landlord cannot evict without proving substantial damage to the property."
        is_grounded, claims, notice, stats = verify_assertion_grounding(analysis, retrieved_laws)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "wrong_proposition")
        self.assertIn("does not substantiate", claims[0]["reason"].lower())

    def test_failure_mode_stale_law(self):
        retrieved_laws = [
            {
                "id": 2,
                "title": "Repealed Costa-Hawkins Exemption Rule",
                "section": "Section 1947.10",
                "jurisdiction": "California Civil Code",
                "content": "Old residential rules governing rent increase exemptions.",
                "repealed": True,
                "preempted_by": "Tenant Protection Act of 2019"
            }
        ]
        analysis = "Under California Civil Code Section 1947.10, the landlord is entirely exempt from rent controls."
        is_grounded, claims, notice, stats = verify_assertion_grounding(analysis, retrieved_laws)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "stale_law")
        self.assertIn("repealed", claims[0]["reason"].lower())

    def test_supported_assertion_with_span(self):
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with written notice of the Rent Adjustment Program at inception of tenancy.",
                "repealed": False
            }
        ]
        analysis = "Pursuant to Section 8.22.030, landlords must provide tenants with written notice of the Rent Adjustment Program at inception of tenancy."
        is_grounded, claims, notice, stats = verify_assertion_grounding(analysis, retrieved_laws)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["status"], "supported")
        self.assertIsNotNone(claims[0]["source_excerpt"])
        self.assertIn("written notice", claims[0]["source_excerpt"])
        self.assertEqual(stats["pass_rate"], 100.0)

    def test_backward_compatible_verify_citation_grounding(self):
        retrieved_laws = [
            {
                "id": 1,
                "title": "Oakland Rent Adjustment Program",
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "content": "Landlords must provide tenants with notice."
            }
        ]
        grounded_text = "Under Section 8.22.030, landlords must provide tenants with notice."
        is_grounded, ungrounded, notice = verify_citation_grounding(grounded_text, retrieved_laws)
        self.assertTrue(is_grounded)
        self.assertEqual(len(ungrounded), 0)

    def test_embedding_cache_lru_and_stats(self):
        embedding_cache.clear()
        initial_stats = embedding_cache.stats()
        self.assertEqual(initial_stats["hits"], 0)
        self.assertEqual(initial_stats["misses"], 0)
        self.assertEqual(initial_stats["size"], 0)

        # Set and get
        test_model = "test-embed-model"
        test_text = "Landlord notice requirement"
        test_vector = [0.123] * 1024

        self.assertIsNone(embedding_cache.get(test_model, test_text))
        embedding_cache.set(test_model, test_text, test_vector)

        cached = embedding_cache.get(test_model, test_text)
        self.assertEqual(cached, test_vector)

        stats = embedding_cache.stats()
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)


if __name__ == "__main__":
    unittest.main()
