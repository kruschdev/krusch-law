# ⚖️ KruschLaw

> **Sovereign Legal Intelligence Engine & Versioned Statutory Graph**  
> *Private municipal code retrieval, assertion-level grounding verification, and audit-logged issue analysis using on-premise open-weight models.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.3.1](https://img.shields.io/badge/Version-0.3.1-green.svg)](https://github.com/kruschdev/krusch-law)
[![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector%2016-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com)
[![Tests: 80 Passing](https://img.shields.io/badge/Tests-80%20Passing-brightgreen.svg)](tests/)
[![Eval Gate: Passing](https://img.shields.io/badge/Golden%20Eval-100%25%20Recall%405-brightgreen.svg)](data/eval/golden_legal_eval.json)

---

> [!WARNING]
> **Research Prototype & Technical Scope (Read Before Evaluating)**:  
> KruschLaw is an open-source technical prototype exploring on-premise retrieval-augmented generation. It is **NOT** a law firm, does **NOT** provide legal advice, and does **NOT** replace certified legal reporters.
> - **Semantic Neighbors ≠ Controlling Law**: Cosine and lexical retrieval identify textually similar sections; they do not determine governing authority, appellate deference, preemption, or statutory hierarchy. KruschLaw addresses this via hierarchical weighting (controlling statute > implementing regulation > municipal ordinance > secondary commentary).
> - **No Shepardizing / KeyCite**: While KruschLaw tracks version dates, amendments, repeals, and preemption tags within its local graph, it does not connect to external appellate citators.
> - **Confidentiality & Storage Boundary**: Default port bindings (`127.0.0.1`) restrict services to loopback. Client matter narratives and retrieved chunks remain entirely on-premise. True sovereign privilege protection requires operator-enforced host storage encryption (LUKS / FileVault) and egress firewall controls.
> - **Mandatory Human Verification**: All generated drafts are explicitly marked `review_required: true` and `provisional_work_product: true`. Outputs must be independently verified and approved by admitted counsel before reliance or filing.

---

## 🏛️ Why KruschLaw?

Law firms, legal aid organizations, and corporate counsel face a critical dilemma:
1. **Public Cloud LLMs & SaaS Vector DBs**: Expose privileged client communications, confidential matter narratives, and trade secrets to third-party sub-processors, vendor logging, and potential training retention—conflicting directly with attorney-client privilege (ABA Model Rule 1.6) and state bar ethics requirements.
2. **Generic RAG Bag-of-Chunks**: Naive semantic search chunks statutes into arbitrary 500-token blocks, discarding statutory hierarchy (title → chapter → article → section → subsection → exceptions/definitions). An obsolete or repealed subsection can easily outrank controlling law.

**KruschLaw** solves this by treating law as a **versioned statutory graph** with **assertion-level proposition verification**, running on an **air-gapped PostgreSQL + Ollama stack** that never phones home.

---

## 🚀 Core Capabilities

* 🔒 **Sovereign Air-Gapped Topology**: Loopback bindings (`127.0.0.1`), zero telemetry, redacting production `/health` diagnostics, and mandatory pre-shared API keys in non-development modes.
* 🌲 **Versioned Statutory Graph**: Preserves legal hierarchy (title, chapter, article, section, subsection, definitions, exceptions) with parent/child linking (`parent_id`, `parent_section`) and temporal validity tracking (`effective_date`, `amended_date`, `repealed`, `preempted_by`).
* ⚖️ **Authority-Weighted Retrieval**: Prioritizes controlling statutes (1.25x) over implementing regulations (1.15x), municipal ordinances (1.0x), and commentary (0.8x), with automatic hydration of referenced definition and exception sections.
* 🛡️ **Assertion-Level Grounding & Failure Taxonomy**: Decomposes legal drafts into discrete claims and verifies each against retrieved authorities, classifying failure modes into:
  * ❌ **Invented Citation**: Cites non-existent or fabricated statutory sections.
  * ⚠️ **Wrong Proposition**: Cites a genuine statutory section for an unsupported proposition (semantic divergence).
  * 🛑 **Stale Law**: Cites a repealed, sunsetted, or preempted statute.
  * ✅ **Supported**: Verbatim quote or high-overlap excerpt with extracted supporting source span.
* 🎯 **Automated Legal Issue-Spotting & Query Expansion**: Maps colloquial tenant grievances ("rent hike without notice", "withheld security deposit", "black mold and broken heat", "lockout without court order") to canonical legal doctrines and statutory citations (`OMC § 8.22.030`, `Cal. Civ. Code § 1950.5`, `Cal. Civ. Code § 1941.1`, `Cal. Civ. Code § 789.3`).
* 📁 **Dedicated Client Discovery & Evidence Isolation**: Complete database partition between public statutory codes (`laws_vectors`) and confidential client discovery exhibits (`matter_evidence` via `GET /api/cases/{case_id}/evidence`), strictly preventing cross-matter fact contamination.
* 📄 **Professional Legal Export (.docx & .md)**: Single-click export of formal legal memorandums featuring law office caption blocks, mandatory UPL disclaimers, 4-part legal brief structure, Appendix A (Assertion-Level Grounding Audit Table), and Appendix B (Table of Authorities Retrieved).
* 🔄 **Persistent Crash-Resilient Ingestion Worker**: Dedicated worker process (`src.backend.worker`) utilizing PostgreSQL `SKIP LOCKED` (and atomic SQLite transaction locks), byte-level SHA-256 deduplication, and resumable offsets.
* 🏷️ **Ensemble Legal Chunk Tagging & Micro-Digests**: Ingestion pipeline (`src.backend.tagger`) performs an ensemble merge combining deterministic regex statutory citations (`sec-1950.5`, matching `Civil Code`, `Civ. Code`, `CC`, `§`, `Section`) and doctrinal keyword anchors with local Ollama (`qwen2.5-coder:7b`) extracting 3–5 lowercase semantic tags (`habitability-defense`, `unlawful-detainer`) and 1-sentence micro-digests. Includes deterministic fallback so statutory anchors are never lost on timeout.
* 🔍 **Dual-Path Semantic Recall & Traceability Registry**: Combines exact statutory section lookup with hybrid BM25 lexical (`tsvector` / `ts_rank_cd`) and dense vector similarity (`bge-large` 1024-dim, RRF $k=60$). Matches receive a +20% exact tag boost with canonical doctrine filtering. Features a persistent Code-to-Statute Traceability Registry (Tab 4 & MCP tool `get_code_traceability`) linking municipal enforcement provisions directly to controlling state codes.
* 📄 **KruschNexus Sovereign Ingestion Spine**: Integrated parser supporting PDF (with OCR fallback), DOCX, EML, Markdown, and TXT with page-true and section-true citations.
* 🗑️ **Enterprise Hard Purge & Audit Trail**: Immutable local audit logging (`AuditLog`) for all searches, consults, ingests, and matter mutations, plus cryptographic matter hard purge (`DELETE /api/cases/{case_id}/purge`).
* 🔌 **Hardened Model Context Protocol (MCP)**: Native stdio JSON-RPC server with 7 tools (`search_ordinances`, `get_section`, `log_matter`, `draft_brief`, `list_matters`, `get_grounding_report`, `get_code_traceability`), refusing to draft briefs unless valid governing authorities exist in the corpus.
* ⚡ **LRU Embedding Cache**: Thread-safe in-memory cache keyed by `model:sha256(text)` eliminating redundant embedding calls across search, consult, and deduplication.
* 🧪 **CI Gate & Golden Legal Benchmark**: Automated GitHub Actions CI pipeline running Ruff linting, 80 unit/integration tests, and a 25-case golden legal evaluation harness.

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
| `search_ordinances` | `query`, `state`, `city`, `topic`, `limit` | Hybrid lexical (`tsvector`) + vector search with authority weighting |
| `get_section` | `section`, `jurisdiction` | Retrieve complete section body, parent/child relationships, and amendments |
| `log_matter` | `title`, `facts`, `matter_number`, `client_name` | Securely log and vectorize client matter narrative on-premise |
| `list_matters` | `limit` | Enumerate active client matters and matter numbers |
| `draft_brief` | `case_id`, `facts`, `title`, `city`, `limit` | Stage 4-part legal brief with assertion grounding; **refuses if authorities absent** |
| `get_grounding_report` | `case_id` | Retrieve stored assertion grounding audit for a specific matter |
| `get_code_traceability` | `doctrine` | Inspect curated statute-to-code traceability invariants and verified mappings |

### Guardrails for Agents
1. **Refusal on Missing Authorities**: If the air-gapped corpus does not contain relevant governing authorities, `draft_brief` rejects the request with `CANNOT_DRAFT_WITHOUT_AUTHORITIES` rather than hallucinating plausible statutes.
2. **Review Mandate**: Every draft includes `review_required: true` and `provisional_work_product: true`.
3. **Discrete Claims Audit**: Returns full side-by-side propositions, source excerpts, and failure classifications.

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
# Run full unit, integration, and eval test suite (80 tests)
pytest tests

# Run golden retrieval and assertion-level grounding CI gate
pytest tests/eval/test_golden_eval_gate.py

# Run legal tagger unit tests
pytest tests/unit/test_legal_tagger.py

# Run ruff code quality and lint gate
ruff check .
```

CI is automated on every push and pull request via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 📊 Empirical Multi-Gate Evaluation Scorecard

KruschLaw is continuously benchmarked across **three independent gates** and an assertion-level grounding calibration matrix. All CI gates evaluate against frozen data without mocking embeddings or masking priority inversions:

```bash
python scripts/eval_retrieval_and_grounding.py
```

### [Gate 1] Fixture Corpus Gate (Bootstrap Baseline)
Evaluates 25 realistic municipal and statutory fact patterns from `data/eval/golden_legal_eval.json` against the seed California legal graph:

| Metric | Target | Measured Score | Evaluation Description |
|---|---|---|---|
| **Recall@1 (Top-1 Accuracy)** | > 85.0% | **92.0%** | Relevant governing statute returned as top hit |
| **Recall@5 (Top-5 Coverage)** | > 95.0% | **100.0%** | Gold section contained in top 5 retrieved items |
| **Mean Reciprocal Rank (MRR)** | > 0.900 | **0.953** | Harmonic mean of gold citation retrieval rank |
| **Distractor / Stale Law Leaks** | 0 | **0** | Repealed or inapplicable statutes leaking as controlling |
| **Mean Retrieval Latency** | < 250 ms | **126.6 ms** | Hybrid lexical + semantic ranking latency |

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

### Grounding Calibration & Confusion Matrix
Empirical accuracy across 32 discrete legal proposition assertions:

| Proposition Class | Tested Cases | Correctly Classified | Calibration Accuracy |
|---|---|---|---|
| **VERIFIED (Supported)** | 9 | 9 | **100.0%** |
| **INVENTED_CITATION** | 9 | 9 | **100.0%** |
| **DIVERGENT_PROPOSITION** | 10 | 7 | **70.0%** |
| **STALE_REPEALED_LAW** | 4 | 4 | **100.0%** |
| **Overall Calibration Accuracy** | 32 | 29 | **90.62%** |

---

## 📜 License

KruschLaw is open-source software licensed under the **[MIT License](LICENSE)**.
Third-party corpora (such as LOCUS-v1) remain governed by their respective licenses (e.g. CC-BY-NC-4.0).
