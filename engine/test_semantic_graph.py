import copy
import unittest

from buffalo_strategy import build_semantic_contract
from semantic_graph import SemanticGraphError, compile_semantic_graph, stable_semantic_id


class SemanticGraphTests(unittest.TestCase):
    def test_compiles_existing_contract_deterministically(self):
        contract = build_semantic_contract("forklift")
        first = compile_semantic_graph(contract)
        second = compile_semantic_graph(copy.deepcopy(contract))

        self.assertEqual(first, second)
        self.assertTrue(first["graph_id"].startswith("sha256:"))
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(len(first["nodes"]), 1 + len(contract["expected_parts"]) + len(contract["material_regions"]))
        self.assertEqual(len(first["edges"]), len(contract["expected_parts"]) + len(contract["material_regions"]))

    def test_order_of_input_lists_cannot_change_graph(self):
        contract = build_semantic_contract("crane")
        reversed_contract = copy.deepcopy(contract)
        reversed_contract["expected_parts"].reverse()
        reversed_contract["material_regions"].reverse()

        self.assertEqual(compile_semantic_graph(contract), compile_semantic_graph(reversed_contract))

    def test_rejects_duplicate_or_nonstable_part_identity(self):
        contract = build_semantic_contract("vehicle")
        contract["expected_parts"][1]["part_id"] = contract["expected_parts"][0]["part_id"]
        with self.assertRaisesRegex(SemanticGraphError, "unstable_part_id"):
            compile_semantic_graph(contract)

    def test_rejects_duplicate_canonical_part_name_as_an_ambiguous_node(self):
        contract = build_semantic_contract("vehicle")
        copied = copy.deepcopy(contract["expected_parts"][0])
        contract["expected_parts"].append(copied)
        with self.assertRaisesRegex(SemanticGraphError, "ambiguous_node_id"):
            compile_semantic_graph(contract)

    def test_rejects_unknown_or_conflicting_evidence(self):
        contract = build_semantic_contract("product")
        contract["expected_parts"][0]["evidence"] = "hallucinated"
        contract["expected_parts"][0]["evidence_class"] = "hallucinated"
        with self.assertRaisesRegex(SemanticGraphError, "invalid_evidence_class"):
            compile_semantic_graph(contract)

        contract = build_semantic_contract("product")
        contract["expected_parts"][0]["evidence_class"] = "measured"
        with self.assertRaisesRegex(SemanticGraphError, "conflicting_evidence_class"):
            compile_semantic_graph(contract)

    def test_measured_evidence_requires_a_real_localizer(self):
        contract = build_semantic_contract("product")
        part = contract["expected_parts"][0]
        part["evidence"] = part["evidence_class"] = "measured"
        with self.assertRaisesRegex(SemanticGraphError, "measured_without_localizer"):
            compile_semantic_graph(contract)

        part["localizers"]["component_ids"] = ["component_0001"]
        graph = compile_semantic_graph(contract)
        node = next(item for item in graph["nodes"] if item["id"] == part["part_id"])
        self.assertEqual(node["localizers"]["component_ids"], ["component_0001"])

    def test_unmeasured_evidence_cannot_smuggle_localizer(self):
        contract = build_semantic_contract("product")
        contract["expected_parts"][0]["localizers"]["surface_mask_hash"] = "a" * 64
        with self.assertRaisesRegex(SemanticGraphError, "unmeasured_with_localizer"):
            compile_semantic_graph(contract)

    def test_rejects_material_global_conflation_for_multi_region_asset(self):
        contract = build_semantic_contract("forklift")
        material = contract["material_regions"][0]
        material["name"] = "global"
        material["region_id"] = stable_semantic_id("forklift", "material", "global")
        with self.assertRaisesRegex(SemanticGraphError, "material_global_conflation"):
            compile_semantic_graph(contract)

    def test_single_material_product_can_remain_explicitly_local(self):
        contract = build_semantic_contract("product")
        graph = compile_semantic_graph(contract)
        materials = [node for node in graph["nodes"] if node["kind"] == "material_region"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["canonical_name"], "primary_material")

    def test_rejects_invalid_localizer_shape_and_duplicate_component_ids(self):
        contract = build_semantic_contract("product")
        part = contract["expected_parts"][0]
        part["evidence"] = part["evidence_class"] = "measured"
        part["localizers"]["aabb"] = [0, 0, 0, 1]
        with self.assertRaisesRegex(SemanticGraphError, "invalid_aabb"):
            compile_semantic_graph(contract)

        part["localizers"]["aabb"] = None
        part["localizers"]["component_ids"] = ["component_0001", "component_0001"]
        with self.assertRaisesRegex(SemanticGraphError, "ambiguous_component_ids"):
            compile_semantic_graph(contract)


if __name__ == "__main__":
    unittest.main()
