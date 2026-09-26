# 🤝 Contributing to KruschLaw

Welcome, and thank you for contributing to KruschLaw!

KruschLaw is an air-gapped, sovereign legal intelligence engine and versioned statutory graph. Because our users rely on deterministic legal precedence and strict statutory grounding, all contributions must uphold non-negotiable architectural invariants.

---

## 🏛️ Core Principles & Invariant Boundaries

1. **Air-Gap Compliance (Zero External Cloud I/O)**:
   - KruschLaw never makes outbound requests to third-party public cloud APIs, hosted LLM endpoints, telemetry trackers, or external servers.
   - All models run locally on loopback (`127.0.0.1` / `::1`) via Ollama or in headless mock mode.
2. **Confirmed-Edge Only Precedence (INV-1)**:
   - Machine-proposed preemption or amendment edges (`status='proposed'`) must never silently alter governing law in the resolver. Precedence resolution walks strictly confirmed edges (`status='confirmed'`).
3. **Temporal As-Of Date Validity (INV-2)**:
   - All statutory inquiries evaluate law strictly as of the inquiry date (`as_of_date`). Future legislative enactments cannot retroactively govern past events.
4. **No Silent Keyword Fallback (INV-4)**:
   - Controlling authority selection is an authority hierarchy and DAG walk, never a lexical or substring search. Unindexed doctrines return an explicit `CoverageHole`.
5. **Two-Pass Assertion Grounding (INV-6)**:
   - Every generated legal claim is verified via Pass A (mechanical validity) and Pass B (propositional entailment). Mutations systematically flip to canonical failure codes.
6. **Immutable Audit Trail (INV-7)**:
   - All compliance records, access events, and cryptographic purge receipts are append-only and cannot be modified or deleted.
7. **Legal Hold Protection (INV-9)**:
   - Matters subject to litigation hold (`case.legal_hold = True`) block all deletion and purge operations with `HTTP 423 Locked`.
8. **UPL & Legal Ethics Compliance**:
   - KruschLaw is a research and decision-support engine, not a law firm. All generated documents are marked provisional work product requiring admitted attorney review.

---

## 🛠️ Local Development Setup

### 1. Clone & Virtual Environment
```bash
git clone https://github.com/kruschdev/krusch-law.git
cd krusch-law
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-backend.txt
pip install -r requirements-frontend.txt
```

### 2. Run in Headless Mode (Zero GPU / Zero Dependencies)
KruschLaw ships with a bundled, pre-seeded SQLite database (`data/demo.db`) and deterministic vector generation:
```bash
HEADLESS_MODE=1 uvicorn src.backend.main:app --host 127.0.0.1 --port 8085
```
Visit `http://127.0.0.1:8085/docs` to interact with the OpenAPI documentation immediately.

### 3. Run the 60-Second Headless Demo
```bash
python scripts/demo_60s.py
```
Executes statutory preemption DAG traversal, temporal gating, and proposition grounding in under 0.10s.

---

## 🧪 Verification & Test Suite

Before opening a pull request, all automated test batteries must pass cleanly:

### 1. Run Complete Test Suite (145 Tests)
```bash
pytest tests/ -v
```

### 2. Run Core Invariant Tests
```bash
pytest tests/test_graph_invariants.py tests/test_security_hardening.py tests/unit/test_grounding_properties.py -v
```

### 3. Run Golden Retrieval & Grounding Evaluation Gate
```bash
python scripts/eval_retrieval_and_grounding.py
```
*Note: Any regression causing a non-zero False Support Rate or failure on the 5 conflict pairs will block CI merge.*

### 4. Code Quality & Formatting
```bash
ruff check .
```

---

## 📋 Pull Request Checklist

When submitting a pull request, ensure your branch passes all items in this checklist:

- [ ] **Tests Passing**: Full test suite passes cleanly with zero errors (`pytest tests/`).
- [ ] **Zero False Support**: `python scripts/eval_retrieval_and_grounding.py` reports 0.00% False Support Rate across the labeled golden set.
- [ ] **Invariant Conformance**: Code does not violate any rules documented in [`docs/INVARIANTS.md`](docs/INVARIANTS.md).
- [ ] **Zero Cloud I/O**: No third-party public cloud network calls or unapproved external dependencies added.
- [ ] **Pre-Spool Header Validation**: Any file ingestion logic validates MIME magic bytes before writing to disk.
- [ ] **Changelog Updated**: Brief description added under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md).
