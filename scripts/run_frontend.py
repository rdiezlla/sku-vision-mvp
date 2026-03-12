from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _launcher_common import FRONTEND_DIR, REPO_ROOT, load_project_env, npm_command, run_checked


def main() -> int:
    env = load_project_env()

    parser = argparse.ArgumentParser(description="Run Vite frontend")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--https", action="store_true")
    parser.add_argument("--backend-url", default=env.get("VITE_BACKEND_URL", env.get("BACKEND_URL", "http://localhost:8000")).strip())
    parser.add_argument("--cert-file", default=str(REPO_ROOT / "certs" / "dev-cert.pem"))
    parser.add_argument("--key-file", default=str(REPO_ROOT / "certs" / "dev-key.pem"))
    args = parser.parse_args()

    if not (FRONTEND_DIR / "package.json").exists():
        raise SystemExit(f"No se encontró package.json en {FRONTEND_DIR}")

    process_env = env.copy()
    if args.backend_url:
        process_env["VITE_BACKEND_URL"] = args.backend_url

    if args.https:
        cert = Path(args.cert_file).expanduser().resolve()
        key = Path(args.key_file).expanduser().resolve()
        if not cert.exists() or not key.exists():
            raise SystemExit(f"Certificados no encontrados: cert={cert}, key={key}")

        process_env["DEV_HTTPS"] = "true"
        process_env["DEV_SSL_CERT_FILE"] = str(cert)
        process_env["DEV_SSL_KEY_FILE"] = str(key)

    cmd = [npm_command(), "run", "dev", "--", "--host", args.host, "--port", str(args.port)]
    run_checked(cmd, cwd=FRONTEND_DIR, env=process_env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
