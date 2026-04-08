from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_FILES = [
    REPO_ROOT / "backend" / "data" / "sku_prototypes.npy",
    REPO_ROOT / "backend" / "data" / "image_embeddings.npy",
    REPO_ROOT / "backend" / "data" / "mapping.json",
]
STATIC_INDEX_FILE = REPO_ROOT / "backend" / "static_dist" / "index.html"


def index_exists() -> bool:
    return all(path.exists() for path in INDEX_FILES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run single-server backend (serves API + optional static frontend)")
    parser.add_argument("--host", default=os.getenv("BACKEND_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BACKEND_PORT", "8000")))
    parser.add_argument("--https", action="store_true")
    parser.add_argument("--cert-file", default=str(REPO_ROOT / "certs" / "dev-cert.pem"))
    parser.add_argument("--key-file", default=str(REPO_ROOT / "certs" / "dev-key.pem"))
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--auto-build-index", action="store_true")
    args = parser.parse_args()

    if not index_exists():
        if args.auto_build_index:
            dataset = os.getenv("DATASET_ROOT", str(REPO_ROOT / "sample_data" / "Fotos"))
            out_dir = os.getenv("DATA_DIR", str(REPO_ROOT / "backend" / "data"))
            print(f"Índice no encontrado. Construyendo desde {dataset} -> {out_dir} ...")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "backend.index.build",
                    "--data_dir",
                    dataset,
                    "--out_dir",
                    out_dir,
                    "--skip_storage",
                ],
                cwd=str(REPO_ROOT),
                check=True,
            )
        else:
            print("[WARN] No se encontró índice en backend/data.")
            print("       Ejecuta: python scripts/build_index.py")

    if STATIC_INDEX_FILE.exists():
        print(f"Frontend estático detectado: {STATIC_INDEX_FILE}")
        print("La app web se servirá en la misma URL del backend.")
    else:
        print("[WARN] No existe backend/static_dist/index.html.")
        print("       Ejecuta: python scripts/build_static_frontend.py")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]

    if args.reload:
        cmd.append("--reload")

    if args.https:
        cert = Path(args.cert_file).expanduser().resolve()
        key = Path(args.key_file).expanduser().resolve()
        if not cert.exists() or not key.exists():
            raise SystemExit(f"Certificados no encontrados: cert={cert}, key={key}")
        cmd.extend(["--ssl-certfile", str(cert), "--ssl-keyfile", str(key)])

    print("Ejecutando:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(REPO_ROOT), check=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Error ejecutando: {exc}", file=sys.stderr)
        raise SystemExit(exc.returncode)
