"""
Unit tests for the KruschLaw FastAPI Lego shell migration (INV-LEGO-25).

Verifies:
- Dual-compatible GET /health (INV-LEGO-01 envelope + top-level legacy keys)
- Strict INV-LEGO-01 GET /doctor envelope
- X-Request-ID propagation, X-Response-Time-Ms timing, and X-Content-Type-Options: nosniff
- Dual-compatible HTTPException (401/404/423) and RequestValidationError (422) payloads
- Standalone CI fallback when krusch_toolkit is absent from sys.modules
"""

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.backend.config
import src.backend.main
from src.backend.db import Case
from tests.base import KruschLawTestCase


class TestFastApiLegoShell(KruschLawTestCase):
    """Verify INV-LEGO-25 brownfield FastAPI shell compatibility and standalone CI fallback."""

    def test_01_health_returns_dual_envelope_and_legacy_keys(self):
        """GET /health returns both INV-LEGO-01 envelope fields and top-level legacy fields."""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        # INV-LEGO-01 envelope fields
        self.assertIs(body["ok"], True)
        self.assertEqual(body["tool"], "kruschlaw-backend")
        self.assertEqual(body["summary"], "Service healthy")
        self.assertIsInstance(body["data"], dict)
        self.assertEqual(body["data"]["status"], "healthy")
        self.assertEqual(body["data"]["service"], "kruschlaw-backend")
        self.assertEqual(body["data"]["version"], "0.3.0")

        # Top-level brownfield compatibility fields
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["service"], "kruschlaw-backend")
        self.assertEqual(body["version"], "0.3.0")
        self.assertIsInstance(body["security"], dict)
        self.assertIn("auth_enabled", body["security"])
        self.assertIn("models", body)

        # Direct callable export remains preserved
        direct = src.backend.main.health_check()
        self.assertEqual(direct["status"], "healthy")
        self.assertEqual(direct["service"], "kruschlaw-backend")

    def test_02_health_non_dev_mode_preserves_production_payload(self):
        """GET /health in non-dev mode preserves auth_enforced and air_gap_verified fields."""
        with patch.object(src.backend.config.settings, "ENVIRONMENT", "production"):
            resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIs(body["ok"], True)
        self.assertIs(body["auth_enforced"], True)
        self.assertIn("air_gap_verified", body)
        self.assertIs(body["data"]["auth_enforced"], True)

    def test_03_doctor_returns_strict_inv_lego_01_envelope(self):
        """GET /doctor returns strict INV-LEGO-01 envelope keys without flattened top-level keys."""
        resp = self.client.get("/doctor")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body.keys()), {"ok", "tool", "summary", "data"})
        self.assertIs(body["ok"], True)
        self.assertEqual(body["tool"], "kruschlaw-backend")
        self.assertEqual(body["summary"], "Service healthy")
        self.assertEqual(body["data"]["status"], "healthy")
        self.assertEqual(body["data"]["service"], "kruschlaw-backend")
        self.assertEqual(body["data"]["version"], "0.3.0")

    def test_04_standard_observability_and_security_headers(self):
        """Responses propagate X-Request-ID and emit X-Response-Time-Ms and nosniff headers."""
        custom_id = "req-kruschlaw-trace-001"
        resp = self.client.get("/health", headers={"X-Request-ID": custom_id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Request-ID"), custom_id)
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        elapsed_ms = float(resp.headers.get("X-Response-Time-Ms", "-1"))
        self.assertGreaterEqual(elapsed_ms, 0.0)

        # Auto-generated request ID when omitted
        resp_auto = self.client.get("/doctor")
        self.assertEqual(resp_auto.status_code, 200)
        self.assertTrue(len(resp_auto.headers.get("X-Request-ID", "")) >= 16)
        self.assertEqual(resp_auto.headers.get("X-Content-Type-Options"), "nosniff")

    def test_05_http_exceptions_emit_dual_error_envelope_and_detail(self):
        """401, 404, and 423 HTTPException responses expose both INV-LEGO-01 error and detail."""
        auth_hdr = {"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}

        # 401 Unauthorized (invalid token)
        resp_401 = self.client.get(
            "/api/cases",
            headers={"X-API-Key": "invalid-credential", "X-Request-ID": "err-401"},
        )
        self.assertEqual(resp_401.status_code, 401)
        body_401 = resp_401.json()
        self.assertIs(body_401["ok"], False)
        self.assertEqual(body_401["tool"], "kruschlaw-backend")
        self.assertEqual(body_401["error"]["code"], "UNAUTHORIZED")
        self.assertIn("Unauthorized", body_401["error"]["message"])
        self.assertIn("Unauthorized", body_401["detail"])
        self.assertEqual(resp_401.headers.get("X-Request-ID"), "err-401")
        self.assertEqual(resp_401.headers.get("X-Content-Type-Options"), "nosniff")

        # 404 Not Found
        resp_404 = self.client.get("/api/cases/999999", headers=auth_hdr)
        self.assertEqual(resp_404.status_code, 404)
        body_404 = resp_404.json()
        self.assertIs(body_404["ok"], False)
        self.assertEqual(body_404["error"]["code"], "NOT_FOUND")
        self.assertIn("not found", body_404["error"]["message"].lower())
        self.assertIn("not found", body_404["detail"].lower())

        # 423 Locked (legal hold matter deletion blocked)
        held_case = Case(
            title="Held Litigation Matter",
            facts="Active litigation hold prevents matter deletion.",
            legal_hold=True,
        )
        self.db.add(held_case)
        self.db.commit()

        resp_423 = self.client.delete(f"/api/cases/{held_case.id}", headers=auth_hdr)
        self.assertEqual(resp_423.status_code, 423)
        body_423 = resp_423.json()
        self.assertIs(body_423["ok"], False)
        self.assertEqual(body_423["error"]["code"], "LOCKED")
        self.assertIn("active legal hold", body_423["error"]["message"])
        self.assertIn("active legal hold", body_423["detail"])

    def test_06_validation_error_emits_422_dual_envelope_and_detail(self):
        """422 RequestValidationError emits VALIDATION_ERROR envelope alongside legacy detail list."""
        auth_hdr = {"X-Session-Token": src.backend.config.settings.LOCAL_SESSION_TOKEN}
        resp_422 = self.client.post(
            "/api/cases",
            json={"title": "X", "facts": "short"},
            headers=auth_hdr,
        )
        self.assertEqual(resp_422.status_code, 422)
        body_422 = resp_422.json()
        self.assertIs(body_422["ok"], False)
        self.assertEqual(body_422["tool"], "kruschlaw-backend")
        self.assertEqual(body_422["error"]["code"], "VALIDATION_ERROR")
        self.assertIsInstance(body_422["error"]["details"], list)
        self.assertIsInstance(body_422["detail"], list)
        self.assertGreater(len(body_422["detail"]), 0)
        self.assertEqual(resp_422.headers.get("X-Content-Type-Options"), "nosniff")

    def test_07_standalone_ci_fallback_without_krusch_toolkit(self):
        """Module loads and serves identical contracts when krusch_toolkit is absent in sys.modules."""
        main_file = os.path.abspath(src.backend.main.__file__)
        temp_mod_name = "src.backend._standalone_fallback_test"

        blocked_modules = {
            "krusch_toolkit": None,
            "krusch_toolkit.fastapi_app": None,
        }
        try:
            with patch.dict(sys.modules, blocked_modules):
                spec = importlib.util.spec_from_file_location(temp_mod_name, main_file)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                fallback_mod = importlib.util.module_from_spec(spec)
                sys.modules[temp_mod_name] = fallback_mod
                spec.loader.exec_module(fallback_mod)

            self.assertIs(
                fallback_mod.create_fastapi_app,
                fallback_mod._build_standalone_fastapi_app,
            )

            def override_fallback_db():
                db_session = self.Session()
                try:
                    yield db_session
                finally:
                    db_session.close()

            fallback_mod.app.dependency_overrides[fallback_mod.get_db] = override_fallback_db
            fb_client = TestClient(fallback_mod.app, raise_server_exceptions=False)

            # 1. /health flattened + envelope
            h_resp = fb_client.get("/health", headers={"X-Request-ID": "fb-req-1"})
            self.assertEqual(h_resp.status_code, 200)
            self.assertEqual(h_resp.headers.get("X-Request-ID"), "fb-req-1")
            self.assertEqual(h_resp.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("X-Response-Time-Ms", h_resp.headers)
            h_body = h_resp.json()
            self.assertIs(h_body["ok"], True)
            self.assertEqual(h_body["status"], "healthy")
            self.assertEqual(h_body["data"]["status"], "healthy")

            # 2. /doctor strict envelope
            d_resp = fb_client.get("/doctor")
            self.assertEqual(d_resp.status_code, 200)
            self.assertEqual(set(d_resp.json().keys()), {"ok", "tool", "summary", "data"})

            # 3. 422 validation + 423 locked + 500 unhandled exception + wildcard CORS clamp
            wildcard_app = fallback_mod.create_fastapi_app(
                title="Fallback Wildcard Check",
                version="0.3.0",
                service_name="fallback-check",
                cors_origins=["*"],
                allow_credentials=True,
                legacy_error_detail=True,
            )

            @wildcard_app.get("/locked-err")
            def _raise_locked():
                raise HTTPException(status_code=423, detail="Resource locked")

            @wildcard_app.get("/boom")
            def _raise_unhandled():
                raise RuntimeError("boom")

            wc_client = TestClient(wildcard_app, raise_server_exceptions=False)

            cors_resp = wc_client.get("/health", headers={"Origin": "http://example.local"})
            self.assertEqual(cors_resp.headers.get("access-control-allow-origin"), "*")
            self.assertNotIn("access-control-allow-credentials", cors_resp.headers)

            locked_resp = wc_client.get("/locked-err")
            self.assertEqual(locked_resp.status_code, 423)
            self.assertEqual(locked_resp.json()["error"]["code"], "LOCKED")
            self.assertEqual(locked_resp.json()["detail"], "Resource locked")

            boom_resp = wc_client.get("/boom")
            self.assertEqual(boom_resp.status_code, 500)
            self.assertEqual(boom_resp.json()["error"]["code"], "INTERNAL_ERROR")
            self.assertIs(boom_resp.json()["ok"], False)
        finally:
            sys.modules.pop(temp_mod_name, None)


if __name__ == "__main__":
    unittest.main()
