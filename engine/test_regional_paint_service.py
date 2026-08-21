import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import trimesh
import numpy as np

from regional_paint_service import RegionalPaintService, RegionalPaintResult


class DummySemanticPart:
    def __init__(self, part_id, name):
        self.part_id = part_id
        self.name = name
        self.mesh = trimesh.creation.box()


class TestRegionalPaintService(unittest.TestCase):

    def test_material_hint_generation_animal(self):
        service = RegionalPaintService()
        parts = [
            DummySemanticPart("p1", "body"),
            DummySemanticPart("p2", "head"),
            DummySemanticPart("p3", "leg_1"),
            DummySemanticPart("p4", "unknown_part"),
        ]
        hints = service.generate_part_material_hints(parts, "animal")
        self.assertEqual(hints["p1"], "fur")
        self.assertEqual(hints["p2"], "fur")
        self.assertEqual(hints["p3"], "fur")
        self.assertEqual(hints["p4"], "auto")

    def test_material_hint_generation_vehicle(self):
        service = RegionalPaintService()
        parts = [
            DummySemanticPart("v1", "car_body"),
            DummySemanticPart("v2", "front_wheel"),
            DummySemanticPart("v3", "front_window"),
        ]
        hints = service.generate_part_material_hints(parts, "vehicle")
        self.assertEqual(hints["v1"], "painted_metal")
        self.assertEqual(hints["v2"], "rubber")
        self.assertEqual(hints["v3"], "glass")

    def test_material_hint_generation_person(self):
        service = RegionalPaintService()
        parts = [
            DummySemanticPart("h1", "human_body"),
            DummySemanticPart("h2", "head"),
            DummySemanticPart("h3", "hair_style"),
        ]
        hints = service.generate_part_material_hints(parts, "person")
        self.assertEqual(hints["h1"], "fabric")
        self.assertEqual(hints["h2"], "skin")
        self.assertEqual(hints["h3"], "hair")

    def test_material_hint_product(self):
        service = RegionalPaintService()
        hints = service.generate_part_material_hints(
            [DummySemanticPart("pr1", "base")], "product"
        )
        self.assertEqual(hints["pr1"], "plastic")

    def test_material_hint_industrial(self):
        service = RegionalPaintService()
        hints = service.generate_part_material_hints(
            [DummySemanticPart("i1", "base")], "industrial"
        )
        self.assertEqual(hints["i1"], "metal")

    def test_merge_pipeline(self):
        service = RegionalPaintService()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            mesh1 = trimesh.creation.box()
            mesh1.visual.face_colors = [255, 0, 0, 255]
            mesh1_path = tmp_path / "part1.glb"
            mesh1.export(str(mesh1_path))

            mesh2 = trimesh.creation.icosphere()
            mesh2.visual.face_colors = [0, 255, 0, 255]
            mesh2_path = tmp_path / "part2.glb"
            mesh2.export(str(mesh2_path))

            painted_parts = [
                {"part_id": "part1", "glb_path": mesh1_path, "paint_report": {}},
                {"part_id": "part2", "glb_path": mesh2_path, "paint_report": {}},
            ]

            merged_path = tmp_path / "merged.glb"
            result_path = service.merge_painted_parts(painted_parts, merged_path)

            self.assertTrue(result_path.exists())
            merged_scene = trimesh.load(result_path)

            if isinstance(merged_scene, trimesh.Scene):
                self.assertGreaterEqual(len(merged_scene.geometry), 2)
            else:
                self.fail("Expected a Scene")

    def test_paint_by_parts_success(self):
        mock_paint_service = MagicMock()

        def mock_run(mesh_path, image_path, output_glb_path, **kwargs):
            mesh = trimesh.creation.box()
            mesh.export(str(output_glb_path))
            return {"passed": True}

        mock_paint_service.run.side_effect = mock_run

        service = RegionalPaintService(paint_service_factory=lambda: mock_paint_service)

        parts = [DummySemanticPart("p1", "body"), DummySemanticPart("p2", "head")]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            result = service.paint_by_parts(
                mesh_path=Path("dummy_mesh.obj"),
                image_path=Path("dummy_img.png"),
                parts=parts,
                output_dir=tmp_path,
                material_hints={"p1": "fur", "p2": "auto"},
            )

            self.assertIsInstance(result, RegionalPaintResult)
            self.assertEqual(result.total_parts, 2)
            self.assertEqual(result.parts_painted, 2)
            self.assertTrue(result.merged_successfully)
            self.assertTrue(Path(result.output_glb).exists())
            self.assertEqual(len(result.per_part_reports), 2)

    def test_paint_by_parts_partial_failure(self):
        mock_paint_service = MagicMock()

        def mock_run(mesh_path, image_path, output_glb_path, **kwargs):
            if "p1" in str(mesh_path):
                mesh = trimesh.creation.box()
                mesh.export(str(output_glb_path))
                return {"passed": True}
            else:
                raise RuntimeError("Paint failed")

        mock_paint_service.run.side_effect = mock_run

        service = RegionalPaintService(paint_service_factory=lambda: mock_paint_service)
        parts = [DummySemanticPart("p1", "body"), DummySemanticPart("p2", "head")]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            result = service.paint_by_parts(
                mesh_path=Path("dummy_mesh.obj"),
                image_path=Path("dummy_img.png"),
                parts=parts,
                output_dir=tmp_path,
            )

            self.assertEqual(result.total_parts, 2)
            self.assertEqual(result.parts_painted, 1)
            self.assertTrue(result.merged_successfully)
            self.assertEqual(len(result.per_part_reports), 1)

    def test_paint_by_parts_empty(self):
        service = RegionalPaintService()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            result = service.paint_by_parts(
                mesh_path=Path("dummy_mesh.obj"),
                image_path=Path("dummy_img.png"),
                parts=[],
                output_dir=tmp_path,
            )

            self.assertEqual(result.total_parts, 0)
            self.assertEqual(result.parts_painted, 0)
            self.assertFalse(result.merged_successfully)


if __name__ == "__main__":
    unittest.main()
