import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from supply_chain_registry import (
    SUPPLY_CHAIN_KIND,
    SUPPLY_CHAIN_SCHEMA_VERSION,
    SupplyChainError,
    load_and_verify_manifest,
    seal_manifest,
    verify_manifest,
    verify_manifest_seal,
)


def _hash(contents: bytes) -> str:
    return "sha256:" + hashlib.sha256(contents).hexdigest()


class SupplyChainRegistryTests(unittest.TestCase):
    def _manifest(self, root: Path) -> dict:
        model = b"sealed local weights"
        skill = b"local skill instructions"
        script = b"print('pinned helper')\n"
        (root / "weights").mkdir(exist_ok=True)
        (root / "skills").mkdir(exist_ok=True)
        (root / "tools").mkdir(exist_ok=True)
        (root / "weights" / "shape.safetensors").write_bytes(model)
        (root / "skills" / "art-director.md").write_bytes(skill)
        (root / "tools" / "validate.py").write_bytes(script)
        return {
            "schema_version": SUPPLY_CHAIN_SCHEMA_VERSION,
            "kind": SUPPLY_CHAIN_KIND,
            "scope": "job",
            "entries": [
                {
                    "id": "hunyuan_shape",
                    "kind": "model",
                    "source": {"repo": "https://github.com/Tencent/Hunyuan3D-2", "commit": "a" * 40},
                    "license_id": "Apache-2.0",
                    "artifact": {"path": "weights/shape.safetensors", "sha256": _hash(model)},
                    "scripts": [{"path": "tools/validate.py", "sha256": _hash(script)}],
                },
                {
                    "id": "art_director_skill",
                    "kind": "skill",
                    "source": {"repo": "https://github.com/multica-ai/andrej-karpathy-skills", "commit": "b" * 40},
                    "license_id": "MIT",
                    "artifact": {"path": "skills/art-director.md", "sha256": _hash(skill)},
                },
            ],
        }

    def test_sealed_local_model_skill_and_optional_script_verify(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed = seal_manifest(self._manifest(root))
            verified = verify_manifest(sealed, local_root=root, expected_scope="job")
            self.assertTrue(verify_manifest_seal(sealed))
            self.assertEqual(verified.by_id("hunyuan_shape").artifact.local_path, (root / "weights" / "shape.safetensors").resolve())
            self.assertEqual(verified.by_id("hunyuan_shape").scripts[0].relative_path, "tools/validate.py")
            with self.assertRaisesRegex(SupplyChainError, "entry_not_found"):
                verified.by_id("unlisted")

    def test_artifact_or_optional_script_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed = seal_manifest(self._manifest(root))
            (root / "tools" / "validate.py").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(SupplyChainError, "artifact_hash_mismatch"):
                verify_manifest(sealed, local_root=root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed = seal_manifest(self._manifest(root))
            (root / "weights" / "shape.safetensors").write_text("changed weights", encoding="utf-8")
            with self.assertRaisesRegex(SupplyChainError, "artifact_hash_mismatch"):
                verify_manifest(sealed, local_root=root)

    def test_manifest_self_hash_detects_all_declaration_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            sealed = seal_manifest(self._manifest(Path(directory)))
            sealed["entries"][0]["source"]["repo"] = "https://github.com/attacker/replacement"
            self.assertFalse(verify_manifest_seal(sealed))
            with self.assertRaisesRegex(SupplyChainError, "manifest_tampered"):
                verify_manifest(sealed, local_root=directory)

    def test_branch_tags_bad_urls_and_licenses_are_never_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = self._manifest(Path(directory))
            manifest["entries"][0]["source"]["commit"] = "main"
            with self.assertRaisesRegex(SupplyChainError, "commit_unpinned"):
                seal_manifest(manifest)
            manifest = self._manifest(Path(directory))
            manifest["entries"][0]["source"]["repo"] = "git@github.com:org/repo.git"
            with self.assertRaisesRegex(SupplyChainError, "source_repo_invalid"):
                seal_manifest(manifest)
            manifest = self._manifest(Path(directory))
            manifest["entries"][0]["license_id"] = "whatever-free-license"
            with self.assertRaisesRegex(SupplyChainError, "license_id_not_allowed"):
                seal_manifest(manifest)

    def test_symlinked_files_and_paths_outside_managed_root_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            sealed = seal_manifest(self._manifest(root))
            target = Path(outside) / "weights"
            target.write_bytes(b"other")
            (root / "weights" / "shape.safetensors").unlink()
            (root / "weights" / "shape.safetensors").symlink_to(target)
            with self.assertRaisesRegex(SupplyChainError, "artifact_symlink"):
                verify_manifest(sealed, local_root=root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            manifest["entries"][0]["artifact"]["path"] = "../outside"
            with self.assertRaisesRegex(SupplyChainError, "artifact_invalid_path"):
                seal_manifest(manifest)

    def test_owner_controlled_manifest_file_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed = seal_manifest(self._manifest(root))
            manifest_path = root / "supply-chain.json"
            manifest_path.write_text(json.dumps(sealed), encoding="utf-8")
            manifest_path.chmod(0o600)
            verified = load_and_verify_manifest(manifest_path, local_root=root, expected_scope="job")
            self.assertEqual(len(verified.entries), 2)
            manifest_path.chmod(0o666)
            with self.assertRaisesRegex(SupplyChainError, "manifest_mutable"):
                load_and_verify_manifest(manifest_path, local_root=root)

    def test_duplicate_paths_and_wrong_scope_fail_before_file_access(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._manifest(root)
            manifest["entries"][1]["artifact"]["path"] = "weights/shape.safetensors"
            with self.assertRaisesRegex(SupplyChainError, "path_duplicate"):
                seal_manifest(manifest)
            sealed = seal_manifest(self._manifest(root))
            with self.assertRaisesRegex(SupplyChainError, "scope_mismatch"):
                verify_manifest(sealed, local_root=root, expected_scope="config")


if __name__ == "__main__":
    unittest.main()
