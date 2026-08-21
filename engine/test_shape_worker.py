import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import trimesh
from PIL import Image, ImageDraw

import server
import shape_worker


class ShapeWorkerTests(unittest.TestCase):
    def test_worker_run_exports_mesh_and_releases_optimizer(self):
        mesh = trimesh.creation.box()
        optimizer = mock.Mock()
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "shape.glb"
            with mock.patch.object(
                shape_worker, "_load_pipeline", return_value=(lambda *args, **kwargs: mesh, optimizer, "local-weights")
            ):
                report = shape_worker.run(
                    Path(directory) / "input.png", result, steps=20, guidance=6.0, octree_resolution=192
                )
            self.assertTrue(result.is_file())
        self.assertTrue(report["passed"])
        self.assertEqual(report["model"], "local-weights")
        optimizer.clear_cache.assert_called_once_with()

    def test_isolated_shape_path_requires_valid_worker_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prepared = root / "prepared.png"
            prepared.write_bytes(b"input")
            raw = server.JOBS_DIR / "shape-worker-test-shape-worker.glb"
            report = server.JOBS_DIR / "shape-worker-test-shape-worker-report.json"
            try:
                trimesh.creation.box().export(raw)
                report.write_text(json.dumps({
                    "passed": True,
                    "provider": "hunyuan3d-2.1-mlx",
                    "output_glb": str(raw.resolve()),
                }))
                with mock.patch.object(server, "StageSupervisor") as supervisor:
                    supervisor.return_value.run.return_value = {"elapsed_seconds": 1.0}
                    mesh, isolation = server.run_isolated_shape_worker(
                        "shape-worker-test",
                        prepared,
                        server.GenerateRequest(image_base64="a" * 32),
                    )
                self.assertGreater(len(mesh.faces), 0)
                self.assertEqual(isolation["worker"]["provider"], "hunyuan3d-2.1-mlx")
            finally:
                raw.unlink(missing_ok=True)
                report.unlink(missing_ok=True)

    def test_worker_feature_flag_is_opt_in(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(server.isolated_shape_worker_enabled())
        with mock.patch.dict("os.environ", {"XREALITY_SHAPE_WORKER": "1"}, clear=True):
            self.assertTrue(server.isolated_shape_worker_enabled())

    @unittest.skipUnless(
        os.environ.get("XREALITY_RUN_SHAPE_WORKER_E2E") == "1",
        "requires local Shape weights and a real Apple Metal device; set XREALITY_RUN_SHAPE_WORKER_E2E=1",
    )
    def test_real_metal_worker_emits_valid_glb(self):
        """Expensive proof of subprocess isolation; never enabled in default CI."""
        job_id = f"shape-e2e-{uuid.uuid4().hex}"
        raw = server.JOBS_DIR / f"{job_id}-shape-worker.glb"
        report = server.JOBS_DIR / f"{job_id}-shape-worker-report.json"
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.png"
            image = Image.new("RGB", (256, 256), "white")
            ImageDraw.Draw(image).ellipse((64, 36, 192, 220), fill=(40, 115, 190))
            image.save(reference)
            try:
                mesh, isolation = server.run_isolated_shape_worker(
                    job_id,
                    reference,
                    server.GenerateRequest(
                        image_base64="a" * 32,
                        steps=10,
                        octree_resolution=96,
                        texture=False,
                    ),
                )
                self.assertGreater(len(mesh.faces), 0)
                self.assertTrue(isolation["worker"]["passed"])
                self.assertTrue(raw.is_file())
            finally:
                raw.unlink(missing_ok=True)
                report.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
