import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from derivative_lineage import DerivativeLineageError, build_derivative_manifest


def write_triangle_glb(path: Path, *, byte: int = 0) -> None:
    binary = bytes([byte]) * 36
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(binary)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "nodes": [{"mesh": 0}], "scenes": [{"nodes": [0]}], "scene": 0,
    }
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total = 12 + 8 + len(payload) + 8 + len(binary)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(payload), 0x4E4F534A) + payload
        + struct.pack("<II", len(binary), 0x004E4942) + binary
    )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certificate(path: Path, target: str = "web") -> dict:
    return {"schema_version": 1, "status": "pass", "target": target, "artifact": {"sha256": digest(path)}}


def rebake(master: Path, output: Path) -> dict:
    return {
        "schema_version": 1, "status": "pass", "tool": "blender-4.5",
        "source_master_sha256": f"sha256:{digest(master)}",
        "derivative_sha256": f"sha256:{digest(output)}",
        "maps": [{"role": "base_color", "sha256": "a" * 64}, {"role": "normal", "sha256": "b" * 64}],
    }


class DerivativeLineageTests(unittest.TestCase):
    def test_glb_manifest_is_deterministic_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "web.glb"
            write_triangle_glb(master, byte=1)
            write_triangle_glb(output, byte=2)
            kwargs = dict(master_path=master, output_path=output, target="web", topology_changed=False,
                          target_certificate=certificate(output), expected_master_hash=digest(master),
                          expected_output_hash=f"sha256:{digest(output)}")
            first = build_derivative_manifest(**kwargs)
            self.assertEqual(first, build_derivative_manifest(**kwargs))
            self.assertEqual(first["source_master"]["sha256"], f"sha256:{digest(master)}")
            self.assertIsNone(first["rebake_evidence"])

    def test_topology_change_requires_hash_bound_rebake_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "mobile.glb"
            write_triangle_glb(master, byte=1)
            write_triangle_glb(output, byte=2)
            base = dict(master_path=master, output_path=output, target="mobile", topology_changed=True,
                        target_certificate=certificate(output, "mobile"))
            with self.assertRaisesRegex(DerivativeLineageError, "rebake_evidence_required"):
                build_derivative_manifest(**base)
            manifest = build_derivative_manifest(**base, rebake_evidence=rebake(master, output))
            self.assertEqual(manifest["rebake_evidence"]["status"], "pass")
            wrong = rebake(master, output)
            wrong["derivative_sha256"] = "0" * 64
            with self.assertRaisesRegex(DerivativeLineageError, "rebake_derivative_hash_mismatch"):
                build_derivative_manifest(**base, rebake_evidence=wrong)

    def test_rejects_mismatched_or_nonpassing_certificate_and_output_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "xr.glb"
            write_triangle_glb(master, byte=1)
            write_triangle_glb(output, byte=2)
            base = dict(master_path=master, output_path=output, target="xr", topology_changed=False,
                        target_certificate=certificate(output, "xr"))
            with self.assertRaisesRegex(DerivativeLineageError, "output_hash_mismatch"):
                build_derivative_manifest(**base, expected_output_hash="0" * 64)
            bad = certificate(output, "xr")
            bad["status"] = "fail"
            with self.assertRaisesRegex(DerivativeLineageError, "target_certificate_not_passed"):
                build_derivative_manifest(**{**base, "target_certificate": bad})
            bad_hash = certificate(output, "xr")
            bad_hash["artifact"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(DerivativeLineageError, "target_certificate_hash_mismatch"):
                build_derivative_manifest(**{**base, "target_certificate": bad_hash})

    def test_usdz_requires_usdz_and_passing_matching_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "asset.usdz"
            write_triangle_glb(master)
            output.write_bytes(b"usdz-placeholder")
            manifest = build_derivative_manifest(master_path=master, output_path=output, target="usdz",
                                                 topology_changed=False, target_certificate=certificate(output, "usdz"))
            self.assertEqual(manifest["target"], "usdz")


if __name__ == "__main__":
    unittest.main()
