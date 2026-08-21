import unittest
import numpy as np
import trimesh
from flexicubes_extractor import FlexiCubesExtractor, extract_mesh_flexicubes

class TestFlexiCubesExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = FlexiCubesExtractor(resolution=32)

    def test_basic_sphere_sdf_extraction(self):
        # Create a basic sphere SDF
        grid_size = 32
        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        z = np.linspace(-1, 1, grid_size)
        xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
        
        # Sphere equation: x^2 + y^2 + z^2 - r^2 = 0
        radius = 0.5
        sdf_grid = np.sqrt(xx**2 + yy**2 + zz**2) - radius
        
        mesh = self.extractor.extract(sdf_grid)
        
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertGreater(len(mesh.vertices), 0)
        self.assertGreater(len(mesh.faces), 0)
        self.assertTrue(mesh.is_watertight)

    def test_sharp_edge_preservation(self):
        # Create a cube SDF
        grid_size = 32
        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        z = np.linspace(-1, 1, grid_size)
        xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
        
        # Cube SDF (L-infinity norm)
        sdf_grid = np.maximum(np.maximum(np.abs(xx), np.abs(yy)), np.abs(zz)) - 0.5
        
        mesh = self.extractor.extract(sdf_grid)
        
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertGreater(len(mesh.vertices), 0)
        
        # Detect sharp edges
        sharp_edges = self.extractor.detect_sharp_edges(mesh, angle_threshold=45.0)
        # A cube should have sharp edges detected
        self.assertGreater(len(sharp_edges), 0)

    def test_sliver_elimination(self):
        # Create a mesh with a known sliver
        vertices = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [0.5, 0.00000001, 0] # Sliver vertex
        ])
        faces = np.array([
            [0, 1, 2],
            [0, 3, 1] # Sliver face
        ])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        
        # Area of second face should be very small
        initial_faces = len(mesh.faces)
        
        cleaned_mesh = self.extractor.eliminate_slivers(mesh, min_area=1e-5)
        
        self.assertLess(len(cleaned_mesh.faces), initial_faces)
        self.assertEqual(len(cleaned_mesh.faces), 1)

    def test_empty_sdf(self):
        # All positive SDF (no zero crossing)
        sdf_grid = np.ones((10, 10, 10))
        
        mesh = self.extractor.extract(sdf_grid)
        
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertEqual(len(mesh.vertices), 0)
        self.assertEqual(len(mesh.faces), 0)

    def test_all_zero_sdf(self):
        # All zero SDF
        sdf_grid = np.zeros((10, 10, 10))
        
        mesh = self.extractor.extract(sdf_grid)
        
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertEqual(len(mesh.vertices), 0)
        self.assertEqual(len(mesh.faces), 0)

    def test_extract_mesh_flexicubes_helper(self):
        grid_size = 16
        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        z = np.linspace(-1, 1, grid_size)
        xx, yy, zz = np.meshgrid(x, y, z, indexing='ij')
        sdf_grid = np.sqrt(xx**2 + yy**2 + zz**2) - 0.5
        
        mesh = extract_mesh_flexicubes(sdf_grid)
        
        self.assertIsInstance(mesh, trimesh.Trimesh)
        self.assertGreater(len(mesh.vertices), 0)

if __name__ == '__main__':
    unittest.main()
