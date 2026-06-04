import tempfile
import unittest
from pathlib import Path

from backend.index.store import SkuSearchIndex


class SkuSearchIndexPortabilityTests(unittest.TestCase):
    def test_mapping_rows_use_relative_dataset_paths(self):
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source_dataset = Path(source_dir) / "Fotos"
            target_dataset = Path(target_dir) / "Fotos"
            source_storage = Path(source_dir) / "storage"
            target_storage = Path(target_dir) / "storage"

            image_path = source_dataset / "051093" / "img1.jpg"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(b"fake")

            target_image_path = target_dataset / "051093" / "img1.jpg"
            target_image_path.parent.mkdir(parents=True, exist_ok=True)
            target_image_path.write_bytes(b"fake")

            index = SkuSearchIndex(
                dataset_root=source_dataset,
                data_dir=Path(source_dir) / "data",
                storage_root=source_storage,
                model_id="unused",
                batch_size=1,
            )
            row = index._make_mapping_row(0, "051093", image_path)

            self.assertEqual(row["root"], "dataset")
            self.assertEqual(row["relative_path"], "051093/img1.jpg")

            relocated_index = SkuSearchIndex(
                dataset_root=target_dataset,
                data_dir=Path(target_dir) / "data",
                storage_root=target_storage,
                model_id="unused",
                batch_size=1,
            )

            resolved_path = relocated_index._resolve_mapping_filepath(row)
            public_url = relocated_index._mapping_row_to_public_url(row)

            self.assertEqual(resolved_path, target_image_path.resolve())
            self.assertEqual(public_url, "/reference-images/051093/img1.jpg")


if __name__ == "__main__":
    unittest.main()
