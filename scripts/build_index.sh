#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

DATA_DIR="${1:-/Users/rubendiezllamas/Desktop/proyectos/reconocimiento_skus/Fotos}"
OUT_DIR="${2:-backend/data}"

cd "$ROOT_DIR"
source "$BACKEND_DIR/.venv/bin/activate"
# Indexado offline del dataset base (sin storage incremental)
python -m backend.index.build --data_dir "$DATA_DIR" --out_dir "$OUT_DIR" --skip_storage
