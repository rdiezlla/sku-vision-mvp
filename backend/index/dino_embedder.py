from __future__ import annotations

from typing import List

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel


class DinoEmbedder:
    def __init__(self, model_id: str = "facebook/dinov2-small") -> None:
        self.model_id = model_id
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModel.from_pretrained(model_id).to(self.device)
        self.model.eval()

    @torch.no_grad()
    def embed_images(self, images: List[Image.Image]) -> np.ndarray:
        if not images:
            return np.empty((0, 0), dtype=np.float32)

        inputs = self.processor(images=images, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        outputs = self.model(**inputs)

        if hasattr(outputs, "last_hidden_state"):
            vectors = outputs.last_hidden_state[:, 0, :]
        elif hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            vectors = outputs.pooler_output
        else:
            raise RuntimeError("El modelo DINO no devolvió embeddings de imagen reconocibles")

        vectors = vectors.detach().cpu().numpy().astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms
