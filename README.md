# ⚖️ KruschLaw

> **Air-Gapped Sovereign Legal RAG & Ordinance Intelligence Engine (Research Prototype)**  
> *Query local municipal codes, statutes, and client matter records with 100% on-premise privacy and zero cloud data leakage.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.2.0-dev](https://img.shields.io/badge/Version-0.2.0--dev%20(Prototype)-orange.svg)](https://github.com/kruschdev/krusch-law)
[![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector%2016-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com)

---

> [!WARNING]
> **Experimental Research Prototype & Legal Limitations**:  
> KruschLaw is an open-source technical prototype exploring sovereign on-premise retrieval-augmented generation. It is **NOT** a law firm, does **NOT** provide legal advice, and does **NOT** replace certified legal reporters.
> - **No Shepardizing / KeyCite**: KruschLaw does not track subsequent appellate history, statutory amendments, or repeals.
> - **Demo Paraphrases**: Built-in seed ordinances are short, paraphrased fixtures designed solely for automated unit testing and interface demonstration.
> - **OCR Quality**: External OCR corpora (such as LOCUS-v1) are subject to scanning artifacts and unverified text.
> - **Mandatory Review**: Admitted counsel must independently verify all cited authorities and factual reasoning prior to taking any formal legal action.

---

## 🏛️ Why KruschLaw?

Law firms, legal aid organizations, and corporate legal departments face a critical dilemma:
1. **Public Cloud LLMs**: Expose privileged client communications and confidential matter facts to external vendor logging and retention, conflicting with attorney-client privilege and state bar ethics rules.
2. **Manual Research**: Sifting through thousands of municipal ordinances, county codes, and changing statutes consumes non-billable hours.

**KruschLaw** is a privacy-first research prototype evaluating whether local open-weight models (`qwen2.5:14b`, `bge-large`), coupled with hybrid PostgreSQL search (`pgvector` + `tsvector`), can deliver trustworthy, citation-grounded statutory analysis within an air-gapped perimeter.

---

## 🚀 Key Features

* 🛡️ **Air-Gapped Privacy Perimeter**: Zero telemetry, external CDNs, or third-party API calls. Port bindings default strictly to `127.0.0.1`.
* 🔍 **Hybrid Retrieval Engine**: Combines full-text lexical ranking (`tsvector` / `ts_rank_cd`) with dense vector cosine similarity (`pgvector` HNSW) using Reciprocal Rank Fusion (RRF).
* 📑 **LOCUS-v1 Parquet Adapter**: First-class support for HuggingFace `LocalLaws/LOCUS-v1` datasets (`header`, `content`, `state`, `city`, `county`, `topic`, `is_substantive`).
* 🧩 **Section-Aware Chunking & Deduplication**: Breaks multi-thousand character statutes into element-aware chunks with heading prefixes (`[{jurisdiction} {section}] {header}`) and SHA-256 content deduplication.
* 🛡️ **Dual-Check Grounding Guardrail**: Verifies both statutory section identifiers and 20+ character quote-spans against retrieved authorities to flag hallucinations.
* ⚡ **Batch Embeddings & Async Jobs**: Leverages Ollama batch embedding (`/api/embed`) and background worker queues (`/api/ingest/jobs/{id}`).
* 💼 **Matter Lifecycle Management**: Log, view, update (`PATCH`), and soft-delete (`DELETE`) client matters with automatic embedding synchronization.
* 📋 **Markdown Brief Export**: Export generated 4-part legal briefs directly into structured Markdown (`.md`).
* 🔬 **Network Isolation Diagnostics**: Runtime `/health` inspection dynamically tests loopback and RFC1918 private network bindings.

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

## 🔒 Security & Air-Gap Verification

* **Strict Sandboxing**: Parquet dataset paths must reside in `ALLOWED_INGEST_DIRS` (`/app/data`, `/app/data/ingest`). `/tmp` is excluded by default.
* **Matter Authorization**: Set `API_KEY` in `.env` to enforce `X-API-Key` headers on all case and consult endpoints.
* **Zero Egress**: Monitor traffic with `tcpdump` or `docker stats` to verify zero outbound network calls.
* **Security Contact**: Report vulnerabilities privately to **security@krusch.io**.

---

## ⚖️ Ethics & Professional Responsibility (ABA Model Rule 1.1)

Attorneys maintain a strict ethical duty of technological competence (*see* ABA Formal Opinion 512; State Bar of CA Formal Opinion 2023-207):
* **Automated Guardrails**: KruschLaw scans generated briefs (`verify_citation_grounding`). Sections or quotes not present in retrieved context are flagged with an explicit advisory.
* **Verification Mandate**: Outputs must be Shepardized and reviewed by admitted counsel prior to filing or advising clients.

---

## 🧪 Automated Testing

Run the offline regression suite:
```bash
python -m unittest discover tests
```

---

## 📜 License

KruschLaw is open-source software licensed under the **[MIT License](LICENSE)**.
Third-party datasets (such as LOCUS-v1) remain governed by their respective licenses (e.g. CC-BY-NC-4.0).
