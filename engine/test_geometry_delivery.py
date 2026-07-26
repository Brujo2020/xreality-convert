import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_delivery import apply_delivery_transform, export_lods, lowpoly_fidelity_reasons, lowpoly_refinement_reasons, normalize_delivery_options, point_cloud_fidelity, refinement_policy, refine_lowpoly_mesh, simplification_policy, simplify_mesh


class FakeMesh:
    def __init__(self, faces=8000):
        self.faces = [None] * faces
        self.extents = [2.0, 4.0, 1.0]
        self.bounds = [[0.0, 0.0, 0.0], [2.0, 4.0, 1.0]]
        self.scales = []
        self.transforms = []
        self.translations = []
        self.exports = []
        self.decimation_calls = []

    def apply_scale(self, value):
        self.scales.append(value)

    def apply_transform(self, matrix):
        self.transforms.append(matrix)

    def apply_translation(self, value):
        self.translations.append(value)

    def simplify_quadric_decimation(self, face_count, **kwargs):
        self.decimation_calls.append({"face_count": face_count, **kwargs})
        simplified = FakeMesh(face_count)
        simplified.decimation_calls = self.decimation_calls
        return simplified

    def copy(self):
        return FakeMesh(len(self.faces))

    def export(self, path):
        self.exports.append(path)
        Path(path).write_text("glb")


class FakeRefinementMesh(FakeMesh):
    def __init__(self, faces, area, components=None):
        super().__init__(faces)
        self.area = area
        self._components = components
        self.merged = False
        self.cleaned = False

    def merge_vertices(self, **_kwargs):
        self.merged = True

    def remove_unreferenced_vertices(self):
        self.cleaned = True

    def split(self, **_kwargs):
        return self._components if self._components is not None else [self]


class GeometryDeliveryTest(unittest.TestCase):
    def test_normalize_delivery_options_fails_closed(self):
        self.assertEqual(
            normalize_delivery_options("bad", "bad", "bad"),
            {"pivot": "center", "up_axis": "y", "units": "m", "pivot_custom": None},
        )

    def test_normalize_delivery_options_accepts_custom_pivot(self):
        self.assertEqual(
            normalize_delivery_options("custom", "y", "mm", ["1", 2, 3.5]),
            {"pivot": "custom", "up_axis": "y", "units": "mm", "pivot_custom": [1.0, 2.0, 3.5]},
        )

    def test_apply_delivery_transform_scales_units_and_places_base(self):
        mesh = FakeMesh()
        apply_delivery_transform(mesh, scale_meters=2.0, pivot="base", up_axis="z", units="cm")
        self.assertEqual(mesh.scales, [0.5, 100.0])
        self.assertEqual(len(mesh.transforms), 1)
        self.assertEqual(mesh.translations[-1], [-1.0, -2.0, -0.0])

    def test_apply_delivery_transform_places_custom_pivot(self):
        mesh = FakeMesh()
        apply_delivery_transform(mesh, scale_meters=1.0, pivot="custom", pivot_custom=[0.25, 0.5, 0.75], up_axis="y", units="m")
        self.assertEqual(mesh.translations[-1], [-0.25, -0.5, -0.75])

    def test_export_lods_writes_three_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            primary = Path(tmp) / "job.glb"
            primary.write_text("glb")
            outputs = export_lods(FakeMesh(4000), Path(tmp), "job", 4000, primary)
            self.assertEqual(set(outputs), {"LOD0", "LOD1", "LOD2"})
            self.assertEqual(outputs["LOD0"]["faces"], 4000)
            self.assertEqual(outputs["LOD0"]["path"], str(primary))
            self.assertEqual(outputs["LOD1"]["faces"], 2000)
            self.assertTrue(Path(outputs["LOD2"]["path"]).exists())

    def test_simplification_policy_preserves_architecture_faces(self):
        policy = simplification_policy("architecture", 2000, 10000)
        self.assertEqual(policy["target_faces"], 6500)
        self.assertTrue(policy["preserve_hard_edges"])

    def test_simplify_mesh_passes_hard_edge_flags_when_supported(self):
        mesh = simplify_mesh(FakeMesh(10000), 2000, "industrial")
        self.assertEqual(len(mesh.faces), 5500)
        self.assertEqual(
            mesh.decimation_calls[-1],
            {"face_count": 5500, "aggression": 3, "preserve_boundary": True},
        )

    def test_lowpoly_profile_uses_aggressive_small_budget(self):
        mesh = simplify_mesh(FakeMesh(100000), 12000, "industrial", "lowpoly")
        self.assertEqual(len(mesh.faces), 12000)
        self.assertEqual(
            mesh.decimation_calls[-1],
            {"face_count": 12000, "aggression": 4, "preserve_boundary": True},
        )

    def test_lowpoly_refinement_rounds_custom_assets_but_not_technical_edges(self):
        rounded = refinement_policy("custom", "lowpoly")
        technical = refinement_policy("industrial", "lowpoly")
        self.assertEqual(rounded["smoothing_iterations"], 3)
        self.assertFalse(rounded["preserve_hard_edges"])
        self.assertEqual(technical["smoothing_iterations"], 0)
        self.assertTrue(technical["preserve_hard_edges"])

    def test_lowpoly_refinement_removes_decimation_fragments_and_smooths_survivor(self):
        main = FakeRefinementMesh(900, 100.0)
        fragment = FakeRefinementMesh(12, 0.1)
        source = FakeRefinementMesh(912, 100.1, [main, fragment])
        smoothing_calls = []
        refined, report = refine_lowpoly_mesh(
            source,
            "custom",
            smoother=lambda mesh, **kwargs: smoothing_calls.append((mesh, kwargs)),
        )
        self.assertIs(refined, main)
        self.assertEqual(report["removed_components"], 1)
        self.assertEqual(report["output_components"], 1)
        self.assertEqual(report["smoothing_iterations"], 3)
        self.assertEqual(smoothing_calls[0][1]["iterations"], 3)

    def test_lowpoly_refinement_gate_rejects_fragments_degenerates_and_spikes(self):
        reasons = lowpoly_refinement_reasons({
            "output_components": 2,
            "degenerate_faces": 1,
            "edge_max_p95": 4.1,
        })
        self.assertEqual(reasons, ["fragmentos_desconectados", "triangulos_degenerados", "puntas_geometricas"])

    def test_point_cloud_fidelity_reports_surface_and_normal_error(self):
        report = point_cloud_fidelity(
            [[0, 0, 0], [1, 0, 0]],
            [[0, 0, 0.1], [1, 0, 0.1]],
            [[0, 0, 1], [0, 0, 1]],
            [[0, 0, -1], [0, 0, -1]],
            diagonal=1.0,
        )
        self.assertAlmostEqual(report["sampled_hausdorff_ratio"], 0.1)
        self.assertAlmostEqual(report["surface_distance_p95_ratio"], 0.1)
        self.assertAlmostEqual(report["normal_error_p95_degrees"], 180.0)

    def test_lowpoly_fidelity_gate_rejects_shape_and_normal_drift(self):
        reasons = lowpoly_fidelity_reasons({
            "sampled_hausdorff_ratio": 0.041,
            "surface_distance_p95_ratio": 0.021,
            "normal_error_p95_degrees": 51.0,
            "thresholds": {
                "sampled_hausdorff_ratio": 0.04,
                "surface_distance_p95_ratio": 0.02,
                "normal_error_p95_degrees": 50.0,
            },
        })
        self.assertEqual(reasons, ["silueta_deformada", "superficie_irregular", "normales_inconsistentes"])

    def test_export_lods_records_category_simplification_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = export_lods(FakeMesh(10000), Path(tmp), "job", 2000, category="architecture")
            self.assertEqual(outputs["LOD1"]["simplification"]["target_faces"], 6500)
            self.assertTrue(outputs["LOD2"]["simplification"]["preserve_hard_edges"])

    def test_export_lods_records_lowpoly_profile_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = export_lods(FakeMesh(100000), Path(tmp), "job", 12000, category="industrial", profile="lowpoly")
            self.assertEqual(outputs["LOD1"]["simplification"]["category"], "lowpoly")
            self.assertEqual(outputs["LOD1"]["simplification"]["aggression"], 4)
            self.assertEqual(outputs["LOD1"]["refinement"]["output_components"], 1)


if __name__ == "__main__":
    unittest.main()
