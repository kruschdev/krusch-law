import os
from datetime import date
from tests.base import KruschLawTestCase
from src.backend.db import LawVector
from src.backend.ingest import ingest_mock_data
from src.backend.resolver import (
    resolve_controlling_law,
    explain_why_not_controlling,
    ResolutionTrace,
    CoverageHole,
    ResolutionHop
)


class TestResolutionTrace(KruschLawTestCase):
    """Unit and integration tests for resolution traces, coverage holes, and explain_why_not_controlling."""

    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_resolution_trace_structure(self):
        # Pre-AB 12 date: 2024-05-01
        res_old = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            city="Oakland",
            as_of_date="2024-05-01",
            db=self.db
        )
        self.assertIsNotNone(res_old.trace)
        self.assertIsInstance(res_old.trace, ResolutionTrace)
        self.assertGreater(len(res_old.trace.hops), 0)
        self.assertIn("1950.5", res_old.governing_citation)
        self.assertIn("deposit_cap_months", res_old.statutory_slots)

        # Post-AB 12 date: 2024-08-01
        res_new = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            city="Oakland",
            as_of_date="2024-08-01",
            db=self.db
        )
        self.assertIsNotNone(res_new.trace)
        self.assertIn("1950.5", res_new.governing_citation)
        self.assertEqual(res_new.statutory_slots.get("deposit_cap_months"), 1.0)

        # Check hops
        hop_types = [h.hop_type for h in res_new.trace.hops]
        self.assertIn("TERMINAL", hop_types)

    def test_coverage_hole_unindexed_topic(self):
        res = resolve_controlling_law(
            doctrine_or_topic="Maritime Admiralty Liens",
            city="Oakland",
            db=self.db
        )
        self.assertTrue(res.is_coverage_hole)
        self.assertIsNotNone(res.coverage_hole)
        self.assertIsInstance(res.coverage_hole, CoverageHole)
        self.assertEqual(res.coverage_hole.doctrine, "Maritime Admiralty Liens")
        self.assertIn("No authority found", res.governing_citation)

    def test_explain_why_not_controlling(self):
        # As of Aug 2024, Cal. Civ. Code § 1950.5 (Pre-AB 12) is NOT controlling (superseded by AB 12)
        explanation = explain_why_not_controlling(
            citation="Cal. Civ. Code § 1950.5 (Pre-2024)",
            doctrine_or_topic="Security Deposits",
            as_of_date="2024-08-01",
            city="Oakland",
            db=self.db
        )
        self.assertFalse(explanation["is_controlling"])
        self.assertIn("1950.5", explanation["controlling_authority"])
        self.assertGreater(len(explanation["reasons"]), 0)

        # As of Aug 2024, Section 1950.5 IS controlling
        ctrl_explanation = explain_why_not_controlling(
            citation="Section 1950.5",
            doctrine_or_topic="Security Deposits",
            as_of_date="2024-08-01",
            city="Oakland",
            db=self.db
        )
        self.assertTrue(ctrl_explanation["is_controlling"])

    def test_api_explain_why_not_endpoint(self):
        resp = self.client.get(
            "/api/resolver/explain-why-not",
            params={
                "citation": "Cal. Civ. Code § 1950.5 (Pre-AB 12)",
                "doctrine": "Security Deposits",
                "as_of_date": "2024-08-01",
                "city": "Oakland"
            }
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["citation"], "Cal. Civ. Code § 1950.5 (Pre-AB 12)")
        self.assertFalse(data["is_controlling"])
        self.assertIn("reasons", data)

    def test_api_search_with_as_of_date(self):
        resp = self.client.get(
            "/api/laws",
            params={
                "q": "security deposit limit",
                "as_of_date": "2024-08-01",
                "city": "Oakland"
            }
        )
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        self.assertGreater(len(results), 0)
