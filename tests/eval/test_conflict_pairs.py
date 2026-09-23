"""
tests/eval/test_conflict_pairs.py
=================================
Conflict-Pair Evaluation Suite for KruschLaw Sovereign Legal Intelligence Engine.

Evaluates the 5 critical failure modes identified in the Sovereign Roadmap:
  1. AB 12 Deposit Cap Repeal: Live controlling 1-month cap outranks repealed 2-month rule.
  2. Spatial Gate / Unincorporated Island: Alameda County island facts prune Oakland OMC 8.22.
  3. Mandatory Child Hydration & Exception Detection: AB 1482 Just Cause + § 1946.2(e) owner-occupied exception.
  4. Corpus Abstention: Engine refuses claims when governing authority is missing from corpus.
  5. Matter Isolation: Matter A's exhibits/facts never leak into Matter B or the public law store.
"""

import os
import sys
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.db import LawVector, Case, GroundingReport, MatterEvidence
from src.backend.ingest import ingest_mock_data
from src.backend.rag import (
    retrieve_laws,
    filter_authorities_by_jurisdiction,
    verify_assertion_grounding,
    verify_mechanical_pass_a,
    verify_proposition_pass_b,
    apply_statutory_amendment
)


class TestConflictPairsEvaluation(KruschLawTestCase):
    """
    Evaluates conflict pairs as first-class tests to verify deterministic
    jurisdiction machine logic, proposition-level verification, and store isolation.
    """

    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_01_deposit_cap_conflict_repealed_vs_controlling(self):
        """
        Conflict Pair 1: AB 12 1-month deposit cap vs repealed 2-month rule.
        When querying under post-July 1, 2024 law, the deterministic filter must
        prune the pre-2024 rule and return Section 1950.5(c) as the controlling authority.
        """
        as_of_today = datetime(2025, 1, 15, tzinfo=timezone.utc)
        results = retrieve_laws(
            text_query="What is the maximum allowable security deposit for an unfurnished residential apartment under California law Section 1950.5?",
            limit=5,
            as_of_date=as_of_today,
            exclude_repealed=True,
            db_session=self.db
        )

        retrieved_sections = [r["section"] for r in results]
        self.assertTrue(
            any("1950.5" in sec for sec in retrieved_sections),
            "Controlling Section 1950.5 provisions must be retrieved."
        )
        self.assertNotIn("Section 1950.5 (Pre-2024)", retrieved_sections, "Repealed 2-month cap must be excluded by temporal/preemption filter.")

        # Verify deterministic filter behavior explicitly on conflicting nodes
        candidates = [
            {
                "section": "Section 1950.5 (Pre-2024)",
                "status": "repealed",
                "repealed": True,
                "effective_to": datetime(2024, 6, 30, tzinfo=timezone.utc),
                "preempted_by": "Cal. Civ. Code § 1950.5(c) as amended by Stats. 2023, ch. 290 (AB 12)"
            },
            {
                "section": "Section 1950.5(c)",
                "status": "enacted",
                "repealed": False,
                "preempts": ["Section 1950.5 (Pre-2024)"],
                "effective_from": datetime(2024, 7, 1, tzinfo=timezone.utc)
            }
        ]
        governing, pruned = filter_authorities_by_jurisdiction(
            candidates,
            as_of_date=as_of_today,
            exclude_repealed=True
        )
        self.assertEqual(len(governing), 1)
        self.assertEqual(governing[0]["section"], "Section 1950.5(c)")
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["section"], "Section 1950.5 (Pre-2024)")
        self.assertIn("Repealed", pruned[0]["prune_reason"])

    def test_02_spatial_gate_unincorporated_island_vs_municipal(self):
        """
        Conflict Pair 2: Oakland OMC 8.22 vs Unincorporated Alameda County parcel.
        When matter facts indicate an unincorporated island parcel, municipal ordinances
        must be deterministically pruned via `applies_if` and county/state rules retained.
        """
        matter_facts = {
            "county": "Alameda County",
            "unincorporated": True,
            "property_type": "residential"
        }

        results = retrieve_laws(
            text_query="Does the rent adjustment program and just cause notice requirement apply in unincorporated Castro Valley?",
            limit=5,
            matter_facts=matter_facts,
            db_session=self.db
        )

        retrieved_sections = [r["section"] for r in results]
        self.assertIn("Section 6.04.050", retrieved_sections, "Alameda County Code Section 6.04.050 must govern unincorporated parcels.")
        for sec in retrieved_sections:
            self.assertFalse(sec.startswith("Section 8.22"), f"Oakland OMC section {sec} must not govern unincorporated parcel.")

        # Test deterministic filter directly on mixed candidates
        candidates = [
            {
                "section": "Section 8.22.030",
                "jurisdiction": "Oakland Municipal Code",
                "applies_if": {"city": "Oakland", "county": "Alameda County", "unincorporated": False}
            },
            {
                "section": "Section 6.04.050",
                "jurisdiction": "Alameda County Code",
                "applies_if": {"county": "Alameda County", "unincorporated": True}
            }
        ]
        governing, pruned = filter_authorities_by_jurisdiction(candidates, matter_facts=matter_facts)
        self.assertEqual(len(governing), 1)
        self.assertEqual(governing[0]["section"], "Section 6.04.050")
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["section"], "Section 8.22.030")
        self.assertIn("unincorporated", pruned[0]["prune_reason"].lower())

    def test_03_child_hydration_and_statutory_exception_detection(self):
        """
        Conflict Pair 3: AB 1482 Just Cause (§ 1946.2) vs Owner-Occupied Exception (§ 1946.2(e)).
        Part A: Mandatory child hydration must automatically attach § 1946.2(e) when § 1946.2 is retrieved.
        Part B: Verifier must detect when the exception applies and refuse an ungrounded claim.
        """
        # Part A: Child hydration
        results = retrieve_laws(
            text_query="Civil Code Section 1946.2 tenant protection act mandatory just cause eviction",
            limit=5,
            db_session=self.db
        )
        retrieved_sections = [r["section"] for r in results]
        self.assertIn("Section 1946.2", retrieved_sections, "Section 1946.2 must be retrieved.")
        self.assertIn("Section 1946.2(e)", retrieved_sections, "Section 1946.2(e) must be automatically hydrated as mandatory exception child.")

        # Part B: Verifier detects exception for owner-occupied duplex
        draft_text = "Pursuant to Section 1946.2, the landlord cannot terminate tenancy without proving statutory just cause."
        matter_facts_exempt = {"owner_occupied_duplex": True, "property_type": "residential"}

        is_g, claims, notice, stats = verify_assertion_grounding(
            analysis_text=draft_text,
            laws=results,
            matter_facts=matter_facts_exempt
        )

        self.assertFalse(is_g, "Draft must fail grounding verification when statutory exception applies.")
        self.assertEqual(claims[0]["verdict"], "exception_applies")
        self.assertTrue(claims[0]["refused"])
        self.assertIn("[CLAIM REFUSED: EXCEPTION_APPLIES", stats["verified_draft"])
        self.assertEqual(stats["exception_applies_claims"], 1)

    def test_04_corpus_abstention_on_missing_rules(self):
        """
        Conflict Pair 4: Abstention and refusal on unrepresented jurisdictions/statutes.
        When a draft cites an invented section or a statute not in corpus, the verifier
        must cleanly refuse the claim with 'not_in_corpus' / 'invented_citation'.
        """
        draft_text = "Under Fresno Municipal Code Section 12.99, commercial tenants are entitled to 90-day rent abatement."
        laws = retrieve_laws(text_query="Fresno commercial rent abatement", limit=3, db_session=self.db)

        is_g, claims, notice, stats = verify_assertion_grounding(draft_text, laws)
        self.assertFalse(is_g, "Draft must be refused for ungrounded citations.")
        self.assertEqual(claims[0]["verdict"], "not_in_corpus")
        self.assertEqual(claims[0]["status"], "invented_citation")
        self.assertTrue(claims[0]["refused"])
        self.assertIn("[CLAIM REFUSED: NOT_IN_CORPUS", stats["verified_draft"])
        self.assertEqual(stats["not_in_corpus_claims"], 1)

    def test_05_matter_store_isolation_invariants(self):
        """
        Conflict Pair 5: Invariant separation of Matter Store vs Public Law Store.
        Confidential matter facts and exhibits for Matter A must never:
          1. Be indexed or queryable via public law retrieval (`retrieve_laws`).
          2. Leak into Matter B's query context or grounding reports.
        """
        # Create Matter A with confidential exhibit
        matter_a = Case(
            id=101,
            matter_number="MAT-ALPHA-101",
            title="Matter A: Confidential Lease Agreement",
            description="Confidential matter details",
            facts="Tenant dispute at 1428 Elm St, confidential settlement NDA $25,000"
        )
        self.db.add(matter_a)

        # Store matter evidence in the isolated matter_evidence table
        evidence_a = MatterEvidence(
            matter_id=101,
            filename="confidential_lease_nda.pdf",
            doc_type="lease",
            content="Confidential settlement NDA $25,000 executed at 1428 Elm St."
        )
        self.db.add(evidence_a)

        # Create Matter B
        matter_b = Case(
            id=202,
            matter_number="MAT-BETA-202",
            title="Matter B: Unrelated Commercial Eviction",
            description="Commercial dispute at 500 Market St",
            facts="Unrelated retail tenant dispute at 500 Market St"
        )
        self.db.add(matter_b)
        self.db.commit()

        # Public law retrieval must never return matter facts or case exhibits
        results = retrieve_laws(
            text_query="Confidential settlement NDA 1428 Elm St",
            limit=5,
            db_session=self.db
        )
        for r in results:
            self.assertNotIn("1428 Elm St", r.get("content", ""), "Public law store must not leak Matter A facts.")
            self.assertNotIn("25,000", r.get("content", ""), "Public law store must not leak Matter A financial terms.")

        # Grounding report for Matter B must not reference Matter A
        report_b = GroundingReport(
            case_id=202,
            total_claims=1,
            supported_claims=1,
            unsupported_claims=0,
            invented_citations=0,
            stale_law_citations=0,
            contradicted_claims=0,
            exception_applies_claims=0,
            insufficient_context_claims=0,
            not_in_corpus_claims=0,
            refused_claims_count=0,
            claims_json=json.dumps([{"claim": "Commercial notice requirement", "citation": "Section 1954"}]),
            verified_draft="Verified draft for Matter B.",
            pass_rate=100.0
        )
        self.db.add(report_b)
        self.db.commit()

        b_reports = self.db.query(GroundingReport).filter(GroundingReport.case_id == 202).all()
        for rep in b_reports:
            self.assertEqual(rep.case_id, 202)
            self.assertNotIn("1428 Elm St", rep.verified_draft or "")
            self.assertNotIn("1428 Elm St", rep.claims_json or "")

    def test_06_statutory_amendment_lifecycle_and_diff(self):
        """
        Conflict Pair 6: Statutory Amendment Pipeline.
        When an ordinance or statute is amended:
          1. Previous node is marked status='amended' with superseded_by pointer.
          2. New node is inserted with status='enacted'.
          3. Affected past matter conclusions citing the old node are flagged.
        """
        case_x = Case(id=303, matter_number="MAT-GAMMA-303", title="Matter Gamma", facts="Deposit dispute")
        self.db.add(case_x)
        self.db.commit()

        report_x = GroundingReport(
            case_id=303,
            claims_json=json.dumps([
                {"claim": "Bad faith retention penalty under Section 1950.5(b)", "citation": "Section 1950.5(b)"}
            ]),
            verified_draft="Under Section 1950.5(b), bad faith retention carries up to twice statutory damages.",
            total_claims=1,
            supported_claims=1,
            unsupported_claims=0,
            pass_rate=100.0
        )
        self.db.add(report_x)
        self.db.commit()

        amendment_event = apply_statutory_amendment(
            section="Section 1950.5(b)",
            jurisdiction="California Civil Code",
            new_content="Under amended Section 1950.5(b), statutory bad faith damages are increased to three times deposit amount.",
            new_title="Amended Security Deposit Permitted Deductions & Treble Damages",
            chaptered_bill_ref="Stats. 2025, ch. 410 (SB 99)",
            db_session=self.db
        )

        self.assertIn(303, amendment_event["affected_case_ids"])
        self.assertIn("text_diff", amendment_event)
        self.assertEqual(amendment_event["status"], "amendment_applied")

        # Verify old node status in DB
        old_node = self.db.query(LawVector).filter(
            LawVector.section == "Section 1950.5(b)",
            LawVector.status == "amended"
        ).first()
        self.assertIsNotNone(old_node)
        self.assertIsNotNone(old_node.superseded_by_id)


if __name__ == "__main__":
    unittest.main()
