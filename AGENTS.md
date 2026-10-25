# KruschLaw — Agent Guidelines & Architecture

> **Status**: Production-Grade Sovereign Legal Intelligence Engine & Versioned Statutory Graph  
> **Version**: 0.8.0 (Ensemble Statutory + Semantic Tagging & Faceted Evidence Explorer)  
> **Ingestion Spine**: KruschNexus (`v0.2.5`)  
> **Tests**: 169 Passing (100% green, 0 ruff errors)  
> **Grounding**: `0.00%` False Support Rate on Golden Benchmark  
> **Last updated**: 2026-10-20  

---

## 1. System Architecture
- **Backend API**: Python 3.12, FastAPI (`src/backend/main.py` on `:8085`), SQLAlchemy, PostgreSQL 16 + `pgvector` (`:5435`, HNSW cosine + `tsvector` cover-density fused via RRF $k=60$).
- **Ingestion Spine**: `krusch_nexus.parsers` & `krusch_nexus.chunking` (Poppler page extraction, Tesseract OCR fallback, section-aware sliding window chunking, SHA-256 deduplication; replaces LlamaIndex completely).
- **Embeddings & Reasoning**: Local Ollama `snowflake-arctic-embed2` (1024-dim, `keep_alive: -1` on `127.0.0.1:11434`) + `qwen2.5-coder:7b` / `hermes3:latest` with air-gapped zero cloud egress.
- **Frontend**: Streamlit (`src/frontend/app.py` on `:8505`) — Legal Research & Memoranda, Matter Evidence & Narrative, Defense Checklist & Statutory Demand Letter.
- **Ingestion Endpoints**: `POST /api/ingest/upload`, `POST /api/ingest/document`, `POST /api/ingest/parquet`, `POST /api/ingest/parquet/async`, `POST /api/ingest/mock`.

---

## 2. Non-Negotiable Invariants & Four Hardened Pillars

1. **Zero Cloud Telemetry**: All inference, embeddings, and vector storage execute strictly within localhost or RFC1918 private subnets.
2. **Zero LlamaIndex**: No imports or runtime dependencies on LlamaIndex; all parsing and chunking use `krusch_nexus`.
3. **Advisory Prototype Boundary**: All generated briefs require independent Shepardizing and human attorney verification under CCP § 128.7 and CRPC 3.3.
4. **Citation Accountability**: Every generated assertion must link to physical page numbers and section headers extracted by KruschNexus.
5. **Pillar 1 — Authority Architecture**: Canonical `StatutoryArtifact` store with SHA-256 hashes, declarative YAML jurisdiction packs (`ca_oakland.yaml`), first-class `as_of_date` temporal parameters, and typed resolution traces (`ResolutionTrace`, `ResolutionHop`, `CoverageHole`).
6. **Pillar 2 — Grounding Verification**: Two-pass assertion verifier with quote spans and entailment scoring; strips unretrieved bare citations; golden benchmark (`labeled_grounding_golden.json`) enforces `false_support_rate == 0.00%`.
7. **Pillar 3 — Privilege & Verifiable Purge**: Loopback API key / session auth; AES/Fernet encryption for `MatterEvidence`; verifiable cryptographic purge (`execute_verifiable_purge`) with SHA-256 tombstones, SQLite `VACUUM`, and immutable audit logs.
8. **Pillar 4 — Matter Workflow & Checklists**: Binding statutory deadline checks (21-day deposit return § 1950.5, 3-court-day notice CCP § 1161, 180-day retaliation presumption § 1942.5); statutory demand letter assembly; refusal-first DOCX export with `STATUTORY COVERAGE GAP` tables.

---

## 3. Native Sovereign Legal MCP Tools (`src/mcp/server.py`)
- `search_ordinances`: Hybrid BM25 + dense vector search across municipal codes and CA statutes with `as_of_date`.
- `get_section`: Unabridged statutory text and metadata retrieval by section number.
- `log_matter` / `list_matters`: Confidential client matter intake and docket tracking (isolated from public statutory store).
- `get_grounding_report`: Proposition-level grounding audit table with 4-class failure taxonomy.
- `draft_brief`: Staged 4-part legal memorandum generation (refuses without governing authorities).
- `get_code_traceability`: Statute-to-code traceability invariants and verified file statuses.
- `get_defense_checklist` / `assemble_statutory_letter`: Statutory deadline evaluation and demand letter assembly (§ 1950.5, § 1941.1, CCP § 1161).
- `explain_why_not_controlling`: Explains why a statute/ordinance is preempted, superseded, or inapplicable.

---

## 4. Ensemble Legal Tagging & Semantic Recall Invariants (`src/backend/tagger.py`)
1. **Ensemble Merge Rule**: Deterministic statutory regex citations (`sec-...`) and doctrine anchors MUST be merged with LLM semantic tags and never overwritten.
2. **Citation Regex Breadth**: Normalize `Civil Code`, `Civ. Code`, `CC`, `Section`, and `§` formats into canonical identifiers (`sec-1950.5`).
3. **Dual-Path Boosting**: `retrieve_laws` and `retrieve_matter_evidence` apply a `+20%` (`score * 1.20`) exact tag match boost alongside BM25 cover-density and cosine similarity.
4. **Air-Gapped Local Tagging**: Uses local `qwen2.5-coder:7b` (`15.0s` timeout) with immediate deterministic regex fallback.
5. **Pydantic Serialization**: SQLite/Postgres JSON tag columns use `@field_validator("tags", mode="before")` to deserialize raw JSON strings into typed `list[str]`.

---

## 5. Testing & Verification Commands
```bash
.venv/bin/pytest tests                                    # Full suite (in-memory SQLite + mock Ollama)
.venv/bin/pytest tests/unit/test_legal_tagger.py          # Ensemble legal chunk tagger
.venv/bin/pytest tests/unit/test_checklist.py             # Defense checklist & demand letters
.venv/bin/pytest tests/unit/test_purge.py                 # Cryptographic purge & privilege
.venv/bin/python scripts/eval_retrieval_and_grounding.py  # 5-gate grounding benchmark (0.00% FSR)
```
