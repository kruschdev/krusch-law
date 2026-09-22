# ⚖️ KruschLaw

> **Private, Air-Gapped Legal RAG & Ordinance Intelligence Engine (Research Prototype)**  
> *Query local municipal codes, statutes, and client matter records with 100% on-premise privacy and zero cloud data leakage.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Version: 0.2.0-dev](https://img.shields.io/badge/Version-0.2.0--dev%20(Prototype)-orange.svg)](https://github.com/kruschdev/krusch-law)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.31+-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io)
[![pgvector](https://img.shields.io/badge/PostgreSQL-pgvector%2016-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com)

---

## 🏛️ Why KruschLaw?

Law firms, legal aid organizations, and corporate legal departments face an impossible dilemma:
1. **Public Cloud LLMs**: Expose privileged client communications and confidential matter facts to external vendor logging, violating attorney-client privilege and state bar ethics rules.
2. **Manual Research**: Sifting through thousands of municipal ordinances, county codes, and changing statutes consumes dozens of non-billable hours.

**KruschLaw** is an open-source experimental research prototype exploring sovereign, on-premise legal retrieval. It is engineered to test local retrieval-augmented generation (RAG) running entirely on private infrastructure without third-party API exposure.

---

## 🚀 Key Features

* 🛡️ **100% Air-Gapped & Sovereign**: Zero cloud dependencies, external CDNs, or telemetry calls. Port bindings default strictly to `127.0.0.1` for host containment.
* 🔐 **Matter Authorization Layer**: Protects client facts and intake records with optional `API_KEY` header verification (`X-API-Key`).
* ⚡ **Production HNSW Vector Indexing**: Automatically builds `pgvector` HNSW indexes (`m=16, ef_construction=64`) on startup to ensure sub-millisecond retrieval on large-scale municipal corpora.
* 🔍 **Semantic Ordinance & Statute Retrieval**: Matches client factual narratives against municipal codes, state statutes, and administrative rules using `pgvector` cosine similarity.
* 🛡️ **Citation-Constrained Grounding Guardrail**: Automated post-generation scanner that extracts statutory section citations from model output and verifies them against retrieved authorities. Flags hallucinated sections with explicit advisories.
* 📦 **LOCUS-v1 Parquet & Municipal Ingestion**: Built-in engine to parse and normalize large-scale municipal law datasets with automatic schema resolution and sandboxed directory controls.
* 💼 **Confidential Matter Portfolio**: Securely log, manage, and vectorize client case matters with local 1024-dim dense embeddings (`bge-large`).
* 📋 **Structured 4-Part Legal Briefs**: Automatically generates citation-backed analyses formatted into Executive Summary, Statutory Authorities, Factual Matrix Analysis, and Strategic Next Steps using local instruction models (`qwen2.5:14b`).
* 🔬 **Dynamic Security Diagnostics**: `/health` actively inspects runtime network topologies to verify that Ollama inference hosts reside strictly on loopback or private RFC1918 subnets.
* ⚖️ **UPL & Ethics Guardrails**: Adheres to strict Unauthorized Practice of Law (UPL) guidelines and ABA Model Rule 1.1 duty of technological competence, ensuring all outputs feature prominent professional review disclaimers.


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
            │        127.0.0.1:5435        │       │  └─ qwen2.5:14b (LLM)       │
            └──────────────────────────────┘       └─────────────────────────────┘
```

---

## ⚡ Quickstart

### Prerequisites
* [Docker](https://docs.docker.com/get-docker/) & Docker Compose
* [Ollama](https://ollama.com/) running locally with the required models pulled:
  ```bash
  ollama pull bge-large
  ollama pull qwen2.5:14b
  ```

### 1. Clone & Configure
```bash
git clone https://github.com/kruschdev/krusch-law.git
cd krusch-law

# Copy environment template
cp .env.example .env
```

### 2. Launch the Stack
```bash
docker compose up --build -d
```

Verify services are healthy:
* **Frontend UI**: [http://localhost:8505](http://localhost:8505)
* **Backend API Docs**: [http://localhost:8085/docs](http://localhost:8085/docs)
* **Health Check**: [http://localhost:8085/health](http://localhost:8085/health)

---

## 📥 Ingesting Legal Data

### Option A: Built-in California Seed Ordinances
In the web dashboard sidebar, click **"🚀 Seed California Ordinances"** (or run via curl):
```bash
curl -X POST http://localhost:8085/api/ingest/mock
```
This loads and embeds sample tenant rights, eviction control, and municipal noise ordinances for Oakland, San Francisco, and Los Angeles.

### Option B: Ingesting LOCUS-v1 Municipal Codes (Parquet)
Download municipal law extracts (such as LOCUS-v1 or municipal open-data sets) into your project or container volume:
```bash
curl -X POST http://localhost:8085/api/ingest/parquet \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/ordinances.parquet", "limit": 250}'
```

---

## 💼 Law Office Evaluation & Trial Guide

If you are evaluating KruschLaw within a law practice:

1. **Hardware Recommendation**: A dedicated desktop or workstation with an NVIDIA RTX GPU (12GB+ VRAM) or Apple Silicon Mac (M2/M3/M4 with 16GB+ unified memory).
2. **Confidential Test Matter**:
   - Navigate to the **Matter Portfolio** tab.
   - Enter a factual scenario (e.g. *A residential tenant was issued a notice of rent increase exceeding statutory limits without required disclosures*).
   - Click **Save & Generate Matter Embedding**.
3. **Generate Precedent Consultation**:
   - Open the **Precedent Consultation** tab, select the matter, set jurisdiction filters (`State: CA`), and click **Generate Sovereign Legal Brief**.
   - Review the matched legal sections and the resulting analysis brief.

---

## 🔒 Security & Air-Gap Verification

To verify that KruschLaw does not transmit data outside your local environment:
* Monitor container network traffic using `docker stats` or `tcpdump`.
* KruschLaw contains **zero** third-party tracking, analytics, or external telemetry libraries.
* Inspect `src/backend/rag.py` to confirm that all embedding and generation calls target your local `OLLAMA_BASE_URL`.

---

## ⚖️ Ethics, Professional Responsibility & Verification

> [!IMPORTANT]
> **Unauthorized Practice of Law (UPL) Notice**:  
> KruschLaw is an offline artificial intelligence decision-support and issue-spotting system. It is designed to assist admitted attorneys, legal researchers, and self-represented litigants in organizing facts and identifying candidate municipal ordinances and statutes. **KruschLaw is not an attorney, is not a law firm, and does not provide formal legal advice or representation.** All statutory interpretations, section applicability, and analytical conclusions must be independently verified by a licensed attorney admitted to the relevant bar before filing or serving legal documents.

### Duty of Competence & Citation Verification (ABA Model Rule 1.1)
Lawyers maintain a strict ethical obligation of competence when utilizing generative AI tools in legal practice (*see* ABA Formal Opinion 512; State Bar of California Formal Opinion No. 2023-207):
* **Grounding Guardrails**: KruschLaw implements automated post-generation citation parsing (`verify_citation_grounding`). If the model references a statute or municipal section not contained within the retrieved dataset, the output is stamped with an explicit `⚠️ Citation Grounding Advisory`.
* **Zero Hallucination Tolerance**: Attorneys must never submit generative output to a court or administrative tribunal without verifying that cited authorities exist, are currently in force, and have not been amended or preempted.
* **Privilege Preservation**: By keeping all matter facts on-premise within localhost-bound sockets, KruschLaw eliminates third-party disclosure under the work-product doctrine and FRE 502 / Cal. Evid. Code § 954.

---

## 📊 Evaluation & Retrieval Quality

KruschLaw evaluates statutory issue-spotting performance using a local fixture suite:
* **Precision@k & Citation Accuracy**: Verified against known landlord-tenant fact patterns to ensure retrieved sections (e.g. Oakland OMC § 8.22.030, CA Civ. Code § 1950.5) match controlling legal provisions.
* **Automated Regression Suite**: Unit tests run without cloud dependencies via in-memory SQLite and mocked vector math:
  ```bash
  python -m unittest tests/test_pipeline.py
  ```


---

## 🤝 Contributing

We welcome community contributions, additional municipal code ingest parsers, and performance optimizations. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and development workflow.

---

## 📜 License

KruschLaw is open-source software licensed under the **[MIT License](LICENSE)**.
