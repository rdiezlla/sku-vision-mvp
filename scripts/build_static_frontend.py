from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from _launcher_common import FRONTEND_DIR, REPO_ROOT, npm_command


def main() -> int:
    parser = argparse.ArgumentParser(description="Build frontend and copy dist to backend/static_dist")
    parser.add_argument("--skip-build", action="store_true", help="Skip npm build and only sync existing dist")
    args = parser.parse_args()

    dist_dir = FRONTEND_DIR / "dist"
    static_dir = REPO_ROOT / "backend" / "static_dist"

    if not args.skip_build:
        subprocess.run([npm_command(), "run", "build"], cwd=str(FRONTEND_DIR), check=True)

    if not dist_dir.exists():
        raise SystemExit(f"No existe {dist_dir}. Ejecuta npm run build en frontend.")

    if static_dir.exists():
        shutil.rmtree(static_dir)
    shutil.copytree(dist_dir, static_dir)

    print(f"Frontend estático actualizado en: {static_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
