import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from multiview_shape_worker import MultiViewWorkerError, load_manifest


def sealed_view(view_id, path):
    content = path.read_bytes() if path.is_file() else view_id.encode()
    return {
        "view_id": view_id,
        "evidence_class": "measured",
        "sha256": hashlib.sha256(content).hexdigest(),
        "file_path": str(path),
    }


class MultiViewShapeWorkerTests(unittest.TestCase):
    def test_manifest_exposes_only_four_supported_shape_cameras(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            views = []
            for view_id in ("front", "right", "back", "left", "top", "bottom"):
                image = root / f"{view_id}.png"
                image.write_bytes(b"image")
                views.append(sealed_view(view_id, image))
            manifest = root / "views.json"
            manifest.write_text(json.dumps({"profile": "xreal", "views": views}))
            result = load_manifest(manifest)
        self.assertEqual(tuple(result), ("front", "right", "back", "left"))

    def test_manifest_rejects_missing_horizontal_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            views = []
            for view_id in ("front", "right", "back", "left", "top", "bottom"):
                image = root / f"{view_id}.png"
                if view_id != "right":
                    image.write_bytes(b"image")
                views.append(sealed_view(view_id, image))
            manifest = root / "views.json"
            manifest.write_text(json.dumps({"profile": "xreal", "views": views}))
            with self.assertRaisesRegex(MultiViewWorkerError, "multiview_image_missing:right"):
                load_manifest(manifest)

    def test_manifest_rejects_mutated_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            views = []
            for view_id in ("front", "right", "back", "left", "top", "bottom"):
                image = root / f"{view_id}.png"
                image.write_bytes(view_id.encode())
                views.append(sealed_view(view_id, image))
            (root / "right.png").write_bytes(b"changed")
            manifest = root / "views.json"
            manifest.write_text(json.dumps({"profile": "xreal", "views": views}))
            with self.assertRaisesRegex(MultiViewWorkerError, "multiview_image_hash_mismatch:right"):
                load_manifest(manifest)
