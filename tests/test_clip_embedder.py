import types
import unittest

import numpy as np
import torch
from PIL import Image

from backend.index.clip_embedder import ClipEmbedder


class DummyProcessor:
    def __call__(self, images, return_tensors="pt"):
        return {"pixel_values": torch.ones((len(images), 3, 4, 4), dtype=torch.float32)}


class TensorModel:
    def get_image_features(self, pixel_values):
        batch = pixel_values.shape[0]
        return torch.arange(batch * 3, dtype=torch.float32).reshape(batch, 3) + 1


class OutputModel:
    def get_image_features(self, pixel_values):
        batch = pixel_values.shape[0]
        values = torch.arange(batch * 3, dtype=torch.float32).reshape(batch, 3) + 1
        return types.SimpleNamespace(pooler_output=values)


class ClipEmbedderTests(unittest.TestCase):
    def _make_embedder(self, model):
        embedder = ClipEmbedder.__new__(ClipEmbedder)
        embedder.device = "cpu"
        embedder.processor = DummyProcessor()
        embedder.model = model
        return embedder

    def test_embed_images_accepts_tensor_output(self):
        embedder = self._make_embedder(TensorModel())

        vectors = embedder.embed_images([Image.new("RGB", (8, 8), "white")])

        self.assertEqual(vectors.shape, (1, 3))
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), np.array([1.0]), rtol=1e-5)

    def test_embed_images_accepts_model_output(self):
        embedder = self._make_embedder(OutputModel())

        vectors = embedder.embed_images(
            [Image.new("RGB", (8, 8), "white"), Image.new("RGB", (8, 8), "black")]
        )

        self.assertEqual(vectors.shape, (2, 3))
        np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), np.ones(2), rtol=1e-5)


if __name__ == "__main__":
    unittest.main()
