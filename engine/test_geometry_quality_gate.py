import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from geometry_quality_gate import GeometryQualityPolicy, audit_geometry_quality


class GeometryQualityGateTests(unittest.TestCase):
    def test_accepts_finite_closed_mesh_and_marks_unmeasurable_lanes(self):
        report = audit_geometry_quality(trimesh.creation.box(extents=(1.0, 2.0, 3.0)))
        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["component_count"], 1)
        self.assertEqual(report["evidence_scope"]["self_intersection"], "not_measured")
        self.assertEqual(report["evidence_scope"]["semantic_geometry_correctness"], "not_measured")

    def test_rejects_degenerate_and_invalid_scale(self):
        mesh = trimesh.Trimesh(
            vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            faces=np.array([[0, 1, 2], [0, 0, 1]]),
            process=False,
        )
        report = audit_geometry_quality(mesh)
        self.assertFalse(report["passed"])
        self.assertIn("degenerate_faces", report["failures"])
        tiny = trimesh.creation.box(extents=(1e-8, 1e-8, 1e-8))
        self.assertIn("scale_below_minimum_extent", audit_geometry_quality(tiny)["failures"])

    def test_policy_can_require_watertight_and_component_cap(self):
        open_mesh = trimesh.creation.icosphere(subdivisions=1)
        open_mesh.update_faces(np.arange(len(open_mesh.faces) - 1))
        report = audit_geometry_quality(open_mesh, policy=GeometryQualityPolicy(require_watertight=True))
        self.assertIn("watertightness_required", report["failures"])
        combined = trimesh.util.concatenate([trimesh.creation.box(), trimesh.creation.box(transform=trimesh.transformations.translation_matrix([3, 0, 0]))])
        report = audit_geometry_quality(combined, policy={"max_components": 1})
        self.assertIn("component_count_out_of_policy", report["failures"])

    def test_accepts_safe_glb_and_rejects_non_glb_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "box.glb"
            path.write_bytes(trimesh.creation.box().export(file_type="glb"))
            report = audit_geometry_quality(path)
            self.assertTrue(report["passed"])
            self.assertIn("sha256", report["artifact"])
            wrong = Path(directory) / "not-glb.obj"
            wrong.write_text("v 0 0 0\n")
            rejected = audit_geometry_quality(wrong)
        self.assertFalse(rejected["passed"])
        self.assertEqual(rejected["failures"], ["geometry_path_must_be_glb"])

    def test_rejects_non_finite_vertices(self):
        mesh = trimesh.Trimesh(
            vertices=np.array([[np.nan, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            faces=np.array([[0, 1, 2]]),
            process=False,
        )
        report = audit_geometry_quality(mesh)
        self.assertIn("non_finite_vertices", report["failures"])


if __name__ == "__main__":
    unittest.main()
