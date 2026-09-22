# ⚖️ KruschLaw

> **Local-First Legal RAG & Ordinance Intelligence Engine (Research Prototype)**  
> *Private municipal code retrieval and citation-grounded preliminary issue analysis using on-premise open-weight models.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.2.0-dev](https://img.shields.io/badge/Version-0.2.0--dev%20(Prototype)-orange.svg)](https://github.com/kruschdev/krusch-law)
[![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector%2016-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com)

---

> [!WARNING]
> **Research Prototype & Technical Scope (Read Before Evaluating)**:  
> KruschLaw is an open-source technical prototype exploring on-premise retrieval-augmented generation. It is **NOT** a law firm, does **NOT** provide legal advice, and does **NOT** replace certified legal reporters.
> - **Semantic Neighbors ≠ Controlling Law**: Cosine and lexical retrieval identify textually similar sections; they do not determine governing authority, appellate deference, preemption, or statutory hierarchy.
> - **No Shepardizing / KeyCite**: KruschLaw does not track subsequent appellate history, statutory amendments, or repeals.
> - **Demo Paraphrases**: Built-in seed ordinances are short, paraphrased fixtures designed solely for automated unit testing and interface demonstration.
> - **OCR Quality**: External OCR corpora (such as LOCUS-v1) are subject to scanning artifacts and unverified text.
> - **Confidentiality & Storage Boundary**: Default port bindings (`127.0.0.1`) restrict services to loopback, avoiding unauthenticated LAN broadcast. However, client matter narratives are stored in plaintext in PostgreSQL unless host-level storage encryption (LUKS / FileVault / BitLocker) is configured. True air-gapping requires operator-enforced egress firewall rules.
> - **Authentication Scope**: The optional `API_KEY` is a single pre-shared key; it does not provide multi-tenant isolation, user accounts, or role-based access control (RBAC).
> - **Mandatory Human Verification**: All generated analyses must be independently Shepardized, verified, and approved by admitted counsel before reliance or filing.

---

## 🏛️ Why KruschLaw?

Law firms, legal aid organizations, and corporate legal departments face a critical dilemma:
1. **Public Cloud LLMs**: Expose privileged client communications and confidential matter facts to external vendor logging and retention, conflicting with attorney-client privilege and state bar ethics rules.
2. **Manual Research**: Sifting through thousands of municipal ordinances, county codes, and changing statutes consumes non-billable hours.

**KruschLaw** is a research prototype evaluating whether local open-weight models (`qwen2.5:14b`, `bge-large`), coupled with hybrid PostgreSQL search (`pgvector` + `tsvector`), can deliver trustworthy, citation-grounded statutory analysis within a private perimeter.

---

## 🚀 Technical Capabilities

* 🔒 **Localhost-Bound Default Topology**: Services bind strictly to `127.0.0.1` by default. Zero third-party telemetry, tracking pixels, or external CDN dependencies.
* 🔍 **Hybrid Retrieval Engine**: Combines PostgreSQL full-text lexical ranking (`tsvector` / `ts_rank_cd`) with dense vector cosine similarity (`pgvector` HNSW) using Reciprocal Rank Fusion (RRF).
* 📑 **LOCUS-v1 Parquet Adapter**: Normalized adapter for HuggingFace `LocalLaws/LOCUS-v1` datasets (`header`, `content`, `state`, `city`, `county`, `topic`, `is_substantive`).
* 🧩 **Section-Aware Chunking & Deduplication**: Breaks multi-thousand character statutes into element-aware chunks with heading prefixes (`[{jurisdiction} {section}] {header}`) and SHA-256 content deduplication.
* 🛡️ **Citation & Quote Grounding Scanner**: Automated post-generation scanner checking statutory section identifiers and 20+ character verbatim quotes against retrieved context, stamping ungrounded citations with warning advisories.
* ⚡ **Batch Embeddings & Async Job Queue**: Employs Ollama batch embeddings (`/api/embed`) and asynchronous background worker queues (`/api/ingest/jobs/{id}`).
* 💼 **Matter Lifecycle CRUD**: Log, view, update (`PATCH` with automatic re-embedding), and soft-delete (`DELETE`) client matters.
* 📋 **Markdown Brief Export**: Export generated 4-part legal briefs directly into structured Markdown (`.md`).
* 🔬 **Runtime Network Diagnostics**: `/health` endpoint inspects whether Ollama inference hosts resolve to loopback or RFC1918 private subnets.

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

| Profile | Recommended Model | Minimum Hardware | Suitable Use Case |
|---|---|---|---|
| **CPU / Lightweight** | `qwen2.5:7b` or `llama3.1:8b` | 16GB System RAM | Laptops, CPU-only servers, initial prototyping |
| **GPU / Standard** | `qwen2.5:14b` | 12GB+ VRAM (RTX 3060/4070 or Mac 16GB+) | High-precision legal synthesis & issue spotting |

To switch models, configure `OLLAMA_LLM_MODEL` in your `.env` file:
```env
OLLAMA_LLM_MODEL=qwen2.5:7b
```

---

## ⚡ Quickstart

### Prerequisites
* [Docker](https://docs.docker.com/get-docker/) & Docker Compose
* [Ollama](https://ollama.com/) running locally with required models:
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
```bash
docker compose up --build -d
```

Verify endpoints:
* **Frontend UI**: [http://localhost:8505](http://localhost:8505)
* **Backend API Docs**: [http://localhost:8085/docs](http://localhost:8085/docs)
* **Health & Diagnostics**: [http://localhost:8085/health](http://localhost:8085/health)

---

## 📥 Ingestion & Datasets

### Option A: Paraphrased Demo Fixtures
Click **"🚀 Seed Paraphrased Demo Fixtures"** in the sidebar (or run via curl):
```bash
curl -X POST http://localhost:8085/api/ingest/mock
```
*Loads 6 sample tenant rights and municipal noise fixtures for Oakland, SF, and LA.*

### Option B: LOCUS-v1 Parquet Ingestion
KruschLaw provides an adapter for municipal laws from the [LOCUS-v1 dataset](https://huggingface.co/datasets/LocalLaws/LOCUS-v1):

> [!IMPORTANT]
> **LOCUS-v1 License Notice**:  
> LOCUS-v1 is released under **Creative Commons Attribution-NonCommercial 4.0 International (CC-BY-NC-4.0)**. It is licensed strictly for non-commercial academic and research evaluation. Commercial law firms must verify data rights before operational use.

1. Download a LOCUS-v1 Parquet slice into `./data/ingest/`:
   ```bash
   cp /path/to/ordinances.parquet ./data/ingest/
   ```
2. Ingest synchronously:
   ```bash
   curl -X POST http://localhost:8085/api/ingest/parquet \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/app/data/ingest/ordinances.parquet", "limit": 250}'
   ```
3. Or dispatch as an asynchronous background job:
   ```bash
   curl -X POST http://localhost:8085/api/ingest/parquet/async \
     -H "Content-Type: application/json" \
     -d '{"file_path": "/app/data/ingest/ordinances.parquet", "limit": 1000}'
   ```
   Check job status:
   ```bash
   curl http://localhost:8085/api/ingest/jobs/<JOB_ID>
   ```

*Security note: Ingestion paths outside `/app/data` are rejected by sandbox policy (`ALLOWED_INGEST_DIRS`).*

---

## 🔌 Model Context Protocol (MCP) Integration

KruschLaw includes a native stdio MCP server (`src/mcp/server.py`) exposing air-gapped legal intelligence tools to AI coding agents (Claude Code, Antigravity, Cursor):

| Tool | Parameters | Description |
|---|---|---|
| `search_ordinances` | `query`, `state`, `city`, `topic`, `limit` | Hybrid full-text (`tsvector`) and vector search across local ordinances |
| `get_section` | `section`, `jurisdiction` | Retrieve complete section body, header, and metadata |
| `log_matter` | `title`, `facts`, `matter_number`, `client_name` | Securely log and vectorize client matter narrative on-premise |
| `draft_brief` | `case_id`, `facts`, `title`, `city`, `limit` | Stage 4-part legal brief with citation grounding for human attorney review |

### Connecting to Claude Code or Antigravity

Add to your `mcpServers` configuration (`claude_desktop_config.json` or Antigravity settings):
```json
{
  "mcpServers": {
    "kruschlaw": {
      "command": "/path/to/krusch-law/.venv/bin/python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/path/to/krusch-law"
    }
  }
}
```
*Note: In accordance with professional responsibility standards, `draft_brief` stages briefs for human attorney approval—it never auto-files.*

---

## ⚖️ Ethics & Professional Responsibility (ABA Model Rule 1.1)

Attorneys maintain a strict ethical duty of technological competence (*see* ABA Formal Opinion 512; State Bar of CA Formal Opinion 2023-207):
* **Automated Guardrails**: KruschLaw scans generated briefs (`verify_citation_grounding`). Sections or quotes not present in retrieved context are flagged with an explicit advisory.
* **Verification Mandate**: Outputs must be Shepardized and reviewed by admitted counsel prior to filing or advising clients.

---

## 🧪 Automated Testing

Run the offline regression suite (18 unit tests covering CRUD, schema normalization, chunking, quote grounding, path sandboxing, and MCP protocol):
```bash
python -m unittest discover tests
```

---

## 📊 Empirical Evaluation & Benchmarks

To eliminate unverified marketing claims and establish measurable retrieval baselines, KruschLaw includes an automated benchmark harness (`scripts/benchmark_retrieval.py`). The script evaluates hybrid search latency, citation grounding overhead, and recall against standardized statutory queries:

```bash
python scripts/benchmark_retrieval.py
```

### Measured Performance Scorecard (Local Test Suite)

| Metric | Measured Baseline | Description |
|---|---|---|
| **Query Latency (Mean)** | `0.91 ms` | Combined hybrid lexical (`tsvector`) + vector ranking |
| **Query Latency (p50 Median)** | `0.79 ms` | 50th percentile query latency |
| **Query Latency (p95)** | `1.73 ms` | 95th percentile query latency |
| **Query Latency (p99)** | `1.79 ms` | 99th percentile query latency |
| **Citation Scanner Overhead** | `0.02 ms` | Regex section extraction + 20-char quote span check |
| **Recall@1** | `100.0%` | Top-1 retrieval accuracy on municipal landlord/tenant queries |
| **Recall@3** | `100.0%` | Top-3 retrieval coverage on test matters |
| **Unit Test Coverage** | `18 / 18 Passing (0.32s)` | Full offline SQLite fallback test suite |

*Note: Latency benchmarks measured on local NVMe/x86_64 hardware using SQLite token-match fallback. Production PostgreSQL 16 HNSW index latencies will vary with corpus size and `ef_search` parameters.*

---

## 📜 License

KruschLaw is open-source software licensed under the **[MIT License](LICENSE)**.
Third-party datasets (such as LOCUS-v1) remain governed by their respective licenses (e.g. CC-BY-NC-4.0).
