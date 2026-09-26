#!/usr/bin/env python3
"""
scripts/demo_60s.py
===================
60-Second Headless Demonstration of KruschLaw.
Runs with zero external dependencies (no Ollama, no PostgreSQL, no GPU).
Demonstrates:
  1. DAG Precedence Resolver walking statutory preemption & amendment hierarchy
  2. Temporal As-Of Gating: Pre-AB 12 (2-month cap) vs Post-AB 12 (1-month cap)
  3. Proposition Grounding Scanner with deterministic Pass A & Pass B failure mode detection
"""

import os
import sys
import time
import json
from datetime import date

# Set headless flags before importing backend
os.environ["HEADLESS_MODE"] = "1"
os.environ["USE_MOCK_EMBEDDINGS"] = "1"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock pgvector before SQLAlchemy imports so SQLite can treat Vector as JSON/TEXT
from sqlalchemy.types import UserDefinedType

class MockVector(UserDefinedType):
    def __init__(self, dim=1024):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"
    def bind_processor(self, dialect):
        def process(value):
            return json.dumps(value) if isinstance(value, list) else value
        return process
    def result_processor(self, dialect, coltype):
        def process(value):
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except Exception:
                    return value
            return value
        return process

if 'pgvector' not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules['pgvector'] = MagicMock()
    sys.modules['pgvector.sqlalchemy'] = MagicMock()
    sys.modules['pgvector.sqlalchemy'].Vector = MockVector

from src.backend.db import SessionLocal, init_db, engine, LawVector
from src.backend.resolver import resolve_controlling_law
from src.backend.rag import verify_assertion_grounding


def main():
    t0 = time.perf_counter()
    print("\n" + "=" * 76)
    print("  ⚖️  KRUSCHLAW 60-SECOND HEADLESS DEMO")
    print("  Sovereign Statutory Precedence & Legal Proposition Grounding Engine")
    print("=" * 76 + "\n")

    init_db()
    db = SessionLocal()

    try:
        # Step 1: Preemption DAG Resolution
        print("Step 1: Statutory Preemption DAG Traversal (Oakland vs California)")
        print("-" * 76)
        res_rent = resolve_controlling_law(
            doctrine_or_topic="Rent Adjustment",
            city="Oakland",
            as_of_date=date(2024, 8, 1),
            db=db
        )
        print("  [Topic: Rent Adjustment] Jurisdiction: Oakland, CA | As-of: 2024-08-01")
        print(f"  -> Controlling Authority:  {res_rent.governing_citation}")
        print(f"  -> Title:                  {res_rent.controlling_node.get('title') if res_rent.controlling_node else 'N/A'}")
        print(f"  -> Precedence Chain Steps: {len(res_rent.precedence_chain)}")
        for step in res_rent.precedence_chain:
            print(f"     Step {step.get('step')}: {step.get('section')} [{step.get('authority_class')}] -> Action: {step.get('action')}")
        print(f"  -> Resolution Confidence:  {res_rent.confidence_score * 100:.1f}%")

        # Step 2: Temporal As-Of Gating
        print("\n" + "=" * 76)
        print("Step 2: Temporal Invariant Gating (Civil Code § 1950.5 vs AB 12)")
        print("-" * 76)
        # Pre-AB 12 (Jan 1, 2024)
        res_pre = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date=date(2024, 1, 1),
            db=db
        )
        cap_pre = res_pre.statutory_slots.get("deposit_cap_months")
        print("  [Inquiry Date: 2024-01-01 (Pre-AB 12)]")
        print(f"  -> Controlling Authority:  {res_pre.governing_citation}")
        print(f"  -> Statutory Deposit Cap:  {cap_pre:.0f} months' rent (Historical Law)")

        # Post-AB 12 (Aug 15, 2024)
        res_post = resolve_controlling_law(
            doctrine_or_topic="Security Deposits",
            as_of_date=date(2024, 8, 15),
            db=db
        )
        cap_post = res_post.statutory_slots.get("deposit_cap_months")
        print("\n  [Inquiry Date: 2024-08-15 (Post-AB 12)]")
        print(f"  -> Controlling Authority:  {res_post.governing_citation}")
        print(f"  -> Statutory Deposit Cap:  {cap_post:.0f} month's rent (AB 12 Reformed)")

        # Step 3: Proposition Grounding Scanner
        print("\n" + "=" * 76)
        print("Step 3: Proposition Grounding Scanner (Deterministic Pass A & Pass B)")
        print("-" * 76)

        retrieved_laws = db.query(LawVector).filter(
            LawVector.section.in_(["Section 1950.5", "Section 1950.5(c)"])
        ).all()
        law_dicts = [
            {
                "id": law.id,
                "title": law.title,
                "section": law.section,
                "jurisdiction": law.jurisdiction,
                "content": law.content,
                "repealed": bool(law.repealed)
            }
            for law in retrieved_laws
        ]

        # Claim A: Grounded Truth
        claim_a = "Within 21 calendar days after vacating, the landlord must furnish an itemized statement under Section 1950.5."
        is_g_a, claims_a, _, _ = verify_assertion_grounding(claim_a, law_dicts)
        print(f"\n  Claim A: \"{claim_a}\"")
        print(f"  -> Grounded:           ✅ {is_g_a}")
        print(f"  -> Verdict:            {claims_a[0].get('verdict')} ({claims_a[0].get('status')})")
        print(f"  -> Bound Span:         {claims_a[0].get('source_excerpt')[:60]}...")

        # Claim B: Mutated Timeline (45 days instead of 21)
        claim_b = "Within 45 calendar days after vacating, the landlord must furnish an itemized statement under Section 1950.5."
        is_g_b, claims_b, _, _ = verify_assertion_grounding(claim_b, law_dicts)
        print(f"\n  Claim B: \"{claim_b}\"")
        print(f"  -> Grounded:           ❌ {is_g_b}")
        print(f"  -> Failure Status:     {claims_b[0].get('status')} [verdict={claims_b[0].get('verdict')}]")
        print(f"  -> Diagnostic:         {claims_b[0].get('reason')}")

        # Claim C: Fabricated Citation
        claim_c = "Under Section 999.99, tenants receive an automatic $5,000 refund."
        is_g_c, claims_c, _, _ = verify_assertion_grounding(claim_c, law_dicts)
        print(f"\n  Claim C: \"{claim_c}\"")
        print(f"  -> Grounded:           ❌ {is_g_c}")
        print(f"  -> Failure Status:     {claims_c[0].get('status')} [verdict={claims_c[0].get('verdict')}]")
        print(f"  -> Diagnostic:         {claims_c[0].get('reason')}")

        elapsed = time.perf_counter() - t0
        print("\n" + "=" * 76)
        print(f"  ✨ All KruschLaw Demo Stages Completed in {elapsed:.3f}s")
        print("=" * 76 + "\n")
    finally:
        db.close()


if __name__ == "__main__":
    main()
