import unittest
from pathlib import Path
from unittest import mock
import json
import tempfile

import trimesh

from shape_parity import compare, mesh_metrics
import benchmark_shape_isolation


class ShapeParityTests(unittest.TestCase):
    def test_identical_meshes_recommend_promotion_within_latency_budget(self):
        mesh = trimesh.creation.box()
        report = compare(mesh, mesh.copy(), resident_seconds=10, worker_seconds=11)
        self.assertTrue(report["promotion_recommended"])
        self.assertTrue(report["checks"]["latency"])

    def test_excessive_geometry_delta_blocks_promotion(self):
        resident = trimesh.creation.box()
        worker = trimesh.creation.icosphere(subdivisions=3)
        report = compare(resident, worker, resident_seconds=10, worker_seconds=10)
        self.assertFalse(report["promotion_recommended"])
        self.assertFalse(report["checks"]["faces"])

    def test_metrics_do_not_claim_visual_equivalence(self):
        metrics = mesh_metrics(trimesh.creation.box())
        self.assertEqual(metrics["components"], 1)
        report = compare(trimesh.creation.box(), trimesh.creation.box(), resident_seconds=1, worker_seconds=1)
        self.assertIn("visual parity", report["scope"])

    def test_resident_compatibility_rejects_missing_contract_artifacts(self):
        request = mock.Mock(steps=10, guidance=6.0, octree_resolution=96)
        with mock.patch.object(benchmark_shape_isolation, "StageSupervisor") as supervisor:
            supervisor.return_value.run.return_value = {}
            with self.assertRaisesRegex(RuntimeError, "resident_compat_missing_artifact"):
                benchmark_shape_isolation.run_resident_compatibility("missing-contract", Path("/tmp/input.png"), request)

    def test_benchmark_persists_admission_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "input.png"
            image.write_bytes(b"image")
            report = Path(directory) / "report.json"
            with mock.patch.object(
                benchmark_shape_isolation, "run_resident_compatibility", side_effect=RuntimeError("resident_compat_failed:memory_admission")
            ):
                status = benchmark_shape_isolation.main(["--input", str(image), "--report", str(report)])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(report.read_text())["reason_code"], "resident_compat_failed")


if __name__ == "__main__":
    unittest.main()
