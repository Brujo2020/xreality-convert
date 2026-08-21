import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gltf_validator_gate as gate_module
from gltf_validator_gate import GlTFValidatorGate, GlTFValidatorGateError, verify_gltf_validator_evidence


def _write_glb(path):
    document = json.dumps({"asset": {"version": "2.0"}, "nodes": [{}]}).encode("utf-8")
    document += b" " * ((-len(document)) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 20 + len(document)) + struct.pack("<II", len(document), 0x4E4F534A) + document)


class GlTFValidatorGateTests(unittest.TestCase):
    def _job(self, directory):
        root = Path(directory) / "job"
        root.mkdir()
        asset = root / "asset.glb"
        _write_glb(asset)
        return root, asset

    def test_runs_offline_cli_and_seals_hash_bound_report_and_verifier(self):
        with tempfile.TemporaryDirectory() as directory:
            root, asset = self._job(directory)
            supervisor = mock.Mock()
            instance = GlTFValidatorGate(
                engine_dir=Path(__file__).parent,
                snapshot=lambda: {"free_percent": 50.0, "swap_used_mb": 0.0},
                supervisor_factory=lambda snapshot: supervisor,
            )
            def worker(command, **kwargs):
                if command[-1] == "--version":
                    return {"stdout": "gltf-validator 2.0.0\n", "elapsed_seconds": 0.01, "minimum_free_percent": 40.0}
                raw = Path(command[-1])
                raw.write_text(json.dumps({"issues": {"numErrors": 0, "numWarnings": 2}}), encoding="utf-8")
                return {"stdout": "", "elapsed_seconds": 0.02, "minimum_free_percent": 39.0}
            supervisor.run.side_effect = worker
            with mock.patch.object(gate_module.shutil, "which", return_value="/mock/gltf-validator"):
                result = instance.run(job_dir=root, glb_path="asset.glb")
            self.assertTrue(result["passed"])
            report_path = root / result["report_path"]
            verifier_path = root / result["verifier_path"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["artifact"]["sha256"], "sha256:" + hashlib.sha256(asset.read_bytes()).hexdigest())
            self.assertEqual(report["validator"]["revision"], "gltf-validator 2.0.0")
            self.assertEqual(report["validator"]["command"][:2], ["/mock/gltf-validator", "-i"])
            self.assertFalse(supervisor.run.call_args.kwargs["limits"].network_allowed)
            self.assertEqual((report_path.stat().st_mode & 0o222), 0)
            self.assertEqual((verifier_path.stat().st_mode & 0o222), 0)
            self.assertTrue(verify_gltf_validator_evidence(
                job_dir=root, report_path=result["report_path"], verifier_path=result["verifier_path"],
            )["passed"])

    def test_missing_cli_is_explicit_unmeasured_rejection_without_substitute(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._job(directory)
            instance = GlTFValidatorGate(engine_dir=Path(__file__).parent)
            with mock.patch.object(gate_module.shutil, "which", return_value=None):
                result = instance.run(job_dir=root, glb_path="asset.glb")
            self.assertEqual(result["status"], "not_measured")
            self.assertFalse(result["passed"])
            self.assertEqual(result["reason"], "gltf_validator_unavailable")
            self.assertFalse((root / "gltf-validator").exists())

    def test_rejects_raw_validator_errors_and_never_writes_pass_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._job(directory)
            supervisor = mock.Mock()
            instance = GlTFValidatorGate(engine_dir=Path(__file__).parent, supervisor_factory=lambda snapshot: supervisor)
            def worker(command, **kwargs):
                if command[-1] == "--version":
                    return {"stdout": "v1"}
                Path(command[-1]).write_text(json.dumps({"issues": {"numErrors": 1, "numWarnings": 0}}), encoding="utf-8")
                return {"stdout": ""}
            supervisor.run.side_effect = worker
            with mock.patch.object(gate_module.shutil, "which", return_value="/mock/gltf-validator"):
                with self.assertRaisesRegex(GlTFValidatorGateError, "gltf_validator_rejected_asset"):
                    instance.run(job_dir=root, glb_path="asset.glb")
            self.assertFalse((root / "gltf-validator" / "gltf-validator-report.json").exists())

    def test_verifier_detects_hash_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = self._job(directory)
            supervisor = mock.Mock()
            instance = GlTFValidatorGate(engine_dir=Path(__file__).parent, supervisor_factory=lambda snapshot: supervisor)
            def worker(command, **kwargs):
                if command[-1] == "--version":
                    return {"stdout": "v1"}
                Path(command[-1]).write_text(json.dumps({"issues": {"numErrors": 0, "numWarnings": 0}}), encoding="utf-8")
                return {"stdout": ""}
            supervisor.run.side_effect = worker
            with mock.patch.object(gate_module.shutil, "which", return_value="/mock/gltf-validator"):
                result = instance.run(job_dir=root, glb_path="asset.glb")
            raw = root / "gltf-validator" / "gltf-validator-raw.json"
            raw.chmod(0o600)
            raw.write_text(json.dumps({"issues": {"numErrors": 0, "numWarnings": 99}}), encoding="utf-8")
            with self.assertRaisesRegex(GlTFValidatorGateError, "validator_evidence_hash_mismatch"):
                verify_gltf_validator_evidence(job_dir=root, report_path=result["report_path"], verifier_path=result["verifier_path"])


if __name__ == "__main__":
    unittest.main()
