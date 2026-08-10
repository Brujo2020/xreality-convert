import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from edit_executor import EditExecutionError, execute_replace_material
from pbr_glb import _read_glb
from secure_artifacts import validate_glb_container


def write_glb(path, document):
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((-len(payload)) % 4)
    total = 12 + 8 + len(payload)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(payload), 0x4E4F534A) + payload)


def master_document(shared_mesh=False):
    meshes = [{"primitives": [{"material": 0}]}]
    if not shared_mesh:
        meshes.append({"primitives": [{"material": 1}]})
    return {
        "asset": {"version": "2.0"},
        "materials": [
            {"name": "body-original", "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "metallicFactor": 0, "roughnessFactor": 1}},
            {"name": "trim-original", "pbrMetallicRoughness": {"baseColorFactor": [0, 0, 0, 1], "metallicFactor": 1, "roughnessFactor": 0.2}},
        ],
        "meshes": meshes,
        "nodes": [
            {"mesh": 0, "extras": {"xrealityPartId": "body"}},
            {"mesh": 0 if shared_mesh else 1, "extras": {"xreality": {"part_id": "trim"}}},
        ],
    }


def delta_for(path, targets=["trim"], protected=["body"], **operation):
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": 3,
        "source_master_hash": f"sha256:{source_hash}",
        "edit_type": "replace_material",
        "target_part_ids": sorted(targets),
        "protected_part_ids": sorted(protected),
        "geometry_operation": None,
        "material_operation": operation or {"base_color_factor": [0.1, 0.2, 0.3, 1.0], "metallic_factor": 0.4, "roughness_factor": 0.5},
        "tolerances": {"protected_geometry_delta": 0.0, "protected_uv_delta": 0.0, "protected_material_delta": 0.0},
    }


class TypedEditExecutorTests(unittest.TestCase):
    def test_replaces_only_target_material_in_new_valid_glb(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "master.glb"
            output = Path(directory) / "edited.glb"
            write_glb(source, master_document())
            original = source.read_bytes()
            report = execute_replace_material(source, output, delta_for(source))
            self.assertEqual(source.read_bytes(), original)
            self.assertTrue(output.is_file())
            self.assertEqual(report["modified_primitives"], [{"part_id": "trim", "mesh": 1, "primitive": 0, "material": 2}])
            self.assertEqual(validate_glb_container(output)["nodes"], 2)
            edited, _ = _read_glb(output)
            self.assertEqual(edited["meshes"][0]["primitives"][0]["material"], 0)
            self.assertEqual(edited["meshes"][1]["primitives"][0]["material"], 2)
            self.assertEqual(edited["materials"][2]["pbrMetallicRoughness"]["baseColorFactor"], [0.1, 0.2, 0.3, 1.0])
            self.assertEqual(edited["materials"][0]["name"], "body-original")

    def test_rejects_delta_overlap_without_writing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "master.glb"
            output = Path(directory) / "edited.glb"
            write_glb(source, master_document())
            bad = delta_for(source, targets=["body"], protected=["body"])
            with self.assertRaisesRegex(EditExecutionError, "target_protected_overlap"):
                execute_replace_material(source, output, bad)
            self.assertFalse(output.exists())

    def test_rejects_target_sharing_protected_primitive(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "master.glb"
            output = Path(directory) / "edited.glb"
            write_glb(source, master_document(shared_mesh=True))
            with self.assertRaisesRegex(EditExecutionError, "target_protected_primitive_overlap"):
                execute_replace_material(source, output, delta_for(source))
            self.assertFalse(output.exists())

    def test_rejects_hash_mismatch_and_keeps_source_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "master.glb"
            output = Path(directory) / "edited.glb"
            write_glb(source, master_document())
            original = source.read_bytes()
            bad = delta_for(source)
            bad["source_master_hash"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(EditExecutionError, "source_master_hash_mismatch"):
                execute_replace_material(source, output, bad)
            self.assertEqual(source.read_bytes(), original)
            self.assertFalse(output.exists())

    def test_rejects_nonzero_protected_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "master.glb"
            write_glb(source, master_document())
            bad = delta_for(source)
            bad["tolerances"]["protected_material_delta"] = 0.001
            with self.assertRaisesRegex(EditExecutionError, "protected_tolerance_must_be_zero"):
                execute_replace_material(source, Path(directory) / "edited.glb", bad)


if __name__ == "__main__":
    unittest.main()
