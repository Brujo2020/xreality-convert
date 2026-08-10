import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pinned_stage_worker import PinnedStageWorker, PinnedStageWorkerError
from stage_supervisor import StageLimits
from supply_chain_registry import SUPPLY_CHAIN_KIND, SUPPLY_CHAIN_SCHEMA_VERSION, seal_manifest


def _hash(contents: bytes) -> str:
    return "sha256:" + hashlib.sha256(contents).hexdigest()


class _Process:
    returncode = 0

    def communicate(self, timeout=None):
        return ("pinned-ok", "")


class PinnedStageWorkerTests(unittest.TestCase):
    def _sealed_manifest(self, root: Path) -> Path:
        (root / "weights").mkdir()
        (root / "tools").mkdir()
        weights = b"sealed local model"
        script = b"print('only this worker may launch')\n"
        (root / "weights" / "shape.bin").write_bytes(weights)
        (root / "tools" / "worker.py").write_bytes(script)
        manifest = seal_manifest({
            "schema_version": SUPPLY_CHAIN_SCHEMA_VERSION,
            "kind": SUPPLY_CHAIN_KIND,
            "scope": "job",
            "entries": [{
                "id": "shape_stage",
                "kind": "model",
                "source": {"repo": "https://github.com/example/shape", "commit": "a" * 40},
                "license_id": "MIT",
                "artifact": {"path": "weights/shape.bin", "sha256": _hash(weights)},
                "scripts": [{"path": "tools/worker.py", "sha256": _hash(script)}],
            }],
        })
        path = root / "supply-chain.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        path.chmod(0o600)
        return path

    def _worker(self):
        return PinnedStageWorker(lambda: {"free_percent": 50.0, "swap_used_mb": 1.0})

    def test_verified_pinned_script_starts_once_with_forced_offline_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._sealed_manifest(root)
            script = root / "tools" / "worker.py"
            with mock.patch("stage_supervisor.subprocess.Popen", return_value=_Process()) as popen:
                result = self._worker().run(
                    [sys.executable, str(script)], cwd=root,
                    manifest_path=manifest, local_root=root, expected_scope="job",
                    expected_entry_ids=["shape_stage"], launcher_entry_id="shape_stage",
                    launcher_relative_path="tools/worker.py",
                    environment={"HTTPS_PROXY": "https://not-used", "KEEP": "yes"},
                    limits=StageLimits(timeout_seconds=2, poll_seconds=0.01),
                )
            self.assertEqual(popen.call_count, 1)
            kwargs = popen.call_args.kwargs
            self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")
            self.assertNotIn("HTTPS_PROXY", kwargs["env"])
            self.assertEqual(kwargs["env"]["KEEP"], "yes")
            self.assertEqual(result["worker"]["stdout"], "pinned-ok")
            self.assertFalse(result["supply_chain"]["network_allowed"])
            self.assertEqual(result["supply_chain"]["entry_ids"], ["shape_stage"])

    def test_tampered_artifact_rejects_before_subprocess(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._sealed_manifest(root)
            (root / "weights" / "shape.bin").write_bytes(b"tampered")
            with mock.patch("stage_supervisor.subprocess.Popen") as popen:
                with self.assertRaisesRegex(PinnedStageWorkerError, "artifact_hash_mismatch"):
                    self._worker().run(
                        [sys.executable, str(root / "tools" / "worker.py")], cwd=root,
                        manifest_path=manifest, local_root=root, expected_scope="job",
                        expected_entry_ids=["shape_stage"], launcher_entry_id="shape_stage",
                        launcher_relative_path="tools/worker.py",
                    )
            popen.assert_not_called()

    def test_missing_expected_entry_and_unpinned_launcher_never_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._sealed_manifest(root)
            with mock.patch("stage_supervisor.subprocess.Popen") as popen:
                with self.assertRaisesRegex(PinnedStageWorkerError, "entry_not_found"):
                    self._worker().run(
                        [sys.executable, str(root / "tools" / "worker.py")], cwd=root,
                        manifest_path=manifest, local_root=root, expected_scope="job",
                        expected_entry_ids=["missing_stage"], launcher_entry_id="missing_stage",
                        launcher_relative_path="tools/worker.py",
                    )
                with self.assertRaisesRegex(PinnedStageWorkerError, "launcher_unpinned"):
                    self._worker().run(
                        [sys.executable, str(root / "tools" / "worker.py")], cwd=root,
                        manifest_path=manifest, local_root=root, expected_scope="job",
                        expected_entry_ids=["shape_stage"], launcher_entry_id="shape_stage",
                        launcher_relative_path="tools/not-approved.py",
                    )
            popen.assert_not_called()

    def test_mutable_or_tampered_manifest_and_network_permission_are_denied_prelaunch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self._sealed_manifest(root)
            command = [sys.executable, str(root / "tools" / "worker.py")]
            with mock.patch("stage_supervisor.subprocess.Popen") as popen:
                manifest.chmod(0o666)
                with self.assertRaisesRegex(PinnedStageWorkerError, "manifest_mutable"):
                    self._worker().run(
                        command, cwd=root, manifest_path=manifest, local_root=root, expected_scope="job",
                        expected_entry_ids=["shape_stage"], launcher_entry_id="shape_stage",
                        launcher_relative_path="tools/worker.py",
                    )
                manifest.chmod(0o600)
                with self.assertRaisesRegex(PinnedStageWorkerError, "network_forbidden"):
                    self._worker().run(
                        command, cwd=root, manifest_path=manifest, local_root=root, expected_scope="job",
                        expected_entry_ids=["shape_stage"], launcher_entry_id="shape_stage",
                        launcher_relative_path="tools/worker.py",
                        limits=StageLimits(network_allowed=True),
                    )
            popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
