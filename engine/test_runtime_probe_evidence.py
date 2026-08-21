import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from runtime_probe_evidence import RuntimeProbeEvidenceError, bind_runtime_probe_evidence, verify_runtime_probe_evidence


REVISION = "sha256:" + "c" * 64
COMMAND = ["local-web-probe", "--target", "web", "--headless"]


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def command_sha256(command) -> str:
    source = json.dumps(command, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(source).hexdigest()


def write_report(job: Path, *, target="web", status="pass", artifact_name="asset.glb", command=COMMAND, revision=REVISION,
                 include_frames=True, include_logs=True):
    artifact = job / artifact_name
    frame = job / "probe" / "frame-0001.png"
    log = job / "probe" / "runner.log"
    frame.parent.mkdir(parents=True, exist_ok=True)
    frame.write_bytes(b"measured frame bytes")
    log.write_text("real runner output\n", encoding="utf-8")
    report = {
        "schema_version": 1,
        "status": status,
        "target": target,
        "measurement": {"kind": "external_runtime_probe", "executed": True, "exit_code": 0},
        "runner": {"producer": "local-web-probe", "execution_id": "run-0001", "command": command,
                   "command_sha256": command_sha256(command), "revision": revision},
        "artifact": {"path": artifact_name, "sha256": sha256(artifact)},
        "evidence": {
            "frames": [{"path": "probe/frame-0001.png", "sha256": sha256(frame)}] if include_frames else [],
            "logs": [{"path": "probe/runner.log", "sha256": sha256(log)}] if include_logs else [],
        },
    }
    report_path = job / "probe" / "probe-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report_path, frame, log


class RuntimeProbeEvidenceTests(unittest.TestCase):
    def test_binds_external_measured_report_and_verifies_immutable_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            job.mkdir()
            (job / "asset.glb").write_bytes(b"glb payload")
            report, _, _ = write_report(job)
            bound = bind_runtime_probe_evidence(
                job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                expected_runner_command=COMMAND, expected_runner_revision=REVISION,
            )
            self.assertEqual(bound["status"], "measured_pass")
            self.assertEqual(bound["promotion"], "human_review_required")
            self.assertTrue(Path(bound["path"]).is_file())
            self.assertFalse(Path(bound["path"]).stat().st_mode & 0o200)
            verified = verify_runtime_probe_evidence(job_dir=job, record_path=Path(bound["path"]).relative_to(job.resolve()).as_posix())
            self.assertEqual(verified["record_id"], bound["record_id"])

    def test_rejects_absent_report_and_never_synthesizes_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "asset.glb").write_bytes(b"glb payload")
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "runtime_probe_report_missing"):
                bind_runtime_probe_evidence(
                    job_dir=job, artifact_path="asset.glb", probe_report_path="no-report.json", target="web",
                    expected_runner_command=COMMAND, expected_runner_revision=REVISION,
                )
            self.assertFalse((job / "runtime-probe-evidence").exists())

    def test_rejects_unmeasured_or_incomplete_external_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "asset.glb").write_bytes(b"glb payload")
            report, _, _ = write_report(job, include_frames=False)
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "runtime_probe_frames_missing"):
                bind_runtime_probe_evidence(
                    job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                    expected_runner_command=COMMAND, expected_runner_revision=REVISION,
                )
            report, _, _ = write_report(job, status="not_measured")
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "runtime_probe_not_passed"):
                bind_runtime_probe_evidence(
                    job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                    expected_runner_command=COMMAND, expected_runner_revision=REVISION,
                )

    def test_rejects_command_revision_hash_and_foreign_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory) / "job"
            foreign = Path(directory) / "foreign"
            job.mkdir()
            foreign.mkdir()
            (job / "asset.glb").write_bytes(b"glb payload")
            report, _, _ = write_report(job, revision="sha256:" + "d" * 64)
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "runtime_probe_revision_mismatch"):
                bind_runtime_probe_evidence(
                    job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                    expected_runner_command=COMMAND, expected_runner_revision=REVISION,
                )
            report, _, _ = write_report(job)
            payload = json.loads(report.read_text(encoding="utf-8"))
            external = foreign / "frame.png"
            external.write_bytes(b"foreign")
            payload["evidence"]["frames"] = [{"path": "../foreign/frame.png", "sha256": sha256(external)}]
            report.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "unsafe_frame_evidence_path"):
                bind_runtime_probe_evidence(
                    job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                    expected_runner_command=COMMAND, expected_runner_revision=REVISION,
                )

    def test_verification_detects_post_bind_frame_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "asset.glb").write_bytes(b"glb payload")
            report, frame, _ = write_report(job)
            bound = bind_runtime_probe_evidence(
                job_dir=job, artifact_path="asset.glb", probe_report_path="probe/probe-report.json", target="web",
                expected_runner_command=COMMAND, expected_runner_revision=REVISION,
            )
            frame.write_bytes(b"tampered")
            with self.assertRaisesRegex(RuntimeProbeEvidenceError, "frame_evidence_hash_mismatch"):
                verify_runtime_probe_evidence(job_dir=job, record_path=Path(bound["path"]).relative_to(job.resolve()).as_posix())


if __name__ == "__main__":
    unittest.main()
