# Security & Privacy Policy

## 🔒 Commitment to Privacy & Confidentiality

KruschLaw is specifically engineered for high-stakes environments where attorney-client privilege, work-product doctrine, and data confidentiality must be preserved without compromise.

* **Zero External Telemetry**: KruschLaw contains no telemetry, analytics beacons, or remote logging services.
* **100% Local Inference**: All embeddings and generative reasoning occur exclusively via your local Ollama instance or on-premise inference server.
* **On-Premise Vector Database**: All matter facts and law vectors are stored within your local PostgreSQL instance and never synchronized to cloud caches.

---

## 🛡️ Production Deployment Hardening

For law offices and corporate environments seeking maximal isolation:

1. **Firewall / Egress Filtering**: Configure your host or container firewall (`iptables` / `ufw`) to block all outbound WAN traffic from the KruschLaw containers. The system functions entirely offline.
2. **Credential Rotation**: Never use default passwords. Generate strong, unique credentials for `POSTGRES_PASSWORD` in `.env`.
3. **Network Binding**: Ensure `docker-compose.yml` port mappings bind strictly to `127.0.0.1` or your private VPN interface (e.g. `127.0.0.1:8505:8501`) rather than `0.0.0.0` if deployed on a multi-tenant network.
4. **Volume Encryption**: Deploy the Docker volumes on an encrypted file system (LUKS on Linux, FileVault on macOS, or BitLocker on Windows).

---

## 🚨 Reporting a Vulnerability

If you identify a security vulnerability or potential data leakage risk in KruschLaw:

1. Please do **NOT** disclose the vulnerability in public GitHub issues.
2. Email the maintainer directly with reproduction steps and risk assessment.
3. We will acknowledge receipt within 48 hours and work with you on a coordinated fix.
