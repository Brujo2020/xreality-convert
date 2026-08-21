import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path

from buffalo_strategy import build_semantic_contract
from regional_pbr_gate import audit_regional_pbr
from semantic_graph import compile_semantic_graph


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def write_glb(path, document, binary=PNG):
    chunk = json.dumps(document, separators=(",", ":")).encode()
    chunk += b" " * (-len(chunk) % 4)
    binary += b"\0" * (-len(binary) % 4)
    body = struct.pack("<II", len(chunk), 0x4E4F534A) + chunk + struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body)


def graph_and_contract():
    graph = compile_semantic_graph(build_semantic_contract("furniture"))
    regions = [node for node in graph["nodes"] if node["kind"] == "material_region"]
    contract = {
        "schema_version": 1,
        "region_count": len(regions),
        "region_maps": {
            node["id"]: {"material_index": index, "required_maps": ["base_color", "metallic_roughness", "normal"]}
            for index, node in enumerate(regions)
        },
    }
    return graph, contract, regions


def regional_document(count):
    # One embedded image can intentionally service independent material slots;
    # the gate's anti-conflation invariant is material assignment, not file
    # duplication.
    material = {"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 0}}, "normalTexture": {"index": 0}}
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(PNG)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(PNG)}],
        "images": [{"bufferView": 0, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "materials": [material.copy() for _ in range(count)],
        "meshes": [{"primitives": [
            {"material": index, "attributes": {"POSITION": 0, "TEXCOORD_0": 1}}
            for index in range(count)
        ]}],
    }


class RegionalPbrGateTests(unittest.TestCase):
    def test_accepts_explicit_distinct_regions_with_embedded_maps(self):
        graph, contract, regions = graph_and_contract()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regional.glb"
            write_glb(path, regional_document(len(regions)))
            report = audit_regional_pbr(path, graph, contract)
        self.assertTrue(report["passed"])
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["evidence_scope"]["texture_to_surface_region_alignment"], "not_measured")

    def test_rejects_global_material_conflation(self):
        graph, contract, regions = graph_and_contract()
        first = regions[0]["id"]
        second = regions[1]["id"]
        contract["region_maps"][second]["material_index"] = contract["region_maps"][first]["material_index"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "conflated.glb"
            write_glb(path, regional_document(len(regions)))
            report = audit_regional_pbr(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn("global_material_conflation", report["failures"])

    def test_rejects_missing_required_map_and_missing_uv(self):
        graph, contract, regions = graph_and_contract()
        document = regional_document(len(regions))
        document["materials"][1].pop("normalTexture")
        document["meshes"][0]["primitives"][2]["attributes"].pop("TEXCOORD_0")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.glb"
            write_glb(path, document)
            report = audit_regional_pbr(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn(f"missing_embedded_map:{regions[1]['id']}:normal", report["failures"])
        self.assertIn(f"missing_uv_for_map:{regions[2]['id']}:base_color:TEXCOORD_0", report["failures"])

    def test_rejects_missing_region_contract_and_unbound_primitive_material(self):
        graph, contract, regions = graph_and_contract()
        contract["region_maps"].pop(regions[-1]["id"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incomplete.glb"
            write_glb(path, regional_document(len(regions)))
            report = audit_regional_pbr(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn("regional_contract_region_coverage_mismatch", report["failures"])

    def test_rejects_global_semantic_region_name(self):
        graph, contract, regions = graph_and_contract()
        target = next(node for node in graph["nodes"] if node.get("id") == regions[0]["id"])
        target["canonical_name"] = "global"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "global-name.glb"
            write_glb(path, regional_document(len(regions)))
            report = audit_regional_pbr(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn(f"global_region_conflation:{regions[0]['id']}", report["failures"])


if __name__ == "__main__":
    unittest.main()
