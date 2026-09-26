#!/usr/bin/env python3
"""
scripts/build_demo_db.py
========================
Builds and packages a zero-dependency frozen SQLite database fixture (data/demo.db) containing
sample California Civil Code, Oakland Municipal Code, Tenant Protection Act provisions,
confirmed preemption/amendment relations, and legal embeddings.

Enables the KruschLaw REST API (/docs) and Streamlit UI to run entirely out-of-the-box
with zero external dependencies (no Ollama, no PostgreSQL, no GPU).
"""

import os
import sys
import json
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ["USE_MOCK_EMBEDDINGS"] = "1"
os.environ["HEADLESS_MODE"] = "1"

demo_db_path = os.path.join(PROJECT_ROOT, "data", "demo.db")
os.environ["DATABASE_URL"] = f"sqlite:///{demo_db_path}"

# Mock pgvector before SQLAlchemy imports so SQLite can treat Vector as JSON/TEXT
from sqlalchemy.types import UserDefinedType

class MockVector(UserDefinedType):
    def __init__(self, dim=1024):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"
    def bind_processor(self, dialect):
        def process(value):
            if isinstance(value, list):
                return json.dumps(value)
            return value
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

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.backend.rag
from src.backend.db import Base, StatuteRelation
from src.backend.ingest import ingest_mock_data


def main():
    if os.path.exists(demo_db_path):
        os.remove(demo_db_path)

    print(f"Creating frozen demo database at: {demo_db_path}")
    demo_engine = create_engine(f"sqlite:///{demo_db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=demo_engine)
    DemoSession = sessionmaker(bind=demo_engine)
    db = DemoSession()

    # Provide deterministic mock embedding batch
    mock_vector = [0.05] * 1024
    src.backend.rag.get_embedding = lambda text: mock_vector
    src.backend.rag.get_embeddings_batch = lambda texts: [mock_vector] * len(texts)

    try:
        inserted = ingest_mock_data(db)
        print(f"Ingested {inserted} mock California and municipal statutes.")

        # Seed confirmed statute relations for DAG walking
        demo_relations = [
            StatuteRelation(
                source_statute="Cal. Civ. Code § 1954.50",
                target_statute="Oakland Municipal Code Section 8.22.030",
                relation_type="PREEMPTS",
                scope_topic="Rent Control",
                confidence=1.0,
                status="confirmed",
                reviewed_by="attorney:krusch",
                reviewed_at=datetime.now(timezone.utc),
                rationale="Costa-Hawkins Rental Housing Act preempts municipal vacancy control."
            ),
            StatuteRelation(
                source_statute="Cal. Civ. Code § 1950.5(c)",
                target_statute="Section 1950.5 (Pre-2024)",
                relation_type="PREEMPTS",
                scope_topic="Security Deposits",
                confidence=1.0,
                status="confirmed",
                reviewed_by="attorney:krusch",
                reviewed_at=datetime.now(timezone.utc),
                rationale="AB 12 amends § 1950.5 to cap residential security deposits at 1 month rent."
            ),
            StatuteRelation(
                source_statute="Cal. Civ. Code § 1946.2",
                target_statute="Oakland Municipal Code Section 8.22.360",
                relation_type="CREATES",
                scope_topic="Eviction & Just Cause",
                confidence=0.95,
                status="confirmed",
                reviewed_by="attorney:krusch",
                reviewed_at=datetime.now(timezone.utc),
                rationale="Statewide mandatory just cause baseline under Tenant Protection Act."
            )
        ]

        for rel in demo_relations:
            db.add(rel)
        db.commit()
        print(f"Seeded {len(demo_relations)} confirmed demo statute relations.")

        print(f"Successfully generated frozen fixture data/demo.db ({os.path.getsize(demo_db_path):,} bytes).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
