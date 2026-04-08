#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing Python virtual environment at $ROOT_DIR/.venv"
  echo "Create it with: python3 -m venv .venv"
  exit 1
fi

exec "$PYTHON_BIN" -m pytest "$ROOT_DIR/tests/smoke" -q
