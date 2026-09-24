import os
from tests.base import KruschLawTestCase
from src.backend.db import StatutoryArtifact, LawVector, rebuild_vectors_from_artifacts
from src.backend.jurisdiction_pack import (
    load_jurisdiction_pack,
    import_jurisdiction_pack,
    JurisdictionPack
)


class TestJurisdictionPack(KruschLawTestCase):
    """Unit tests for jurisdiction pack loading, artifact storage, and vector rebuild."""

    def test_load_ca_oakland_pack(self):
        pack_path = os.path.join(os.path.dirname(__file__), "../../data/packs/ca_oakland.yaml")
        pack_path = os.path.abspath(pack_path)
        self.assertTrue(os.path.exists(pack_path), f"Pack file not found: {pack_path}")

        pack = load_jurisdiction_pack(pack_path)
        self.assertIsInstance(pack, JurisdictionPack)
        self.assertEqual(pack.state, "CA")
        self.assertEqual(pack.municipality, "Oakland")
        self.assertEqual(pack.version, "1.0.0")
        self.assertGreaterEqual(len(pack.statutes), 6)
        self.assertIn("Security Deposits", pack.coverage.covered_topics)
        self.assertIn("Commercial Lease Evictions", pack.coverage.uncovered_topics)

    def test_import_and_rebuild_vectors(self):
        pack_path = os.path.join(os.path.dirname(__file__), "../../data/packs/ca_oakland.yaml")
        pack_path = os.path.abspath(pack_path)

        # 1. Import pack into DB
        stats = import_jurisdiction_pack(pack_path, self.db)
        self.assertGreaterEqual(stats["artifacts_imported"], 6)
        self.assertGreaterEqual(stats["vectors_created"], 6)

        # 2. Verify statutory artifacts stored with hashes
        artifacts = self.db.query(StatutoryArtifact).all()
        self.assertGreaterEqual(len(artifacts), 6)
        for art in artifacts:
            self.assertIsNotNone(art.artifact_hash)
            self.assertEqual(len(art.artifact_hash), 64)
            self.assertIn(art.publisher, ("California Office of Legislative Counsel", "California State Legislature", "City of Oakland / Municode", "City of Oakland City Clerk"))

        # 3. Verify LawVectors have artifact_id links
        vectors = self.db.query(LawVector).all()
        self.assertGreaterEqual(len(vectors), 6)
        for vec in vectors:
            self.assertIsNotNone(vec.artifact_id)
            art = self.db.query(StatutoryArtifact).filter_by(id=vec.artifact_id).first()
            self.assertIsNotNone(art)

        # 4. Verify vector rebuild from raw artifacts
        rebuilt_count = rebuild_vectors_from_artifacts(self.db)
        self.assertGreaterEqual(rebuilt_count, 6)

        # Check that vectors still exist and are linked
        vectors_after = self.db.query(LawVector).all()
        self.assertEqual(len(vectors_after), rebuilt_count)
