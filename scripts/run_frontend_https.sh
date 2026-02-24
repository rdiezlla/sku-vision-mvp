#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
CERT_FILE="$ROOT_DIR/certs/dev-cert.pem"
KEY_FILE="$ROOT_DIR/certs/dev-key.pem"

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  echo "Faltan certificados HTTPS. Ejecuta primero: ./scripts/setup_https.sh"
  exit 1
fi

IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo localhost)"

cd "$FRONTEND_DIR"
DEV_HTTPS=true \
DEV_SSL_KEY_FILE="$KEY_FILE" \
DEV_SSL_CERT_FILE="$CERT_FILE" \
VITE_BACKEND_URL="https://$IP:8443" \
npm run dev -- --host 0.0.0.0 --port 5173
