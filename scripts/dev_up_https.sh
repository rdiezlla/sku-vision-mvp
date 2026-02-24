#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
CERT_FILE="$ROOT_DIR/certs/dev-cert.pem"
KEY_FILE="$ROOT_DIR/certs/dev-key.pem"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "\nDeteniendo backend HTTPS (PID $BACKEND_PID)..."
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

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  echo "Faltan certificados HTTPS. Ejecuta primero: ./scripts/setup_https.sh"
  exit 1
fi

if [[ ! -f "$BACKEND_DIR/data/sku_prototypes.npy" || ! -f "$BACKEND_DIR/data/image_embeddings.npy" || ! -f "$BACKEND_DIR/data/mapping.json" ]]; then
  echo "Índice no encontrado. Construyendo índice inicial..."
  ./scripts/build_index.sh
fi

source "$BACKEND_DIR/.venv/bin/activate"

echo "Levantando backend HTTPS en https://0.0.0.0:8443 ..."
uvicorn backend.app:app --host 0.0.0.0 --port 8443 --reload --ssl-keyfile "$KEY_FILE" --ssl-certfile "$CERT_FILE" > /tmp/sku_backend_https.log 2>&1 &
BACKEND_PID=$!

sleep 2
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  echo "El backend HTTPS no arrancó. Revisa /tmp/sku_backend_https.log"
  exit 1
fi

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"
echo "Levantando frontend HTTPS en https://0.0.0.0:5173 ..."
echo "Backend URL para frontend: https://$IP:8443"

cd "$FRONTEND_DIR"
DEV_HTTPS=true \
DEV_SSL_KEY_FILE="$KEY_FILE" \
DEV_SSL_CERT_FILE="$CERT_FILE" \
VITE_BACKEND_URL="https://$IP:8443" \
npm run dev -- --host 0.0.0.0 --port 5173
