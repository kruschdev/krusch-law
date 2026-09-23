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

---

## 4. Testing & Verification

Run the complete test suite (in-memory SQLite + mock Ollama, 0 external network dependencies):
```bash
.venv/bin/python -m unittest discover tests
```

Run cross-repo integration tests with KruschNexus:
```bash
.venv/bin/python -m unittest tests/test_nexus_integration.py
```
