#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "${PROJECT_DIR}/.venv/bin/pytest" ]] && head -n 1 "${PROJECT_DIR}/.venv/bin/pytest" | grep -q '^#!'; then
  SHEBANG_BIN="$(head -n 1 "${PROJECT_DIR}/.venv/bin/pytest" | sed 's/^#!//; s/[[:space:]].*//')"
  if [[ -x "${SHEBANG_BIN}" ]]; then
    echo "✅ Verified runnable pytest at ${PROJECT_DIR}/.venv/bin/pytest"
    exit 0
  fi
fi

if command -v python3 >/dev/null 2>&1 && python3 -m pytest --version >/dev/null 2>&1; then
  echo "✅ Verified runnable pytest via $(command -v python3) -m pytest"
  exit 0
fi

echo "❌ ERROR: pytest is not available in ${PROJECT_DIR}/.venv or system python3. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
exit 1
