import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import trimesh

from lod_derivation import LODDerivationError, derive_glb_lod
from secure_artifacts import validate_glb_container


def write_mesh(path: Path, *, subdivisions: int = 3) -> None:
    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.icosphere(subdivisions=subdivisions), node_name="sphere", geom_name="sphere")
    path.write_bytes(scene.export(file_type="glb"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LODDerivationTests(unittest.TestCase):
    def test_derives_finite_hash_bound_lod_without_mutating_master(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "mobile.glb"
            write_mesh(master)
            before = master.read_bytes()
            report = derive_glb_lod(master, output, target_faces=120, expected_master_sha256=f"sha256:{digest(master)}")
            self.assertEqual(before, master.read_bytes())
            self.assertTrue(output.is_file())
            self.assertLessEqual(report["output"]["faces"], 120)
            self.assertLess(report["output"]["faces"], report["source_master"]["faces"])
            self.assertEqual(report["source_master"]["sha256"], f"sha256:{digest(master)}")
            self.assertEqual(report["output"]["sha256"], f"sha256:{digest(output)}")
            self.assertTrue(report["seal"]["value"].startswith("sha256:"))
            self.assertEqual(
                validate_glb_container(output)["nodes"],
                validate_glb_container(master)["nodes"],
            )
            on_disk = json.loads(output.with_suffix(".lod-report.json").read_text())
            self.assertEqual(on_disk, report)

    def test_rejects_master_overwrite_and_non_reducing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            master = Path(directory) / "master.glb"
            write_mesh(master, subdivisions=2)
            with self.assertRaisesRegex(LODDerivationError, "overwrite_master"):
                derive_glb_lod(master, master, target_faces=10)
            source_faces = len(trimesh.load(master, force="mesh", process=False).faces)
            with self.assertRaisesRegex(LODDerivationError, "lower_than_master"):
                derive_glb_lod(master, Path(directory) / "same.glb", target_faces=source_faces)

    def test_fails_closed_for_bad_simplifier_without_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "broken.glb"
            write_mesh(master)

            def corrupt(mesh, _target_faces):
                mesh.vertices[0] = np.array([np.nan, 0.0, 0.0])
                return mesh

            with self.assertRaisesRegex(LODDerivationError, "non_finite_geometry"):
                derive_glb_lod(master, output, target_faces=100, simplifier=corrupt)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".lod-report.json").exists())

    def test_report_and_derivative_are_never_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "lod.glb"
            write_mesh(master)
            output.write_bytes(b"do-not-replace")
            with self.assertRaisesRegex(LODDerivationError, "already_exists"):
                derive_glb_lod(master, output, target_faces=100)
            self.assertEqual(output.read_bytes(), b"do-not-replace")

    def test_rejects_a_report_path_that_would_replace_the_derivative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master, output = root / "master.glb", root / "lod.glb"
            write_mesh(master)
            with self.assertRaisesRegex(LODDerivationError, "paths_must_differ"):
                derive_glb_lod(master, output, target_faces=100, report_path=output)

    def test_expected_master_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            master = root / "master.glb"
            write_mesh(master)
            with self.assertRaisesRegex(LODDerivationError, "expected_master_sha256_mismatch"):
                derive_glb_lod(master, root / "lod.glb", target_faces=100, expected_master_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
