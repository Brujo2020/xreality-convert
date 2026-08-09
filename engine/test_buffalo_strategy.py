import tempfile
import unittest
from pathlib import Path

from buffalo_strategy import (
    STRATEGY_VERSION,
    build_apple_execution_graph,
    build_semantic_contract,
    build_strategy_report,
    capture_assembly_fingerprint,
    embed_strategy_metadata,
    validate_assembly_preservation,
)
from pbr_glb import _read_glb, _write_glb


class FakeComponent:
    def __init__(self, faces, area, extents, centroid=(0, 0, 0)):
        self.faces = [None] * faces
        self.vertices = [None] * max(4, faces // 2)
        self.area = area
        self.extents = extents
        self.centroid = centroid


class FakeMesh(FakeComponent):
    def __init__(self, components, extents=(4, 2, 2)):
        super().__init__(
            sum(len(component.faces) for component in components),
            sum(component.area for component in components),
            extents,
        )
        self._components = components

    def split(self, only_watertight=False):
        self.only_watertight = only_watertight
        return self._components


class BuffaloStrategyTests(unittest.TestCase):
    def test_crane_contract_names_critical_thin_parts_without_claiming_evidence(self):
        contract = build_semantic_contract("crane", "xreal", "painted_metal", 1)

        self.assertEqual(contract["version"], STRATEGY_VERSION)
        self.assertFalse(contract["provenance"]["official_buffalo_code_or_weights"])
        self.assertIn("cable", contract["critical_part_names"])
        self.assertIn("hook", contract["thin_part_names"])
        self.assertIn("safety_markings", [item["name"] for item in contract["material_regions"]])
        self.assertEqual(contract["semantic_evidence_status"], "not_measured")

    def test_apple_graph_never_overlaps_metal_stages(self):
        graph = build_apple_execution_graph({
            "chip": "Apple M5 Max",
            "logicalCores": 16,
            "performanceCores": 12,
            "validationWorkers": 4,
        })

        self.assertEqual(graph["maximum_concurrent_metal_stages"], 1)
        self.assertEqual(graph["metal_sequence"][0], "shape_mlx")
        self.assertEqual(graph["metal_sequence"][2], "paint_mlx")
        self.assertEqual(graph["validation_workers"], 4)

    def test_preservation_gate_rejects_meaningful_component_loss(self):
        before_mesh = FakeMesh([
            FakeComponent(800, 80, (4, 2, 2)),
            FakeComponent(200, 20, (1, 1, 1), (2, 0, 0)),
        ])
        after_mesh = FakeMesh([FakeComponent(500, 100, (4, 2, 2))])
        contract = build_semantic_contract("vehicle")

        report = validate_assembly_preservation(
            capture_assembly_fingerprint(before_mesh),
            capture_assembly_fingerprint(after_mesh),
            contract,
        )

        self.assertFalse(report["passed"])
        self.assertIn("meaningful_component_loss", report["reasons"])
        self.assertIn("component_count_retention_below_contract", report["reasons"])

    def test_preservation_gate_accepts_decimation_that_keeps_assembly(self):
        before_mesh = FakeMesh([
            FakeComponent(800, 80, (4, 2, 2)),
            FakeComponent(200, 20, (1, 1, 1), (2, 0, 0)),
        ])
        after_mesh = FakeMesh([
            FakeComponent(400, 80, (4, 2, 2)),
            FakeComponent(100, 20, (1, 1, 1), (2, 0, 0)),
        ])

        report = validate_assembly_preservation(
            capture_assembly_fingerprint(before_mesh),
            capture_assembly_fingerprint(after_mesh),
            build_semantic_contract("vehicle"),
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["metrics"]["component_retention"], 1.0)

    def test_master_report_cannot_self_certify_unmeasured_parts(self):
        contract = build_semantic_contract("truck", "maxquality")
        fingerprint = capture_assembly_fingerprint(
            FakeMesh([FakeComponent(100, 10, (2, 1, 1))])
        )
        preservation = validate_assembly_preservation(fingerprint, fingerprint, contract)
        report = build_strategy_report(
            contract,
            build_apple_execution_graph(),
            preservation,
            material_report={"passed": True},
        )

        self.assertFalse(report["master_promotion_passed"])
        self.assertIn("semantic_parts", report["not_measured"])

    def test_strategy_metadata_is_embedded_in_glb_asset_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.glb"
            _write_glb(path, {"asset": {"version": "2.0"}, "scenes": [{}], "scene": 0}, b"")
            contract = build_semantic_contract("forklift", "vrready")
            preservation = {"passed": True, "decision": "pass"}

            report = embed_strategy_metadata(path, contract, preservation)
            document, _ = _read_glb(path)
            metadata = document["asset"]["extras"]["xrealityBuffaloMLX"]

            self.assertTrue(report["embedded"])
            self.assertEqual(metadata["category"], "forklift")
            self.assertFalse(metadata["officialBuffaloBackend"])
            self.assertIn("forks", [item["name"] for item in metadata["expectedParts"]])


if __name__ == "__main__":
    unittest.main()
