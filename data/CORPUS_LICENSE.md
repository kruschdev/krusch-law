# 📜 Evaluation Corpus License & Data Provenance

> **Authoritative Compliance Statement**: This document defines the legal provenance, copyright status, and usage licensing for all statutory corpora, evaluation fixtures, and demo databases bundled within KruschLaw.

---

## 1. Provenance Classifications

All statutory texts, municipal ordinances, and evaluation fixtures in `data/` belong to one of two strictly documented, non-confidential categories:

### Category A: Public Domain California & Municipal Codes
- **Source**:
  - California State Legislature (California Civil Code, including §§ 1946.2, 1950.5, 1954, 789.3, and California Tenant Protection Act of 2019 / Assembly Bill 12).
  - City of Oakland (Oakland Municipal Code Chapter 8.22, Rent Adjustment Program & Just Cause Eviction).
- **Legal Status**:
  - Government edicts, public statutes, and municipal codes are in the public domain and not subject to copyright under U.S. law (*Georgia v. Public.Resource.Org, Inc.*, 140 S. Ct. 1498 (2020)).
- **Fair Use & Reproduction**:
  - Evaluated and reproduced under 17 U.S.C. § 107 for automated legal informatics research, software benchmarking, and retrieval evaluation.
- **Privacy & Redaction Policy**:
  - No private tenant personal identifiers, court case docket records, or confidential client records are included in the baseline law store.

### Category B: Synthetic Adversarial Fixtures & Conflict Pairs
- **Source**:
  - 100% synthetically authored by the KruschLaw engineering team specifically designed to test algorithmic edge cases (`tests/eval/test_conflict_pairs.py`, `tests/unit/test_grounding_properties.py`).
- **Composition**: Structured legal mock text containing targeted edge cases:
  - Temporal amendment conflicts (Pre-AB 12 two-month cap vs Post-AB 12 one-month cap).
  - Spatial preemption conflicts (Oakland Municipal Code vs California Civil Code Costa-Hawkins).
  - Timeline and notice mutations (21-day deposit accounting mutated to 14, 30, 45 days).
  - Duty and polarity negations (landlord entering without 24-hr written notice).
  - Invented / ungrounded statutory section citations.
- **Licensing**: Released under the **Creative Commons Attribution 4.0 International (CC-BY-4.0)** license and dual-licensed under the **MIT License**.

---

## 2. Zero Confidential Client Data Warranty

The authors of KruschLaw warrant that:
1. **Zero Client Data**: No confidential, attorney-client privileged, work product, or private client matter records from any tenant or enterprise are included in this repository.
2. **Deterministic Reproducibility**: Third-party legal clinics, public defenders, and open-source contributors can freely clone, execute, inspect, and redistribute the benchmark fixtures without intellectual property infringement or unauthorized practice of law liability.

---

## 3. Bundled SQLite Demo (`data/demo.db`)

The pre-seeded SQLite database file (`data/demo.db`) is derived strictly from public California and municipal statutory provisions and synthetic evaluation fixtures. It contains:
- 16 substantive California Civil Code and Oakland Municipal Code provisions.
- Confirmed preemption and amendment relationship edges for interactive Streamlit and REST API evaluation.
- Pre-computed 1024-dimensional pseudo-vectors for offline semantic retrieval evaluation with zero external Ollama or GPU dependencies.
