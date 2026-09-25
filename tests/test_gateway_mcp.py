"""
tests/test_gateway_mcp.py
=========================
Unit tests for KruschLaw's 5-verb Sovereign Gateway MCP Router:
  1. Exact 5-tool catalog validation (ask_law, ask_biz, check_compliance, ingest, purge)
  2. Strict token budget enforcement (<450 prompt tokens)
  3. JSON-RPC protocol execution: initialize, tools/list, tools/call
  4. ask_law search and resolve handlers
  5. check_compliance join execution
"""

import json
import os
import sys
import unittest
from datetime import datetime

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.backend.db as db_mod
from src.backend.db import LawVector, Case, init_db
from src.mcp.gateway import (
    GATEWAY_TOOLS_CATALOG,
    handle_tools_call,
    handle_tools_list,
    process_json_rpc,
)


class TestGatewayMCP(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.Session = sessionmaker(bind=cls.engine)
        db_mod.engine = cls.engine
        db_mod.SessionLocal = cls.Session
        init_db(cls.engine)

    def setUp(self):
        self.db = self.Session()
        self.db.query(LawVector).delete()
        self.db.query(Case).delete()
        self.db.commit()

        # Seed statutory authorities
        self.ab12 = LawVector(
            jurisdiction="California Civil Code",
            state="CA",
            city="Oakland",
            topic="Security Deposits",
            title="Civil Code 1950.5 - AB 12 1-Month Cap",
            section="Cal. Civ. Code § 1950.5(c)(1)",
            content="A landlord may not demand or receive security in an amount exceeding one month's rent.",
            authority_class="controlling_statute",
            effective_date=datetime(2024, 7, 1),
            is_substantive=True
        )
        self.db.add(self.ab12)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_01_catalog_has_exact_5_verbs(self):
        """Gateway MCP must consolidate tool sprawl into exactly 5 canonical verbs."""
        tools = GATEWAY_TOOLS_CATALOG
        self.assertEqual(len(tools), 5)
        names = {t["name"] for t in tools}
        expected = {"ask_law", "ask_biz", "check_compliance", "ingest", "purge"}
        self.assertEqual(names, expected)

    def test_02_strict_token_budget_under_450_tokens(self):
        """
        Hard Token Budget Invariant:
        Tool schema catalog must be strictly <450 tokens (~1800 characters)
        so local 7B/14B models do not waste context window on tool schemas.
        """
        catalog_json = json.dumps(GATEWAY_TOOLS_CATALOG, separators=(',', ':'))
        approx_tokens = len(catalog_json) / 4.0
        self.assertLess(
            approx_tokens,
            450,
            f"Gateway tools catalog ({approx_tokens:.1f} tokens, {len(catalog_json)} chars) exceeds 450-token budget!"
        )

    def test_03_json_rpc_initialize_and_tools_list(self):
        """Verify standard JSON-RPC 2.0 initialize and tools/list flow."""
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        resp = json.loads(process_json_rpc(init_req))
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "krusch-gateway-mcp")

        list_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        resp_list = json.loads(process_json_rpc(list_req))
        self.assertEqual(len(resp_list["result"]["tools"]), 5)

    def test_04_ask_law_search_and_resolve(self):
        """Verify ask_law search and resolve actions."""
        # 1. Search action
        res_search = handle_tools_call("ask_law", {
            "action": "search",
            "query": "security deposit",
            "topic": "Security Deposits"
        })
        self.assertEqual(res_search["status"], "success")
        self.assertGreaterEqual(res_search["count"], 1)

        # 2. Resolve action
        res_resolve = handle_tools_call("ask_law", {
            "action": "resolve",
            "topic": "Security Deposits",
            "as_of_date": "2024-08-15"
        })
        self.assertEqual(res_resolve["status"], "success")
        self.assertIn("controlling_citation", res_resolve)

    def test_05_check_compliance_via_gateway_rpc(self):
        """Verify check_compliance executes via JSON-RPC."""
        rpc_call = json.dumps({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "check_compliance",
                "arguments": {
                    "jurisdiction": "CA:Oakland",
                    "as_of_date": "2024-08-15",
                    "topics": ["SECURITY_DEPOSIT", "ENTRY_NOTICE"]
                }
            }
        })
        raw_resp = process_json_rpc(rpc_call)
        resp = json.loads(raw_resp)
        self.assertEqual(resp["id"], 42)
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["status"], "success")
        self.assertGreaterEqual(payload["findings_count"], 1)


if __name__ == "__main__":
    unittest.main()
