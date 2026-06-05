from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _launcher_common import BACKEND_DIR, load_project_env, run_checked, venv_python


def main() -> int:
    env = load_project_env()

    default_dataset = env.get("DATASET_ROOT", str((Path(__file__).resolve().parents[1] / "Fotos")))
    default_out_dir = env.get("DATA_DIR", "backend/data")
    default_backend = env.get("EMBEDDING_BACKEND", "clip")
    default_model = env.get("EMBEDDING_MODEL_ID", env.get("CLIP_MODEL_ID", "openai/clip-vit-base-patch32"))

    parser = argparse.ArgumentParser(description="Build SKU index")
    parser.add_argument("--data-dir", default=default_dataset, help="Dataset root with SKU folders")
    parser.add_argument("--out-dir", default=default_out_dir, help="Output directory for index files")
    parser.add_argument("--skip-storage", action="store_true", help="Exclude backend/storage during build")
    parser.add_argument("--include-storage", action="store_true", help="Include backend/storage during build")
    parser.add_argument("--embedding-backend", default=default_backend, choices=["clip", "dino", "dinov2"])
    parser.add_argument("--model-id", default=default_model)
    args = parser.parse_args()

    py = venv_python()
    if not py.exists():
        raise SystemExit("No existe backend/.venv. Ejecuta primero setup_backend.")

    data_dir = Path(args.data_dir).expanduser().resolve()
    out_dir_arg = args.out_dir

    if not data_dir.exists():
        raise SystemExit(f"DATASET_ROOT no existe: {data_dir}")

    cmd = [
        str(py),
        "-m",
        "backend.index.build",
        "--data_dir",
        str(data_dir),
        "--out_dir",
        out_dir_arg,
        "--embedding_backend",
        args.embedding_backend,
        "--model_id",
        args.model_id,
    ]

    use_skip_storage = True
    if args.include_storage:
        use_skip_storage = False
    if args.skip_storage:
        use_skip_storage = True
    if use_skip_storage:
        cmd.append("--skip_storage")

    print(f"Construyendo índice desde {data_dir} -> {out_dir_arg}")
    run_checked(cmd, cwd=BACKEND_DIR.parents[0], env=env)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
