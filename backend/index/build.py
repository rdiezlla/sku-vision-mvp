from __future__ import annotations

import argparse
import logging
from pathlib import Path

from backend.index.store import SkuSearchIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Construye índices de SKUs a partir del dataset de imágenes")
    parser.add_argument("--data_dir", required=True, help="Ruta del dataset Fotos/<SKU>/*")
    parser.add_argument("--out_dir", default="backend/data", help="Directorio de salida para índices")
    parser.add_argument("--storage_dir", default="backend/storage", help="Directorio de storage incremental")
    parser.add_argument("--embedding_backend", default="clip", choices=["clip", "dino", "dinov2"], help="Motor de embeddings")
    parser.add_argument("--model_id", default="openai/clip-vit-base-patch32", help="Modelo de embeddings")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size para embeddings")
    parser.add_argument(
        "--prototype_method",
        choices=["mean", "median"],
        default="mean",
        help="Método para prototipo por SKU",
    )
    parser.add_argument(
        "--skip_storage",
        action="store_true",
        help="No incluir imágenes de backend/storage durante el build",
    )
    return parser.parse_args()


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    storage_dir = Path(args.storage_dir).expanduser().resolve()

    setup_logging(out_dir / "logs" / "build.log")

    index = SkuSearchIndex(
        dataset_root=data_dir,
        data_dir=out_dir,
        storage_root=storage_dir,
        model_id=args.model_id,
        batch_size=args.batch_size,
        embedding_backend=args.embedding_backend,
        prototype_method=args.prototype_method,
        include_storage_on_build=not args.skip_storage,
    )

    stats = index.build(data_dir=data_dir, include_storage=not args.skip_storage)

    print("Indexado offline completado")
    print(f"- Nº SKUs: {stats['sku_count']}")
    print(f"- Nº imágenes: {stats['image_count']}")
    print(f"- Imágenes corruptas saltadas: {stats['skipped_images']}")
    print(f"- Tiempo: {stats['seconds']} s")
    print(f"- Device: {stats['device']}")
    print(f"- Embeddings: {stats['embedding_backend']} / {stats['model_id']}")
    print(f"- Engine: {stats['index_engine']}")
    print(f"- Output: {stats['out_dir']}")


if __name__ == "__main__":
    main()
