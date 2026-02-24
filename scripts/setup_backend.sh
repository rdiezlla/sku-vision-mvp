#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

cd "$BACKEND_DIR"
python3 -m venv .venv
source .venv/bin/activate

if python -c "import fastapi, torch, transformers" >/dev/null 2>&1; then
  echo "Dependencias backend ya instaladas. Saltando pip install."
else
  pip install -r requirements.txt
fi

echo "Backend listo en: $BACKEND_DIR"
