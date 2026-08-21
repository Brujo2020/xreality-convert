"""Unit and integration test suite for 3D Local Orchestrator, AssetGraph, and Model Adapters.
"""

import unittest
import tempfile
import json
import shutil
from pathlib import Path

from asset_graph import AssetGraph, AssetGraphNode, PartialRegenerationEngine
from capability_router import CapabilityRouter, CapabilityProfile
from models.trellis2_adapter import Trellis2Adapter
from models.pixal3d_adapter import Pixal3dAdapter
from models.partpacker_adapter import PartPackerAdapter
from models.triposg_adapter import TripoSGAdapter
from models.riganything_adapter import RigAnythingAdapter
from models.material_generator import MaterialGenerator
from blender_mcp import BlenderMCPBridge
from visionos_bridge import VisionOSBridge
from benchmark_3d_local import BenchmarkSuite3DLocal
from cli_orchestrator import Orchestrator3DLocal


class Test3DLocalOrchestrator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_asset_graph_serialization(self):
        graph = AssetGraph(prompt="Test Robot", model_name="pixal3d", backend="mlx")
        node = AssetGraphNode(node_id="head_01", name="head", category="character", triangles=12000)
        graph.add_node(node)
        graph.set_lod("lod0", "/tmp/model_lod0.glb", 50000)

        json_file = self.temp_dir / "test_graph.json"
        graph.save_json(json_file)
        self.assertTrue(json_file.is_file())

        loaded_graph = AssetGraph.load_json(json_file)
        self.assertEqual(loaded_graph.asset_id, graph.asset_id)
        self.assertEqual(loaded_graph.source["prompt"], "Test Robot")
        self.assertIn("head_01", loaded_graph.parts)

    def test_partial_regeneration_engine(self):
        graph = AssetGraph(prompt="Test Chair")
        node = AssetGraphNode(node_id="leg_01", name="leg_1", category="furniture", transform_matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
        graph.add_node(node)

        modified = PartialRegenerationEngine.modify_node(graph, "leg_01", "scale", {"scale_factors": [1.0, 0.5, 1.0]})
        self.assertEqual(modified.parts["leg_01"].transform_matrix[5], 0.5)

    def test_capability_router_resolution(self):
        spec_fast = CapabilityRouter.resolve_pipeline(quality="fast")
        self.assertEqual(spec_fast["profile"], CapabilityProfile.FAST)
        self.assertEqual(spec_fast["backbone_model"], "triposg")

        spec_max = CapabilityRouter.resolve_pipeline(quality="max", target="visionos")
        self.assertEqual(spec_max["profile"], CapabilityProfile.MAX)
        self.assertEqual(spec_max["backbone_model"], "pixal3d")
        self.assertTrue(spec_max["parts_separation"])
        self.assertTrue(spec_max["rigging"])

    def test_model_adapters(self):
        trellis = Trellis2Adapter(device="mlx")
        t_res = trellis.generate_geometry(self.temp_dir / "test.png", octree_resolution=192)
        self.assertEqual(t_res["status"], "success")

        pixal = Pixal3dAdapter(device="mlx")
        p_res = pixal.generate(self.temp_dir / "test.png", self.temp_dir / "out.glb", octree_resolution=192)
        self.assertEqual(p_res["status"], "success")

        graph = AssetGraph(prompt="Furniture Test")
        partpacker = PartPackerAdapter()
        parts_res = partpacker.decompose(self.temp_dir / "out.glb", graph, category="furniture")
        self.assertEqual(parts_res["status"], "success")
        self.assertGreaterEqual(parts_res["parts_count"], 4)

        rigger = RigAnythingAdapter()
        rig_res = rigger.rig(self.temp_dir / "out.glb", graph, category="generic")
        self.assertEqual(rig_res["status"], "success")
        self.assertTrue(graph.rig["has_rig"])

        mat_gen = MaterialGenerator(backend="pixal")
        mat_res = mat_gen.generate(self.temp_dir / "out.glb", graph, resolution=2048)
        self.assertEqual(mat_res["status"], "success")
        self.assertIn("pbr_master_material", graph.materials)

    def test_visionos_bridge(self):
        graph = AssetGraph(prompt="XR Box")
        res = VisionOSBridge.validate_and_package(self.temp_dir / "in.glb", self.temp_dir / "out.usdz", graph)
        self.assertEqual(res["status"], "success")
        self.assertTrue(graph.targets["visionos_ready"])

    def test_blender_mcp_bridge(self):
        graph = AssetGraph(prompt="Blender Asset")
        bridge = BlenderMCPBridge()
        res = bridge.process_asset_graph(graph, "reduce polycount to 25k and unwrap uv")
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["parsed_operations"]), 2)

    def test_benchmark_suite(self):
        suite = BenchmarkSuite3DLocal(corpus_dir=self.temp_dir)
        res = suite.run_benchmark(sample_count=3)
        self.assertEqual(res["status"], "success")
        self.assertIn("QUALITY_PER_GB_PER_SECOND", res["primary_metric"]["name"])

    def test_full_north_star_orchestrator(self):
        orchestrator = Orchestrator3DLocal(output_dir=self.temp_dir)
        res = orchestrator.create(
            input_source="retro futuristic robot",
            quality="max",
            target="visionos",
            parts=True,
            pbr=True,
            rig=True,
            lod=True,
            device="mlx",
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["pipeline_profile"], CapabilityProfile.MAX)
        self.assertTrue(res["visionos_ready"])
        self.assertTrue(Path(res["asset_graph_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
