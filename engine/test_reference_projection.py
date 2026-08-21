import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from trimesh.visual.texture import TextureVisuals

from reference_projection import (
    _largest_face_component,
    _rasterize_silhouette,
    apply_reference_fidelity,
    evaluate_aligned_fidelity,
    evaluate_native_paint_fidelity,
    evaluate_quarter_texture_stability,
    measure_uv_seams,
    project_reference_to_texture,
)

def _reference(size=64):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, size - 9, size - 9), fill=(220, 48, 20, 255))
    return np.asarray(image, dtype=np.uint8)


class ReferenceProjectionTests(unittest.TestCase):
    def test_uv_seam_metric_detects_discontinuous_neighboring_faces(self):
        vertices = np.array(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
        uv = np.array(
            [[0.05, 0.05], [0.45, 0.05], [0.05, 0.95], [0.55, 0.05], [0.95, 0.95], [0.55, 0.95]],
            dtype=np.float64,
        )
        texture = np.zeros((32, 32, 4), dtype=np.uint8)
        texture[:, :16] = (220, 30, 20, 255)
        texture[:, 16:] = (20, 40, 220, 255)

        metrics = measure_uv_seams(vertices, faces, uv, texture)

        self.assertEqual(metrics["adjacentEdges"], 1)
        self.assertEqual(metrics["severeSeamRatio"], 1.0)

    def test_workflow_fails_closed_when_aligned_gate_rejects(self):
        projector = lambda *_args: {"gate": {"passed": False, "reasons": ["color"]}}

        with self.assertRaisesRegex(RuntimeError, "Reference fidelity gate failed: color"):
            apply_reference_fidelity("paint.glb", "reference.png", "final.glb", "evidence", projector=projector)

    def test_workflow_requires_projected_glb_to_remain_structurally_valid(self):
        projector = lambda *_args: {"gate": {"passed": True, "reasons": []}}
        validator = lambda _path: {"passed": False, "reasons": ["missing_map"]}

        with self.assertRaisesRegex(RuntimeError, "Projected GLB validation failed: missing_map"):
            apply_reference_fidelity(
                "paint.glb",
                "reference.png",
                "final.glb",
                "evidence",
                projector=projector,
                validator=validator,
            )

    def test_silhouette_is_a_union_when_faces_overlap(self):
        vertices = np.array([[8, 56], [56, 56], [32, 8]], dtype=np.float64)
        faces = np.array([[0, 1, 2], [0, 1, 2]], dtype=np.int64)

        mask = _rasterize_silhouette(vertices, faces, (64, 64))

        self.assertGreater(mask.sum(), 1000)

    def test_component_detection_merges_uv_seam_vertices_by_position(self):
        vertices = np.array(
            [
                [0, 0, 0], [1, 0, 0], [0, 1, 0],
                [1, 0, 0], [1, 1, 0], [0, 1, 0],
                [3, 0, 0], [4, 0, 0], [3, 1, 0],
            ],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2], [3, 4, 5], [6, 7, 8]], dtype=np.int64)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        mesh.visual = TextureVisuals(uv=np.zeros((len(vertices), 2)))

        component = _largest_face_component(mesh)

        np.testing.assert_array_equal(component, np.array([0, 1]))

    def test_zbuffer_projects_only_the_camera_visible_surface(self):
        vertices = np.array(
            [
                [-0.5, -0.5, 0.5],
                [0.5, -0.5, 0.5],
                [0.5, 0.5, 0.5],
                [-0.5, 0.5, 0.5],
                [-0.5, -0.5, -0.5],
                [0.5, -0.5, -0.5],
                [0.5, 0.5, -0.5],
                [-0.5, 0.5, -0.5],
            ],
            dtype=np.float64,
        )
        faces = np.array(
            [[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]],
            dtype=np.int64,
        )
        uv = np.array(
            [
                [0.02, 0.02],
                [0.48, 0.02],
                [0.48, 0.98],
                [0.02, 0.98],
                [0.52, 0.02],
                [0.98, 0.02],
                [0.98, 0.98],
                [0.52, 0.98],
            ],
            dtype=np.float64,
        )
        base = np.full((64, 64, 4), (24, 96, 180, 255), dtype=np.uint8)
        calibration = {
            "yawDegrees": 0.0,
            "elevationDegrees": 0.0,
            "scalePixelsPerUnit": 48.0,
            "offsetX": 32.0,
            "offsetY": 32.0,
        }

        projected, confidence, metrics = project_reference_to_texture(
            vertices,
            faces,
            uv,
            base,
            _reference(),
            calibration,
        )

        self.assertGreater(metrics["projectedTexelRatio"], 0.15)
        self.assertEqual(metrics["minimumFacingCosine"], 0.1)
        self.assertGreater(confidence[:, :32].max(), 0)
        self.assertEqual(confidence[:, 32:].max(), 0)
        self.assertGreater(projected[:, :32, 0].mean(), base[:, :32, 0].mean())
        np.testing.assert_array_equal(projected[:, 32:], base[:, 32:])

    def test_angular_confidence_rejects_grazing_faces(self):
        vertices = np.array(
            [[-0.5, -0.5, 0.0], [0.5, -0.5, -9.95], [-0.5, 0.5, 0.0]],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        uv = np.array([[0.05, 0.05], [0.95, 0.05], [0.05, 0.95]], dtype=np.float64)
        base = np.full((64, 64, 4), (24, 96, 180, 255), dtype=np.uint8)
        calibration = {
            "yawDegrees": 0.0,
            "elevationDegrees": 0.0,
            "scalePixelsPerUnit": 48.0,
            "offsetX": 32.0,
            "offsetY": 32.0,
        }

        projected, confidence, metrics = project_reference_to_texture(
            vertices,
            faces,
            uv,
            base,
            _reference(),
            calibration,
            min_facing=0.2,
        )

        np.testing.assert_array_equal(projected, base)
        self.assertEqual(int(confidence.max()), 0)
        self.assertEqual(metrics["grazingRejectedFaces"], 1)
        self.assertEqual(metrics["minimumFacingCosine"], 0.2)

    def test_angular_confidence_softens_oblique_projection(self):
        vertices = np.array(
            [[-0.5, -0.5, 0.0], [0.5, -0.5, -3.873], [-0.5, 0.5, 0.0]],
            dtype=np.float64,
        )
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        uv = np.array([[0.05, 0.05], [0.95, 0.05], [0.05, 0.95]], dtype=np.float64)
        base = np.full((64, 64, 4), (24, 96, 180, 255), dtype=np.uint8)
        calibration = {
            "yawDegrees": 0.0,
            "elevationDegrees": 0.0,
            "scalePixelsPerUnit": 48.0,
            "offsetX": 32.0,
            "offsetY": 32.0,
        }

        projected, confidence, _ = project_reference_to_texture(
            vertices,
            faces,
            uv,
            base,
            _reference(),
            calibration,
            min_facing=0.1,
        )

        changed = confidence > 0
        self.assertTrue(np.any(changed))
        self.assertGreater(projected[:, :, 0][changed].max(), 24)
        self.assertLess(projected[:, :, 0][changed].max(), 220)

    def test_aligned_gate_passes_exact_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.png"
            render = root / "render.png"
            image = Image.fromarray(_reference())
            image.save(reference)
            image.save(render)

            report = evaluate_aligned_fidelity(reference, render)

            self.assertTrue(report["passed"])
            self.assertEqual(report["decision"], "pass")
            self.assertEqual(report["reasons"], [])
            self.assertEqual(report["metrics"]["silhouetteIoU"], 1.0)
            self.assertEqual(report["metrics"]["colorSimilarity"], 1.0)

    def test_aligned_gate_rejects_white_color_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.png"
            render = root / "render.png"
            Image.fromarray(_reference()).save(reference)
            white = _reference().copy()
            white[white[:, :, 3] > 0, :3] = (242, 240, 236)
            Image.fromarray(white).save(render)

            report = evaluate_aligned_fidelity(reference, render)

            self.assertFalse(report["passed"])
            self.assertIn("reference_color_mismatch", report["reasons"])
            self.assertIn("white_leakage", report["reasons"])

    def test_aligned_gate_rejects_localized_texture_cracks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "reference.png"
            render = root / "render.png"
            Image.fromarray(_reference()).save(reference)
            cracked = _reference().copy()
            cracked[12:52:5, 8:56, :3] = (10, 10, 10)
            Image.fromarray(cracked).save(render)

            report = evaluate_aligned_fidelity(reference, render)

            self.assertFalse(report["passed"])
            self.assertIn("localized_texture_mismatch", report["reasons"])

    def test_native_paint_gate_accepts_spatially_coherent_color(self):
        reference = _reference()

        report = evaluate_native_paint_fidelity(reference, reference.copy())

        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["spatialColorCorrelation"], 1.0)

    def test_native_paint_gate_rejects_spatially_scrambled_palette(self):
        reference = _reference().copy()
        reference[8:56, 8:32, :3] = (220, 48, 20)
        reference[8:56, 32:56, :3] = (20, 48, 220)
        scrambled = reference.copy()
        scrambled[8:56, 8:32, :3] = (20, 48, 220)
        scrambled[8:56, 32:56, :3] = (220, 48, 20)

        report = evaluate_native_paint_fidelity(reference, scrambled)

        self.assertFalse(report["passed"])
        self.assertIn("spatial_texture_mismatch", report["reasons"])

    def test_native_paint_gate_rejects_previous_false_positive_boundary(self):
        reference = _reference()

        with patch(
            "reference_projection._low_frequency_color_correlation",
            return_value=0.7999,
        ):
            report = evaluate_native_paint_fidelity(reference, reference.copy())

        self.assertFalse(report["passed"])
        self.assertIn("spatial_texture_mismatch", report["reasons"])
        self.assertEqual(report["thresholds"]["minimumSpatialColorCorrelation"], 0.8)

    def test_native_paint_gate_accepts_strict_boundary(self):
        reference = _reference()

        with patch(
            "reference_projection._low_frequency_color_correlation",
            return_value=0.8,
        ):
            report = evaluate_native_paint_fidelity(reference, reference.copy())

        self.assertTrue(report["passed"])

    def test_native_paint_gate_rejects_silhouette_below_strict_boundary(self):
        image = np.zeros((10, 10, 4), dtype=np.uint8)
        reference_mask = np.ones((10, 10), dtype=bool)
        render_mask = np.zeros((10, 10), dtype=bool)
        render_mask.flat[:79] = True

        with (
            patch(
                "reference_projection._foreground_mask",
                side_effect=[reference_mask, render_mask],
            ),
            patch(
                "reference_projection._low_frequency_color_correlation",
                return_value=1.0,
            ),
        ):
            report = evaluate_native_paint_fidelity(image, image.copy())

        self.assertFalse(report["passed"])
        self.assertIn("silhouette_mismatch", report["reasons"])
        self.assertEqual(report["thresholds"]["minimumSilhouetteIoU"], 0.8)

    def test_native_paint_gate_accepts_silhouette_strict_boundary(self):
        image = np.zeros((10, 10, 4), dtype=np.uint8)
        reference_mask = np.ones((10, 10), dtype=bool)
        render_mask = np.zeros((10, 10), dtype=bool)
        render_mask.flat[:80] = True

        with (
            patch(
                "reference_projection._foreground_mask",
                side_effect=[reference_mask, render_mask],
            ),
            patch(
                "reference_projection._low_frequency_color_correlation",
                return_value=1.0,
            ),
        ):
            report = evaluate_native_paint_fidelity(image, image.copy())

        self.assertTrue(report["passed"])

    def test_quarter_gate_accepts_stable_painted_views(self):
        front = _reference().copy()

        report = evaluate_quarter_texture_stability(
            front,
            {"quarter-left": front.copy(), "quarter-right": front.copy()},
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["reasons"], [])

    def test_quarter_gate_rejects_color_loss(self):
        front = _reference().copy()
        front[8:56, 32:56, :3] = (20, 48, 220)
        blank = front.copy()
        blank[blank[:, :, 3] > 0, :3] = (238, 238, 238)

        report = evaluate_quarter_texture_stability(
            front,
            {"quarter-left": blank, "quarter-right": front.copy()},
        )

        self.assertFalse(report["passed"])
        self.assertIn("quarter-left_paint_loss", report["reasons"])


if __name__ == "__main__":
    unittest.main()
