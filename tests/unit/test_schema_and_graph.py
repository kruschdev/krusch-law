from datetime import datetime, timezone
import os
import tempfile
import unittest
from tests.base import KruschLawTestCase
from src.backend.db import LawVector
from src.backend.ingest import (
    ingest_mock_data,
    ingest_locus_parquet,
    parse_header_section_and_title,
    chunk_statute_content
)
from src.backend.rag import retrieve_laws
import src.backend.config


class TestSchemaAndLegalGraph(KruschLawTestCase):
    """Unit tests for versioned legal graph schema, hierarchy, and authority levels."""

    def test_hierarchical_attributes_and_defaults(self):
        eff_date = datetime(2020, 2, 1, tzinfo=timezone.utc)
        law = LawVector(
            jurisdiction="Oakland Municipal Code",
            state="CA",
            city="Oakland",
            title="Exceptions to Rent Adjustment Program",
            section="Section 8.22.030(B)",
            parent_section="Section 8.22.030",
            hierarchy_level="subsection",
            definitions_ref="Section 8.22.020",
            exceptions_ref="Section 8.22.030(B)",
            authority_class="municipal_ordinance",
            effective_date=eff_date,
            repealed=False,
            content="Owner-occupied duplexes and units constructed after 1983 are exempt.",
            embedding=self.mock_vector,
            is_substantive=True
        )
        self.db.add(law)
        self.db.commit()

        retrieved = self.db.query(LawVector).filter_by(section="Section 8.22.030(B)").first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.parent_section, "Section 8.22.030")
        self.assertEqual(retrieved.hierarchy_level, "subsection")
        self.assertEqual(retrieved.definitions_ref, "Section 8.22.020")
        self.assertEqual(retrieved.authority_class, "municipal_ordinance")
        self.assertEqual(retrieved.effective_date.strftime("%Y-%m-%d"), "2020-02-01")
        self.assertFalse(retrieved.repealed)

    def test_seed_hierarchical_data_ingestion(self):
        inserted = ingest_mock_data(self.db)
        self.assertGreater(inserted, 0)

        # Confirm definition section exists
        def_sec = self.db.query(LawVector).filter_by(section="Section 8.22.020").first()
        self.assertIsNotNone(def_sec)
        self.assertEqual(def_sec.hierarchy_level, "definitions")

        # Confirm parent rule and exception clause link together
        parent_sec = self.db.query(LawVector).filter_by(section="Section 8.22.030").first()
        child_sec = self.db.query(LawVector).filter_by(section="Section 8.22.030(B)").first()
        self.assertIsNotNone(parent_sec)
        self.assertIsNotNone(child_sec)
        self.assertEqual(child_sec.parent_section, "Section 8.22.030")

        # Confirm repealed statute is cataloged with repealed=True
        repealed_sec = self.db.query(LawVector).filter_by(section="Section 1947.10").first()
        self.assertIsNotNone(repealed_sec)
        self.assertTrue(repealed_sec.repealed)

    def test_mock_deduplication_by_content_hash(self):
        first_count = ingest_mock_data(self.db)
        self.assertGreater(first_count, 0)

        # Re-running ingestion must insert 0 records due to source_hash collision
        second_count = ingest_mock_data(self.db)
        self.assertEqual(second_count, 0)

    def test_parse_header_and_chunking(self):
        sec, title = parse_header_section_and_title("8.22.030 - Notice of Rent Adjustment Program.")
        self.assertEqual(sec, "Section 8.22.030")
        self.assertIn("Notice of Rent Adjustment", title)

        sec2, title2 = parse_header_section_and_title("Sec. 1.05.010 General Penalties")
        self.assertEqual(sec2, "Section 1.05.010")

        long_content = "Paragraph 1: Statutory basis.\n\n" + ("Long legal text element. " * 150) + "\n\nParagraph 3: Final penalty clause."
        chunks = chunk_statute_content(
            header="Test Header",
            content=long_content,
            jurisdiction="Oakland Municipal Code",
            section="Section 8.22.030",
            max_chars=500
        )
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertIn("Oakland Municipal Code", chunks[0]["chunk_text"])
        self.assertIsNotNone(chunks[0]["source_hash"])

    def test_locus_parquet_ingestion_with_columns(self):
        import pandas as pd

        test_df = pd.DataFrame([
            {
                "header": "8.22.010 - Purpose and Findings",
                "content": "This chapter is enacted to protect residential tenants from arbitrary evictions.",
                "state": "CA",
                "city": "Oakland",
                "county": "Alameda County",
                "topic": "Housing & Tenant Protections",
                "function": "Regulation",
                "is_substantive": True
            },
            {
                "header": "8.22.020 - Table of Contents",
                "content": "1. Purpose\n2. Rent limits",
                "state": "CA",
                "city": "Oakland",
                "county": "Alameda County",
                "topic": "Housing & Tenant Protections",
                "function": "TOC",
                "is_substantive": False
            }
        ])

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            temp_path = f.name
            test_df.to_parquet(temp_path)

        temp_dir = os.path.dirname(temp_path)
        src.backend.config.settings.extra_allowed_dirs.append(temp_dir)

        try:
            inserted = ingest_locus_parquet(temp_path, db=self.db, limit=10)
            self.assertEqual(inserted, 1)

            oakland_sub = self.db.query(LawVector).filter_by(section="Section 8.22.010").first()
            self.assertIsNotNone(oakland_sub)
            self.assertEqual(oakland_sub.city, "Oakland")
            self.assertTrue(oakland_sub.is_substantive)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_authority_hierarchy_weighting(self):
        statute = LawVector(
            jurisdiction="California Civil Code",
            state="CA",
            city=None,
            title="Statewide Security Deposit Limit",
            section="Section 1950.5",
            authority_class="controlling_statute",
            content="Landlords may not demand a security deposit exceeding one month rent.",
            embedding=[0.8] + [0.0] * 1023,
            is_substantive=True
        )
        commentary = LawVector(
            jurisdiction="Practice Guide",
            state="CA",
            city="Oakland",
            title="Commentary on Deposits",
            section="Section 99.1",
            authority_class="secondary_commentary",
            content="Landlords may not demand a security deposit exceeding one month rent commentary.",
            embedding=[0.8] + [0.0] * 1023,
            is_substantive=True
        )
        self.db.add_all([statute, commentary])
        self.db.commit()

        results = retrieve_laws(
            query_vector=[1.0] + [0.0] * 1023,
            text_query="security deposit limit",
            limit=2,
            db_session=self.db
        )
        self.assertEqual(len(results), 2)
        # Controlling statute must rank before secondary commentary
        self.assertEqual(results[0]["authority_class"], "controlling_statute")


if __name__ == "__main__":
    unittest.main()
