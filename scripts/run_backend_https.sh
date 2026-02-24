#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
CERT_FILE="$ROOT_DIR/certs/dev-cert.pem"
KEY_FILE="$ROOT_DIR/certs/dev-key.pem"

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
  echo "Faltan certificados HTTPS. Ejecuta primero: ./scripts/setup_https.sh"
  exit 1
fi

cd "$ROOT_DIR"
source "$BACKEND_DIR/.venv/bin/activate"
uvicorn backend.app:app --host 0.0.0.0 --port 8443 --reload --ssl-keyfile "$KEY_FILE" --ssl-certfile "$CERT_FILE"
