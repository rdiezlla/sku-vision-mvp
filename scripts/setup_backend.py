from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _launcher_common import BACKEND_DIR, python_cmd, run_checked, venv_python


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup backend virtualenv and dependencies")
    parser.add_argument("--python", default=python_cmd(), help="Python executable to create venv")
    parser.add_argument("--upgrade-pip", action="store_true", help="Upgrade pip/setuptools/wheel")
    parser.add_argument("--skip-torch-cpu", action="store_true", help="Skip CPU-only PyTorch preinstall")
    args = parser.parse_args()

    venv_dir = BACKEND_DIR / ".venv"
    requirements = BACKEND_DIR / "requirements.txt"

    if not requirements.exists():
        raise SystemExit(f"No se encontró requirements.txt en {requirements}")

    if not venv_dir.exists():
        print(f"Creando entorno virtual en {venv_dir}...")
        run_checked([args.python, "-m", "venv", str(venv_dir)], cwd=BACKEND_DIR)

    py = venv_python()
    if not py.exists():
        raise SystemExit(f"Python del venv no encontrado: {py}")

    if args.upgrade_pip:
        run_checked([str(py), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], cwd=BACKEND_DIR)

    if not args.skip_torch_cpu:
        print("Instalando PyTorch CPU-only...")
        run_checked(
            [
                str(py),
                "-m",
                "pip",
                "install",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
                "torch>=2.2",
            ],
            cwd=BACKEND_DIR,
        )

    print("Instalando dependencias backend...")
    run_checked([str(py), "-m", "pip", "install", "-r", str(requirements)], cwd=BACKEND_DIR)

    print(f"Backend listo: {BACKEND_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
