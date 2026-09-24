# KruschLaw — Agent Guidelines & Architecture

> **Status**: Sovereign Legal AI & Ordinance Intelligence Engine (Research Prototype)  
> **Version**: 0.3.0  
> **Ingestion Spine**: KruschNexus (v0.2.3)  
> **Last updated**: 2026-09-22  

---

## 1. System Architecture

**KruschLaw** is a sovereign, local-first legal research, statutory issue analysis, and ordinance intelligence platform.
- **Backend API**: Python 3.11+, FastAPI (`src/backend/main.py`), SQLAlchemy, pgvector
- **Ingestion Spine**: **KruschNexus** (`krusch_nexus.parsers` & `krusch_nexus.chunking`) — replaces LlamaIndex entirely
- **Embeddings**: Local Ollama (`bge-large`, 1024-dim, batch embeddings via `/api/embed`)
- **Reasoning**: Local Ollama (`qwen2.5:14b` or `qwen2.5:7b`) with air-gapped zero cloud egress
- **Database**: PostgreSQL 16 with `pgvector` HNSW cosine similarity & `tsvector` cover-density lexical ranking fused via Reciprocal Rank Fusion ($k=60$)
- **Frontend**: Streamlit (`src/frontend/app.py`) with cyber-legal theme and system font stack
- **Protocol**: Stdio Model Context Protocol (MCP) server (`src/mcp/server.py`) exposing 4 legal research tools

---

## 2. Ingestion Architecture: KruschNexus Spine

KruschLaw consumes **KruschNexus** as its native document ingestion and citation engine:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          INCOMING DOCUMENTS                            │
│           PDF (with OCR), DOCX, EML, Markdown, Plain Text             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        KRUSCH_NEXUS PARSER                             │
│  - Poppler page-at-a-time extraction (preserves physical page numbers) │
│  - Tesseract OCR fallback for scanned exhibits and image pages         │
│  - Heading hierarchy extraction (Article IV > Section 8.22.030)        │
│  - SHA-256 content deduplication and true MIME magic detection        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       KRUSCH_NEXUS CHUNKER                             │
│  - Section-aware sliding window chunking with breadcrumb isolation     │
│  - Canonical citation preservation (filename, p. X, § Section)         │
│  - Raw text isolation for embedding (no breadcrumb pollution)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        KRUSCHLAW LAWVECTOR                             │
│  - Stored in PostgreSQL 16 + pgvector on 127.0.0.1:5435                │
│  - Hybrid CTE retrieval: tsvector ts_rank_cd + pgvector cosine (RRF)   │
│  - Automated Citation & Verbatim Quote Grounding Scanner               │
└────────────────────────────────────────────────────────────────────────┘
```

### Ingestion Endpoints
- `POST /api/ingest/upload`: Multipart file upload for PDF, DOCX, EML, MD, TXT directly from Streamlit frontend.
- `POST /api/ingest/document`: Path-based sandboxed document ingestion.
- `POST /api/ingest/parquet`: Synchronous HuggingFace LOCUS-v1 municipal code Parquet ingestion.
- `POST /api/ingest/parquet/async`: Background worker queue for high-volume municipal datasets.
- `POST /api/ingest/mock`: 6 demo California ordinance fixtures for deterministic local testing.

---

## 3. Strict Boundary Rules

1. **Zero Cloud Telemetry**: All inference, embeddings, and vector storage execute strictly within localhost or RFC1918 private subnets.
2. **Zero LlamaIndex**: No imports or runtime dependencies on LlamaIndex. All document parsing and chunking utilize `krusch_nexus`.
3. **No Automated Court Filings**: KruschLaw is an advisory research prototype. All generated briefs require independent Shepardizing and human attorney verification under CCP § 128.7 and CRPC 3.3.
4. **Citation Accountability**: Every generated assertion must link back to physical page numbers and section headers extracted by KruschNexus.

## 4. 3-Tier MCP Ecosystem & KruschLaw Tool Integration

KruschLaw is fully integrated into the fleet agentic ecosystem via the 3-Tier MCP standard:

### Tier 1: Working Memory & Invariant Steering (`krusch-context-mcp`)
- **Hydration**: Call `krusch_context_retrieve({ query: "krusch-law legal statutory", project: "krusch-law", include_state: true })` at session start.
- **Pre-Commit Invariant Audits**: Run `krusch_context_nudge({ trigger: "pre_commit", code: "<diff>" })` before modifying database schemas, RAG pipelines, or verification rules.
- **Matter Memory & Holdings**: Legal decisions, statutory interpretations, and procedural invariants persist to SQLite Lakebase (`.agent/context.db`) with active superseding and invalidation.

### Tier 2: Codebase Structure & AST Symbol Graphs (`krusch-git`)
- **Symbol Search**: Locate FastAPI endpoints, database models, and RAG handlers via `krusch_git_search_symbols({ repo: "krusch-law", query: "<symbol>" })`.
- **Dependency Blast Radius**: Trace caller/callee graphs via `krusch_git_dependency_graph({ repo: "krusch-law", symbol: "<symbol>" })` before refactoring database tables or ingestion pipelines.
- **Semantic Code Search**: Search codebase implementations via `krusch_git_semantic_search({ repo: "krusch-law", query: "<query>" })`.

### Tier 3: Staged Execution & Verification (`krusch-harness`)
- Verify staged diffs and unit test passes (`krusch_run`, `krusch_diff`, `krusch_apply_diff`) before applying mutations to core models or migration scripts.

### Native Sovereign Legal MCP Server (`kruschlaw-mcp`)
KruschLaw exposes its own stdio JSON-RPC MCP server (`src/mcp/server.py`) for IDE and coding agent access:
- `search_ordinances`: Hybrid full-text (BM25) and dense vector search across municipal codes and California statutes.
- `get_section`: Unabridged statutory text and metadata retrieval by section number.
- `log_matter`: Confidential client matter intake with dense local embeddings (strictly isolated from public statutory store).
- `list_matters`: Active matter tracking with docket codes and client references.
- `get_grounding_report`: Proposition-level grounding audit table with 4-class failure taxonomy.
- `draft_brief`: Staged 4-part legal memorandum generation for human attorney review (refuses to draft without governing authorities).
- `get_code_traceability`: Curated statute-to-code traceability invariants, verified files, and attorney audit statuses.

---

## 5. Testing & Verification

Run the full pytest suite (80 tests, in-memory SQLite + mock Ollama, 0 external network dependencies):
```bash
.venv/bin/pytest tests
```

Run legal chunk tagger unit tests:
```bash
.venv/bin/pytest tests/unit/test_legal_tagger.py
```

Run the 4-gate empirical retrieval & proposition grounding evaluation harness:
```bash
.venv/bin/python scripts/eval_retrieval_and_grounding.py
```

Run cross-repo integration tests with KruschNexus:
```bash
.venv/bin/pytest tests/test_nexus_integration.py
```

---

## 6. Ensemble Legal Tagging & Semantic Recall Invariants

1. **Ensemble Merge Rule**: When processing chunks in `src/backend/tagger.py`, deterministic statutory regex citations (`sec-...`) and doctrine anchors MUST be merged with LLM semantic tags. Deterministic anchors must NEVER be dropped or overwritten by model hallucinations.
2. **Citation Regex Breadth**: Statutory citation regex must detect `Civil Code`, `Civ. Code`, `CC`, `Section`, and `§` formats into canonical normalized identifiers (e.g. `sec-1950.5`).
3. **Dual-Path Boosting**: Semantic retrieval queries (`retrieve_laws`, `retrieve_matter_evidence`) apply an exact tag boost of +20% (`score * 1.20`) when candidate chunks match issue tags, alongside lexical BM25 cover-density and dense cosine similarity.
4. **Air-Gapped Local Model**: Chunk tagging uses local Ollama `qwen2.5-coder:7b` with a 15.0s timeout and immediate deterministic fallback. Zero cloud network calls are permitted.
5. **Pydantic Serialization**: SQLite/Postgres text columns storing JSON tags must utilize `@field_validator("tags", mode="before")` to transparently deserialize raw JSON strings into typed string lists.
