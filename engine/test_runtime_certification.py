import json
import struct
import tempfile
import unittest
from pathlib import Path

from runtime_certification import RuntimeCertificationError, certify_glb_for_target


def write_triangle_glb(path: Path, *, vertices: int = 3, document_override=None):
    # Three float3 positions.  The accessor count is configurable to make a
    # compact synthetic budget failure without any renderer dependency.
    binary = b"\x00" * max(36, vertices * 12)
    document = document_override or {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(binary)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": vertices, "type": "VEC3"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    binary += b"\x00" * ((4 - len(binary) % 4) % 4)
    total = 12 + 8 + len(payload) + 8 + len(binary)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A) + payload
        + struct.pack("<II", len(binary), 0x004E4942) + binary
    )


class RuntimeCertificationTests(unittest.TestCase):
    def test_certifies_minimal_embedded_triangle_for_all_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "triangle.glb"
            write_triangle_glb(path)
            for target in ("web", "xr", "mobile"):
                certificate = certify_glb_for_target(path, target)
                self.assertEqual(certificate["status"], "pass")
                self.assertEqual(certificate["facts"]["triangles"], 1)
                self.assertEqual(certificate["evidence_scope"]["viewer_rendering"], "not_measured")

    def test_rejects_unknown_target_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "triangle.glb"
            write_triangle_glb(path)
            with self.assertRaisesRegex(RuntimeCertificationError, "unknown_runtime_target"):
                certify_glb_for_target(path, "desktop")

    def test_rejects_missing_scene_even_when_container_is_well_formed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene-less.glb"
            document = {
                "asset": {"version": "2.0"}, "buffers": [{"byteLength": 36}],
                "bufferViews": [{"buffer": 0, "byteLength": 36}],
                "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
                "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}], "nodes": [{"mesh": 0}],
            }
            write_triangle_glb(path, document_override=document)
            with self.assertRaisesRegex(RuntimeCertificationError, "missing_scene"):
                certify_glb_for_target(path, "web")

    def test_rejects_budget_overrun(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.glb"
            write_triangle_glb(path, vertices=75_003)
            with self.assertRaisesRegex(RuntimeCertificationError, "runtime_budget_exceeded:vertices"):
                certify_glb_for_target(path, "mobile")

