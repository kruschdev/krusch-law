"""
tests/test_security_hardening.py
================================
Unit tests verifying security boundaries and hardening for KruschLaw:
  - Mandatory API_KEY outside development environment
  - Strict loopback bind enforcement unless ALLOW_LAN=1
  - MIME magic-byte verification (rejecting MZ, ELF, Mach-O, HTML disguised as PDF)
  - AuditLog append-only immutability (UPDATE and DELETE raise PermissionError)
  - Legal hold protection (HTTP 423 Locked gating and purge prevention)
  - Tamper-evident SHA-256 export bundle manifests
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.backend.config import Settings, validate_security_invariants
from src.backend.ingest import validate_file_magic_bytes
from tests.base import KruschLawTestCase
from src.backend.db import Case, AuditLog, MatterEvidence, GroundingReport
from src.backend.crypto import execute_verifiable_purge


class TestSecurityHardening(KruschLawTestCase):

    def test_01_api_key_required_outside_development(self):
        """Verify that server refuses to bind outside dev without API_KEY."""
        s = Settings(APP_ENV="production", API_KEY=None, HOST="127.0.0.1")
        with self.assertRaises(RuntimeError) as ctx:
            validate_security_invariants(s)
        self.assertIn("API_KEY is strictly required", str(ctx.exception))

    def test_02_api_key_accepted_in_production(self):
        """Verify that server starts in production with valid API_KEY."""
        s = Settings(APP_ENV="production", API_KEY="kruschlaw-prod-secret-999", HOST="127.0.0.1")
        validate_security_invariants(s)

    def test_03_refuse_binding_0_0_0_0_without_allow_lan(self):
        """Verify that server refuses to bind 0.0.0.0 unless ALLOW_LAN=1."""
        s = Settings(APP_ENV="development", HOST="0.0.0.0", ALLOW_LAN=False)
        with self.assertRaises(RuntimeError) as ctx:
            validate_security_invariants(s)
        self.assertIn("Refusing to bind to non-loopback host", str(ctx.exception))

    def test_04_allow_lan_binding_with_flag(self):
        """Verify that 0.0.0.0 bind is accepted when ALLOW_LAN=1."""
        s = Settings(APP_ENV="development", HOST="0.0.0.0", ALLOW_LAN=True)
        validate_security_invariants(s)

    def test_05_fail_boot_on_empty_and_default_api_keys_outside_dev(self):
        """Verify that server refuses to boot outside development with empty or default placeholder keys."""
        for bad_key in ("", "   ", "default", "changeme", "secret", "kruschlaw_secret", "replace_me"):
            s = Settings(APP_ENV="production", API_KEY=bad_key, HOST="127.0.0.1")
            with self.assertRaises(RuntimeError) as ctx:
                validate_security_invariants(s)
            self.assertIn("API_KEY is strictly required outside development environment", str(ctx.exception))

    def test_06_mime_magic_rejects_mz_elf_and_html_disguised_pdf(self):
        """Verify that executable magic bytes (MZ, ELF) and HTML disguised as PDF are rejected."""
        # 1. Windows MZ header disguised as PDF and TXT
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00")
            mz_pdf = f.name
        # 2. Linux ELF header disguised as PDF and TXT
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00")
            elf_pdf = f.name
        # 3. HTML disguised as PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"<!DOCTYPE html>\n<html><head><title>Lease</title></head><body><h1>Fake</h1></body></html>")
            html_pdf = f.name
        # 4. Lowercase HTML tag disguised as PDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"<html><body><script>malicious()</script></body></html>")
            script_pdf = f.name
        # 5. Valid PDF header
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.7 \x25\xe2\xe3\xcf\xd3\n")
            valid_pdf = f.name

        try:
            self.assertFalse(validate_file_magic_bytes(mz_pdf, ".pdf"))
            self.assertFalse(validate_file_magic_bytes(mz_pdf, ".txt"))
            self.assertFalse(validate_file_magic_bytes(elf_pdf, ".pdf"))
            self.assertFalse(validate_file_magic_bytes(elf_pdf, ".txt"))
            self.assertFalse(validate_file_magic_bytes(html_pdf, ".pdf"))
            self.assertFalse(validate_file_magic_bytes(script_pdf, ".pdf"))
            self.assertTrue(validate_file_magic_bytes(valid_pdf, ".pdf"))
        finally:
            for p in (mz_pdf, elf_pdf, html_pdf, script_pdf, valid_pdf):
                if os.path.exists(p):
                    os.remove(p)

    def test_07_audit_log_immutability_update_and_delete_raise_permission_error(self):
        """Verify that AuditLog records are append-only; UPDATE and DELETE trigger PermissionError."""
        log = AuditLog(
            action="consult",
            actor_key_hash="hash_12345",
            client_ip="127.0.0.1"
        )
        self.db.add(log)
        self.db.commit()
        log_id = log.id

        # 1. Verify UPDATE fails
        log_fetched = self.db.query(AuditLog).filter_by(id=log_id).first()
        log_fetched.actor_key_hash = "tampered_hash"
        with self.assertRaises(PermissionError) as ctx:
            self.db.commit()
        self.assertIn("AuditLog records are append-only and strictly immutable", str(ctx.exception))
        self.db.rollback()

        # 2. Verify DELETE fails
        log_to_delete = self.db.query(AuditLog).filter_by(id=log_id).first()
        self.db.delete(log_to_delete)
        with self.assertRaises(PermissionError) as ctx:
            self.db.commit()
        self.assertIn("AuditLog records are append-only and strictly immutable", str(ctx.exception))
        self.db.rollback()

    def test_08_legal_hold_blocks_case_purge_and_delete(self):
        """Verify that legal_hold=True blocks soft deletion and verifiable purge with HTTP 423 / PermissionError."""
        import src.backend.config
        auth_hdr = {"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}
        case = Case(
            title="Subpoena Preserved Matter",
            facts="Active Alameda County unlawful detainer litigation.",
            legal_hold=True
        )
        self.db.add(case)
        self.db.commit()
        c_id = case.id

        # 1. Direct crypto purge raises PermissionError
        with self.assertRaises(PermissionError) as ctx:
            execute_verifiable_purge(self.db, c_id)
        self.assertIn("CANNOT_PURGE_LEGAL_HOLD_ACTIVE", str(ctx.exception))

        # 2. API DELETE endpoint returns HTTP 423 Locked
        del_resp = self.client.delete(f"/api/cases/{c_id}", headers=auth_hdr)
        self.assertEqual(del_resp.status_code, 423)
        self.assertIn("active legal hold", del_resp.json()["detail"])

        # 3. API Purge endpoint returns HTTP 423 Locked
        purge_resp = self.client.delete(f"/api/cases/{c_id}/purge", headers=auth_hdr)
        self.assertEqual(purge_resp.status_code, 423)
        self.assertIn("active legal hold", purge_resp.json()["detail"])

    def test_09_legal_hold_toggle_and_release(self):
        """Verify toggling legal hold via POST /api/cases/{id}/legal-hold."""
        import src.backend.config
        auth_hdr = {"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}
        case = Case(
            title="Toggle Legal Hold Matter",
            facts="Investigation matter subject to pending hold.",
            legal_hold=False
        )
        self.db.add(case)
        self.db.commit()
        c_id = case.id

        # 1. Place on legal hold
        h_resp = self.client.post(f"/api/cases/{c_id}/legal-hold", json={"legal_hold": True}, headers=auth_hdr)
        self.assertEqual(h_resp.status_code, 200)
        self.assertTrue(h_resp.json()["legal_hold"])
        self.assertEqual(h_resp.json()["status"], "active")

        # 2. Deletion blocked
        del_resp = self.client.delete(f"/api/cases/{c_id}", headers=auth_hdr)
        self.assertEqual(del_resp.status_code, 423)

        # 3. Release legal hold
        rel_resp = self.client.post(f"/api/cases/{c_id}/legal-hold", json={"legal_hold": False}, headers=auth_hdr)
        self.assertEqual(rel_resp.status_code, 200)
        self.assertFalse(rel_resp.json()["legal_hold"])
        self.assertEqual(rel_resp.json()["status"], "released")

        # 4. Deletion now succeeds
        del_ok = self.client.delete(f"/api/cases/{c_id}", headers=auth_hdr)
        self.assertEqual(del_ok.status_code, 200)

    def test_10_tamper_evident_export_bundle_manifest(self):
        """Verify GET /api/cases/{id}/export-bundle generates SHA-256 evidence bundle."""
        import src.backend.config
        auth_hdr = {"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}
        case = Case(
            title="Export Bundle Matter",
            facts="Lease facts and tenant testimony.",
            legal_hold=True
        )
        self.db.add(case)
        self.db.commit()

        ev = MatterEvidence(
            matter_id=case.id,
            filename="residential_lease.pdf",
            content="Standard 12-month lease agreement."
        )
        self.db.add(ev)
        self.db.commit()

        resp = self.client.get(f"/api/cases/{case.id}/export-bundle", headers=auth_hdr)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["case_id"], case.id)
        self.assertTrue(data["legal_hold"])
        self.assertEqual(data["evidence_count"], 1)
        self.assertIn("bundle_sha256", data)
        self.assertEqual(len(data["bundle_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
