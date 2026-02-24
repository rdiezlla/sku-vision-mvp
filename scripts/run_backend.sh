#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"

cd "$ROOT_DIR"
source "$BACKEND_DIR/.venv/bin/activate"
uvicorn backend.app:app --host "$HOST" --port "$PORT" --reload
