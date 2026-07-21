import tempfile
import unittest
from pathlib import Path

from paint_service import PaintService, paint_profile


class FakePipeline:
    def __call__(self, **kwargs):
        Path(kwargs["output_mesh_path"]).with_suffix(".glb").write_bytes(b"paint")


class PaintServiceTests(unittest.TestCase):
    def test_profiles_map_to_real_work(self):
        self.assertEqual(paint_profile("1K"), {
            "views": 4, "resolution": 256, "steps": 10, "texture_size": 1024, "super_res": False,
        })
        self.assertEqual(paint_profile("2K")["texture_size"], 2048)
        with self.assertRaisesRegex(ValueError, "texture size"):
            paint_profile("4K")

    def test_run_returns_only_after_pbr_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "final.glb"
            service = PaintService(
                pipeline_factory=lambda _profile: FakePipeline(),
                validator=lambda path: {"passed": Path(path).read_bytes() == b"paint", "reasons": []},
            )
            report = service.run("shape.glb", "reference.png", output, "1K")
            self.assertTrue(report["passed"])
            self.assertEqual(output.read_bytes(), b"paint")

    def test_failed_gate_is_not_reported_as_textured(self):
        with tempfile.TemporaryDirectory() as directory:
            service = PaintService(
                pipeline_factory=lambda _profile: FakePipeline(),
                validator=lambda _path: {"passed": False, "reasons": ["missing_base_color_texture"]},
            )
            with self.assertRaisesRegex(RuntimeError, "missing_base_color_texture"):
                service.run("shape.glb", "reference.png", Path(directory) / "final.glb")


if __name__ == "__main__":
    unittest.main()
