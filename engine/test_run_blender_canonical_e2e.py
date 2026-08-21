import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from buffalo_runtime import JobLedger, make_read_only


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_blender_canonical_e2e.py"
SPEC = importlib.util.spec_from_file_location("run_blender_canonical_e2e", SCRIPT_PATH)
runner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(runner)


def _seal(path: Path) -> dict:
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


class BlenderCanonicalE2ETests(unittest.TestCase):
    job_id = "0123456789abcdef"

    def staged_job(self, directory: str):
        jobs = Path(directory) / "jobs"
        ledger = JobLedger(jobs, self.job_id)
        ledger.seal({"kind": "sealed-contract"}, {"kind": "sealed-evidence"})
        inputs = ledger.job_dir / "validation-inputs"
        inputs.mkdir()
        asset = inputs / "asset.glb"
        projection = inputs / "projection-report.json"
        asset.write_bytes(b"immutable-glb")
        projection.write_text(json.dumps({"calibration": {"cameraDirection": [0, 0, 1]}}), encoding="utf-8")
        make_read_only(asset)
        make_read_only(projection)
        ledger.record_stage("validation_inputs", "passed", {
            "glb": _seal(asset), "projection_report": _seal(projection),
        })
        return jobs, ledger, asset, projection

    def test_runs_only_staged_sealed_inputs_and_stays_human_review_only(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, ledger, asset, projection = self.staged_job(directory)
            service = mock.Mock()
            service.run.return_value = {"passed": True, "promotion": "human_review_required", "backend": "real-blender"}
            with mock.patch.object(runner.shutil, "which", return_value="/opt/blender"):
                result = runner.run_e2e(
                    jobs_root=jobs,
                    job_id=self.job_id,
                    service_factory=lambda **kwargs: service,
                )
            self.assertTrue(result["ok"])
            self.assertEqual(result["promotion"], "human_review_required")
            self.assertEqual(result["network"], "disabled_by_blender_validation_service")
            self.assertEqual(service.run.call_args.kwargs["job_dir"], ledger.job_dir)
            self.assertEqual(service.run.call_args.kwargs["glb_path"], asset)
            self.assertEqual(service.run.call_args.kwargs["projection_report_path"], projection)
            self.assertEqual(service.run.call_args.kwargs["output_dir"], ledger.job_dir / "canonical-blender-e2e")

    def test_rejects_unsealed_or_unstaged_inputs_before_blender_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory) / "jobs"
            JobLedger(jobs, self.job_id)
            with mock.patch.object(runner.shutil, "which") as which:
                with self.assertRaisesRegex(runner.CanonicalE2EAdmissionError, "job_not_sealed"):
                    runner.run_e2e(jobs_root=jobs, job_id=self.job_id)
            which.assert_not_called()

    def test_missing_job_does_not_create_a_job_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = Path(directory) / "jobs"
            jobs.mkdir()
            with mock.patch.object(runner.shutil, "which") as which:
                with self.assertRaisesRegex(runner.CanonicalE2EAdmissionError, "unsafe_or_missing_job"):
                    runner.run_e2e(jobs_root=jobs, job_id=self.job_id)
            self.assertFalse((jobs / self.job_id).exists())
            which.assert_not_called()

    def test_rejects_stage_hash_or_mutability_drift_before_blender_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, _, asset, _ = self.staged_job(directory)
            asset.chmod(0o644)
            with mock.patch.object(runner.shutil, "which") as which:
                with self.assertRaisesRegex(runner.CanonicalE2EAdmissionError, "sealed_asset_mismatch"):
                    runner.run_e2e(jobs_root=jobs, job_id=self.job_id)
            which.assert_not_called()

    def test_reports_missing_blender_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, ledger, _, _ = self.staged_job(directory)
            with mock.patch.object(runner.shutil, "which", return_value=None):
                with self.assertRaisesRegex(runner.CanonicalE2EAdmissionError, "blender_unavailable"):
                    runner.run_e2e(jobs_root=jobs, job_id=self.job_id)
            self.assertFalse((ledger.job_dir / "canonical-blender-e2e").exists())

    def test_rejects_result_that_attempts_automatic_promotion(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs, _, _, _ = self.staged_job(directory)
            service = mock.Mock()
            service.run.return_value = {"passed": True, "promotion": "MASTER"}
            with mock.patch.object(runner.shutil, "which", return_value="/opt/blender"):
                with self.assertRaisesRegex(runner.CanonicalE2EAdmissionError, "canonical_validation_not_human_review_only"):
                    runner.run_e2e(jobs_root=jobs, job_id=self.job_id, service_factory=lambda **kwargs: service)


if __name__ == "__main__":
    unittest.main()
