from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from _launcher_common import (
    BACKEND_DIR,
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch backend + frontend (HTTP)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--no-auto-setup", action="store_true")
    parser.add_argument("--no-auto-index", action="store_true")
    args = parser.parse_args()

    env = load_project_env()
    auto_setup = not args.no_auto_setup
    auto_index = not args.no_auto_index

    ensure_dependencies(env, auto_setup=auto_setup)
    ensure_index(env, auto_build_index=auto_index)

    backend_log = "backend_http.log"
    frontend_log = "frontend_http.log"

    local_ip = preferred_local_ip()
    backend_url = f"http://{local_ip}:{args.backend_port}"

    backend_env = env.copy()
    backend_env["BACKEND_HOST"] = args.host
    backend_env["BACKEND_PORT"] = str(args.backend_port)
    backend_env["ALLOW_ORIGINS"] = build_allow_origins(
        [
            f"http://localhost:{args.frontend_port}",
            f"http://127.0.0.1:{args.frontend_port}",
            f"http://{local_ip}:{args.frontend_port}",
        ]
    )

    frontend_env = env.copy()
    frontend_env["VITE_BACKEND_URL"] = backend_url

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
        backend = start_logged_process("backend", backend_cmd, REPO_ROOT, backend_env, backend_log)
        processes.append(backend)
        if not wait_until_healthy(backend, timeout_seconds=5):
            raise SystemExit(f"Backend no arrancó. Revisa {backend.log_file}")

        frontend = start_logged_process("frontend", frontend_cmd, FRONTEND_DIR, frontend_env, frontend_log)
        processes.append(frontend)
        if not wait_until_healthy(frontend, timeout_seconds=5):
            raise SystemExit(f"Frontend no arrancó. Revisa {frontend.log_file}")

        print("Servicios HTTP activos:")
        print(f"- Frontend local: http://localhost:{args.frontend_port}")
        print(f"- Frontend móvil: http://{local_ip}:{args.frontend_port}")
        print(f"- Backend: {backend_url}")
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
