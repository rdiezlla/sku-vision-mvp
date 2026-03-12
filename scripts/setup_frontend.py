from __future__ import annotations

import argparse
import subprocess
import sys

from _launcher_common import FRONTEND_DIR, npm_command, run_checked


def main() -> int:
    parser = argparse.ArgumentParser(description="Setup frontend dependencies")
    parser.parse_args()

    print("Instalando dependencias frontend (npm install)...")
    run_checked([npm_command(), "install"], cwd=FRONTEND_DIR)
    print(f"Frontend listo: {FRONTEND_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
