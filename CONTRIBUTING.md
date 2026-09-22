# Contributing to KruschLaw

Thank you for your interest in improving KruschLaw! We welcome contributions from developers, legal practitioners, legal-tech researchers, and open-source advocates.

---

## 🏛️ Guiding Principles

1. **Air-Gap Integrity**: Never introduce dependencies that silently reach out to external cloud APIs or send telemetry. All data must stay on-premise.
2. **UPL & Legal Ethics Compliance**: AI features must serve as research and decision-support tools, not unqualified legal practice. Ensure proper disclaimers accompany any analytical output.
3. **Data Schema Flexibility**: Municipal and statutory datasets vary widely across jurisdictions. Parsers should handle missing fields gracefully without crashing.

---

## 🛠️ Development Setup

### 1. Fork & Clone
```bash
git clone https://github.com/kruschdev/krusch-law.git
cd krusch-law
```

### 2. Set Up Local Python Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Automated Tests
```bash
python3 -m unittest tests/test_pipeline.py
```

All tests execute in-memory with SQLite fixtures and mock vectors—no running PostgreSQL or Ollama instance is required.

---

## 📥 Contributing Legal Datasets & Parsers

We are actively expanding municipal coverage. If you are adding support for a new county, city, or state:

1. Add your parser or batch script under `src/backend/ingest.py`.
2. Normalize jurisdictional columns:
   - `jurisdiction`: Name of the municipal code or statute book (e.g., `"Chicago Municipal Code"`).
   - `state`: Two-letter state postal code (e.g., `"IL"`).
   - `city_or_county`: City or county name (e.g., `"Chicago"`).
   - `title`: Chapter or title heading.
   - `section`: Specific statutory section number.
   - `content`: Unabridged section body text.
3. Submit sample data or fixtures with your Pull Request.

---

## 📋 Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature-name`.
2. Commit your changes with clear, concise messages.
3. Ensure the test suite passes: `python3 -m unittest discover tests`.
4. Open a Pull Request on GitHub describing what your change accomplishes and any relevant legal context.
