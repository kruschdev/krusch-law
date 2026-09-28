# 📓 Changelog

All notable changes to **KruschLaw** are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-09-28

### 🚀 Added
- **Dual-Provider RAG Substrate (`src/backend/nexus_rag.py`)**: Wired KruschLaw into the swappable retrieval substrate via `NexusClient`. Supports `RAG_PROVIDER="local"` (PostgreSQL pgvector / SQLite) and `RAG_PROVIDER="nexus"` / `"wondersearch"` (Wondersearch Cloud Drives) with zero code changes in the statutory resolution engine.
- **Physical Coordinates Preserved (INV-11)**: Propagates bounding boxes (`bbox: [x0, y0, w, h]`), 1-based page numbers (`page_number`), and character slice offsets (`char_start`, `char_end`) bit-for-bit from Wondersearch SearchHit models directly into downstream proposition grounders and litigation exhibit highlighters.
- **Air-Gap Invariant Gate**: Explicitly enforces `ALLOW_CLOUD=1` before connecting to cloud Wondersearch backends, failing closed with `AirGapViolationError` to prevent inadvertent legal data leakage.
- **Unit Test Coverage (`tests/test_nexus_rag_provider.py`)**: Added 5 automated unit tests verifying law search routing, matter evidence isolation, and air-gap exception gating (159 passing tests total).

---

## [0.7.0] - 2026-09-27

### 🚀 Added
- **Tenant Rent Cap & Notice Defense Workflows**: Added Defense 7 (`Unlawful Rent Increase & Statutory Rent Cap Violation`), Defense 8 (`No-Fault Eviction & Mandatory Relocation Assistance Compliance`), and Defense 9 (`Curable Lease Breach & Mandatory Opportunity to Cure`) to `generate_defense_checklist` with pinpoint statutory citations and verified remedies.
- **Formal Statutory Letter Templates**: Added 5th template (`unlawful_rent_increase_objection`) and 6th template (`no_fault_relocation_demand`) to `assemble_statutory_letter`, enforcing advance notice timelines (Civ. Code § 827 30/90 days + CCP § 1013 mail extension) and strict relocation compliance voiding mandates (Civ. Code § 1946.2(d)(4) / Oakland OMC § 8.22.360).
- **Substantive Conflict Detector Hardening**: Added Conflict 8 (Rent increase cap violations exceeding 5% + CPI or 10% maximum), Conflict 9 (Rent increase notice period shortfall), and Conflict 10 (No-fault relocation assistance payment default voiding termination notice) to `detect_legal_conflicts`.
- **California Statutory Corpus Expansion**: Added Cal. Civ. Code § 1947.12 (Tenant Protection Act Rent Cap), Cal. Civ. Code § 827 (Notice Requirements for Terms & Rent Increases), Cal. Civ. Code § 1942.5 (Retaliatory Eviction Prohibition), and Cal. Civ. Code § 789.3 (Self-Help Lockout Prohibition) to `SEED_CALIFORNIA_ORDINANCES`, complete with physical citation spine coordinates and traceability fixtures.
- **Rebuilt Offline Fixture `data/demo.db`**: Regenerated frozen SQLite demo database (663,552 bytes) with 20 California and municipal statutes with full coordinate geometry and 0.068s headless demo speed.
- **Test Suite Expansion**: Added 5 new regression and conflict-pair tests across `test_defense_checklist_and_letter.py` and `test_conflict_pairs.py`, increasing KruschLaw's test suite to 156 / 156 passing tests.

---

## [0.6.0] - 2026-09-27

### 🚀 Added
- **Physical Citation Spine Coordinates (INV-11)**: Integrated physical document layout geometry (`page_number`, `printed_page`, `bbox` `[x0, y0, x1, y1]`, `char_start`, `char_end`, `extra_metadata`) across `LawVector`, `MatterEvidence`, KruschNexus chunk ingestion, and hybrid RAG retrieval.
- **Harmonized Floor vs. Ceiling Preemption (INV-12)**: Formalized regulatory floor vs ceiling doctrines in `STATEWIDE_PREEMPTION_REGISTRY`. Statewide floors (AB 1482 Cal. Civ. Code § 1946.2 & § 1947.12) preserve stricter local municipal ordinances (e.g., Oakland RAP OMC § 8.22) under the `HARMONIZED_FLOOR_RULE`. Statewide ceilings (Costa-Hawkins Civ. Code § 1954.52) preempt local rent caps on exempt units.
- **Length-Descending Word-Numeral Parity**: Implemented sorted word-numeral replacement in `extract_statutory_slots` ensuring compound numbers ("twenty-one calendar days", "twenty-four hours", "three court days", "one hundred dollars per day") achieve exact quantitative parity with numeric digits.
- **Landlord Unlawful Entry & Tenant Harassment Category**: Added 6th defense category to `generate_defense_checklist` with pinpoint statutory citations (§ 1954(d)(1) 24-hr notice, § 1954(b) normal business hours, § 1940.2(b) $2,000 harassment civil penalties).
- **Statutory Entry Objection Letter**: Added 4th formal demand letter template (`landlord_entry_objection`) in `assemble_statutory_letter` enforcing mandatory notice restrictions and statutory quiet enjoyment rights.
- **Decrypted Client Evidence Grounding**: Added automatic Fernet decryption when evaluating `MatterEvidence` during defense checklist generation and statutory letter drafting, preventing encrypted text blindness.
- **Comprehensive Regression Tests**: Added property tests for numeric word-digit equivalence, physical coordinate preservation, floor vs ceiling preemption, and encrypted evidence defense spotting, increasing test suite to 151 / 151 passing tests (12/12 verified invariants).

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
