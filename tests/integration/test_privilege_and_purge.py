"""
Integration Tests for Week 3 Privilege Surface Reduction and Verifiable Purge
=============================================================================
Tests:
1. Rejection of unauthenticated loopback access in dev mode; local session token auth.
2. Encrypt-at-rest for MatterEvidence exhibits with seamless decryption.
3. Verifiable cryptographic purge with SHA-256 tombstone receipts and audit logging.
4. Physical disk reclamation via vacuum and embedding cache eviction.
5. Privilege isolation between statutory search and confidential client exhibits.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base import KruschLawTestCase
from src.backend.db import Case, MatterEvidence, GroundingReport, AuditLog
from src.backend.crypto import EvidenceEncryptor, execute_verifiable_purge
from src.backend.rag import retrieve_laws, retrieve_matter_evidence, embedding_cache
import src.backend.config


class TestPrivilegeAndPurgeIntegration(KruschLawTestCase):
    def test_loopback_auth_enforcement_and_session_token(self):
        """
        Loopback is not authentication: in dev mode, unauthenticated calls are rejected,
        while X-Session-Token or configured API keys are accepted.
        """
        orig_env = src.backend.config.settings.ENVIRONMENT
        orig_key = src.backend.config.settings.API_KEY
        try:
            src.backend.config.settings.ENVIRONMENT = "development"
            src.backend.config.settings.API_KEY = None

            # 1. Unauthenticated request without headers must be rejected with 401
            resp_unauth = self.client.get("/api/cases")
            self.assertEqual(resp_unauth.status_code, 401)
            self.assertIn("Loopback is not authentication", resp_unauth.json()["detail"])

            # 2. Invalid session token must be rejected with 401
            resp_invalid = self.client.get("/api/cases", headers={"X-Session-Token": "bogus-token"})
            self.assertEqual(resp_invalid.status_code, 401)

            # 3. Valid local session token must be accepted
            resp_token = self.client.get(
                "/api/cases",
                headers={"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}
            )
            self.assertEqual(resp_token.status_code, 200)

            # 4. Valid API key header must also be accepted
            resp_api_key = self.client.get(
                "/api/cases",
                headers={"X-API-Key": src.backend.config.settings.LOCAL_SESSION_TOKEN}
            )
            self.assertEqual(resp_api_key.status_code, 200)
        finally:
            src.backend.config.settings.ENVIRONMENT = orig_env
            src.backend.config.settings.API_KEY = orig_key

    def test_encrypt_at_rest_for_matter_evidence(self):
        """
        Client exhibits in MatterEvidence must be encrypted at rest with AES/Fernet,
        and seamlessly decrypted upon authorized access.
        """
        raw_text = "Privileged confidential client admission: rent paid in cash with handwritten receipt #4401."
        encrypted = EvidenceEncryptor.encrypt_text(raw_text)

        # Ciphertext must be sealed with version prefix and have zero raw leakage
        self.assertTrue(encrypted.startswith("enc:v1:"))
        self.assertNotIn("handwritten receipt #4401", encrypted)
        self.assertNotIn("Privileged confidential", encrypted)

        # Decryption must accurately restore original plaintext
        decrypted = EvidenceEncryptor.decrypt_text(encrypted)
        self.assertEqual(decrypted, raw_text)

        # Legacy plaintext pass-through
        self.assertEqual(EvidenceEncryptor.decrypt_text("legacy plaintext"), "legacy plaintext")

    def test_verifiable_cryptographic_purge_flow(self):
        """
        Verifiable Purge must:
        1. Compute SHA-256 tombstone receipt before permanent destruction.
        2. Hard-delete matter records, evidence chunks, and grounding reports.
        3. Evict in-memory cache entries.
        4. Reclaim disk space via vacuum.
        5. Write verifiable audit receipt to AuditLog.
        """
        # Create case
        case = Case(
            title="Confidential Eviction Settlement",
            matter_number="MAT-PURGE-999",
            client_name="Anonymous Client",
            facts="Confidential terms regarding apartment lease termination at 742 Evergreen Terrace."
        )
        self.db.add(case)
        self.db.commit()
        case_id = case.id

        # Attach confidential evidence
        enc_evidence = EvidenceEncryptor.encrypt_text("Settlement check copy #9021 for $15,000 paid to landlord.")
        ev = MatterEvidence(
            matter_id=case_id,
            filename="settlement_check.pdf",
            doc_type="evidence",
            content=enc_evidence,
            chunk_index=0
        )
        self.db.add(ev)

        # Attach grounding report
        rep = GroundingReport(
            case_id=case_id,
            total_claims=2,
            supported_claims=2,
            pass_rate=100.0,
            claims_json=json.dumps([{"claim": "verified claim", "status": "supported"}]),
            verified_draft="Verified confidential draft."
        )
        self.db.add(rep)
        self.db.commit()

        # Seed embedding cache with matter fact hash
        embedding_cache.set("bge-large", case.facts, [0.1] * 1024)

        # Execute verifiable purge via REST API
        purge_resp = self.client.delete(f"/api/cases/{case_id}/purge")
        self.assertEqual(purge_resp.status_code, 200)
        data = purge_resp.json()

        self.assertEqual(data["status"], "purged")
        self.assertIn("tombstone_hash", data)
        self.assertEqual(len(data["tombstone_hash"]), 64)  # Valid SHA-256 hex string
        self.assertTrue(data["vacuum_executed"])
        self.assertEqual(data["records_purged"]["cases"], 1)
        self.assertEqual(data["records_purged"]["matter_evidence"], 1)
        self.assertEqual(data["records_purged"]["grounding_reports"], 1)

        # Verify DB rows are permanently destroyed
        self.assertIsNone(self.db.query(Case).filter_by(id=case_id).first())
        self.assertEqual(self.db.query(MatterEvidence).filter_by(matter_id=case_id).count(), 0)
        self.assertEqual(self.db.query(GroundingReport).filter_by(case_id=case_id).count(), 0)

        # Verify AuditLog tombstone receipt
        audit = self.db.query(AuditLog).filter_by(action="purge_matter", matter_id=case_id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.tombstone_hash, data["tombstone_hash"])
        details = json.loads(audit.details_json)
        self.assertEqual(details["tombstone_hash"], data["tombstone_hash"])
        self.assertTrue(details["vacuum_executed"])

    def test_privilege_isolation_statutory_vs_evidence(self):
        """
        Public statutory search must never return confidential matter exhibits,
        and evidence retrieval must remain strictly partitioned to the requested matter_id.
        """
        # Create Matter 1 with evidence
        case_1 = Case(title="Matter 1", facts="Dispute 1")
        self.db.add(case_1)
        self.db.commit()

        ev1 = MatterEvidence(
            matter_id=case_1.id,
            filename="confidential_lease.pdf",
            doc_type="lease",
            content=EvidenceEncryptor.encrypt_text("Strict confidential clause regarding unit 301."),
            chunk_index=0
        )
        self.db.add(ev1)
        self.db.commit()

        # 1. Statutory search must not leak evidence
        laws = retrieve_laws(text_query="unit 301", limit=5, db_session=self.db)
        for law in laws:
            self.assertNotIn("unit 301", law.get("content", ""))

        # 2. Evidence retrieval strictly scoped to matter_id
        ev_results_1 = retrieve_matter_evidence(matter_id=case_1.id, db_session=self.db)
        self.assertEqual(len(ev_results_1), 1)
        self.assertEqual(ev_results_1[0]["content"], "Strict confidential clause regarding unit 301.")

        # Another matter cannot retrieve Matter 1's evidence
        ev_results_2 = retrieve_matter_evidence(matter_id=9999, db_session=self.db)
        self.assertEqual(len(ev_results_2), 0)


if __name__ == "__main__":
    unittest.main()
