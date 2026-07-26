import base64
import json
import struct
import tempfile
import unittest
from pathlib import Path

from pbr_glb import validate_pbr_glb


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


if __name__ == "__main__":
    unittest.main()
