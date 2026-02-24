from __future__ import annotations

import argparse
import random
from pathlib import Path

from PIL import Image

from backend.index.store import SkuSearchIndex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluación rápida top-k usando imágenes indexadas")
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--out_dir", default="backend/data")
    parser.add_argument("--storage_dir", default="backend/storage")
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--k", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data_dir).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    storage_dir = Path(args.storage_dir).expanduser().resolve()

    index = SkuSearchIndex(
        dataset_root=data_dir,
        data_dir=out_dir,
        storage_root=storage_dir,
        model_id="openai/clip-vit-base-patch32",
        batch_size=32,
    )
    index.load()

    records = [record for record in index.mapping_images if Path(record["filepath"]).exists()]
    if not records:
        raise RuntimeError("No hay imágenes válidas para evaluar")

    sample_size = min(args.sample, len(records))
    subset = random.sample(records, sample_size)

    top1 = 0
    topk = 0

    for record in subset:
        with Image.open(record["filepath"]) as img:
            payload = index.search(
                query_image=img.convert("RGB"),
                k=args.k,
                retrieval_top_n=50,
                max_examples=3,
                enable_multicrop=True,
                enable_color_tiebreak=True,
                color_tie_threshold=0.015,
            )
        predicted = [row["sku"] for row in payload["results"]]
        if not predicted:
            continue
        if predicted[0] == record["sku"]:
            top1 += 1
        if record["sku"] in predicted:
            topk += 1

    print(f"Samples evaluadas: {sample_size}")
    print(f"Top-1: {top1 / sample_size:.3f}")
    print(f"Top-{args.k}: {topk / sample_size:.3f}")


if __name__ == "__main__":
    main()
