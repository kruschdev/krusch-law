# 📓 Changelog

All notable changes to **KruschLaw** are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] - 2026-09-25

### 🚀 Added
- **Authoritative Invariants Specification**: Published `docs/INVARIANTS.md` establishing a formal pass/fail regression test matrix across 10 core architectural invariants.
- **Zero-Dependency Headless Demo**: Added `data/demo.db` pre-seeded SQLite fixture with `HEADLESS_MODE=1` support and `scripts/demo_60s.py` executing statutory preemption DAG traversal, temporal gating, and proposition grounding in under 0.10s without Ollama, PostgreSQL, or GPU dependencies.
- **Property-Based Grounding Mutation Suite**: Published `tests/unit/test_grounding_properties.py` verifying that proposition grounding checkers flip deterministically on statutory timelines, cap units, duty polarities, stale citations, and fabricated sections.
- **Graph Invariant Suite**: Published `tests/test_graph_invariants.py` enforcing confirmed-edge only precedence, temporal as-of date validity, cycle detection fail-closed, and honest coverage holes.
- **Pre-Spool MIME Magic-Byte Filter**: Added `validate_file_magic_bytes` and `virus_scan_hook` in `src/backend/ingest.py`, checking bytes 0-512 to reject PE (`MZ`), ELF, Mach-O, and HTML disguised as matter evidence PDF/DOCX files.
- **Append-Only Immutable Audit Trail**: Configured SQLAlchemy event listeners on `AuditLog` intercepting `before_update` and `before_delete` to enforce cryptographic immutability.
- **Legal Hold State Machine & 423 Locked Gating**: Added `legal_hold` attribute to `Case` model, blocking deletion and verifiable purge operations with `HTTP 423 Locked`. Added `GET /api/cases/{case_id}/export-bundle` for chain-of-custody archive generation.
- **Strict Data Residency & Host Validation**: Added `APP_ENV`, `HOST`, `ALLOW_LAN`, `is_strict_loopback()`, and `validate_security_invariants()` in `src/backend/config.py` enforcing strict loopback binding and mandatory API key outside development mode.
- **Database-Level Relational Constraints**: Added check constraints on `StatuteRelation` (`ck_statute_relation_not_self`, `ck_statute_relation_type`, `ck_statute_relation_status`) and reviewer auto-population validation.
- **Corpus License & Data Provenance**: Published `data/CORPUS_LICENSE.md` certifying public domain California/Oakland statutory origin and synthetic evaluation fixtures with zero confidential client data.

### 🛡️ Changed
- **Excised Substring Fallback**: Removed arbitrary keyword/ILIKE fallback search from the controlling precedence path in `resolve_controlling_law`. Uncovered doctrines return an explicit `CoverageHole` object rather than promoting unrelated statutes.
- **Hardened Temporal Preemption & Amendment Traversal**: Hardened Check 4C (historical lookback) and Check 4A (future preemption gating) in `src/backend/resolver.py` to ensure that future amendments and modern preemption statutes (such as AB 12) cannot retroactively govern past inquiry dates.
- **Enhanced Pass B Entailment Verification**: Expanded numeric word normalization (`three months` -> `3`) and duty negation pattern matching (`without any prior notice`) in `src/backend/rag.py`.

---

## [0.3.0] - 2026-08-15
### Added
- Statutory precedence DAG traversal and multi-hop authority hierarchy resolver.
- Two-Pass assertion grounding checker (Pass A mechanical + Pass B propositional entailment).
- Sovereign legal intelligence REST API and Streamlit user interface.
