from __future__ import annotations

import argparse
import subprocess
import sys
import time

from _launcher_common import (
    CERTS_DIR,
    FRONTEND_DIR,
    REPO_ROOT,
    backend_index_exists,
    build_allow_origins,
    load_project_env,
    npm_command,
    preferred_local_ip,
    print_process_logs_hint,
    python_cmd,
    start_logged_process,
    terminate_processes,
    venv_python,
    wait_until_healthy,
)


def ensure_dependencies(env: dict[str, str], auto_setup: bool) -> None:
    py = venv_python()
    if not py.exists():
        if not auto_setup:
            raise SystemExit("No existe backend/.venv. Ejecuta scripts/setup_backend.")
        subprocess.run([python_cmd(), str(REPO_ROOT / "scripts" / "setup_backend.py")], check=True, env=env, cwd=str(REPO_ROOT))

    if not (FRONTEND_DIR / "node_modules").exists():
        if not auto_setup:
            raise SystemExit("No existe frontend/node_modules. Ejecuta scripts/setup_frontend.")
        subprocess.run([python_cmd(), str(REPO_ROOT / "scripts" / "setup_frontend.py")], check=True, env=env, cwd=str(REPO_ROOT))


def ensure_index(env: dict[str, str], auto_build_index: bool) -> None:
    if backend_index_exists():
        return
    if not auto_build_index:
        raise SystemExit("No existe índice en backend/data. Ejecuta scripts/build_index.")
    subprocess.run([python_cmd(), str(REPO_ROOT / "scripts" / "build_index.py")], check=True, env=env, cwd=str(REPO_ROOT))


def ensure_https_certs(env: dict[str, str], force: bool = False) -> None:
    cert = CERTS_DIR / "dev-cert.pem"
    key = CERTS_DIR / "dev-key.pem"
    if cert.exists() and key.exists() and not force:
        return

    cmd = [python_cmd(), str(REPO_ROOT / "scripts" / "setup_https.py")]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, check=True, env=env, cwd=str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch backend + frontend (HTTPS)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--backend-port", type=int, default=8443)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--no-auto-setup", action="store_true")
    parser.add_argument("--no-auto-index", action="store_true")
    parser.add_argument("--force-regenerate-certs", action="store_true")
    args = parser.parse_args()

    env = load_project_env()
    auto_setup = not args.no_auto_setup
    auto_index = not args.no_auto_index

    ensure_dependencies(env, auto_setup=auto_setup)
    ensure_index(env, auto_build_index=auto_index)
    ensure_https_certs(env, force=args.force_regenerate_certs)

    cert_file = (CERTS_DIR / "dev-cert.pem").resolve()
    key_file = (CERTS_DIR / "dev-key.pem").resolve()

    if not cert_file.exists() or not key_file.exists():
        raise SystemExit("No se encontraron certificados. Ejecuta scripts/setup_https.")

    local_ip = preferred_local_ip()

    backend_env = env.copy()
    backend_env.update(
        {
            "BACKEND_HOST": args.host,
            "BACKEND_PORT": str(args.backend_port),
        }
    )

    frontend_env = env.copy()
    frontend_env.update(
        {
            "DEV_HTTPS": "true",
            "DEV_SSL_CERT_FILE": str(cert_file),
            "DEV_SSL_KEY_FILE": str(key_file),
            "VITE_BACKEND_URL": f"https://{local_ip}:{args.backend_port}",
        }
    )

    backend_cmd = [
        str(venv_python()),
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        args.host,
        "--port",
        str(args.backend_port),
        "--reload",
        "--ssl-certfile",
        str(cert_file),
        "--ssl-keyfile",
        str(key_file),
    ]

    frontend_cmd = [
        npm_command(),
        "run",
        "dev",
        "--",
        "--host",
        args.host,
        "--port",
        str(args.frontend_port),
    ]

    processes = []
    try:
        backend_env["ALLOW_ORIGINS"] = build_allow_origins(
            [
                f"https://localhost:{args.frontend_port}",
                f"https://127.0.0.1:{args.frontend_port}",
                f"https://{local_ip}:{args.frontend_port}",
            ]
        )

        backend = start_logged_process("backend", backend_cmd, REPO_ROOT, backend_env, "backend_https.log")
        processes.append(backend)
        if not wait_until_healthy(backend, timeout_seconds=5):
            raise SystemExit(f"Backend HTTPS no arrancó. Revisa {backend.log_file}")

        frontend = start_logged_process("frontend", frontend_cmd, FRONTEND_DIR, frontend_env, "frontend_https.log")
        processes.append(frontend)
        if not wait_until_healthy(frontend, timeout_seconds=5):
            raise SystemExit(f"Frontend HTTPS no arrancó. Revisa {frontend.log_file}")

        print("Servicios HTTPS activos:")
        print(f"- Frontend local: https://localhost:{args.frontend_port}")
        print(f"- Frontend móvil: https://{local_ip}:{args.frontend_port}")
        print(f"- Backend: https://{local_ip}:{args.backend_port}")

        print_process_logs_hint(processes)
        print("Ctrl+C para detener.")

        while True:
            time.sleep(0.8)
            for item in processes:
                if item.process.poll() is not None:
                    raise SystemExit(f"{item.name} terminó inesperadamente. Revisa {item.log_file}")
    except KeyboardInterrupt:
        pass
    finally:
        terminate_processes(processes)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
