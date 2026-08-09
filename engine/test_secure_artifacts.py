import json
import struct
import tempfile
import unittest
from pathlib import Path

from secure_artifacts import UnsafeAssetError, validate_glb_container


def write_glb(path, document):
    payload = json.dumps(document).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total = 12 + 8 + len(payload)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(payload), 0x4E4F534A) + payload)


class SecureArtifactTests(unittest.TestCase):
    def test_validates_small_embedded_glb(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.glb"
            write_glb(path, {"asset": {"version": "2.0"}, "nodes": [{}], "images": [{"uri": "data:image/png;base64,AA=="}]})
            self.assertEqual(validate_glb_container(path)["nodes"], 1)

    def test_rejects_external_texture_uri(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset.glb"
            write_glb(path, {"asset": {"version": "2.0"}, "images": [{"uri": "https://example.invalid/x.png"}]})
            with self.assertRaisesRegex(UnsafeAssetError, "external_texture_uri"):
                validate_glb_container(path)
