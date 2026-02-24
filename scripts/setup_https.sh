#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CERTS_DIR="$ROOT_DIR/certs"
CERT_FILE="$CERTS_DIR/dev-cert.pem"
KEY_FILE="$CERTS_DIR/dev-key.pem"

if ! command -v mkcert >/dev/null 2>&1; then
  echo "mkcert no está instalado. Instálalo con: brew install mkcert nss"
  exit 1
fi

mkdir -p "$CERTS_DIR"

IP_EN0="$(ipconfig getifaddr en0 2>/dev/null || true)"
IP_EN1="$(ipconfig getifaddr en1 2>/dev/null || true)"

NAMES=("localhost" "127.0.0.1" "::1")
if [[ -n "$IP_EN0" ]]; then NAMES+=("$IP_EN0"); fi
if [[ -n "$IP_EN1" && "$IP_EN1" != "$IP_EN0" ]]; then NAMES+=("$IP_EN1"); fi

mkcert -install
mkcert -cert-file "$CERT_FILE" -key-file "$KEY_FILE" "${NAMES[@]}"

CAROOT="$(mkcert -CAROOT)"
cp "$CAROOT/rootCA.pem" "$CERTS_DIR/rootCA.pem"

echo "Certificados HTTPS generados:"
echo "- Cert: $CERT_FILE"
echo "- Key : $KEY_FILE"
echo "- CA  : $CERTS_DIR/rootCA.pem"
echo ""
echo "Para iPhone: instala y confía en rootCA.pem (Ajustes > General > Información > Ajustes de confianza de certificados)."
