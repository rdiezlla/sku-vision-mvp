from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

import numpy as np
from PIL import Image

from backend.index.clip_embedder import ClipEmbedder

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class IndexPaths:
    root: Path

    @property
    def sku_prototypes(self) -> Path:
        return self.root / "sku_prototypes.npy"

    @property
    def image_embeddings(self) -> Path:
        return self.root / "image_embeddings.npy"

    @property
    def image_color_hists(self) -> Path:
        return self.root / "image_color_hists.npy"

    @property
    def mapping(self) -> Path:
        return self.root / "mapping.json"

    @property
    def sku_index(self) -> Path:
        return self.root / "sku_index.faiss"

    @property
    def image_index(self) -> Path:
        return self.root / "image_index.faiss"

    @property
    def build_log(self) -> Path:
        return self.root / "logs" / "build.log"


class SkuSearchIndex:
    def __init__(
        self,
        dataset_root: Path,
        data_dir: Path,
        storage_root: Path,
        model_id: str,
        batch_size: int,
        prototype_method: str = "mean",
        include_storage_on_build: bool = True,
    ) -> None:
        self.dataset_root = dataset_root
        self.storage_root = storage_root
        self.paths = IndexPaths(root=data_dir)
        self.model_id = model_id
        self.batch_size = batch_size
        self.prototype_method = prototype_method
        self.include_storage_on_build = include_storage_on_build

        self._embedder: Optional[ClipEmbedder] = None
        self._sku_faiss = None
        self._image_faiss = None
        self._loaded = False
        self._lock = RLock()

        self.image_embeddings = np.empty((0, 0), dtype=np.float32)
        self.image_color_hists = np.empty((0, 0), dtype=np.float32)
        self.sku_prototypes = np.empty((0, 0), dtype=np.float32)
        self.mapping_images: List[Dict[str, Any]] = []
        self.sku_to_image_ids: Dict[str, List[int]] = {}
        self.sku_order: List[str] = []
        self.index_engine = "none"

        self.paths.root.mkdir(parents=True, exist_ok=True)
        self.paths.build_log.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("sku_vision.index")

    @property
    def embedder(self) -> ClipEmbedder:
        if self._embedder is None:
            self._embedder = ClipEmbedder(model_id=self.model_id)
        return self._embedder

    @staticmethod
    def _normalize_vector(vector: np.ndarray) -> np.ndarray:
        vector = np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            return vector.astype(np.float32)
        return (vector / norm).astype(np.float32)

    @staticmethod
    def _compute_color_hist(image: Image.Image, bins: int = 8) -> np.ndarray:
        rgb = image.convert("RGB")
        # Evita picos de memoria con fotos muy grandes (móvil 12-48MP).
        max_side = 512
        if max(rgb.size) > max_side:
            rgb = rgb.copy()
            rgb.thumbnail((max_side, max_side))

        arr = np.asarray(rgb, dtype=np.float32) / 255.0
        hist, _ = np.histogramdd(
            arr.reshape(-1, 3),
            bins=(bins, bins, bins),
            range=((0.0, 1.0), (0.0, 1.0), (0.0, 1.0)),
        )
        hist = hist.astype(np.float32).reshape(-1)
        norm = float(np.linalg.norm(hist))
        if norm > 1e-12:
            hist = hist / norm
        return hist

    def _iter_images_from_root(self, root: Path) -> List[Tuple[str, Path]]:
        entries: List[Tuple[str, Path]] = []
        if not root.exists():
            return entries

        for sku_dir in sorted(root.iterdir()):
            if not sku_dir.is_dir():
                continue

            sku = sku_dir.name
            for path in sorted(sku_dir.iterdir()):
                if path.suffix.lower() in IMAGE_EXTENSIONS:
                    entries.append((sku, path.resolve()))
        return entries

    def _collect_entries(self, data_dir: Path, include_storage: bool) -> List[Tuple[str, Path]]:
        entries = self._iter_images_from_root(data_dir)
        if include_storage:
            entries.extend(self._iter_images_from_root(self.storage_root))
        return entries

    def _embed_entries(self, entries: Sequence[Tuple[str, Path]]) -> Tuple[List[Dict[str, str]], np.ndarray, np.ndarray, int]:
        valid_records: List[Dict[str, str]] = []
        embedding_chunks: List[np.ndarray] = []
        hist_chunks: List[np.ndarray] = []
        skipped = 0

        for start in range(0, len(entries), self.batch_size):
            batch = entries[start : start + self.batch_size]
            images: List[Image.Image] = []
            batch_records: List[Dict[str, str]] = []
            batch_hists: List[np.ndarray] = []

            for sku, path in batch:
                try:
                    with Image.open(path) as img:
                        rgb = img.convert("RGB")
                    images.append(rgb)
                    batch_hists.append(self._compute_color_hist(rgb))
                    batch_records.append({"sku": sku, "filepath": str(path)})
                except Exception as exc:  # pragma: no cover - image corruption dependent
                    skipped += 1
                    self.logger.warning("Imagen corrupta o inválida: %s (%s)", path, exc)

            if not images:
                continue

            embeddings = self.embedder.embed_images(images)
            if len(embeddings) != len(batch_records):
                raise RuntimeError("Número de embeddings no coincide con el batch procesado")

            embedding_chunks.append(embeddings)
            hist_chunks.append(np.vstack(batch_hists).astype(np.float32))
            valid_records.extend(batch_records)

        if not valid_records:
            return [], np.empty((0, 0), dtype=np.float32), np.empty((0, 0), dtype=np.float32), skipped

        return (
            valid_records,
            np.vstack(embedding_chunks).astype(np.float32),
            np.vstack(hist_chunks).astype(np.float32),
            skipped,
        )

    def _build_sku_structures(self, records: Sequence[Dict[str, str]], image_embeddings: np.ndarray) -> Tuple[Dict[str, List[int]], List[str], np.ndarray]:
        sku_to_ids: Dict[str, List[int]] = {}
        for idx, record in enumerate(records):
            sku_to_ids.setdefault(record["sku"], []).append(idx)

        sku_order = sorted(sku_to_ids.keys())
        prototypes: List[np.ndarray] = []

        for sku in sku_order:
            ids = sku_to_ids[sku]
            vectors = image_embeddings[ids]
            if self.prototype_method == "median":
                proto = np.median(vectors, axis=0)
            else:
                proto = np.mean(vectors, axis=0)
            prototypes.append(self._normalize_vector(proto))

        if not prototypes:
            return sku_to_ids, sku_order, np.empty((0, 0), dtype=np.float32)

        return sku_to_ids, sku_order, np.vstack(prototypes).astype(np.float32)

    def _mapping_payload(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "prototype_method": self.prototype_method,
            "embedding_dim": int(self.image_embeddings.shape[1]) if self.image_embeddings.size else 0,
            "sku_count": len(self.sku_order),
            "image_count": len(self.mapping_images),
            "sku_order": self.sku_order,
            "sku_to_image_ids": self.sku_to_image_ids,
            "images": self.mapping_images,
        }

    def _write_arrays_and_mapping(self) -> None:
        np.save(self.paths.image_embeddings, self.image_embeddings)
        np.save(self.paths.sku_prototypes, self.sku_prototypes)
        np.save(self.paths.image_color_hists, self.image_color_hists)
        with self.paths.mapping.open("w", encoding="utf-8") as f:
            json.dump(self._mapping_payload(), f, ensure_ascii=False, indent=2)

    def _rebuild_faiss_indexes(self) -> None:
        self._sku_faiss = None
        self._image_faiss = None

        if faiss is None or self.image_embeddings.size == 0 or self.sku_prototypes.size == 0:
            if self.paths.sku_index.exists():
                self.paths.sku_index.unlink()
            if self.paths.image_index.exists():
                self.paths.image_index.unlink()
            self.index_engine = "numpy"
            return

        sku_index = faiss.IndexFlatIP(self.sku_prototypes.shape[1])
        sku_index.add(self.sku_prototypes.astype(np.float32))
        faiss.write_index(sku_index, str(self.paths.sku_index))

        image_index = faiss.IndexFlatIP(self.image_embeddings.shape[1])
        image_index.add(self.image_embeddings.astype(np.float32))
        faiss.write_index(image_index, str(self.paths.image_index))

        self._sku_faiss = sku_index
        self._image_faiss = image_index
        self.index_engine = "faiss"

    def build(self, data_dir: Optional[Path] = None, include_storage: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            start_time = time.perf_counter()
            source_root = data_dir.resolve() if data_dir else self.dataset_root
            include_storage = self.include_storage_on_build if include_storage is None else include_storage

            entries = self._collect_entries(source_root, include_storage=include_storage)
            if not entries:
                raise RuntimeError(f"No se encontraron imágenes en {source_root}")

            records, embeddings, color_hists, skipped = self._embed_entries(entries)
            if len(records) == 0:
                raise RuntimeError("Todas las imágenes fallaron al indexar")

            embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            embeddings = np.clip(embeddings, -1.0, 1.0).astype(np.float32)
            color_hists = np.nan_to_num(color_hists, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

            mapping_images: List[Dict[str, Any]] = []
            for idx, record in enumerate(records):
                mapping_images.append(
                    {
                        "id": idx,
                        "sku": record["sku"],
                        "filepath": record["filepath"],
                    }
                )

            sku_to_ids, sku_order, prototypes = self._build_sku_structures(records, embeddings)

            self.mapping_images = mapping_images
            self.image_embeddings = embeddings
            self.image_color_hists = color_hists
            self.sku_to_image_ids = sku_to_ids
            self.sku_order = sku_order
            self.sku_prototypes = prototypes

            self._write_arrays_and_mapping()
            self._rebuild_faiss_indexes()
            self._loaded = True

            elapsed = time.perf_counter() - start_time
            stats = {
                "sku_count": len(self.sku_order),
                "image_count": len(self.mapping_images),
                "skipped_images": skipped,
                "seconds": round(elapsed, 2),
                "device": self.embedder.device,
                "index_engine": self.index_engine,
                "out_dir": str(self.paths.root),
            }
            self.logger.info("Build completado: %s", stats)
            return stats

    def load(self) -> None:
        with self._lock:
            if self._loaded:
                return

            required = [self.paths.image_embeddings, self.paths.sku_prototypes, self.paths.mapping]
            missing = [str(path) for path in required if not path.exists()]
            if missing:
                raise RuntimeError(
                    "Índices no encontrados. Ejecuta primero: "
                    "python -m backend.index.build --data_dir \"<ruta_fotos>\" --out_dir backend/data"
                )

            with self.paths.mapping.open("r", encoding="utf-8") as f:
                mapping = json.load(f)

            self.image_embeddings = np.load(self.paths.image_embeddings)
            self.sku_prototypes = np.load(self.paths.sku_prototypes)
            self.image_embeddings = np.nan_to_num(self.image_embeddings, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            self.image_embeddings = np.clip(self.image_embeddings, -1.0, 1.0).astype(np.float32)
            self.sku_prototypes = np.nan_to_num(self.sku_prototypes, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            self.sku_prototypes = np.clip(self.sku_prototypes, -1.0, 1.0).astype(np.float32)

            if self.paths.image_color_hists.exists():
                self.image_color_hists = np.load(self.paths.image_color_hists)
            else:
                self.image_color_hists = np.zeros((len(self.image_embeddings), 512), dtype=np.float32)

            self.mapping_images = list(mapping.get("images", []))
            self.sku_order = list(mapping.get("sku_order", []))
            self.sku_to_image_ids = {
                sku: [int(i) for i in ids]
                for sku, ids in dict(mapping.get("sku_to_image_ids", {})).items()
            }

            if not self.sku_order:
                self.sku_order = sorted(self.sku_to_image_ids.keys())

            if faiss is not None and self.paths.sku_index.exists() and self.paths.image_index.exists():
                self._sku_faiss = faiss.read_index(str(self.paths.sku_index))
                self._image_faiss = faiss.read_index(str(self.paths.image_index))
                self.index_engine = "faiss"
            else:
                self._sku_faiss = None
                self._image_faiss = None
                self.index_engine = "numpy"

            self._loaded = True

    def status(self) -> Dict[str, Any]:
        ready = (
            self.paths.image_embeddings.exists()
            and self.paths.sku_prototypes.exists()
            and self.paths.mapping.exists()
        )

        image_count = 0
        sku_count = 0
        if ready:
            try:
                with self.paths.mapping.open("r", encoding="utf-8") as f:
                    mapping = json.load(f)
                image_count = int(mapping.get("image_count", len(mapping.get("images", []))))
                sku_count = int(mapping.get("sku_count", len(mapping.get("sku_order", []))))
            except Exception:
                ready = False

        return {
            "index_ready": ready,
            "indexed_images": image_count,
            "indexed_skus": sku_count,
            "index_engine": "faiss" if self.paths.sku_index.exists() else "numpy",
        }

    def _top_prototype_indices(self, query_vector: np.ndarray, top_n: int) -> List[int]:
        query_vector = np.nan_to_num(query_vector, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        query_vector = np.clip(query_vector, -1.0, 1.0).astype(np.float32)
        top_n = min(top_n, len(self.sku_order))
        if top_n <= 0:
            return []

        if self._sku_faiss is not None:
            distances, indices = self._sku_faiss.search(query_vector[np.newaxis, :], top_n)
            return [int(idx) for idx in indices[0].tolist() if idx >= 0]

        scores = np.einsum("ij,j->i", self.sku_prototypes, query_vector, optimize=True)
        local_indices = np.argpartition(-scores, top_n - 1)[:top_n]
        ordered = local_indices[np.argsort(-scores[local_indices])]
        return [int(i) for i in ordered.tolist()]

    @staticmethod
    def _make_query_views(image: Image.Image, enable_multicrop: bool) -> List[Image.Image]:
        base = image.convert("RGB")
        if not enable_multicrop:
            return [base]

        views = [base]
        width, height = base.size

        # Recorte central suave
        margin_w = int(width * 0.1)
        margin_h = int(height * 0.1)
        if width - (2 * margin_w) > 32 and height - (2 * margin_h) > 32:
            center_crop = base.crop((margin_w, margin_h, width - margin_w, height - margin_h))
            views.append(center_crop)

        # Recorte central más cerrado para captar branding/color
        zoom_margin_w = int(width * 0.2)
        zoom_margin_h = int(height * 0.2)
        if width - (2 * zoom_margin_w) > 32 and height - (2 * zoom_margin_h) > 32:
            zoom_crop = base.crop((zoom_margin_w, zoom_margin_h, width - zoom_margin_w, height - zoom_margin_h))
            views.append(zoom_crop)

        return views

    def _path_to_public_url(self, filepath: str) -> str:
        full = Path(filepath).resolve()

        try:
            rel = full.relative_to(self.dataset_root).as_posix()
            return "/reference-images/" + rel
        except ValueError:
            pass

        try:
            rel = full.relative_to(self.storage_root).as_posix()
            return "/storage-images/" + rel
        except ValueError:
            pass

        return "/reference-images/" + full.name

    @staticmethod
    def _is_within_root(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _color_score_for_sku(self, query_hist: np.ndarray, image_ids: Sequence[int]) -> float:
        if self.image_color_hists.size == 0 or len(image_ids) == 0:
            return 0.0

        sku_hists = self.image_color_hists[list(image_ids)]
        scores = sku_hists @ query_hist
        return float(np.max(scores)) if len(scores) else 0.0

    def search(
        self,
        query_image: Image.Image,
        k: int,
        retrieval_top_n: int,
        max_examples: int,
        enable_multicrop: bool,
        enable_color_tiebreak: bool,
        color_tie_threshold: float,
    ) -> Dict[str, Any]:
        with self._lock:
            self.load()

            if k <= 0:
                return {"query_id": str(uuid4()), "results": []}

            query_views = self._make_query_views(query_image, enable_multicrop=enable_multicrop)
            query_vectors = self.embedder.embed_images(query_views)
            query_vectors = np.nan_to_num(query_vectors, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            query_vectors = np.clip(query_vectors, -1.0, 1.0).astype(np.float32)
            query_hist = self._compute_color_hist(query_views[0])

            candidate_skus: Dict[str, float] = {}
            for query_vector in query_vectors:
                prototype_indices = self._top_prototype_indices(query_vector, retrieval_top_n)
                for idx in prototype_indices:
                    sku = self.sku_order[idx]
                    score = float(self.sku_prototypes[idx] @ query_vector)
                    prev = candidate_skus.get(sku)
                    if prev is None or score > prev:
                        candidate_skus[sku] = score

            reranked: List[Dict[str, Any]] = []
            for sku in candidate_skus.keys():
                image_ids = self.sku_to_image_ids.get(sku, [])
                if not image_ids:
                    continue

                sku_matrix = self.image_embeddings[image_ids]
                sims = np.einsum("qd,id->qi", query_vectors, sku_matrix, optimize=True)
                per_image_scores = np.max(sims, axis=0)
                sku_score = float(np.max(per_image_scores))  # score por SKU = max(sim)

                top_local = np.argsort(-per_image_scores)[:max_examples]
                example_urls = [
                    self._path_to_public_url(self.mapping_images[image_ids[idx]]["filepath"])
                    for idx in top_local.tolist()
                ]

                color_score = self._color_score_for_sku(query_hist, image_ids)
                reranked.append(
                    {
                        "sku": sku,
                        "score": sku_score,
                        "examples": example_urls,
                        "color_score": color_score,
                    }
                )

            reranked.sort(key=lambda item: item["score"], reverse=True)

            if enable_color_tiebreak and len(reranked) > 1:
                i = 0
                while i < len(reranked):
                    j = i + 1
                    while j < len(reranked):
                        if abs(reranked[i]["score"] - reranked[j]["score"]) <= color_tie_threshold:
                            j += 1
                        else:
                            break
                    if j - i > 1:
                        segment = sorted(
                            reranked[i:j],
                            key=lambda item: item["color_score"],
                            reverse=True,
                        )
                        reranked[i:j] = segment
                    i = j

            top_results = [
                {
                    "sku": row["sku"],
                    "score": round(float(row["score"]), 6),
                    "examples": row["examples"],
                }
                for row in reranked[:k]
            ]

            return {
                "query_id": str(uuid4()),
                "results": top_results,
                "index_engine": self.index_engine,
                "retrieval_top_n": retrieval_top_n,
            }

    def get_examples(self, sku: str, limit: int) -> List[str]:
        with self._lock:
            self.load()
            image_ids = self.sku_to_image_ids.get(sku, [])[: max(limit, 0)]
            urls: List[str] = []
            for image_id in image_ids:
                if image_id < len(self.mapping_images):
                    filepath = self.mapping_images[image_id]["filepath"]
                    urls.append(self._path_to_public_url(filepath))
            return urls

    def list_sku_images(self, sku: str, storage_only: bool = True) -> List[Dict[str, Any]]:
        with self._lock:
            self.load()
            clean_sku = sku.strip()
            if not clean_sku:
                return []

            images: List[Dict[str, Any]] = []
            for row in self.mapping_images:
                if row.get("sku") != clean_sku:
                    continue

                raw_path = str(row.get("filepath", "")).strip()
                if not raw_path:
                    continue

                full_path = Path(raw_path).resolve()
                if storage_only and not self._is_within_root(full_path, self.storage_root):
                    continue

                images.append(
                    {
                        "id": int(row.get("id", 0)),
                        "sku": clean_sku,
                        "filepath": str(full_path),
                        "filename": full_path.name,
                        "url": self._path_to_public_url(str(full_path)),
                    }
                )

            return images

    def sku_exists(self, sku: str) -> bool:
        with self._lock:
            self.load()
            key = sku.strip()
            if not key:
                return False
            return key in self.sku_to_image_ids or key in self.sku_order

    def _recompute_prototype_for_sku(self, sku: str) -> None:
        image_ids = self.sku_to_image_ids.get(sku, [])
        if not image_ids:
            return

        vectors = self.image_embeddings[image_ids]
        if self.prototype_method == "median":
            proto = np.median(vectors, axis=0)
        else:
            proto = np.mean(vectors, axis=0)
        proto = self._normalize_vector(proto)

        if sku in self.sku_order:
            idx = self.sku_order.index(sku)
            self.sku_prototypes[idx] = proto
        else:
            self.sku_order.append(sku)
            if self.sku_prototypes.size == 0:
                self.sku_prototypes = proto[np.newaxis, :]
            else:
                self.sku_prototypes = np.vstack([self.sku_prototypes, proto])

    def append_items(self, sku: str, files: Sequence[Tuple[str, bytes]]) -> Dict[str, Any]:
        with self._lock:
            self.load()

            clean_sku = sku.strip()
            if not clean_sku:
                raise RuntimeError("sku es obligatorio")
            if not files:
                raise RuntimeError("Debes subir al menos una imagen")

            target_dir = (self.storage_root / clean_sku).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)

            valid_images: List[Image.Image] = []
            valid_paths: List[Path] = []

            for filename, content in files:
                suffix = Path(filename or "").suffix.lower()
                if suffix not in IMAGE_EXTENSIONS:
                    suffix = ".jpg"

                file_name = f"{int(time.time())}_{uuid4().hex[:8]}{suffix}"
                destination = target_dir / file_name
                destination.write_bytes(content)

                try:
                    with Image.open(destination) as img:
                        rgb = img.convert("RGB")
                    valid_images.append(rgb)
                    valid_paths.append(destination)
                except Exception as exc:  # pragma: no cover - depends on payload
                    self.logger.warning("No se pudo procesar imagen subida %s (%s)", destination, exc)
                    if destination.exists():
                        destination.unlink()

            if not valid_images:
                raise RuntimeError("No se pudo procesar ninguna imagen válida")

            new_embeddings = self.embedder.embed_images(valid_images)
            new_color_hists = np.vstack([self._compute_color_hist(img) for img in valid_images]).astype(np.float32)

            start_id = len(self.mapping_images)
            new_ids: List[int] = []
            for offset, path in enumerate(valid_paths):
                image_id = start_id + offset
                new_ids.append(image_id)
                self.mapping_images.append(
                    {
                        "id": image_id,
                        "sku": clean_sku,
                        "filepath": str(path.resolve()),
                    }
                )

            if self.image_embeddings.size == 0:
                self.image_embeddings = new_embeddings.astype(np.float32)
            else:
                self.image_embeddings = np.vstack([self.image_embeddings, new_embeddings]).astype(np.float32)

            if self.image_color_hists.size == 0:
                self.image_color_hists = new_color_hists
            else:
                self.image_color_hists = np.vstack([self.image_color_hists, new_color_hists]).astype(np.float32)

            self.sku_to_image_ids.setdefault(clean_sku, [])
            self.sku_to_image_ids[clean_sku].extend(new_ids)
            self._recompute_prototype_for_sku(clean_sku)

            self._write_arrays_and_mapping()
            self._rebuild_faiss_indexes()
            self._loaded = True

            return {
                "sku": clean_sku,
                "added_images": len(new_ids),
                "total_images": len(self.mapping_images),
                "total_skus": len(self.sku_order),
                "index_engine": self.index_engine,
            }

    def remove_sku_images(self, sku: str, filepaths: Sequence[str]) -> Dict[str, Any]:
        with self._lock:
            self.load()

            clean_sku = sku.strip()
            if not clean_sku:
                raise RuntimeError("sku es obligatorio")
            if not filepaths:
                raise RuntimeError("Debes seleccionar al menos una imagen")

            target_paths: set[str] = set()
            for raw_path in filepaths:
                clean_path = str(raw_path or "").strip()
                if not clean_path:
                    continue
                full_path = Path(clean_path).resolve()
                if not self._is_within_root(full_path, self.storage_root):
                    continue
                target_paths.add(str(full_path))

            if not target_paths:
                raise RuntimeError("No se seleccionaron imágenes válidas del storage")

            remove_indices: List[int] = []
            remove_paths: List[Path] = []
            for idx, row in enumerate(self.mapping_images):
                if row.get("sku") != clean_sku:
                    continue
                full_path = Path(str(row.get("filepath", ""))).resolve()
                if str(full_path) in target_paths:
                    remove_indices.append(idx)
                    remove_paths.append(full_path)

            if not remove_indices:
                raise RuntimeError("No se encontraron imágenes del SKU para eliminar")

            current_dim = int(self.image_embeddings.shape[1]) if self.image_embeddings.ndim == 2 and self.image_embeddings.size else 0
            current_hist_dim = (
                int(self.image_color_hists.shape[1]) if self.image_color_hists.ndim == 2 and self.image_color_hists.size else 512
            )

            keep_mask = np.ones(len(self.mapping_images), dtype=bool)
            keep_mask[np.array(remove_indices, dtype=np.int64)] = False

            kept_records = [self.mapping_images[i] for i in range(len(self.mapping_images)) if keep_mask[i]]

            if self.image_embeddings.size and len(keep_mask) == self.image_embeddings.shape[0]:
                kept_embeddings = self.image_embeddings[keep_mask].astype(np.float32)
            else:
                kept_embeddings = np.empty((0, current_dim), dtype=np.float32)

            if self.image_color_hists.size and len(keep_mask) == self.image_color_hists.shape[0]:
                kept_hists = self.image_color_hists[keep_mask].astype(np.float32)
            else:
                kept_hists = np.empty((0, current_hist_dim), dtype=np.float32)

            if not kept_records:
                self.mapping_images = []
                self.image_embeddings = np.empty((0, current_dim), dtype=np.float32)
                self.image_color_hists = np.empty((0, current_hist_dim), dtype=np.float32)
                self.sku_to_image_ids = {}
                self.sku_order = []
                self.sku_prototypes = np.empty((0, current_dim), dtype=np.float32)
            else:
                normalized_records: List[Dict[str, str]] = []
                mapping_images: List[Dict[str, Any]] = []
                for new_id, row in enumerate(kept_records):
                    row_sku = str(row.get("sku", "")).strip()
                    row_filepath = str(Path(str(row.get("filepath", ""))).resolve())
                    mapping_images.append({"id": new_id, "sku": row_sku, "filepath": row_filepath})
                    normalized_records.append({"sku": row_sku, "filepath": row_filepath})

                sku_to_ids, sku_order, prototypes = self._build_sku_structures(normalized_records, kept_embeddings)

                self.mapping_images = mapping_images
                self.image_embeddings = kept_embeddings
                self.image_color_hists = kept_hists
                self.sku_to_image_ids = sku_to_ids
                self.sku_order = sku_order
                self.sku_prototypes = prototypes.astype(np.float32) if prototypes.size else np.empty((0, current_dim), dtype=np.float32)

            self._write_arrays_and_mapping()
            self._rebuild_faiss_indexes()
            self._loaded = True

            removed_files = 0
            for full_path in remove_paths:
                try:
                    if full_path.exists():
                        full_path.unlink()
                        removed_files += 1
                except Exception as exc:  # pragma: no cover - filesystem dependent
                    self.logger.warning("No se pudo eliminar el archivo %s (%s)", full_path, exc)

            sku_storage_dir = (self.storage_root / clean_sku).resolve()
            try:
                if sku_storage_dir.exists() and sku_storage_dir.is_dir() and not any(sku_storage_dir.iterdir()):
                    sku_storage_dir.rmdir()
            except Exception:  # pragma: no cover - filesystem dependent
                pass

            return {
                "sku": clean_sku,
                "removed_images": len(remove_indices),
                "removed_files": removed_files,
                "remaining_sku_images": len(self.sku_to_image_ids.get(clean_sku, [])),
                "total_images": len(self.mapping_images),
                "total_skus": len(self.sku_order),
                "index_engine": self.index_engine,
            }
