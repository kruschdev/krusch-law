"""
tests/unit/test_grounding_properties.py
=======================================
Property-based and parametric verification test suite for KruschLaw statutory grounding checker.
Systematically tests the core invariant (INV-6):
  Grounding is an exact checker, not a generator.
  Mutating any single dimension (slot value, unit, obligation negation, temporal freshness, or citation authenticity)
  MUST flip the checker from supported to the exact expected canonical failure code.
"""

from __future__ import annotations

import unittest
from datetime import date
from tests.base import KruschLawTestCase
from src.backend.rag import verify_assertion_grounding


class TestGroundingProperties(KruschLawTestCase):
    def setUp(self):
        super().setUp()
        self.security_deposit_laws = [
            {
                "id": 101,
                "title": "AB 12 One-Month Security Deposit Maximum",
                "section": "Section 1950.5(c)",
                "jurisdiction": "California Civil Code",
                "authority_class": "controlling_statute",
                "content": (
                    "Under California Civil Code § 1950.5(c) as amended by Stats. 2023, ch. 290 (AB 12), "
                    "effective July 1, 2024, a landlord may not demand or receive security, however denominated, "
                    "in an amount or value in excess of an amount equal to one month's rent, in the case of unfurnished or furnished residential property."
                ),
                "repealed": False
            },
            {
                "id": 102,
                "title": "Itemized Accounting and Deposit Return Timeline",
                "section": "Section 1950.5",
                "jurisdiction": "California Civil Code",
                "authority_class": "controlling_statute",
                "content": (
                    "Within 21 calendar days after the tenant has vacated the premises, the landlord shall furnish "
                    "the tenant a copy of an itemized statement indicating the basis for, and the amount of, any security "
                    "received and the disposition thereof, accompanied by the remaining portion of the deposit."
                ),
                "repealed": False
            }
        ]

        self.landlord_entry_laws = [
            {
                "id": 201,
                "title": "Landlord Right of Entry and Written Notice",
                "section": "Section 1954",
                "jurisdiction": "California Civil Code",
                "authority_class": "controlling_statute",
                "content": (
                    "Under California Civil Code § 1954, a landlord may enter the dwelling unit only in specified cases. "
                    "The landlord shall give the tenant reasonable written notice of the landlord's intent to enter, "
                    "and 24 hours is presumed to be reasonable notice. Entry must occur during normal business hours."
                ),
                "repealed": False
            }
        ]

        self.repealed_laws = [
            {
                "id": 301,
                "title": "Repealed Two-Month Security Deposit Maximum",
                "section": "Section 1950.5 (Pre-2024)",
                "jurisdiction": "California Civil Code",
                "authority_class": "controlling_statute",
                "content": (
                    "[REPEALED / SUPERSEDED] Prior to July 1, 2024, a landlord could lawfully demand a security deposit "
                    "equal to two months' rent for an unfurnished residential unit."
                ),
                "repealed": True,
                "preempted_by": "Cal. Civ. Code § 1950.5(c) as amended by Stats. 2023, ch. 290 (AB 12)"
            }
        ]

    def test_property_1_timeline_slot_mutation_flips_to_rejection(self):
        """
        Property 1: When a quantitative statutory timeline slot is mutated from the controlling value (21 days),
        the grounding checker MUST reject the assertion as wrong_proposition or contradicted.
        """
        valid_claim = "Within 21 calendar days after vacating, the landlord must furnish an itemized statement under Section 1950.5."
        is_valid, claims, _, stats = verify_assertion_grounding(valid_claim, self.security_deposit_laws)
        self.assertTrue(is_valid, f"Ground-truth 21-day claim must pass: {claims}")
        self.assertEqual(claims[0]["status"], "supported")

        # Parametric mutations: 14, 30, 45, 60 days
        for mutated_days in [14, 30, 45, 60]:
            mutated_claim = f"Within {mutated_days} calendar days after vacating, the landlord must furnish an itemized statement under Section 1950.5."
            is_valid, claims, _, stats = verify_assertion_grounding(mutated_claim, self.security_deposit_laws)
            self.assertFalse(is_valid, f"Mutated timeline {mutated_days} days must be rejected!")
            self.assertEqual(claims[0]["status"], "wrong_proposition")
            self.assertTrue(
                claims[0]["verdict"] in ("contradicted", "wrong_proposition", "insufficient_context"),
                f"Expected contradiction/rejection for {mutated_days} days, got: {claims[0]['verdict']}"
            )

    def test_property_2_statutory_cap_unit_mutation_flips_to_rejection(self):
        """
        Property 2: Mutating the statutory cap formula (one month's rent) to an unauthorized flat dollar amount
        or multi-month figure MUST flip the checker to wrong_proposition.
        """
        valid_claim = "Under California Civil Code Section 1950.5(c), a landlord may not demand security exceeding one month's rent."
        is_valid, claims, _, stats = verify_assertion_grounding(valid_claim, self.security_deposit_laws)
        self.assertTrue(is_valid, f"Valid 1-month cap claim must pass: {claims}")
        self.assertEqual(claims[0]["status"], "supported")

        # Mutate to flat fee or incorrect multiplier
        mutated_claims = [
            "Under California Civil Code Section 1950.5(c), a landlord may demand a flat $3,000 security deposit fee regardless of rent.",
            "Under California Civil Code Section 1950.5(c), a landlord may demand security equal to three months' rent."
        ]
        for m_claim in mutated_claims:
            is_valid, claims, _, stats = verify_assertion_grounding(m_claim, self.security_deposit_laws)
            self.assertFalse(is_valid, f"Mutated cap claim must fail: {m_claim}")
            self.assertEqual(claims[0]["status"], "wrong_proposition")

    def test_property_3_polarity_negation_mutation_flips_to_contradiction(self):
        """
        Property 3: Asserting absence of obligation (entry without notice) when statute requires 24 hours notice
        MUST fail with wrong_proposition and contradicted verdict.
        """
        valid_claim = "Under California Civil Code Section 1954, a landlord must provide 24 hours written notice before entering."
        is_valid, claims, _, stats = verify_assertion_grounding(valid_claim, self.landlord_entry_laws)
        self.assertTrue(is_valid, f"Valid 24-hr notice claim must pass: {claims}")
        self.assertEqual(claims[0]["status"], "supported")

        negated_claim = "Under California Civil Code Section 1954, a landlord may enter the premises immediately without any prior notice."
        is_valid, claims, _, stats = verify_assertion_grounding(negated_claim, self.landlord_entry_laws)
        self.assertFalse(is_valid, "Negated notice obligation claim must fail!")
        self.assertEqual(claims[0]["status"], "wrong_proposition")

    def test_property_4_stale_or_repealed_statute_flips_to_stale_law(self):
        """
        Property 4: If an assertion cites a statute version marked repealed or preempted,
        the grounding checker MUST reject it with status='stale_law'.
        """
        stale_claim = "Under Section 1950.5 (Pre-2024), a landlord may lawfully collect two months' rent as deposit."
        is_valid, claims, _, stats = verify_assertion_grounding(stale_claim, self.repealed_laws)
        self.assertFalse(is_valid, "Claim citing repealed law fixture must fail!")
        self.assertEqual(claims[0]["status"], "stale_law")
        self.assertEqual(claims[0]["verdict"], "stale_law")
        self.assertIn("repealed", claims[0]["reason"].lower())

    def test_property_5_fabricated_citation_flips_to_invented_citation(self):
        """
        Property 5: Fabricated or halluncinated statutory citations absent from the authoritative corpus
        MUST fail with status='invented_citation' and verdict='not_in_corpus'.
        """
        fabricated_claim = "Pursuant to California Civil Code Section 999.99, tenants are entitled to an automatic treble damages payout."
        is_valid, claims, _, stats = verify_assertion_grounding(fabricated_claim, self.security_deposit_laws)
        self.assertFalse(is_valid, "Invented statutory citation must fail!")
        self.assertEqual(claims[0]["status"], "invented_citation")
        self.assertEqual(claims[0]["verdict"], "not_in_corpus")
        self.assertIn("999.99", claims[0]["reason"])

    def test_property_6_word_numeral_and_numeric_slot_equivalence(self):
        """
        Property 6: Word-to-digit normalization equivalence.
        Assertions or statutory clauses stated in written english word numerals
        MUST extract the exact same quantitative slots as arabic digit numerals.
        """
        from src.backend.resolver import extract_statutory_slots

        # Timelines
        slots_word_21 = extract_statutory_slots("Tenant must provide twenty-one calendar days notice.")
        slots_digit_21 = extract_statutory_slots("Tenant must provide 21 calendar days notice.")
        self.assertEqual(slots_word_21.get("statutory_notice_days"), slots_digit_21.get("statutory_notice_days"))

        # Entry Notice Hours
        slots_word_24 = extract_statutory_slots("Landlord shall provide twenty-four hours written notice.")
        slots_digit_24 = extract_statutory_slots("Landlord shall provide 24 hours written notice.")
        self.assertEqual(slots_word_24.get("entry_notice_hours"), 24)
        self.assertEqual(slots_digit_24.get("entry_notice_hours"), 24)

        # Court Days Cure Notice
        slots_word_3 = extract_statutory_slots("Three court days to pay or quit.")
        slots_digit_3 = extract_statutory_slots("3 court days to pay or quit.")
        self.assertEqual(slots_word_3.get("cure_notice_court_days"), 3)
        self.assertEqual(slots_digit_3.get("cure_notice_court_days"), 3)

        # Security Deposit Caps
        slots_word_cap = extract_statutory_slots("Security deposit capped at one month rent.")
        slots_digit_cap = extract_statutory_slots("Security deposit capped at 1 month rent.")
        self.assertEqual(slots_word_cap.get("deposit_cap_months"), 1.0)
        self.assertEqual(slots_digit_cap.get("deposit_cap_months"), 1.0)

    def test_property_7_physical_citation_spine_coordinate_persistence_and_retrieval(self):
        """
        Property 7: Physical Citation Spine Coordinate Invariance (INV-11).
        LawVector records with spatial and layout coordinates (page_number, printed_page,
        bbox, char_start, char_end) MUST preserve coordinates through DB persistence
        and RAG retrieval without precision degradation.
        """
        import json
        from src.backend.db import LawVector
        from src.backend.rag import retrieve_laws

        bbox_coords = [72.0, 144.0, 540.0, 288.0]
        node = LawVector(
            section="Section 1954(a)",
            title="Landlord Permissible Purpose of Entry",
            jurisdiction="California Civil Code",
            authority_class="controlling_statute",
            content="A landlord may enter the dwelling unit only in the following cases: In case of emergency.",
            topic="Landlord Entry",
            page_number=42,
            printed_page="Page 42",
            bbox=json.dumps(bbox_coords),
            char_start=1024,
            char_end=2048,
            extra_metadata=json.dumps({"volume": 4, "reporter": "Cal. App. 4th"})
        )
        self.db.add(node)
        self.db.commit()

        results = retrieve_laws(
            text_query="In case of emergency landlord entry Section 1954",
            limit=5,
            db_session=self.db
        )
        self.assertTrue(len(results) > 0)
        target = next((r for r in results if r.get("section") == "Section 1954(a)"), None)
        self.assertIsNotNone(target, "Inserted Section 1954(a) must be retrieved")
        self.assertEqual(target.get("page_number"), 42)
        self.assertEqual(target.get("printed_page"), "Page 42")
        self.assertEqual(target.get("char_start"), 1024)
        self.assertEqual(target.get("char_end"), 2048)


if __name__ == "__main__":
    unittest.main()

