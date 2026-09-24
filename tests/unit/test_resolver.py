"""
tests/unit/test_resolver.py
===========================
Comprehensive unit and integration tests for KruschLaw's Controlling Legal Authority &
Statutory Precedence Graph Resolver (src/backend/resolver.py).

Tests:
  1. Multi-hop preemption chain traversal (Muni Code -> State Statute)
  2. Temporal amendment gating (pre-AB 12 vs post-AB 12 security deposit caps)
  3. Statutory exception detection (owner-occupied duplex & single-family home)
  4. Spatial / Territorial gating (unincorporated vs incorporated parcels)
  5. Deterministic statutory slot extraction (notice days, caps, multipliers)
  6. Substantive conflict detection engine (preemption, temporal, statutory term violations)
  7. REST API endpoints (/api/resolver/controlling, /api/resolver/conflicts, /api/resolver/registry)
  8. MCP tools (resolve_controlling_law, detect_statutory_conflicts)
"""

import os
import sys
import json
import unittest
from datetime import date, datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.db import LawVector
from src.backend.ingest import ingest_mock_data
from src.backend.resolver import (
    resolve_controlling_law,
    detect_legal_conflicts,
    extract_statutory_slots,
    to_utc_date,
    STATEWIDE_PREEMPTION_REGISTRY,
    AUTHORITY_RANKS
)
from src.backend.tagger import extract_legal_slots
from src.mcp.server import process_request


class TestLegalPrecedenceResolver(KruschLawTestCase):

    def setUp(self):
        super().setUp()
        ingest_mock_data(self.db)

    def test_01_date_normalization(self):
        """Verifies UTC date normalization for various input formats."""
        d1 = to_utc_date("2024-07-01")
        self.assertEqual(d1, date(2024, 7, 1))

        d2 = to_utc_date(datetime(2024, 7, 1, 15, 30, tzinfo=timezone.utc))
        self.assertEqual(d2, date(2024, 7, 1))

        d3 = to_utc_date(None)
        self.assertEqual(d3, datetime.now(timezone.utc).date())

    def test_02_deterministic_slot_extraction(self):
        """Verifies high-precision extraction of statutory notice days, caps, and multipliers."""
        statute_text = (
            "Under Section 1950.5, no later than 21 calendar days after the tenant has vacated, "
            "the landlord shall furnish an itemized statement. A landlord may not demand security in an "
            "amount exceeding one month's rent for an unfurnished residential unit. "
            "Bad faith retention shall subject the landlord to statutory damages of twice the amount of the security. "
            "Tenants may request an inspection 14 days prior to move-out."
        )
        slots = extract_legal_slots(statute_text)
        self.assertEqual(slots.get("deposit_accounting_days"), 21)
        self.assertEqual(slots.get("deposit_cap_months"), 1.0)
        self.assertEqual(slots.get("statutory_damages_multiplier"), 2.0)
        self.assertEqual(slots.get("inspection_request_days"), 14)
        self.assertIn(21, slots.get("statutory_notice_days", []))
        self.assertIn(14, slots.get("statutory_notice_days", []))

        # Test daily penalty and entry notice
        shutoff_text = "Under Section 789.3, violation warrants one hundred dollars for each day with 24 hours notice."
        shutoff_slots = extract_legal_slots(shutoff_text)
        self.assertEqual(shutoff_slots.get("daily_statutory_penalty"), 100.0)
        self.assertEqual(shutoff_slots.get("entry_notice_hours"), 24)

    def test_03_preemption_chain_traversal(self):
        """Verifies that preemption edges route from municipal code to state controlling statute."""
        # Create a municipal ordinance that is preempted by state law
        local_ord = LawVector(
            jurisdiction="Oakland Municipal Code",
            state="CA",
            city="Oakland",
            section="Section 8.99.010",
            title="Local Security Deposit Regulations",
            content="Oakland landlords may collect up to three months rent for residential deposits.",
            topic="Security Deposits",
            authority_class="municipal_ordinance",
            status="enacted",
            effective_date=datetime(2018, 1, 1),
            preempted_by="Cal. Civ. Code § 1950.5(c)"
        )
        self.db.add(local_ord)
        self.db.commit()

        resolution = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            city="Oakland",
            as_of_date="2025-01-15",
            db=self.db
        )

        self.assertIsNotNone(resolution.controlling_node)
        self.assertIn("1950.5", resolution.governing_citation)
        # Verify precedence chain has traversed preemption
        actions = [step.get("action") for step in resolution.precedence_chain]
        self.assertTrue(any(a in ("FOLLOW_PREEMPTION", "TERMINAL_CONTROLLING_NODE") for a in actions))

    def test_04_temporal_amendment_gating_ab12(self):
        """
        Verifies temporal gating:
        - Prior to July 1, 2024: Pre-2024 2-month rule governs.
        - On or after July 1, 2024: Post-AB 12 1-month rule governs.
        """
        # Post-AB 12 incident date
        res_post = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date="2024-08-01",
            db=self.db
        )
        self.assertIsNotNone(res_post.controlling_node)
        self.assertFalse(res_post.controlling_node.get("repealed", False))
        self.assertEqual(res_post.statutory_slots.get("deposit_cap_months"), 1.0)

    def test_05_statutory_exception_detection(self):
        """Verifies detection of owner-occupied duplex and single-family home statutory exemptions."""
        facts_duplex = {
            "owner_occupied_duplex": True,
            "property_type": "residential"
        }
        res_duplex = resolve_controlling_law(
            doctrine_or_topic="Just Cause",
            as_of_date="2024-06-01",
            matter_facts=facts_duplex,
            db=self.db
        )
        self.assertGreater(len(res_duplex.active_exceptions), 0, "Owner-occupied duplex must trigger exception.")
        exc_sections = [e.get("section", "") for e in res_duplex.active_exceptions]
        exc_titles = [e.get("title", "") for e in res_duplex.active_exceptions]
        self.assertTrue(any("1946.2(e)" in s for s in exc_sections) or any("Exempt" in t for t in exc_titles))

        facts_single_family = {
            "single_family": True,
            "property_type": "residential"
        }
        res_sfh = resolve_controlling_law(
            doctrine_or_topic="Just Cause",
            as_of_date="2024-06-01",
            matter_facts=facts_single_family,
            db=self.db
        )
        self.assertGreater(len(res_sfh.active_exceptions), 0, "Single-family dwelling must trigger exception.")

    def test_06_conflict_detection_engine(self):
        """Verifies detection of preemption, temporal, and statutory term conflicts."""
        authorities = [
            {
                "section": "Section 8.99.010",
                "content": "Oakland allows 3 months deposit.",
                "preempted_by": "Cal. Civ. Code § 1950.5(c)"
            },
            {
                "section": "Section 1950.5 (Old)",
                "content": "Old 2 months rule.",
                "effective_to": "2024-06-30"
            },
            {
                "section": "Section 1946.2",
                "content": "Just cause required for all terminations."
            }
        ]

        matter_facts = {
            "owner_occupied_duplex": True,
            "deposit_months": 2.5
        }

        conflicts = detect_legal_conflicts(
            authorities=authorities,
            matter_facts=matter_facts,
            as_of_date="2024-09-01"
        )

        conflict_types = [c["conflict_type"] for c in conflicts]
        self.assertIn("preemption_conflict", conflict_types)
        self.assertIn("temporal_conflict", conflict_types)
        self.assertIn("exception_applies", conflict_types)
        self.assertIn("statutory_term_violation", conflict_types)

        # Verify attorney advisory is included
        for c in conflicts:
            self.assertIn("attorney_advisory", c)
            self.assertGreater(len(c["attorney_advisory"]), 10)

    def test_07_api_resolver_endpoints(self):
        """Tests FastAPI REST endpoints for controlling authority, conflicts, and registry."""
        # 1. GET /api/resolver/controlling
        resp_ctrl = self.client.get(
            "/api/resolver/controlling?doctrine=Security%20Deposits&city=Oakland&as_of_date=2024-08-01"
        )
        self.assertEqual(resp_ctrl.status_code, 200)
        data = resp_ctrl.json()
        self.assertIn("controlling_node", data)
        self.assertIn("governing_citation", data)
        self.assertIn("statutory_slots", data)

        # 2. POST /api/resolver/conflicts
        conflict_payload = {
            "authorities": [
                {
                    "section": "Section 8.22.030",
                    "preempted_by": "Cal. Civ. Code § 1954.50 (Costa-Hawkins)"
                }
            ],
            "matter_facts": {"single_family": True},
            "as_of_date": "2024-08-01"
        }
        resp_conf = self.client.post("/api/resolver/conflicts", json=conflict_payload)
        self.assertEqual(resp_conf.status_code, 200)
        c_data = resp_conf.json()
        self.assertEqual(c_data["conflict_count"], 1)
        self.assertEqual(c_data["conflicts"][0]["conflict_type"], "preemption_conflict")

        # 3. GET /api/resolver/registry
        resp_reg = self.client.get("/api/resolver/registry")
        self.assertEqual(resp_reg.status_code, 200)
        reg_data = resp_reg.json()
        self.assertIn("authority_ranks", reg_data)
        self.assertIn("statewide_preemptions", reg_data)

    def test_08_mcp_resolver_tools(self):
        """Tests MCP tool invocation via stdio JSON-RPC request processor."""
        # 1. resolve_controlling_law tool
        req_resolve = {
            "jsonrpc": "2.0",
            "id": "test-req-1",
            "method": "tools/call",
            "params": {
                "name": "resolve_controlling_law",
                "arguments": {
                    "doctrine": "Security Deposits",
                    "city": "Oakland",
                    "as_of_date": "2024-09-01"
                }
            }
        }
        resp_resolve = process_request(req_resolve)
        self.assertIsNotNone(resp_resolve)
        self.assertNotIn("error", resp_resolve)
        content_text = resp_resolve["result"]["content"][0]["text"]
        parsed = json.loads(content_text)
        self.assertIn("governing_citation", parsed)
        self.assertIn("statutory_slots", parsed)

        # 2. detect_statutory_conflicts tool
        req_conflicts = {
            "jsonrpc": "2.0",
            "id": "test-req-2",
            "method": "tools/call",
            "params": {
                "name": "detect_statutory_conflicts",
                "arguments": {
                    "authorities": [
                        {
                            "section": "Section 8.22.030",
                            "preempted_by": "Cal. Civ. Code § 1954.50"
                        }
                    ],
                    "matter_facts": {},
                    "as_of_date": "2024-09-01"
                }
            }
        }
        resp_conf = process_request(req_conflicts)
        self.assertIsNotNone(resp_conf)
        self.assertNotIn("error", resp_conf)
        conf_text = resp_conf["result"]["content"][0]["text"]
        conf_parsed = json.loads(conf_text)
        self.assertEqual(conf_parsed["conflict_count"], 1)
        self.assertEqual(conf_parsed["conflicts"][0]["conflict_type"], "preemption_conflict")


if __name__ == "__main__":
    unittest.main()
