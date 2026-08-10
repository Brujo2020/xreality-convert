import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pbr_texture_quality_gate import audit_pbr_texture_quality


def png(pixels):
    image = Image.new("RGBA", (2, 2))
    image.putdata(pixels)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


VARIED = png([(20, 40, 60, 120), (40, 60, 90, 160), (70, 100, 120, 210), (90, 130, 160, 240)])
CONSTANT = png([(128, 128, 128, 255)] * 4)


def write_glb(path, document, binary):
    json_chunk = json.dumps(document, separators=(",", ":")).encode()
    json_chunk += b" " * (-len(json_chunk) % 4)
    binary += b"\0" * (-len(binary) % 4)
    body = struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk + struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(body)) + body)


def document(payloads, *, external=False, constant_role=None):
    offsets, views, images = [], [], []
    cursor = 0
    binary = b""
    for payload in payloads:
        offsets.append(cursor)
        views.append({"buffer": 0, "byteOffset": cursor, "byteLength": len(payload)})
        images.append({"bufferView": len(views) - 1, "mimeType": "image/png"})
        binary += payload
        cursor += len(payload)
    if external:
        images[0] = {"uri": "https://example.invalid/albedo.png", "mimeType": "image/png"}
    roles = {"baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 1}}
    material = {
        "pbrMetallicRoughness": roles,
        "normalTexture": {"index": 2},
        "alphaMode": "BLEND",
        "extensions": {"KHR_materials_transmission": {"transmissionFactor": 0.5, "transmissionTexture": {"index": 0}}},
    }
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "images": images,
        "textures": [{"source": i} for i in range(len(images))],
        "materials": [material],
        "meshes": [{"primitives": [{"material": 0, "attributes": {"POSITION": 0, "TEXCOORD_0": 1}}]}],
    }, binary


def graph_and_contract():
    graph = {"nodes": [{"id": "material:glass", "kind": "material_region", "canonical_name": "glass", "evidence_class": "observed"}]}
    contract = {"schema_version": 1, "region_count": 1, "region_maps": {"material:glass": {"material_index": 0, "required_maps": ["base_color", "metallic_roughness", "normal"]}}}
    return graph, contract


class PbrTextureQualityGateTests(unittest.TestCase):
    def test_accepts_bounded_embedded_varied_maps_and_reports_measurements(self):
        graph, contract = graph_and_contract()
        doc, binary = document([VARIED, VARIED, VARIED])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "good.glb"
            write_glb(path, doc, binary)
            report = audit_pbr_texture_quality(path, graph, contract)
        self.assertTrue(report["passed"])
        base = report["regions"][0]["maps"]["base_color"]
        self.assertEqual(base["measurement"]["width"], 2)
        self.assertGreater(base["measurement"]["alpha"]["non_opaque_samples"], 0)
        self.assertEqual(report["evidence_scope"]["relighting"], "not_measured")

    def test_rejects_constant_map(self):
        graph, contract = graph_and_contract()
        doc, binary = document([CONSTANT, VARIED, VARIED])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "constant.glb"
            write_glb(path, doc, binary)
            report = audit_pbr_texture_quality(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn("constant_texture_measurement:material:glass:base_color", report["failures"])

    def test_rejects_missing_uv_accessor_through_regional_binding(self):
        graph, contract = graph_and_contract()
        doc, binary = document([VARIED, VARIED, VARIED])
        doc["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no-uv.glb"
            write_glb(path, doc, binary)
            report = audit_pbr_texture_quality(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn(
            "regional_binding_failed:missing_uv_for_map:material:glass:base_color:TEXCOORD_0",
            report["failures"],
        )

    def test_rejects_malformed_embedded_payload(self):
        graph, contract = graph_and_contract()
        doc, binary = document([b"not-an-image", VARIED, VARIED])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.glb"
            write_glb(path, doc, binary)
            report = audit_pbr_texture_quality(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertIn("image_decode_failed:material:glass:base_color", report["failures"])

    def test_rejects_external_texture_before_pixel_measurement(self):
        graph, contract = graph_and_contract()
        doc, binary = document([VARIED, VARIED, VARIED], external=True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "external.glb"
            write_glb(path, doc, binary)
            report = audit_pbr_texture_quality(path, graph, contract)
        self.assertFalse(report["passed"])
        self.assertTrue(any(reason.startswith("regional_binding_failed:unsafe_or_invalid_glb:") for reason in report["failures"]))


if __name__ == "__main__":
    unittest.main()
