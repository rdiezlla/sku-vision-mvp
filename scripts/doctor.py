from __future__ import annotations

import argparse
import socket
import subprocess
import sys
from pathlib import Path

from _launcher_common import (
    BACKEND_DIR,
    CERTS_DIR,
    FRONTEND_DIR,
    REPO_ROOT,
    backend_index_exists,
    command_exists,
    load_project_env,
    venv_python,
)


def _check_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _port_status_line(ports: list[int]) -> tuple[bool, str]:
    busy = [port for port in ports if not _check_port_free(port)]
    if busy:
        return False, f"ocupados: {', '.join(str(port) for port in busy)}"
    return True, f"libres: {', '.join(str(port) for port in ports)}"


def _print_result(ok: bool, label: str, detail: str = "") -> None:
    prefix = "[OK]" if ok else "[WARN]"
    if detail:
        print(f"{prefix} {label}: {detail}")
    else:
        print(f"{prefix} {label}")


def _run_import_check(python_bin: Path) -> tuple[bool, str]:
    cmd = [
        str(python_bin),
        "-c",
        "import fastapi, uvicorn, PIL, numpy, torch, transformers; print('ok')",
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return True, "dependencias backend instaladas"
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip().splitlines()
        return False, stderr[-1] if stderr else "faltan dependencias backend"


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico rapido para SKU Vision MVP (macOS)")
    parser.add_argument("--https", action="store_true", help="Incluye comprobaciones HTTPS")
    args = parser.parse_args()

    env = load_project_env()
    has_warnings = False

    print("== SKU Vision Doctor (macOS) ==")

    py_ok = sys.version_info >= (3, 10)
    _print_result(py_ok, "Python", f"{sys.version.split()[0]} (requerido >= 3.10)")
    has_warnings = has_warnings or not py_ok

    backend_venv_py = venv_python()
    venv_ok = backend_venv_py.exists()
    _print_result(venv_ok, "backend/.venv", str(backend_venv_py))
    has_warnings = has_warnings or not venv_ok

    if venv_ok:
        deps_ok, deps_detail = _run_import_check(backend_venv_py)
        _print_result(deps_ok, "Dependencias backend", deps_detail)
        has_warnings = has_warnings or not deps_ok

    node_ok = command_exists("node")
    npm_ok = command_exists("npm")
    frontend_deps_ok = (FRONTEND_DIR / "node_modules").exists()
    _print_result(node_ok, "Node", "en PATH")
    _print_result(npm_ok, "npm", "en PATH")
    _print_result(frontend_deps_ok, "frontend/node_modules", str(FRONTEND_DIR / "node_modules"))
    has_warnings = has_warnings or not (node_ok and npm_ok and frontend_deps_ok)

    dataset_root = Path(str(env.get("DATASET_ROOT", "")).strip() or (REPO_ROOT / "Fotos")).expanduser()
    dataset_ok = dataset_root.exists()
    _print_result(dataset_ok, "DATASET_ROOT", str(dataset_root))
    has_warnings = has_warnings or not dataset_ok

    index_ok = backend_index_exists()
    _print_result(index_ok, "Indice backend/data", "sku_prototypes.npy + image_embeddings.npy + mapping.json")
    has_warnings = has_warnings or not index_ok

    http_ports_ok, http_ports_detail = _port_status_line([8000, 5173])
    _print_result(http_ports_ok, "Puertos HTTP", http_ports_detail)
    has_warnings = has_warnings or not http_ports_ok

    cert_file = CERTS_DIR / "dev-cert.pem"
    key_file = CERTS_DIR / "dev-key.pem"
    if args.https:
        certs_ok = cert_file.exists() and key_file.exists()
        _print_result(certs_ok, "Certificados HTTPS", f"cert={cert_file} key={key_file}")
        has_warnings = has_warnings or not certs_ok

        https_ports_ok, https_ports_detail = _port_status_line([8443, 5173])
        _print_result(https_ports_ok, "Puertos HTTPS", https_ports_detail)
        has_warnings = has_warnings or not https_ports_ok

    print("\nComandos recomendados:")
    print("1) Setup backend:  python3 scripts/setup_backend.py")
    print("2) Setup frontend: python3 scripts/setup_frontend.py")
    print("3) Build index:    python3 scripts/build_index.py")
    if args.https:
        print("4) Setup certs:    python3 scripts/setup_https.py")
        print("5) Run app:        ./run_https.sh")
    else:
        print("4) Run app:        ./run_http.sh")

    if has_warnings:
        print("\nEstado: WARN (hay puntos por corregir antes de arrancar).")
        return 1

    print("\nEstado: OK (entorno listo).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
