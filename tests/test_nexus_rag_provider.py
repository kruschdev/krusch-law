"""
tests/test_nexus_rag_provider.py
================================
Unit tests verifying that KruschLaw can hook into KruschNexus and Wondersearch
as a swappable RAG retrieval provider while preserving air-gap security invariants.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

NEXUS_SRC = os.path.join(os.path.dirname(PROJECT_ROOT), "krusch-nexus", "src")
if os.path.isdir(NEXUS_SRC) and NEXUS_SRC not in sys.path:
    sys.path.insert(0, NEXUS_SRC)

from krusch_nexus.models import SearchHit, Citation
from krusch_nexus.exceptions import AirGapViolationError
from src.backend.config import settings
from src.backend.nexus_rag import (
    is_nexus_available,
    get_nexus_client,
    search_laws_nexus,
    search_matter_evidence_nexus
)
from src.backend.rag import retrieve_laws, retrieve_matter_evidence


class TestNexusRagProvider(unittest.TestCase):
    """Test suite for KruschLaw RAG delegation to Nexus/Wondersearch."""

    def setUp(self):
        self.orig_rag_provider = getattr(settings, "RAG_PROVIDER", "local")
        self.orig_allow_cloud = getattr(settings, "ALLOW_CLOUD", False)

    def tearDown(self):
        settings.RAG_PROVIDER = self.orig_rag_provider
        settings.ALLOW_CLOUD = self.orig_allow_cloud
        import src.backend.nexus_rag
        src.backend.nexus_rag._NEXUS_CLIENT = None

    def test_nexus_available(self):
        """KruschNexus should be discoverable in the monorepo."""
        self.assertTrue(is_nexus_available())

    def test_air_gap_protection_wondersearch_blocked_by_default(self):
        """Wondersearch backend must raise AirGapViolationError when ALLOW_CLOUD is not 1."""
        settings.ALLOW_CLOUD = False
        with patch.dict(os.environ, {"NEXUS_BACKEND": "wondersearch", "ALLOW_CLOUD": "0"}):
            with self.assertRaises(AirGapViolationError):
                get_nexus_client()

    def test_wondersearch_allowed_when_allow_cloud_enabled(self):
        """Wondersearch backend succeeds when ALLOW_CLOUD=1."""
        settings.ALLOW_CLOUD = True
        with patch.dict(os.environ, {
            "NEXUS_BACKEND": "wondersearch",
            "ALLOW_CLOUD": "1",
            "WONDERSEARCH_API_KEY": "ws_test_key"
        }):
            client = get_nexus_client()
            self.assertIsNotNone(client)
            self.assertEqual(client.config.backend, "wondersearch")

    @patch("src.backend.nexus_rag.get_nexus_client")
    def test_retrieve_laws_routing(self, mock_get_client):
        """When RAG_PROVIDER='nexus', retrieve_laws delegates to NexusClient and preserves INV-11 coordinates."""
        settings.RAG_PROVIDER = "nexus"

        mock_hit = SearchHit(
            chunk_id=101,
            document_id=5,
            text="Cal. Civ. Code § 1950.5: Security deposit return within 21 days.",
            score=0.92,
            citation="Cal. Civ. Code § 1950.5, p. 3",
            locator="§ 1950.5",
            page_number=3,
            char_start=120,
            char_end=185,
            bbox=[72.0, 140.0, 520.0, 180.0],
            score_vector={
                "jurisdiction": "California",
                "state": "CA",
                "topic": "Security Deposit Retention & Itemization"
            }
        )

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_hit]
        mock_get_client.return_value = mock_client

        results = retrieve_laws(text_query="security deposit return deadline")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["id"], 101)
        self.assertEqual(r["title"], "Cal. Civ. Code § 1950.5, p. 3")
        self.assertEqual(r["page_number"], 3)
        self.assertEqual(r["bbox"], [72.0, 140.0, 520.0, 180.0])
        self.assertEqual(r["char_start"], 120)
        self.assertEqual(r["char_end"], 185)
        self.assertEqual(r["similarity"], 0.92)

    @patch("src.backend.nexus_rag.get_nexus_client")
    def test_retrieve_matter_evidence_routing(self, mock_get_client):
        """When RAG_PROVIDER='nexus', retrieve_matter_evidence delegates to NexusClient with workspace isolation."""
        settings.RAG_PROVIDER = "nexus"

        mock_hit = SearchHit(
            chunk_id=202,
            document_id=8,
            text="Tenant paid $1,500 deposit on March 1 via cashier check.",
            score=0.88,
            citation="Lease Agreement, p. 1",
            filename="lease_contract.pdf",
            locator="Section 3",
            page_number=1,
            char_start=50,
            char_end=110,
            bbox=[50.0, 100.0, 450.0, 130.0],
            doc_type="lease",
            score_vector={
                "tags": ["deposit", "payment", "lease"]
            }
        )

        mock_client = MagicMock()
        mock_client.search.return_value = [mock_hit]
        mock_get_client.return_value = mock_client

        results = retrieve_matter_evidence(matter_id=42, text_query="cashier check")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["id"], 202)
        self.assertEqual(r["matter_id"], 42)
        self.assertEqual(r["filename"], "lease_contract.pdf")
        self.assertEqual(r["page_number"], 1)
        self.assertEqual(r["bbox"], [50.0, 100.0, 450.0, 130.0])
        mock_client.search.assert_called_once()
        self.assertEqual(mock_client.search.call_args.kwargs["workspace"], "matter_42")


if __name__ == "__main__":
    unittest.main()
