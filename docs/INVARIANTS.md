# 🛡️ KruschLaw Core Invariants & Pass/Fail Test Matrix

> **Authoritative Specification**: This document establishes the non-negotiable architectural invariants of KruschLaw. Every invariant is paired with deterministic, pass/fail automated regression tests.

---

## 📋 The Invariants Matrix

| # | Invariant Name | Failure Mode if Violated | Enforcing Test(s) | Status |
|---|---|---|---|---|
| **INV-1** | **Confirmed-Edge Only** | Proposed/unconfirmed relations silently alter controlling law or preemption DAG traversal | `tests/test_graph_invariants.py::TestGraphInvariants::test_01_confirmed_edge_invariant`<br>`tests/test_statute_relations.py` | ✅ PASS |
| **INV-2** | **Temporal As-Of Date Validity** | Modern amendments retroactively misapplied to past events, or repealed rules applied to modern disputes | `tests/test_graph_invariants.py::TestGraphInvariants::test_02_temporal_amendment_gating_invariant`<br>`tests/eval/test_conflict_pairs.py` | ✅ PASS |
| **INV-3** | **Cycle Detection & Fail-Closed** | Circular preemption or amendment loops (A → B → C → A) cause infinite recursion crashes | `tests/test_graph_invariants.py::TestGraphInvariants::test_03_cycle_detection_fail_closed`<br>`tests/unit/test_resolver.py` | ✅ PASS |
| **INV-4** | **No Silent Keyword Promotion** | Keyword/lexical match promotes arbitrary unrelated statute when authoritative doctrine is missing | `tests/test_graph_invariants.py::TestGraphInvariants::test_04_no_silent_keyword_promotion`<br>`tests/unit/test_resolution_trace.py` | ✅ PASS |
| **INV-5** | **Relational Check Constraints** | Self-referential relations, invalid relationship types, or unreviewed confirmed edges stored in DB | `tests/test_graph_invariants.py::TestGraphInvariants::test_05_statute_relation_database_check_constraints` | ✅ PASS |
| **INV-6** | **Canonical Grounding Taxonomy** | Hallucinated slots, timeline mutations, duty inversions, or stale citations pass verification silently | `tests/unit/test_grounding_properties.py (5/5 property tests)`<br>`tests/unit/test_assertion_grounding.py (7/7 tests)` | ✅ PASS |
| **INV-7** | **Immutable Append-Only Audit** | Administrative tampering or deletion of historical case audit events or advice trace records | `tests/test_security_hardening.py::TestSecurityHardening::test_04_audit_log_append_only` | ✅ PASS |
| **INV-8** | **Pre-Spool Magic-Byte Gate** | Polyglot files, executable binaries (PE/ELF/Mach-O), or HTML disguised as matter evidence PDFs | `tests/test_security_hardening.py::TestSecurityHardening::test_03_magic_byte_rejection_pre_spool` | ✅ PASS |
| **INV-9** | **Legal Hold & 423 Locked Gating** | Case records subject to litigation hold deleted or purged; chain-of-custody export unavailable | `tests/test_security_hardening.py (test_05, test_06, test_07)` | ✅ PASS |
| **INV-10** | **Strict Loopback Residency** | Orchestrator processes bind externally; API key requirements bypassed outside local development | `tests/test_security_hardening.py (test_01, test_02)` | ✅ PASS |

---

## 🔍 Detailed Invariant Specifications

### INV-1: Confirmed-Edge Only Precedence
* **Requirement**: The relation extraction pipeline may propose edges with `status='proposed'`. The precedence resolver (`resolve_controlling_law`) **must strictly quarantine** unconfirmed relations.
* **Behavior**: Unconfirmed proposals emit an explicit high-visibility advisory:
  `> ⚠️ **CONTROLLING STATUTE UNCERTAIN; N proposed preemption/amendment link(s) pending human attorney review.**`
  They never alter the controlling authority walk until admitted counsel reviews and confirms the edge.
* **Verification Command**:
  ```bash
  pytest tests/test_graph_invariants.py -k "test_01_confirmed_edge_invariant"
  ```

### INV-2: Temporal As-Of Date Validity
* **Requirement**: Legal resolution must evaluate statutory authority strictly as of the matter incident date (`as_of_date`).
* **Behavior**:
  - Inquiries prior to July 1, 2024 evaluate Civil Code § 1950.5 under the historical 2-month security deposit cap.
  - Inquiries on or after July 1, 2024 evaluate Civil Code § 1950.5 under Assembly Bill 12 (Stats. 2023, ch. 290) capping deposits at 1 month's rent.
  - Future statutes or amendments cannot preempt or govern prior incident dates before their statutory effective date.
* **Verification Command**:
  ```bash
  pytest tests/test_graph_invariants.py -k "test_02_temporal_amendment_gating_invariant"
  ```

### INV-3: Cycle Detection & Fail-Closed Precedence
* **Requirement**: Any circular reference in `PREEMPTS`, `AMENDS`, or `SUPERSEDES` relations must terminate deterministically without stack overflow.
* **Behavior**: The resolver maintains a visited node set and enforces a strict `depth_cap` (default: 32). Upon cycle detection, it halts recursion, logs a diagnostic warning, and returns the highest-ranking valid statutory ancestor.
* **Verification Command**:
  ```bash
  pytest tests/test_graph_invariants.py -k "test_03_cycle_detection_fail_closed"
  ```

### INV-4: No Silent Keyword Promotion
* **Requirement**: Controlling legal authority selection is an authority hierarchy and DAG walk, **never** a lexical substring or ungrounded BM25 fallback.
* **Behavior**: If a topic is unindexed in the authoritative corpus, `resolve_controlling_law` returns `controlling_node = None` with an explicit `CoverageHole` object and `confidence_score = 0.0`. It suppresses semantic vector neighbors to prevent inventing law.
* **Verification Command**:
  ```bash
  pytest tests/test_graph_invariants.py -k "test_04_no_silent_keyword_promotion"
  ```

### INV-5: Database-Level Relational Check Constraints
* **Requirement**: Relational integrity of the statutory graph must be guaranteed at the database schema level.
* **Behavior**:
  - `ck_statute_relation_not_self`: `source_statute != target_statute`
  - `ck_statute_relation_type`: `relation_type IN ('PREEMPTS', 'AMENDS', 'SUPERSEDES', 'CARVES_OUT', 'EXEMPTS_FROM', 'IMPLEMENTS', 'CREATES')`
  - `ck_statute_relation_status`: `status IN ('proposed', 'confirmed', 'rejected')`
  - Transitioning an edge to `confirmed` requires a non-null `reviewed_by` attribute (auto-populated by attorney session if omitted).
* **Verification Command**:
  ```bash
  pytest tests/test_graph_invariants.py -k "test_05_statute_relation_database_check_constraints"
  ```

### INV-6: Canonical Two-Pass Grounding Verification
* **Requirement**: Every generated legal assertion must pass mechanical verification (Pass A) and propositional entailment (Pass B).
* **Behavior**:
  - Fabricated section citations absent from corpus fail with `invented_citation` / `not_in_corpus`.
  - Repealed or superseded citations fail with `stale_law`.
  - Mutated timeline periods (e.g., 45 days instead of 21 days for security deposit accounting under § 1950.5) fail with `wrong_proposition` / `contradicted`.
  - Duty negations (e.g., entering without statutory 24-hr written notice under § 1954) fail with `wrong_proposition` / `contradicted`.
* **Verification Command**:
  ```bash
  pytest tests/unit/test_grounding_properties.py
  ```

### INV-7: Append-Only Immutable Audit Trail
* **Requirement**: Compliance records, case access events, and purge logs must be cryptographically durable and tamper-evident.
* **Behavior**: SQLAlchemy event listeners intercept `before_update` and `before_delete` on `AuditLog` and raise `PermissionError("AuditLog records are append-only and cannot be modified or deleted.")`.
* **Verification Command**:
  ```bash
  pytest tests/test_security_hardening.py -k "test_04_audit_log_append_only"
  ```

### INV-8: Pre-Spool MIME Magic-Byte Verification
* **Requirement**: Reject executable payloads, polyglots, and disguised scripts before writing files to persistent storage.
* **Behavior**: Validates file headers within the first 512 bytes prior to disk spooling:
  - Rejects Windows PE (`MZ`), Linux ELF (`\x7fELF`), macOS Mach-O binaries.
  - Rejects HTML masquerading as court evidence or lease PDF files (`<html`, `<!doctype`, `<script`).
  - Accepts authentic PDF (`%PDF-`) and DOCX (`PK\x03\x04`).
* **Verification Command**:
  ```bash
  pytest tests/test_security_hardening.py -k "test_03_magic_byte_rejection_pre_spool"
  ```

### INV-9: Legal Hold State Machine & 423 Locked Gating
* **Requirement**: Matters flagged for preservation under pending litigation must be protected from accidental or intentional destruction.
* **Behavior**:
  - `Case.legal_hold = True` blocks all deletion and verifiable purge endpoints with `HTTP 423 Locked`.
  - Case metadata and evidence files can be cryptographically verified and exported via `GET /api/cases/{case_id}/export-bundle`.
* **Verification Command**:
  ```bash
  pytest tests/test_security_hardening.py -k "legal_hold"
  ```

### INV-10: Strict Loopback Residency & Security
* **Requirement**: Central orchestrator and API services must maintain air-gapped sovereignty.
* **Behavior**:
  - The application strictly binds to `127.0.0.1` or `::1` (`is_strict_loopback()`).
  - Outside development mode (`APP_ENV != 'development'`), an API key (`settings.API_KEY`) is strictly mandatory.
* **Verification Command**:
  ```bash
  pytest tests/test_security_hardening.py -k "test_01_api_key_required_outside_development or test_02_strict_loopback_binding_enforced"
  ```
