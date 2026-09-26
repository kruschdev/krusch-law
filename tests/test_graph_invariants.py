"""
tests/test_graph_invariants.py
==============================
Deterministic pass/fail tests enforcing the core graph and precedence invariants of KruschLaw:
  - INV-1: Confirmed-Edge Only Precedence (proposed edges never silently control)
  - INV-2: Temporal As-Of Date Validity (pre-amendment vs post-amendment controlling law)
  - INV-3: Preemption DAG Hierarchy & Cycle Fail-Closed
  - INV-4: No Silent Keyword Promotion (honest CoverageHole over arbitrary content substring fallback)
  - Relation check constraints (preventing self-referential relations and invalid types)
"""

import os
import sys
import unittest
from datetime import date, datetime, timezone
from sqlalchemy.exc import IntegrityError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.db import LawVector, StatuteRelation
from src.backend.ingest import ingest_mock_data
from src.backend.resolver import resolve_controlling_law


class TestGraphInvariants(KruschLawTestCase):

    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_01_confirmed_edge_invariant(self):
        """
        INV-1: Proposed / unconfirmed relations must never silently alter controlling law.
        They must emit high-visibility uncertainty warnings until confirmed by admitted counsel.
        """
        # Create a proposed preemption relation
        prop_rel = StatuteRelation(
            source_statute="Cal. Civ. Code § 1954.50",
            target_statute="Oakland Municipal Code Section 8.22.030",
            relation_type="PREEMPTS",
            scope_topic="Rent Control",
            confidence=0.85,
            status="proposed"
        )
        self.db.add(prop_rel)
        self.db.commit()

        # Resolver detects proposed relation and warns counsel
        res = resolve_controlling_law(
            doctrine_or_topic="Rent Control",
            city="Oakland",
            as_of_date=date(2024, 8, 1),
            db=self.db
        )
        self.assertIsNotNone(res.uncertainty_warning)
        self.assertIn("CONTROLLING STATUTE UNCERTAIN", res.uncertainty_warning)
        self.assertEqual(len(res.unconfirmed_proposals), 1)

        # Confirm the edge
        prop_rel.status = "confirmed"
        prop_rel.reviewed_by = "attorney:krusch"
        self.db.commit()

        # After confirmation, uncertainty warning is cleared
        res_confirmed = resolve_controlling_law(
            doctrine_or_topic="Rent Control",
            city="Oakland",
            as_of_date=date(2024, 8, 1),
            db=self.db
        )
        self.assertIsNone(res_confirmed.uncertainty_warning)
        self.assertEqual(len(res_confirmed.unconfirmed_proposals), 0)

    def test_02_temporal_amendment_gating_invariant(self):
        """
        INV-2: The statutory graph walk MUST evaluate law strictly as of the inquiry date.
        Pre-July 1, 2024 -> 2-month cap (§ 1950.5 historical).
        Post-July 1, 2024 -> 1-month cap (AB 12 Stats. 2023, ch. 290).
        """
        # Pre-AB 12 inquiry
        res_pre = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date=date(2024, 1, 1),
            db=self.db
        )
        self.assertEqual(res_pre.statutory_slots.get("deposit_cap_months"), 2.0)
        self.assertIn("1950.5", res_pre.governing_citation)

        # Post-AB 12 inquiry
        res_post = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date=date(2024, 8, 15),
            db=self.db
        )
        self.assertEqual(res_post.statutory_slots.get("deposit_cap_months"), 1.0)
        self.assertIn("1950.5", res_post.governing_citation)


    def test_03_cycle_detection_fail_closed(self):
        """
        INV-3: Circular preemption or amendment loops (A -> B -> C -> A) must terminate
        safely within depth_cap without recursion crashes.
        """
        res = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date=date(2024, 8, 1),
            db=self.db,
            depth_cap=5
        )
        self.assertIsNotNone(res)
        self.assertIsNotNone(res.trace)
        self.assertLessEqual(len(res.trace.hops), 5)

    def test_04_no_silent_keyword_promotion(self):
        """
        INV-4: Controlling authority selection is an authority hierarchy and DAG walk,
        NEVER a lexical or content substring match.
        Unindexed/uncovered topics MUST return an explicit CoverageHole rather than
        promoting an arbitrary statute whose content mentions the keyword.
        """
        res = resolve_controlling_law(
            doctrine_or_topic="NonExistentDoctrineMaritimeSalvage",
            city="Oakland",
            as_of_date=date(2024, 8, 1),
            db=self.db
        )
        self.assertTrue(res.is_coverage_hole)
        self.assertIsNotNone(res.coverage_hole)
        self.assertIn("No controlling section found", res.coverage_hole.reason)
        self.assertIn("Zero matching statutory sections", res.trace.hops[0].reason)
        self.assertEqual(res.confidence_score, 0.0)

    def test_05_statute_relation_database_check_constraints(self):
        """
        Enforce DB-level check constraints:
          1. Self-referential relations (source == target) must fail.
          2. Invalid relation types must fail.
          3. Invalid status values must fail.
        """
        # 1. Self-referential relation fails
        bad_self = StatuteRelation(
            source_statute="Cal. Civ. Code § 1950.5",
            target_statute="Cal. Civ. Code § 1950.5",
            relation_type="PREEMPTS",
            status="proposed"
        )
        self.db.add(bad_self)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

        # 2. Invalid relation type fails
        bad_type = StatuteRelation(
            source_statute="Statute A",
            target_statute="Statute B",
            relation_type="INVALID_TYPE_XYZ",
            status="proposed"
        )
        self.db.add(bad_type)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

        # 3. Invalid status fails
        bad_status = StatuteRelation(
            source_statute="Statute A",
            target_statute="Statute B",
            relation_type="PREEMPTS",
            status="invalid_status_xyz"
        )
        self.db.add(bad_status)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
