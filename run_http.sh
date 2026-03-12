#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if [ ! -x "backend/.venv/bin/python" ]; then
  echo "[setup] Creando backend/.venv e instalando dependencias..."
  "$PYTHON_BIN" scripts/setup_backend.py
fi

if [ ! -d "frontend/node_modules" ]; then
  echo "[setup] Instalando dependencias frontend..."
  "$PYTHON_BIN" scripts/setup_frontend.py
fi

echo "[run] Arrancando SKU Vision en HTTP..."
exec "$PYTHON_BIN" scripts/dev_up.py "$@"
