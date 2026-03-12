from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _launcher_common import BACKEND_DIR, REPO_ROOT, load_project_env, read_setting, run_checked, venv_python


def main() -> int:
    env = load_project_env()

    parser = argparse.ArgumentParser(description="Run FastAPI backend")
    parser.add_argument("--host", default=read_setting(env, "BACKEND_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(read_setting(env, "BACKEND_PORT", "8000")))
    parser.add_argument("--https", action="store_true", help="Enable HTTPS with cert files")
    parser.add_argument("--cert-file", default=str(REPO_ROOT / "certs" / "dev-cert.pem"))
    parser.add_argument("--key-file", default=str(REPO_ROOT / "certs" / "dev-key.pem"))
    parser.add_argument("--reload", action="store_true", help="Enable autoreload")
    parser.add_argument("--no-reload", action="store_true", help="Disable autoreload")
    parser.set_defaults(reload=True)
    args = parser.parse_args()

    py = venv_python()
    if not py.exists():
        raise SystemExit("No existe backend/.venv. Ejecuta primero setup_backend.")

    reload_enabled = args.reload and not args.no_reload

    cmd = [
        str(py),
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    if reload_enabled:
        cmd.append("--reload")

    if args.https:
        cert = Path(args.cert_file).expanduser().resolve()
        key = Path(args.key_file).expanduser().resolve()
        if not cert.exists() or not key.exists():
            raise SystemExit(f"Certificados no encontrados: cert={cert}, key={key}")
        cmd.extend(["--ssl-certfile", str(cert), "--ssl-keyfile", str(key)])

    run_checked(cmd, cwd=REPO_ROOT, env=env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
