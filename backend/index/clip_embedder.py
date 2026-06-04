from __future__ import annotations

from typing import Any, List

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

    @staticmethod
    def _extract_image_vectors(output: Any) -> torch.Tensor:
        if isinstance(output, torch.Tensor):
            return output

        for attr in ("image_embeds", "pooler_output"):
            value = getattr(output, attr, None)
            if isinstance(value, torch.Tensor):
                return value

        if isinstance(output, dict):
            for key in ("image_embeds", "pooler_output"):
                value = output.get(key)
                if isinstance(value, torch.Tensor):
                    return value

        if isinstance(output, (tuple, list)):
            for item in output:
                if isinstance(item, torch.Tensor):
                    return item

        raise TypeError(f"Salida de embedding no compatible: {type(output)!r}")

    @torch.inference_mode()
    def embed_images(self, images: List[Image.Image]) -> np.ndarray:
        if not images:
            return np.empty((0, 0), dtype=np.float32)

        inputs = self.processor(images=images, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(self.device)
        raw_output = self.model.get_image_features(pixel_values=pixel_values)
        # Algunas versiones recientes/dev de transformers devuelven un ModelOutput
        # en lugar del tensor final directamente.
        vectors = self._extract_image_vectors(raw_output)
        vectors = vectors.detach().cpu().numpy().astype(np.float32)
        return l2_normalize(vectors)

    def embed_image(self, image: Image.Image) -> np.ndarray:
        vectors = self.embed_images([image.convert("RGB")])
        if len(vectors) == 0:
            raise RuntimeError("No se pudo generar embedding de la imagen")
        return vectors[0]
