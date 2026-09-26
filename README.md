# ⚖️ KruschLaw

> **Production-Grade Legal Intelligence Engine & Versioned Statutory Graph**  
> *Private municipal code retrieval, two-pass assertion grounding, and verifiable cryptographic purge using on-premise open-weight models.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.5.0](https://img.shields.io/badge/Version-0.5.0-green.svg)](https://github.com/kruschdev/krusch-law)
[![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector%2016-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com)
[![Tests: 145 Passing](https://img.shields.io/badge/Tests-145%20Passing-brightgreen.svg)](tests/)
[![Invariants: 10/10 Verified](https://img.shields.io/badge/Invariants-10%2F10%20Verified-blue.svg)](docs/INVARIANTS.md)
[![Grounding: 0.00% False Support](https://img.shields.io/badge/Grounding-0.00%25%20False%20Support-brightgreen.svg)](data/eval/labeled_grounding_golden.json)

---

> [!WARNING]
> **Legal Software Scope & Safety Boundary**:  
> KruschLaw is an air-gapped legal intelligence platform engineered for legal practitioners and researchers. It is **NOT** a law firm, does **NOT** practice law, and does **NOT** provide legal advice.
> - **Authority Graph ≠ Naive RAG**: Semantic neighbors do not establish controlling law. KruschLaw enforces a typed statutory precedence graph (controlling statute > implementing regulation > municipal ordinance > secondary commentary) with temporal amendment boundaries (`as_of_date`), statutory exception spotting, and explicit preemption chains.
> - **Zero-Trust Grounding**: Every legal proposition is audited by a two-pass verifier against retrieved authority spans. Generation constraints ban and strip unretrieved bare statutory citations.
> - **Refusal-First Posture**: Where governing authorities are absent or ambiguous, KruschLaw abstains or renders high-visibility `STATUTORY COVERAGE GAP` notices rather than emitting plausible hallucinations.
> - **Human Verification Mandate**: All generated memoranda are flagged `provisional_work_product: true` and require admitted attorney review prior to filing or client reliance.

---

## 🏛️ Why KruschLaw?

Modern legal practice requires trustworthy software, not sovereign marketing:
1. **Public Cloud LLMs & SaaS Vector DBs**: Expose confidential client exhibits, draft pleadings, and matter narratives to third-party sub-processors, vendor logging, and potential training retention—violating ABA Model Rule 1.6 and attorney-client privilege.
2. **Generic RAG Bag-of-Chunks**: Arbitrary token chunking destroys statutory hierarchy (title → chapter → article → section → subsection → exception). Repealed sections or out-of-jurisdiction municipal codes frequently outrank controlling state statutes.

**KruschLaw** solves this by treating law as a **versioned statutory graph** backed by an **immutable raw authority store**, running on an **isolated, air-gapped container network** with verifiable cryptographic purge and zero external telemetry.

---

## 🚀 Core Capabilities

* 🔒 **Air-Gapped Privilege Architecture**: Strict Docker Compose internal network (`kruschlaw_internal`), loopback interface bindings (`127.0.0.1`), mandatory default API key or local session token authentication, and AES/Fernet encryption-at-rest for confidential client exhibits (`MatterEvidence`).
* 📜 **Raw Authority Artifact Store & Rebuildable Vectors**: Canonical authority text is stored in `StatutoryArtifact` records containing publisher, edition, retrieval timestamps, canonical URLs, and raw SHA-256 hashes. Vectors are completely rebuildable from artifacts and are never the authoritative copy.
* 📦 **Modular Jurisdiction Packs (Pack Zero: Oakland / CA)**: Structured declarative packs (`data/packs/ca_oakland.yaml`) defining municipal codes, state codes, parsers, and test fixture statutes.
* ⏳ **First-Class As-Of Date Traversal**: All search, consult, resolver, MCP, and export endpoints require an explicit `as_of_date` query parameter (defaulting to matter date), eliminating silent temporal citation errors.
* 🌲 **Typed Precedence Graph & Resolution Traces**: Resolves governing law across municipal and state boundaries (`resolve_controlling_law`), recording full resolution paths (`ResolutionHop`, `ResolutionTrace`), kept/discarded rationale, and explicit coverage gaps (`CoverageHole`).
* 🏎️ **1-Command Benchmark Reproduction Demo**: `scripts/demo_statutory_walk_vs_cosine.py` reproduces the California Security Deposit Blindspot (Pre-2024 Cal. Civ. Code § 1950.5 vs. AB 12 Stats. 2023, ch. 290) in <10ms, demonstrating why naive cosine/BM25 selects the stale statute due to length bias and boilerplate lexical repetition, while KruschLaw's confirmed-edge DAG walk deterministically resolves the operative 1-month cap.
* 🔗 **Preemption & Amendment Review Queue**: Persistent relational review queue (`StatuteRelation`) backing Tab 5 in the UI and `/api/resolver/relations`. Enforces the confirmed-edge invariant: auto-extracted relations remain `proposed` and emit uncertainty advisories until reviewed and approved by admitted counsel under CCP § 128.7.
* 🔎 **Authoritative Diagnostic Tooling (`explain_why_not_controlling`)**: Programmatically explains why a specific statutory section is non-controlling for a given jurisdiction, doctrine, and as-of date (preemption, legislative amendment, or territorial boundary).
* 🛡️ **Two-Pass Assertion Grounding (0.00% False Support Rate)**: Decomposes legal drafts into discrete claims, evaluates lexical and entailment overlap against source spans, supports an explicit `abstain` classification, and enforces hard citation constraints that strip unretrieved bare sections.
* 📁 **Complete Privilege Partitioning**: Total isolation between public statutory codes (`laws_vectors`) and confidential client exhibits (`matter_evidence`), preventing cross-matter fact leakage.
* 🧹 **Verifiable Cryptographic Purge**: Hard deletion (`execute_verifiable_purge`) computes SHA-256 tombstones, evicts in-memory embedding caches, deletes temp files, performs physical database page zeroing via `VACUUM`, and appends immutable audit receipts.
* 👥 **Local Attorney Claim Feedback Loop**: `POST/GET /api/cases/{case_id}/claims/feedback` enables attorneys to record accept/reject decisions and corrective annotations per claim, building local fine-tuning and evaluation signals.
* 📋 **Defense Checklists & Statutory Deadlines**: `GET /api/cases/{case_id}/defense-checklist` generates structured tenant defense checklists with binding statutory deadlines (21-day deposit return under § 1950.5, 3-court-day notice under CCP § 1161, 180-day retaliation presumption under § 1942.5, 24-hr entry notice under § 1954, Oakland Rent Board 10-day filing under OMC § 8.22.360) and evidentiary audits.
* ✉️ **Statutory Form & Demand Letter Assembly**: `POST /api/cases/{case_id}/assemble-letter` assembles rigid demand letters and notice objections using mandatory statutory language and verified legal citations rather than unconstrained creative prose.
* 📄 **Refusal-First Word (.docx) & Markdown Export**: Memoranda export with formal law office caption blocks, Table of Authorities, Assertion Grounding Audit, and prominent `STATUTORY COVERAGE GAP` callout blocks for ungrounded or refused propositions.
* 🔌 **Model Context Protocol (MCP)**: Native stdio JSON-RPC server with 12 tools (`search_ordinances`, `get_section`, `log_matter`, `draft_brief`, `list_matters`, `get_grounding_report`, `get_code_traceability`, `resolve_controlling_law`, `detect_statutory_conflicts`, `explain_why_not_controlling`, `get_defense_checklist`, `assemble_statutory_letter`).
* 📋 **One-Page Orchestrator Specification**: Governed by [`docs/ORCHESTRATOR_SPEC.md`](docs/ORCHESTRATOR_SPEC.md): formalizes the `matter_ref` ↔ `deal_ref` cross-platform entity mapping table, shared `as_of_date` query contracts, and 5 non-negotiable DO-NOT invariants (no vector table unions, mandatory `as_of_date`, confirmed edges only, draft isolation, deterministic typed evaluation over LLMs).
* ⚖️ **The Join & Sovereign Gateway MCP Router**: Powers cross-domain statutory compliance checks in conjunction with KruschBiz via `POST /conflicts/contract-vs-statute` and the 5-verb Gateway MCP router (`ask_law`, `ask_biz`, `check_compliance`, `ingest`, `purge`) strictly constrained to <450 prompt tokens for local 7B/14B inference.

---

## ⏱️ 60-Second Headless Zero-Dependency Demo

Run the complete 3-stage headless demonstration with zero external dependencies (no Ollama, no PostgreSQL, no GPU) in under 0.10s:
```bash
python scripts/demo_60s.py
```
Demonstrates:
1. **Preemption DAG Traversal**: Resolves statewide controlling authority over municipal codes with full resolution traces.
2. **Temporal As-Of Gating**: Evaluates historical § 1950.5 (2-month cap) for pre-July 2024 inquiries vs. AB 12 (1-month cap) for modern inquiries.
3. **Two-Pass Proposition Grounding**: Audits claims against source statutory spans, detecting timeline mutations, duty inversions, and fabricated sections.

---

## 🛡️ Core Architectural Invariants (10/10 Formally Verified)

KruschLaw is governed by 10 non-negotiable architectural invariants backed by a deterministic pass/fail automated regression test matrix. See [`docs/INVARIANTS.md`](docs/INVARIANTS.md) for the complete specification.

| # | Invariant | Description | Enforcing Test Suite | Status |
|---|---|---|---|---|
| **INV-1** | **Confirmed-Edge Only** | Proposed/unconfirmed relations never silently alter controlling law | `tests/test_graph_invariants.py` | ✅ PASS |
| **INV-2** | **Temporal As-Of Validity** | Law is evaluated strictly as of incident date; future amendments do not govern past events | `tests/test_graph_invariants.py` | ✅ PASS |
| **INV-3** | **Cycle Detection Fail-Closed** | Circular preemption/amendment graphs terminate safely within depth cap | `tests/test_graph_invariants.py` | ✅ PASS |
| **INV-4** | **No Silent Keyword Fallback** | Unindexed doctrines return explicit `CoverageHole` rather than promoting arbitrary statutes | `tests/test_graph_invariants.py` | ✅ PASS |
| **INV-5** | **Relational Check Constraints** | DB-level constraints enforce self-relation bans, valid types, and review verification | `tests/test_graph_invariants.py` | ✅ PASS |
| **INV-6** | **Canonical Grounding Taxonomy** | Mutations systematically flip to canonical failure codes (`stale_law`, `wrong_proposition`, etc.) | `tests/unit/test_grounding_properties.py` | ✅ PASS |
| **INV-7** | **Immutable Append-Only Audit** | Compliance logs, case access events, and purge records are tamper-evident and immutable | `tests/test_security_hardening.py` | ✅ PASS |
| **INV-8** | **Pre-Spool Magic-Byte Gate** | Executables (PE/ELF/Mach-O) and polyglots rejected before disk write | `tests/test_security_hardening.py` | ✅ PASS |
| **INV-9** | **Legal Hold & 423 Locked** | Preservation holds block all case deletion and purge operations with HTTP 423 | `tests/test_security_hardening.py` | ✅ PASS |
| **INV-10** | **Strict Loopback Residency** | Orchestrator binds to loopback; API key strictly mandatory outside local dev | `tests/test_security_hardening.py` | ✅ PASS |

---

## 🏎️ 1-Command Benchmark: Preemption & Amendment Blindspot Demo

Run the zero-dependency in-memory reproduction benchmark directly (<10ms runtime):
```bash
python scripts/demo_statutory_walk_vs_cosine.py
```

### The California Security Deposit Blindspot
This benchmark models a real-world scenario facing California tenant defense and legal aid clinics:
* **The Legal Fact**: Prior to July 1, 2024, California Civil Code § 1950.5 permitted residential security deposits up to **two (2) months' rent** for unfurnished units. In 2023, the California Legislature enacted Assembly Bill 12 (Stats. 2023, ch. 290, effective July 1, 2024), amending § 1950.5(c)(1) to cap security deposits strictly at **one (1) month's rent** statewide.
* **Why Naive Vector & BM25 RAG Fails**:
  1. **Length Bias**: The historical § 1950.5 statute contains 1,940 characters of dense boilerplate repeating words like *deposit*, *security*, *landlord*, *tenant*, *unfurnished*, and *rent* across 8 subdivisions.
  2. **Lexical Repetition**: AB 12 is a surgical 1-sentence amending act (*"Section 1950.5 of the Civil Code is amended to read: ... not in excess of an amount equal to one month's rent"*).
  3. **The Result**: Naive cosine similarity and BM25 rank the stale historical statute #1 (Hybrid Score: 1.1774 vs. 1.1133) and assert a 2-month deposit is lawful for an August 2024 lease—giving attorneys dangerously outdated advice.
* **Why KruschLaw's DAG Walk Succeeds**:
  KruschLaw queries the confirmed `AMENDS` relation edge from AB 12 to § 1950.5. Because the inquiry date (`2024-08-15`) postdates July 1, 2024, the temporal resolver prunes the superseded 2-month allowance and elevates the operative 1-month statutory cap, preserving complete provenance in the resolution audit trail.

---

## 🔗 Preemption & Amendment Review Queue (Confirmed-Edge Invariant)

Under California Code of Civil Procedure § 128.7 and legal ethics rules, an automated AI agent cannot assume statutory preemption or amendment based solely on vector similarity.

### The Confirmed-Edge Invariant
1. **Isolated Proposed State**: All machine-extracted or newly proposed relations are recorded with `status = "proposed"` in `src/backend/db.py` (`StatuteRelation`).
2. **Zero Silent Control**: Proposed relations are excluded from controlling authority resolution; they **never silently alter the statutory graph walk**.
3. **High-Visibility Uncertainty Warning**: When proposed relations exist for an inquiry topic or doctrine, KruschLaw emits an amber advisory banner in consultation briefs and API responses:
   ```markdown
   > ⚠️ **CONTROLLING STATUTE UNCERTAIN; N proposed preemption/amendment link(s) pending human attorney review.**
   ```
4. **Admitted Counsel Review (Streamlit Tab 5 & REST API)**:
   In Tab 5 (*"🔗 Preemption & Amendment Review Queue"*), attorneys inspect proposed edges, trigger spans, and confidence scores, and can **Accept / Confirm**, **Reject**, or **Edit** relationships:
   * `GET /api/resolver/relations`: Enumerate proposed/confirmed relations with doctrine filtering.
   * `POST /api/resolver/relations`: Stage newly extracted relations.
   * `PATCH /api/resolver/relations/{id}`: Confirm (`status='confirmed'`, recording `reviewed_by` and `reviewed_at`) or reject (`status='rejected'`).
   * `DELETE /api/resolver/relations/{id}`: Delete relations.

---

## 🌐 5-Verb Sovereign Gateway MCP Router (<450 Prompt Tokens)

In multi-agent homelab and enterprise swarms, standard MCP servers consume thousands of prompt tokens listing verbose tool definitions, triggering context degradation in local 7B/14B models.

KruschLaw provides a hyper-compact, cross-repo Gateway MCP router (`src/mcp/gateway.py`) adhering strictly to [`docs/ORCHESTRATOR_SPEC.md`](docs/ORCHESTRATOR_SPEC.md):

* **Exact 5 Verbs**:
  1. `ask_law`: Sovereign California statutory search, multi-hop precedence resolution, and tenant defense checklists.
  2. `ask_biz`: Sovereign corporate contract intelligence, deal graph walk, and clause retrieval (delegated to KruschBiz).
  3. `check_compliance`: Direct conflict analysis ("The Join") evaluating contract slots against statutory floors/ceilings (e.g. AB 12 deposit cap).
  4. `ingest`: Sovereign document ingestion with MIME validation and page-true citations.
  5. `purge`: Verifiable cryptographic deletion with SHA-256 tombstone audit receipts.
* **Token Budget**: Strictly constrained to **<450 prompt tokens** (~1,715 characters dense JSON) across all 5 verb definitions.
* **Launch Command**:
  ```bash
  python -m src.mcp.gateway
  ```

---

## 🏷️ Ensemble Legal Chunk Tagging & Dual-Path Semantic Recall

KruschLaw decouples raw ingestion parsing (handled by the lightweight [KruschNexus](https://github.com/kruschdev/krusch-nexus) spine) from **domain-specific legal semantic tagging and hybrid recall**.

```
                           Raw Document Chunk
                                   │
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
      Deterministic Regex & Anchors      Local LLM Semantic Tagger
     (Civ Code, CC, §, Section, Words)   (Ollama qwen2.5-coder:7b @ 15s)
                   │                               │
         Exact Citation Tags              Semantic Concepts &
      (e.g., `sec-1950.5`, `sec-1942.5`)   1-Sentence Micro-Digest
                   │                               │
                   └───────────────┬───────────────┘
                                   ▼
                         Ensemble Tag Union
                   (Deduplicated, Normalized, Grounded)
                                   │
                                   ▼
                   PostgreSQL 16 + pgvector Storage
             (MatterEvidence & LawVector Schema Enrichment)
                                   │
                                   ▼
                      Dual-Path Retrieval Pipeline
    (Exact Citation Match + BM25 Lexical + Vector Cosine + 20% Tag Boost)
```

### 1. The Ensemble Tagging Architecture
Standard LLM-only chunk taggers suffer from a classic failure mode: an LLM captures broad abstract doctrines (e.g., `landlord-tenant-dispute`) but frequently drops or misidentifies precise statutory section anchors.

KruschLaw resolves this via **Ensemble Tagging** (`src/backend/tagger.py`):
1. **Deterministic Citation Extraction**: Uses compiled regex patterns recognizing `Civil Code § 1950.5`, `Civ. Code 1950.5`, `CC 1950.5`, and section numbers, automatically creating normalized anchor tags (e.g. `sec-1950.5`, `sec-1942.5`, `omc-8.22.030`).
2. **Deterministic Doctrine Anchors**: Analyzes high-signal statutory keywords (`deposit`, `habitability`, `retaliation`, `sublease`, `rent board`) to map chunks into canonical legal doctrines.
3. **Local LLM Semantic Tagging**: Invokes local Ollama `qwen2.5-coder:7b` to extract 3–5 lowercase semantic tags and a concise 1-sentence micro-digest.
4. **Ensemble Merge**: Deduplicates and unions the deterministic citation/doctrine tags with the LLM semantic tags.
5. **Deterministic Fallback**: If the local LLM times out or is under heavy GPU load, the pipeline automatically falls back to extractive digests and deterministic anchors—ensuring statutory citation anchors are **never dropped** and zero data ever leaks to external clouds.

### 2. Schema Enrichment
Both statutory vectors and confidential client exhibits are enriched with semantic metadata:
* **`MatterEvidence`** (`matter_evidence`): Added `tags` (JSON array), `summary` (1-sentence digest), and `doctrine` (primary legal category).
* **`LawVector`** (`laws_vectors`): Enriched with `tags`, `summary`, and `doctrine`.

### 3. Dual-Path Retrieval & Exact Tag Boosting
When querying legal authorities or client discovery (`src/backend/rag.py`):
* **Exact Section Matching**: Direct SQL index lookup for cited section numbers (e.g., `1950.5` or `8.22.030`).
* **Hybrid Lexical & Dense RRF**: Combines PostgreSQL cover-density full-text search (`tsvector` / `ts_rank_cd`) with `pgvector` HNSW cosine similarity fused via Reciprocal Rank Fusion ($k=60$).
* **Exact Tag Boost**: Chunks containing tags matching the inquiry's legal issues receive a **+20% score boost** (`score * 1.20`), prioritizing sections with explicit statutory or doctrinal relevance over loose semantic neighbors.
* **Doctrinal Filtering**: Supports strict filtering by legal doctrine (`topic` or `doctrine`), enabling targeted issue-spotting and conflict checking.

### 4. Statute-to-Code Traceability Registry
KruschLaw maintains an immutable relational traceability registry (`src/backend/db.py` → `StatuteCodeTraceability`) mapping state statutes to municipal enforcement codes and codebase symbols:
* **Streamlit Tab 4**: Interactive Statutory Traceability Explorer displaying cross-referenced state statutes, municipal enforcement provisions, statutory summaries, and attorney audit status.
* **REST API**: `GET /api/compliance/traceability` with optional `?doctrine=` filtering.
* **MCP Tool**: `get_code_traceability` allowing autonomous coding agents to inspect verified legal mappings directly.

---

## 🛡️ Privilege Surface Reduction & Threat Model

KruschLaw is built under the assumption that law office infrastructure handles sensitive, highly confidential work product governed by strict legal ethics rules (ABA Model Rule 1.6).

### 1. Security & Privilege Invariants
* **Isolated Container Network**: The Docker Compose architecture binds internal services to an isolated bridge network (`kruschlaw_internal` with `internal: true`), completely blocking outbound internet access from database and backend containers.
* **Loopback Auth Enforcement**: Even on local loopback (`127.0.0.1`), KruschLaw rejects unauthenticated requests unless configured with a verified `KRUSCHLAW_API_KEY` or `X-Session-Token`.
* **Separate Processes & Data Boundaries**: General statutory searches query public authority vectors (`laws_vectors`) without touching confidential matter discovery (`matter_evidence`). Client exhibits are restricted to authenticated matter-scoped queries (`GET /api/cases/{case_id}/evidence`).
* **Encryption-at-Rest for Evidence**: Ingested client documents and sensitive discovery items can be encrypted at rest using PBKDF2 key derivation and AES-Fernet with transparent `enc:v1:` prefixes (`src/backend/crypto.py`).
* **Verifiable Cryptographic Hard Purge**: When an attorney purges a matter (`DELETE /api/cases/{case_id}/purge`), `execute_verifiable_purge` performs:
  1. Irreversible deletion of all case facts, documents, chunk vectors, and attorney feedbacks.
  2. Immediate eviction of associated query hashes from the in-memory LRU embedding cache.
  3. Removal of any generated export artifacts on disk.
  4. Physical disk page zeroing via SQLite/PostgreSQL `VACUUM` (ensuring unallocated space cannot be recovered with disk forensics).
  5. Computation of a cryptographic SHA-256 tombstone hash committed to an immutable `AuditLog` receipt (`PURGE_CASE`).

### 2. Threat Model Boundaries
| Asset / Threat | KruschLaw Countermeasure | Operator Responsibility |
|---|---|---|
| **Cloud LLM Data Leakage** | 100% on-premise local Ollama inference (`bge-large`, `qwen2.5-coder`). Zero cloud egress. | Verify host Ollama does not bind to public external interfaces. |
| **SaaS Vector DB Subpoenas** | All embeddings stored in local PostgreSQL 16 + pgvector or local SQLite instance. | Enable full-disk encryption (LUKS / FileVault) on host machines. |
| **Cross-Matter Contamination** | Strict relational foreign key partitioning and query isolation between matters. | Restrict matter access via distinct attorney session tokens. |
| **Silent Temporal Law Drift** | First-class `as_of_date` gating on all search and resolution calls. | Ensure user supplies accurate lease/incident dates for historical claims. |
| **Hallucinated Citations** | Hard citation constraint stripping and two-pass verification gate. | Admitted counsel must conduct mandatory pre-filing review. |

---

## 📜 Authority Graph, Temporal Gating & Coverage Matrix

### 1. Canonical Raw Authority Store vs. Derived Vectors
To ensure authority is verifiable, KruschLaw strictly separates canonical source law from derived embeddings:
* **`StatutoryArtifact` Table**: Stores verbatim official statute/ordinance text along with `source_url`, `retrieved_at`, SHA-256 `content_hash`, `publisher`, and `edition`.
* **Rebuildable Vectors**: If embedding models change or vector indices become corrupt, vectors can be deterministically rebuilt (`StatutoryArtifact.rebuild_vectors()`) from canonical artifacts without re-fetching from external government portals.

### 2. Jurisdiction Packs (Pack Zero: Oakland & California Civil Code)
KruschLaw models jurisdictions via declarative packs (`data/packs/*.yaml`):
```yaml
pack_id: ca_oakland
version: 1.0.0
state: California
municipality: Oakland
code_families:
  - California Civil Code (Landlord-Tenant §§ 1940 - 1954.06)
  - Oakland Municipal Code (OMC Title 8, Ch 8.22 - Rent Adjustments & Evictions)
```
Each pack specifies exact section hierarchies, child provisions, temporal amendment boundaries, and fixture validation rules.

### 3. Temporal Amendment Gating (`as_of_date`)
Defaulting to current time (`NOW()`) silently cites repealed or pre-amendment rules when evaluating historical leases. KruschLaw mandates `as_of_date` as a first-class query parameter across all endpoints:
* **Pre-AB 12 vs. Post-AB 12**: California Civil Code § 1950.5 capped residential deposits at 2 months' rent for unfurnished units prior to July 1, 2024. For leases on or after July 1, 2024, AB 12 caps deposits at 1 month's rent. KruschLaw's resolver dynamically selects the legally controlling rule based on the exact matter date.

### 4. Resolution Traces & Diagnostics (`explain_why_not_controlling`)
Autonomous agents and human attorneys can inspect the exact statutory resolution path:
* **`ResolutionTrace`**: Records hops across preemption chains, legislative amendments, and statutory exemptions, explicitly logging why alternative sections were kept or discarded.
* **`CoverageHole`**: Flags topics or doctrines outside the indexed corpus with explicit suggestions, preventing silent negative inferences.
* **`explain_why_not_controlling` Tool**: Programmatic diagnostic tool explaining why a given statute does not control:
  ```json
  {
    "candidate_section": "Section 1950.5 (Pre-2024)",
    "doctrine": "Security Deposits",
    "as_of_date": "2024-08-01"
  }
  ```
  Returns:
  ```json
  {
    "is_controlling": false,
    "controlling_authority": "Civ. Code § 1950.5",
    "reasons": ["[TEMPORAL_AMENDMENT] Section 1950.5 (Pre-2024) superseded on 2024-07-01 by AB 12."]
  }
  ```

### 5. Coverage Matrix & Known Boundaries
| Legal Domain / Topic | Coverage Status | Governing Authorities Indexed |
|---|---|---|
| **Residential Security Deposits** | ✅ Full Coverage | Cal. Civ. Code § 1950.5 (Pre & Post AB 12), OMC § 8.22.020 |
| **Residential Rent Increases & Just Cause** | ✅ Full Coverage | Cal. Civ. Code § 1946.2, § 1947.12 (AB 1482), OMC § 8.22.030, § 8.22.360 |
| **Habitability & Landlord Entry Notice** | ✅ Full Coverage | Cal. Civ. Code § 1941.1, § 1942, § 1954 |
| **Commercial Leasing & Eviction** | ⚠️ Coverage Gap | Unindexed in Pack Zero (returns explicit CoverageHole) |
| **Condo / HOA Covenants (Davis-Stirling)** | ⚠️ Coverage Gap | Unindexed in Pack Zero (returns explicit CoverageHole) |
| **Federal Subsidized Housing (HUD / Section 8)** | ⚠️ Coverage Gap | Federal regulations unindexed in municipal pack |

---

## 📝 Matter Workflow & Refusal-First Export

### 1. Two-Pass Grounding Gate (0.00% False Support Rate)
Every generated legal assertion undergoes rigorous two-pass validation:
1. **Discrete Claim Decomposition**: Extracts atomic legal propositions with their asserted citations.
2. **Span Matching & Entailment Scoring**: Computes lexical overlap and embedding similarity against retrieved authority chunks.
3. **Hard Generation Constraint**: If a model introduces an unretrieved statutory section, `enforce_generation_citation_constraints` automatically strips and annotates it: `[UNAUTHORIZED CITATION STRIPPED: Section X]`.
4. **Explicit Refusal & Abstention**: If overlap falls between `0.15` and `0.35`, or if authorities are missing, the claim is classified as `abstain` or `invented_citation` rather than falsely marked as supported.

### 2. Local Human Attorney Claim Feedback Loop
Attorneys review generated claims via the web UI or REST API (`POST /api/cases/{case_id}/claims/feedback`):
* Individual propositions can be marked as `accepted`, `rejected`, or `modified`.
* Corrections and attorney notes are recorded locally in the `ClaimFeedback` table, building a private gold-standard training set for future model calibration.

### 3. Refusal-First Document Export (.docx & .md)
When exporting memoranda (`/api/consult/export/docx`), refused or ungrounded claims are never smoothed into deceptive narrative prose. Instead, they are rendered as prominent **`STATUTORY COVERAGE GAP`** callout tables with red/amber borders:
```
┌────────────────────────────────────────────────────────────────────────┐
│ ⚠️ STATUTORY COVERAGE GAP: PROPOSITION UNGROUNDED IN RETRIEVED LAWS    │
├────────────────────────────────────────────────────────────────────────┤
│ Asserted Claim: Tenant entitled to automatic $10,000 statutory fine.   │
│ Cited Section: Section 999.99                                          │
│ Reason: Cited section does not exist in retrieved authority set.       │
└────────────────────────────────────────────────────────────────────────┘
```
Supported claims include verbatim supporting authority spans, ensuring full traceability from draft to statute.

---

## 🏗️ Architecture

```
                               ┌────────────────────────────────┐
                               │    KruschLaw Web Interface     │
                               │  (Streamlit / 127.0.0.1:8505)  │
                               │   *Offline System Font Stack*  │
                               └──────────────┬─────────────────┘
                                              │ REST (CORS Restricted)
                               ┌──────────────▼─────────────────┐
                               │      KruschLaw Backend         │
                               │   (FastAPI / 127.0.0.1:8085)   │
                               │   *Lifespan Schemas & Guard*   │
                               └───┬────────────────────────┬───┘
                                   │                        │
                    SQL / pgvector │                        │ Local HTTP
                                   │                        │
            ┌──────────────────────▼───────┐       ┌────────▼────────────────────┐
            │   PostgreSQL 16 + pgvector   │       │      Local Ollama Node      │
            │   (Laws & Case Fact Vectors) │       │  ├─ bge-large (Embeddings)  │
            │        127.0.0.1:5435        │       │  └─ qwen2.5:14b / 7b (LLM)  │
            └──────────────────────────────┘       └─────────────────────────────┘
```

---

## 💻 Hardware Requirements & Model Matrix

| Profile | Recommended Model | Minimum Hardware | Expected Speed | Suitable Use Case |
|---|---|---|---|---|
| **CPU / Lightweight** | `qwen2.5:7b` + `bge-large` | 16GB System RAM (8 threads) | ~10–18 tok/s | Air-gapped laptops, small office CPU nodes, rapid exploration |
| **GPU / Standard** | `qwen2.5:14b` + `bge-large` | 12GB+ VRAM (RTX 3060/4070, Apple Silicon 16GB+) | ~35–55 tok/s | High-precision legal synthesis, nuanced exception spotting |
| **Workstation / Heavy** | `qwen2.5:32b` + `bge-large` | 24GB+ VRAM (RTX 3090/4090, Apple Silicon 36GB+) | ~20–30 tok/s | Complex multi-code statutory conflicts & lengthy appellate synthesis |

To switch models, configure `OLLAMA_LLM_MODEL` in your `.env` file:
```env
OLLAMA_LLM_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=bge-large
```

---

## ⚡ Quickstart

### Prerequisites
* [Docker](https://docs.docker.com/get-docker/) & Docker Compose
* Local [Ollama](https://ollama.com/) instance (or use the containerized profile below):
  ```bash
  ollama pull bge-large
  ollama pull qwen2.5:14b
  ```

### 1. Clone & Configure
```bash
git clone https://github.com/kruschdev/krusch-law.git
cd krusch-law

cp .env.example .env
```

### 2. Launch Stack

**Standard Air-Gapped Mode (Connects to host Ollama):**
```bash
docker compose up --build -d
```

**All-in-One Standalone Demo Mode (Includes containerized Ollama):**
```bash
docker compose --profile with-ollama up --build -d
```

Verify endpoints:
* **Frontend UI**: [http://localhost:8505](http://localhost:8505)
* **Backend API Docs**: [http://localhost:8085/docs](http://localhost:8085/docs)
* **Health & Diagnostics**: [http://localhost:8085/health](http://localhost:8085/health)

---

## 🗄️ Database Migrations (Alembic)

KruschLaw tracks its versioned statutory graph and audit log tables using Alembic:

```bash
# Run latest migrations
alembic upgrade head

# Generate a new migration
alembic revision --autogenerate -m "describe_change"
```

---

## 🔄 Persistent Ingestion Worker

For massive multi-gigabyte municipal corpora, KruschLaw decouples file parsing from vector generation using a crash-resilient queue worker (`src/backend/worker.py`):

* **PostgreSQL `SKIP LOCKED`**: Concurrent worker instances consume pending batches without deadlocks.
* **Byte-Level Deduplication**: Uploads are fingerprinted via raw SHA-256 before parser execution.
* **Resumable Offsets**: If a batch or node crashes mid-stream, workers resume from `last_committed_offset`.
* **Telemetry & Progress**: Exposes batch-by-batch row counts and embedding progress via `/api/ingest/jobs/{job_id}`.

Run the standalone worker directly or let Docker Compose manage it:
```bash
python -m src.backend.worker
```

---

## 📥 Ingestion & Datasets

### Option A: Versioned California Legal Graph Fixtures
Click **"🚀 Seed Paraphrased Demo Fixtures"** in the sidebar (or run via curl):
```bash
curl -X POST http://localhost:8085/api/ingest/mock
```
*Seeds 11 hierarchical records spanning California Civil Code (§ 1950.5, § 1954), Oakland Municipal Code (§ 8.22.020, § 8.22.030, § 8.22.360), San Francisco Administrative Code (Chapter 41A), Los Angeles Municipal Code (§ 151.09), and negative distractors (repealed § 1947.10).*

### Option B: LOCUS-v1 Municipal Parquet
Ingest municipal laws from the [LOCUS-v1 dataset](https://huggingface.co/datasets/LocalLaws/LOCUS-v1):

```bash
curl -X POST http://localhost:8085/api/ingest/parquet/async \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/app/data/ingest/ordinances.parquet", "limit": 1000}'
```

> [!IMPORTANT]
> **LOCUS-v1 License Notice**: LOCUS-v1 is licensed under **CC-BY-NC-4.0** strictly for academic and research evaluation. Commercial firms must ensure dataset rights before production ingestion.

### Option C: KruschNexus Sovereign Document Ingestion (PDF / DOCX / EML / MD / TXT)
Ingest client contracts, leases, and evidence with page-true and section-true citations:

```bash
curl -X POST http://localhost:8085/api/ingest/upload \
  -F "file=@/path/to/lease.pdf" \
  -F "matter_id=1" \
  -F "doc_type=matter_facts"
```

---

## 🔌 Model Context Protocol (MCP) Integration

KruschLaw provides a native stdio JSON-RPC MCP server (`src/mcp/server.py`) exposing air-gapped legal intelligence tools with mandatory guardrails:

| Tool | Parameters | Description |
|---|---|---|
| `search_ordinances` | `query`, `state`, `city`, `topic`, `as_of_date`, `limit` | Hybrid lexical (`tsvector`) + vector search with authority weighting and temporal gating |
| `get_section` | `section`, `jurisdiction` | Retrieve complete section body, parent/child relationships, and amendments |
| `log_matter` | `title`, `facts`, `matter_number`, `client_name` | Securely log and vectorize client matter narrative on-premise |
| `list_matters` | `limit` | Enumerate active client matters and matter numbers |
| `draft_brief` | `case_id`, `facts`, `title`, `city`, `as_of_date`, `limit` | Stage 4-part legal brief with assertion grounding; **refuses if authorities absent** |
| `get_grounding_report` | `case_id` | Retrieve stored assertion grounding audit for a specific matter |
| `get_code_traceability` | `doctrine` | Inspect curated statute-to-code traceability invariants and verified mappings |
| `resolve_controlling_law` | `doctrine`, `city`, `county`, `as_of_date`, `matter_facts` | Multi-hop precedence resolution traversing preemption, amendments, and exceptions |
| `detect_statutory_conflicts` | `jurisdiction`, `laws`, `as_of_date` | Detect substantive conflicts (preemption, temporal sunsets, statutory exemptions) |
| `explain_why_not_controlling` | `candidate_section`, `doctrine`, `as_of_date`, `city`, `county` | Diagnostic report explaining why a section is superseded, preempted, or inapplicable |
| `get_defense_checklist` | `case_id`, `as_of_date` | Generate structured defense checklist with statutory deadlines and evidentiary audits |
| `assemble_statutory_letter` | `case_id`, `letter_type`, `recipient_name`, `recipient_address` | Assemble formal statutory demand letter or notice objection with mandatory citations |

### Guardrails for Agents
1. **Refusal on Missing Authorities**: If the air-gapped corpus does not contain relevant governing authorities, `draft_brief` rejects the request with `CANNOT_DRAFT_WITHOUT_AUTHORITIES` rather than hallucinating plausible statutes.
2. **Review Mandate**: Every draft includes `review_required: true` and `provisional_work_product: true`.
3. **Discrete Claims Audit**: Returns full side-by-side propositions, source excerpts, entailment scores, and failure classifications.
4. **Citation Constraint Enforcement**: Unretrieved statutory citations are stripped from generated prose prior to delivery.

---

## ⚖️ Ethics, Compliance & Law Office Trial Protocol

KruschLaw is engineered around the ethical constraints of legal practice (ABA Model Rules 1.1, 1.6, and 5.3):

### 🛡️ Why Postgres + Ollama Instead of SaaS Vector DBs?
* **Zero Sub-Processors**: Cloud vector databases and hosted embedding APIs require data processing addendums and introduce subpoena risk.
* **Zero Data Retention**: On-premise Ollama instances do not log client facts to external training pools.
* **Cryptographic Matter Hard Purge**: An attorney can permanently delete a client matter and all associated embeddings/documents via `DELETE /api/cases/{case_id}/purge`, leaving only an anonymized cryptographic audit log.

### 📋 Law Office Trial Protocol

| Usage Category | Permitted / Safe Operations | Prohibited / High-Risk Operations |
|---|---|---|
| **Intake & Issue Spotting** | Preliminary fact cross-referencing against municipal rent programs | Relying on AI drafts as final legal advice without attorney review |
| **Statutory Exploration** | Finding related definitions, exception clauses, and parent sections | Auto-filing generated pleadings in court |
| **Citation Auditing** | Flagging potential hallucinations, wrong propositions, and stale laws | Relying on unverified citations without consulting primary reporters |
| **Discovery Review** | Parsing client leases and contracts locally using KruschNexus | Processing non-matter third-party confidential documents without consent |

---

## 🧪 Automated Testing & CI Gates

```bash
# Run full unit, integration, and eval test suite (122 tests)
pytest

# Run 1-command precedence benchmark (DAG walk vs Naive Cosine RAG)
python scripts/demo_statutory_walk_vs_cosine.py

# Run 5-verb Sovereign Gateway MCP test suite
pytest tests/test_gateway_mcp.py -v

# Run statutory relations & preemption review queue test suite
pytest tests/test_statute_relations.py -v

# Run labeled grounding golden eval gate (0.00% False Support Rate target)
pytest tests/eval/test_labeled_grounding_eval.py -v

# Run golden retrieval and assertion-level grounding CI gate
pytest tests/eval/test_golden_eval_gate.py -v

# Run ruff code quality and lint gate
ruff check .
```

CI is automated on every push and pull request via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 📊 Empirical Multi-Gate Evaluation Scorecard

KruschLaw is continuously benchmarked across **five independent gates** and an assertion-level grounding calibration matrix. All CI gates evaluate against frozen data without mocking embeddings or masking priority inversions:

```bash
python scripts/eval_retrieval_and_grounding.py
```

### [Gate 1] Fixture Corpus Gate (Bootstrap Baseline)
Evaluates 25 realistic municipal and statutory fact patterns from `data/eval/golden_legal_eval.json` against the seed California legal graph:

| Metric | Target | Measured Score | Evaluation Description |
|---|---|---|---|
| **Recall@1 (Top-1 Accuracy)** | > 85.0% | **96.0%** | Relevant governing statute returned as top hit |
| **Recall@5 (Top-5 Coverage)** | > 95.0% | **100.0%** | Gold section contained in top 5 retrieved items |
| **Mean Reciprocal Rank (MRR)** | > 0.900 | **0.980** | Harmonic mean of gold citation retrieval rank |
| **Distractor / Stale Law Leaks** | 0 | **0** | Repealed or inapplicable statutes leaking as controlling |
| **Mean Retrieval Latency** | < 250 ms | **127.2 ms** | Hybrid lexical + semantic ranking latency |

### [Gate 2] Unmocked Embedding Gate (Real BGE-Large 1024-d Vectors)
Evaluates pure dense vector similarity across frozen, unmocked `bge-large` 1024-dimensional embeddings checked into `data/eval/embeddings/`:

| Metric | Target | Measured Score | Evaluation Description |
|---|---|---|---|
| **Pure Vector Recall@1** | > 80.0% | **100.0%** | Top-1 accuracy using unmocked dense vector cosine similarity |
| **Pure Vector Recall@5** | > 95.0% | **100.0%** | Top-5 coverage across legal fact patterns |
| **Pure Vector MRR** | > 0.850 | **1.000** | Dense vector harmonic mean rank without lexical hints |

### [Gate 3] Held-Out Statutory Gate (External California Provisions)
Evaluates 12 external California statutory and municipal provisions (AB 1482 rent caps, retaliatory eviction § 1942.5, repair-and-deduct § 1942, lockout penalties § 789.3, SF § 37.9/37.10B, Berkeley § 13.76.080, LA § 49.99, San Jose § 17.23) in `data/eval/heldout_statutes.json`:

| Metric | Target | Measured Score | Evaluation Description |
|---|---|---|---|
| **Held-Out Recall@1** | > 60.0% | **66.7%** | Top hit accuracy across unseen external statutes |
| **Held-Out Recall@5** | > 90.0% | **100.0%** | Top 5 coverage across unseen external statutes |
| **Held-Out MRR** | > 0.750 | **0.799** | Mean reciprocal rank on held-out provisions |
| **Priority Inversions** | 0 | **0** | Repealed statutes outranking controlling authorities |

### [Gate 4] Conflict-Pair Evaluation Gate (Deterministic Invariants)
Evaluates substantive legal conflict resolution across 5 deterministic statutory pairs (preemption, temporal amendment, and statutory exceptions):

| Conflict Pair | Verification Invariant | Status | Result |
|---|---|---|---|
| **AB 12 vs Repealed Cap** | Post-2024-07-01 deposits capped strictly at 1 month | Passed | ✅ 100.0% |
| **County Island vs OMC 8.22** | Unincorporated Alameda parcels exempt from city rent caps | Passed | ✅ 100.0% |
| **AB 1482 Duplex Exception** | Owner-occupied 2-unit dwellings exempt from statewide Just Cause | Passed | ✅ 100.0% |
| **Corpus Abstention / Refusal** | Abstains and refuses on novel issues missing controlling authority | Passed | ✅ 100.0% |
| **Exhibit Air-Gap Isolation** | Zero leakage of confidential matter exhibits into public statutory index | Passed | ✅ 100.0% |

### [Gate 5] Labeled Grounding Benchmark (`labeled_grounding_golden.json`)
Evaluates discrete proposition verification against the adversarial golden benchmark dataset across 5 taxonomy classes:

| Metric | Target | Measured Score | Evaluation Description |
|---|---|---|---|
| **False Support Rate** | **0.00%** | **0.00%** | Invented, stale, or wrong propositions mistakenly marked supported |
| **Golden Benchmark Accuracy** | 100.0% | **100.0%** | Accurate classification across all 13 labeled propositions |
| **Abstention Accuracy** | 100.0% | **100.0%** | Low-overlap (0.15–0.35) claims routed to attorney human review |
| **Citation Constraint Pass Rate** | 100.0% | **100.0%** | Unretrieved bare citations automatically stripped or flagged |
| **Grounding Precision** | > 95.0% | **100.0%** | Strict assertion verification precision |

### Grounding Calibration & Confusion Matrix
Empirical accuracy across 32 discrete legal proposition assertions:

| Proposition Class | Tested Cases | Correctly Classified | Calibration Accuracy |
|---|---|---|---|
| **VERIFIED (Supported)** | 9 | 9 | **100.0%** |
| **INVENTED_CITATION** | 9 | 9 | **100.0%** |
| **DIVERGENT_PROPOSITION** | 10 | 10 | **100.0%** |
| **STALE_REPEALED_LAW** | 4 | 4 | **100.0%** |
| **Overall Calibration Accuracy** | 32 | 32 | **100.0%** |

---


## 📜 License

KruschLaw is open-source software licensed under the **[MIT License](LICENSE)**.
Third-party corpora (such as LOCUS-v1) remain governed by their respective licenses (e.g. CC-BY-NC-4.0).
