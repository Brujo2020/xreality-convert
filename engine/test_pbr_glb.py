import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pbr_glb import (
    _read_glb,
    apply_material_features,
    validate_material_contract,
    validate_pbr_glb,
)


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def write_glb(path, document, binary=b""):
    json_chunk = json.dumps(document, separators=(",", ":")).encode("utf-8")
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    chunks = struct.pack("<II", len(json_chunk), 0x4E4F534A) + json_chunk
    if binary:
        chunks += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + len(chunks)) + chunks)


def pbr_document(image):
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(PNG_1X1)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(PNG_1X1)}],
        "images": [image],
        "textures": [{"source": 0}],
        "materials": [{"pbrMetallicRoughness": {
            "baseColorTexture": {"index": 0},
            "metallicRoughnessTexture": {"index": 0},
        }}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "TEXCOORD_0": 1}, "material": 0}]}],
    }


class PbrGlbTests(unittest.TestCase):
    def test_accepts_embedded_visible_pbr_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "embedded.glb"
            write_glb(path, pbr_document({"bufferView": 0, "mimeType": "image/png"}), PNG_1X1)
            report = validate_pbr_glb(path)
            self.assertTrue(report["passed"])
            self.assertEqual(report["embedded_images"], 1)
            self.assertTrue(report["embedded_base_color"])
            self.assertTrue(report["embedded_metallic_roughness"])

    def test_rejects_external_texture_uris(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "external.glb"
            write_glb(path, pbr_document({"uri": "albedo.png", "mimeType": "image/png"}))
            report = validate_pbr_glb(path)
            self.assertFalse(report["passed"])
            self.assertIn("base_color_texture_not_embedded", report["reasons"])
            self.assertIn("metallic_roughness_texture_not_embedded", report["reasons"])

    def test_rejects_fake_embedded_image_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fake.glb"
            document = pbr_document({"bufferView": 0, "mimeType": "image/png"})
            document["buffers"][0]["byteLength"] = 8
            document["bufferViews"][0]["byteLength"] = 8
            write_glb(path, document, b"not a png")
            report = validate_pbr_glb(path)
            self.assertFalse(report["passed"])
            self.assertEqual(report["embedded_images"], 0)

    def test_rejects_embedded_textures_without_uv_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing-uv.glb"
            document = pbr_document({"bufferView": 0, "mimeType": "image/png"})
            document["meshes"][0]["primitives"][0]["attributes"].pop("TEXCOORD_0")
            write_glb(path, document, PNG_1X1)
            report = validate_pbr_glb(path)
            self.assertFalse(report["passed"])
            self.assertIn("missing_texture_coordinates", report["reasons"])

    def test_material_contract_rejects_missing_master_normal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skin.glb"
            write_glb(path, pbr_document({"bufferView": 0, "mimeType": "image/png"}), PNG_1X1)
            contract = {
                "required_maps": ["base_color", "metallic_roughness"],
                "recommended_maps": ["normal"],
                "extensions": {},
            }

            production = validate_material_contract(path, contract)
            master = validate_material_contract(path, contract, enforce_recommended=True)

            self.assertTrue(production["passed"])
            self.assertFalse(production["premium_ready"])
            self.assertFalse(master["passed"])
            self.assertIn("missing_master_map:normal", master["reasons"])

    def test_glass_features_are_embedded_and_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glass.glb"
            write_glb(path, pbr_document({"bufferView": 0, "mimeType": "image/png"}), PNG_1X1)
            contract = {
                "required_maps": ["base_color", "metallic_roughness"],
                "recommended_maps": [],
                "extensions": {
                    "KHR_materials_transmission": {"transmissionFactor": 1.0},
                    "KHR_materials_ior": {"ior": 1.5},
                },
            }

            before = validate_material_contract(path, contract)
            applied = apply_material_features(path, contract)
            after = validate_material_contract(path, contract)
            document, _ = _read_glb(path)

            self.assertFalse(before["passed"])
            self.assertTrue(applied["applied"])
            self.assertTrue(after["passed"])
            self.assertEqual(
                document["materials"][0]["pbrMetallicRoughness"]["metallicFactor"],
                0.0,
            )

    def test_material_contract_rejects_physically_wrong_mr_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong-rubber.glb"
            write_glb(path, pbr_document({"bufferView": 0, "mimeType": "image/png"}), PNG_1X1)
            contract = {
                "required_maps": ["base_color", "metallic_roughness"],
                "recommended_maps": [],
                "extensions": {},
                "metallic_range": [0.0, 0.02],
                "roughness_range": [0.68, 1.0],
            }

            report = validate_material_contract(path, contract)

            self.assertFalse(report["passed"])
            self.assertIn("material_0_roughness_out_of_range", report["reasons"])
            self.assertTrue(report["range_reports"][0]["checks"]["metallic"]["passed"])

    def test_material_contract_rejects_unassigned_primitive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unassigned.glb"
            document = pbr_document({"bufferView": 0, "mimeType": "image/png"})
            document["meshes"][0]["primitives"].append({"attributes": {"POSITION": 0}})
            write_glb(path, document, PNG_1X1)

            report = validate_material_contract(
                path,
                {
                    "required_maps": ["base_color", "metallic_roughness"],
                    "recommended_maps": [],
                    "extensions": {},
                },
            )

            self.assertFalse(report["passed"])
            self.assertIn("primitive_without_valid_material", report["reasons"])

    def test_multimaterial_intent_never_applies_one_extension_globally(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vehicle.glb"
            write_glb(path, pbr_document({"bufferView": 0, "mimeType": "image/png"}), PNG_1X1)
            contract = {
                "required_maps": ["base_color", "metallic_roughness"],
                "recommended_maps": [],
                "extensions": {
                    "KHR_materials_clearcoat": {"clearcoatFactor": 0.72}
                },
                "recommended_material_regions": 3,
                "allow_global_material_features": False,
                "allow_global_mr_ranges": False,
            }

            applied = apply_material_features(path, contract)
            report = validate_material_contract(path, contract)

            self.assertFalse(applied["applied"])
            self.assertEqual(applied["skipped"], "material_region_segmentation_required")
            self.assertTrue(report["passed"])
            self.assertFalse(report["premium_ready"])
            self.assertEqual(report["recommended_extensions"], ["KHR_materials_clearcoat"])


if __name__ == "__main__":
    unittest.main()
