import tempfile
import unittest
from pathlib import Path

from multiview_shape_backend import inspect_hunyuan2mv_install, inspect_multiview_shape_backend


class MultiViewShapeBackendTests(unittest.TestCase):
    def test_missing_pipeline_is_not_installed(self):
        result = inspect_multiview_shape_backend(Path("/definitely/missing"))
        self.assertFalse(result["available"])
        self.assertEqual(result["reason_code"], "mlx_shape_pipeline_missing")

    def test_single_view_pipeline_cannot_claim_multiview(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = Path(temp_dir) / "hy3dshape" / "hy3dshape" / "pipeline_mlx.py"
            pipeline.parent.mkdir(parents=True)
            pipeline.write_text("def preprocess_image(image): pass\\n", encoding="utf-8")
            result = inspect_multiview_shape_backend(Path(temp_dir))
        self.assertFalse(result["available"])
        self.assertEqual(result["reason_code"], "multiview_weights_missing")

    def test_explicit_camera_pipeline_is_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = Path(temp_dir) / "hy3dshape" / "hy3dshape" / "pipeline_mlx.py"
            pipeline.parent.mkdir(parents=True)
            pipeline.write_text(
                "def preprocess_multiview(image_dict): pass\\nVIEW_IDS = ('front', 'right', 'back', 'left')\\n",
                encoding="utf-8",
            )
            result = inspect_multiview_shape_backend(Path(temp_dir))
        self.assertTrue(result["available"])
        self.assertEqual(result["state"], "ready")

    def test_completed_weights_need_physical_certification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model_dir = root / "models" / "Hunyuan3D-2mv" / "hunyuan3d-dit-v2-mv"
            model_dir.mkdir(parents=True)
            (model_dir / "config.yaml").write_text("model: mv", encoding="utf-8")
            checkpoint = model_dir / "model.fp16.safetensors"
            checkpoint.touch()
            checkpoint.write_bytes(b"0" * (1024 ** 2))
            self.assertFalse(inspect_hunyuan2mv_install(root / "models" / "Hunyuan3D-2mv")["installed"])
