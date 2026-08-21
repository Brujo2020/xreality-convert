import unittest
import tempfile
import numpy as np
import trimesh
from pathlib import Path
from part_decomposer import PartDecomposer, decompose_mesh, SemanticPart


def create_mock_mesh():
    """Sphere + Box composite for testing decomposition."""
    sphere = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    sphere.apply_translation([0, 2, 0])

    box = trimesh.creation.box(extents=[2, 2, 2])
    box.apply_translation([0, 0, 0])

    combined = trimesh.util.concatenate([sphere, box])
    return combined


class TestPartDecomposer(unittest.TestCase):

    def test_empty_mesh(self):
        mesh = trimesh.Trimesh()
        parts = decompose_mesh(mesh)
        self.assertEqual(len(parts), 0)

    def test_single_triangle(self):
        mesh = trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]])
        parts = decompose_mesh(mesh)
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].label, "body")

    def test_segment_connected_components(self):
        mesh1 = trimesh.creation.box()
        mesh2 = trimesh.creation.box()
        mesh2.apply_translation([5, 0, 0])
        mesh = trimesh.util.concatenate([mesh1, mesh2])

        decomposer = PartDecomposer()
        components = decomposer.segment_connected_components(mesh)
        self.assertGreaterEqual(len(components), 2)

    def test_normal_based_clustering(self):
        mesh = trimesh.creation.box()
        decomposer = PartDecomposer()
        labels = decomposer.segment_by_normals(mesh, n_clusters=6)
        self.assertEqual(len(labels), len(mesh.faces))
        self.assertLessEqual(len(np.unique(labels)), 6)

    def test_decompose_composite_mesh(self):
        mesh = create_mock_mesh()
        decomposer = PartDecomposer(min_part_fraction=0.01)
        parts = decomposer.decompose(mesh)

        self.assertGreater(len(parts), 0)

        total_faces = sum(len(p.face_indices) for p in parts)
        self.assertLessEqual(total_faces, len(mesh.faces))

    def test_semantic_labeling(self):
        decomposer = PartDecomposer(category="animal")
        mesh = create_mock_mesh()
        parts = decomposer.decompose(mesh)

        labels = [p.label for p in parts]
        self.assertIn("body", labels)

    def test_export_parts_glb(self):
        mesh = create_mock_mesh()
        parts = decompose_mesh(mesh)

        decomposer = PartDecomposer()
        with tempfile.TemporaryDirectory() as tmp_path:
            exported = decomposer.export_parts_glb(parts, Path(tmp_path))

            self.assertEqual(len(exported), len(parts))
            for filepath in exported.values():
                self.assertTrue(Path(filepath).exists())

    def test_min_part_fraction(self):
        mesh = create_mock_mesh()
        parts = decompose_mesh(mesh, min_part_fraction=0.99)
        self.assertEqual(len(parts), 1)


if __name__ == "__main__":
    unittest.main()
