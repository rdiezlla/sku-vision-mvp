#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "\nDeteniendo backend (PID $BACKEND_PID)..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

if [[ ! -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  echo "No existe backend/.venv. Ejecuta primero: ./scripts/setup_backend.sh"
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "No existe frontend/node_modules. Ejecuta primero: ./scripts/setup_frontend.sh"
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/data/sku_prototypes.npy" || ! -f "$BACKEND_DIR/data/image_embeddings.npy" || ! -f "$BACKEND_DIR/data/mapping.json" ]]; then
  echo "Índice no encontrado. Construyendo índice inicial..."
  ./scripts/build_index.sh
fi

source "$BACKEND_DIR/.venv/bin/activate"

echo "Levantando backend en http://0.0.0.0:8000 ..."
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload > /tmp/sku_backend.log 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "El backend no arrancó. Revisa /tmp/sku_backend.log"
  exit 1
fi

echo "Levantando frontend en http://0.0.0.0:5173 ..."
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 --port 5173
