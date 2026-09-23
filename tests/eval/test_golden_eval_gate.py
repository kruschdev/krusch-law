"""
tests/eval/test_golden_eval_gate.py
===================================
CI Multi-Gate Evaluation Harness for KruschLaw Sovereign Legal Intelligence Engine.

Enforces 3 discrete gates + grounding calibration matrix in CI:
  1. Fixture Gate: Lexical + hybrid retrieval across seeded California ordinances.
  2. Unmocked Embedding Gate: Real BGE-Large 1024-d vectors on frozen local cache.
  3. Held-Out Statutory Gate: 12 external California statutory & municipal provisions.
  4. Grounding Calibration: Empirical 4-way confusion matrix on legal propositions.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Force in-memory SQLite for test execution
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["OLLAMA_EMBED_HOST"] = "http://mock-ollama:11434"
os.environ["OLLAMA_BASE_URL"] = "http://mock-ollama:11434"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy.types import UserDefinedType

class MockVector(UserDefinedType):
    cache_ok = True
    def __init__(self, dim=1024):
        self.dim = dim
    def get_col_spec(self, **kw):
        return "TEXT"
    def bind_processor(self, dialect):
        def process(value):
            return str(value) if value is not None else None
        return process
    def result_processor(self, dialect, coltype):
        def process(value):
            return None
        return process

sys.modules.setdefault('pgvector', MagicMock())
sys.modules.setdefault('pgvector.sqlalchemy', MagicMock())
sys.modules['pgvector.sqlalchemy'].Vector = MockVector

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.backend.db
import src.backend.rag
import src.backend.ingest
from src.backend.db import Base
from src.backend.ingest import ingest_mock_data
from scripts.eval_retrieval_and_grounding import (
    run_fixture_gate,
    run_unmocked_embedding_gate,
    run_heldout_statutory_gate,
    run_grounding_calibration
)


class TestMultiGateEvaluationCI(unittest.TestCase):
    """
    CI Gate: Ensures multi-gate retrieval recall and assertion grounding pass rates
    meet minimum sovereign legal standards without mocking embeddings to uniform vectors.
    """
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        cls.Session = sessionmaker(bind=cls.engine)

        src.backend.db.engine = cls.engine
        src.backend.db.SessionLocal = cls.Session
        src.backend.rag.SessionLocal = cls.Session
        src.backend.ingest.SessionLocal = cls.Session

        Base.metadata.create_all(cls.engine)

        # Fallback dummy vector for live embed requests if any
        mock_vec = [0.05] * 1024
        src.backend.rag.get_embedding = MagicMock(return_value=mock_vec)
        src.backend.rag.get_embeddings_batch = MagicMock(side_effect=lambda texts: [mock_vec] * len(texts))
        src.backend.ingest.get_embedding = MagicMock(return_value=mock_vec)
        src.backend.ingest.get_embeddings_batch = MagicMock(side_effect=lambda texts: [mock_vec] * len(texts))

        db = cls.Session()
        ingest_mock_data(db)
        db.close()

    def test_01_fixture_gate(self):
        """Gate 1: Verify lexical/hybrid recall across bootstrap fixtures."""
        eval_path = os.path.join(PROJECT_ROOT, "data", "eval", "golden_legal_eval.json")
        session = self.Session()
        try:
            metrics = run_fixture_gate(dataset_path=eval_path, db_session=session)

            self.assertGreaterEqual(
                metrics["recall_at_5"], 95.0,
                f"Gate 1 Recall@5 ({metrics['recall_at_5']}%) regressed below 95% threshold."
            )
            self.assertEqual(
                metrics["distractor_leaks"], 0,
                f"Gate 1 detected {metrics['distractor_leaks']} forbidden distractor leaks."
            )
            self.assertGreaterEqual(
                metrics["mrr"], 0.900,
                f"Gate 1 MRR ({metrics['mrr']}) below 0.900 target."
            )
        finally:
            session.close()

    def test_02_unmocked_embedding_gate(self):
        """Gate 2: Pure dense vector search with frozen unmocked bge-large 1024-d vectors."""
        metrics = run_unmocked_embedding_gate()
        self.assertGreaterEqual(
            metrics["vector_recall_at_5"], 95.0,
            f"Gate 2 Pure Vector Recall@5 ({metrics['vector_recall_at_5']}%) regressed below 95% threshold."
        )
        self.assertGreaterEqual(
            metrics["vector_mrr"], 0.850,
            f"Gate 2 Pure Vector MRR ({metrics['vector_mrr']}) regressed below 0.850 threshold."
        )

    def test_03_heldout_statutory_gate(self):
        """Gate 3: Evaluation against 12 external California statutory & municipal provisions."""
        metrics = run_heldout_statutory_gate()
        self.assertGreaterEqual(
            metrics["heldout_recall_at_5"], 90.0,
            f"Gate 3 Held-Out Recall@5 ({metrics['heldout_recall_at_5']}%) regressed below 90% threshold."
        )
        self.assertEqual(
            metrics["priority_inversions"], 0,
            f"Gate 3 detected {metrics['priority_inversions']} priority inversions (repealed laws outranking controlling)."
        )

    def test_04_grounding_calibration_matrix(self):
        """Gate 4: Assertion grounding calibration matrix accuracy across proposition failure modes."""
        cal = run_grounding_calibration()
        self.assertGreaterEqual(
            cal["overall_accuracy"], 80.0,
            f"Grounding calibration overall accuracy ({cal['overall_accuracy']}%) regressed below 80%."
        )
        cm = cal["confusion_matrix"]
        self.assertGreaterEqual(cm["supported"]["accuracy"], 90.0)
        self.assertGreaterEqual(cm["invented_citation"]["accuracy"], 90.0)
        self.assertGreaterEqual(cm["stale_law"]["accuracy"], 90.0)


if __name__ == "__main__":
    unittest.main()
