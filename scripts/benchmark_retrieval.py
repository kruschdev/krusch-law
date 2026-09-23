#!/usr/bin/env python3
"""
Empirical Retrieval & Grounding Benchmark for KruschLaw.
Measures query latency (p50, p95, p99), Recall@k against known statutory fixtures,
and citation verification overhead.
"""

import os
import sys
import time
import math
import json
from typing import List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Use SQLite in-memory for reproducible offline evaluation if no PG available
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy.types import UserDefinedType
class MockVector(UserDefinedType):
    def __init__(self, dim):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"
    def bind_processor(self, dialect):
        return lambda value: json.dumps(value) if isinstance(value, list) else value
    def result_processor(self, dialect, coltype):
        return lambda value: json.loads(value) if isinstance(value, str) else value

from unittest.mock import MagicMock
sys.modules['pgvector'] = MagicMock()
sys.modules['pgvector.sqlalchemy'] = MagicMock()
sys.modules['pgvector.sqlalchemy'].Vector = MockVector

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.backend.db
import src.backend.rag
import src.backend.ingest

from src.backend.db import Base
from src.backend.ingest import ingest_mock_data
from src.backend.rag import retrieve_laws, verify_citation_grounding

# Configure deterministic pseudo-embeddings for keyword/vector pairing
def deterministic_embedding(text: str) -> List[float]:
    vec = [0.0] * 1024
    for i, word in enumerate(text.lower().split()[:20]):
        h = sum(ord(c) for c in word) % 1024
        vec[h] = 0.5 + (0.5 / (i + 1))
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]

src.backend.rag.get_embedding = deterministic_embedding
src.backend.ingest.get_embedding = deterministic_embedding
src.backend.ingest.get_embeddings_batch = lambda texts: [deterministic_embedding(t) for t in texts]

BENCHMARK_QUERIES = [
    {
        "query": "Oakland Rent Adjustment Program tenant notice barred rent increase",
        "city": "Oakland",
        "expected_section": "Section 8.22.030"
    },
    {
        "query": "Oakland Just Cause for eviction owner occupancy grounds",
        "city": "Oakland",
        "expected_section": "Section 8.22.360"
    },
    {
        "query": "San Francisco noise level limit 5 dBA residential night",
        "city": "San Francisco",
        "expected_section": "Section 2909"
    },
    {
        "query": "Short-term rental transient occupancy primary resident 275 days",
        "city": "San Francisco",
        "expected_section": "Section 41A.5"
    },
    {
        "query": "Rent Stabilization Ordinance relocation assistance payment owner occupancy",
        "city": "Los Angeles",
        "expected_section": "Section 151.09"
    },
    {
        "query": "Security deposit limit one month rent itemized statement 21 days",
        "city": None,
        "expected_section": "Section 1950.5"
    }
]


def run_benchmark():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine)
    src.backend.db.engine = engine
    src.backend.db.SessionLocal = Session
    src.backend.rag.SessionLocal = Session
    src.backend.ingest.SessionLocal = Session

    Base.metadata.create_all(engine)
    db = Session()

    print("\n" + "=" * 70)
    print(" ⚖️  KRUSCHLAW EMPIRICAL RETRIEVAL BENCHMARK")
    print("=" * 70)

    # 1. Ingestion Phase
    t0 = time.perf_counter()
    inserted = ingest_mock_data(db)
    ingest_time_ms = (time.perf_counter() - t0) * 1000
    print(f"[*] Ingested {inserted} test provisions in {ingest_time_ms:.2f} ms")

    # 2. Retrieval Accuracy & Latency
    latencies_ms = []
    r_at_1_hits = 0
    r_at_3_hits = 0
    total_queries = len(BENCHMARK_QUERIES) * 10

    print(f"[*] Executing {total_queries} hybrid retrieval iterations...")
    for _ in range(10):
        for bq in BENCHMARK_QUERIES:
            t_start = time.perf_counter()
            results = retrieve_laws(
                text_query=bq["query"],
                city_filter=bq.get("city"),
                limit=5,
                db_session=db
            )
            elapsed_ms = (time.perf_counter() - t_start) * 1000
            latencies_ms.append(elapsed_ms)

            retrieved_secs = [r.get("section") for r in results]
            if retrieved_secs and retrieved_secs[0] == bq["expected_section"]:
                r_at_1_hits += 1
            if bq["expected_section"] in retrieved_secs[:3]:
                r_at_3_hits += 1

    latencies_ms.sort()
    p50 = latencies_ms[len(latencies_ms) // 2]
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
    p99 = latencies_ms[int(len(latencies_ms) * 0.99)]
    avg_latency = sum(latencies_ms) / len(latencies_ms)
    r1_pct = (r_at_1_hits / total_queries) * 100
    r3_pct = (r_at_3_hits / total_queries) * 100

    # 3. Citation & Quote Verification Benchmark
    laws_fixture = [
        {"id": 1, "title": "Oakland RAP", "section": "Section 8.22.030", "content": "Landlords must provide notice."}
    ]
    sample_brief = (
        "Under Section 8.22.030, landlords must provide notice. \"Landlords must provide notice.\" "
        "Failure to do so violates the municipal code."
    )
    guard_latencies_ms = []
    for _ in range(100):
        t_g = time.perf_counter()
        verify_citation_grounding(sample_brief, laws_fixture)
        guard_latencies_ms.append((time.perf_counter() - t_g) * 1000)

    guard_p50 = sorted(guard_latencies_ms)[50]

    # Report Results
    print("\n" + "-" * 70)
    print(" EMPIRICAL EVALUATION RESULTS")
    print("-" * 70)
    print(f"  • Total Retrieval Runs:       {total_queries}")
    print(f"  • Query Latency (Mean):        {avg_latency:.3f} ms")
    print(f"  • Query Latency (p50 Median):  {p50:.3f} ms")
    print(f"  • Query Latency (p95):         {p95:.3f} ms")
    print(f"  • Query Latency (p99):         {p99:.3f} ms")
    print(f"  • Grounding Scanner Latency:   {guard_p50:.3f} ms")
    print(f"  • Recall@1:                    {r1_pct:.1f}%")
    print(f"  • Recall@3:                    {r3_pct:.1f}%")
    print("-" * 70)
    print(" ✅ Benchmark Completed Successfully.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_benchmark()
