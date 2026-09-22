# Security & Privacy Policy

## 🔒 Commitment to Privacy & Confidentiality

KruschLaw is specifically engineered for high-stakes environments where attorney-client privilege, work-product doctrine, and data confidentiality must be preserved without compromise.

* **Zero External Telemetry**: KruschLaw contains no telemetry, analytics beacons, or remote logging services.
* **100% Local Inference**: All embeddings and generative reasoning occur exclusively via your local Ollama instance or on-premise inference server.
* **On-Premise Vector Database**: All matter facts and law vectors are stored within your local PostgreSQL instance and never synchronized to cloud caches.

---

## 🛡️ Production Deployment Hardening

For law offices and corporate environments seeking maximal isolation:

1. **Localhost Network Binding**: Ports in `docker-compose.yml` bind strictly to `127.0.0.1` by default (`DATABASE_BIND_IP`, `BACKEND_BIND_IP`, `FRONTEND_BIND_IP`), preventing unauthenticated LAN exposure. If remote access is required, deploy an authenticated TLS reverse proxy (e.g., Caddy or Nginx with client certs / OAuth).
2. **Offline Web Application**: The web dashboard is engineered with zero CDN dependencies. Web fonts rely exclusively on the client's local system typography stack, eliminating external HTTP requests upon page load.
3. **Ingest Directory Sandboxing**: Parquet dataset ingestion enforces directory whitelist validation (`ALLOWED_INGEST_DIRS`), preventing path traversal or unauthorized local file exposure.
4. **Credential Rotation**: Never use default passwords. Generate strong, unique credentials for `POSTGRES_PASSWORD` in `.env`.
5. **Firewall / Egress Filtering**: For true air-gapping, enforce an operator egress firewall policy (`ufw default deny outgoing`) or Docker internal network isolation. The application operates 100% offline.
6. **Volume Encryption**: Deploy persistent database volumes on an encrypted storage volume (LUKS on Linux, FileVault on macOS, or BitLocker on Windows).


---

## 🚨 Reporting a Vulnerability

If you identify a security vulnerability or potential data leakage risk in KruschLaw:

1. Please do **NOT** disclose the vulnerability in public GitHub issues.
2. Email the maintainer directly with reproduction steps and risk assessment.
3. We will acknowledge receipt within 48 hours and work with you on a coordinated fix.
