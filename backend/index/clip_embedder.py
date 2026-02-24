from __future__ import annotations

from typing import List

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.nan_to_num(vectors, nan=0.0, posinf=0.0, neginf=0.0)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-12, None)
    return (vectors / norms).astype(np.float32)


class ClipEmbedder:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.device = self._resolve_device()
        self.processor = CLIPProcessor.from_pretrained(model_id)
        self.model = CLIPModel.from_pretrained(model_id).to(self.device)
        self.model.eval()

    @staticmethod
    def _resolve_device() -> str:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @torch.inference_mode()
    def embed_images(self, images: List[Image.Image]) -> np.ndarray:
        if not images:
            return np.empty((0, 0), dtype=np.float32)

        inputs = self.processor(images=images, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(self.device)
        vectors = self.model.get_image_features(pixel_values=pixel_values)
        vectors = vectors.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

    def embed_image(self, image: Image.Image) -> np.ndarray:
        vectors = self.embed_images([image.convert("RGB")])
        if len(vectors) == 0:
            raise RuntimeError("No se pudo generar embedding de la imagen")
        return vectors[0]
