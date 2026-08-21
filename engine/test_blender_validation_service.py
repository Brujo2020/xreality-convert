import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import blender_validation_service as service_module
from blender_validation_service import BlenderCanonicalValidationService, BlenderValidationError


def _write_minimal_glb(path):
    document = json.dumps({"asset": {"version": "2.0"}, "nodes": [{}]}).encode("utf-8")
    document += b" " * ((-len(document)) % 4)
    path.write_bytes(struct.pack("<III", 0x46546C67, 2, 20 + len(document)) + struct.pack("<II", len(document), 0x4E4F534A) + document)


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_projection(path):
    path.write_text(json.dumps({"calibration": {"cameraDirection": [0.0, 0.0, 1.0]}}), encoding="utf-8")


class BlenderCanonicalValidationServiceTests(unittest.TestCase):
    def _paths(self, directory):
        root = Path(directory) / "job"
        root.mkdir()
        glb = root / "mesh.glb"
        projection = root / "projection.json"
        output = root / "blender-renders"
        _write_minimal_glb(glb)
        _write_projection(projection)
        return root, glb, projection, output

    def _write_worker_evidence(self, glb, projection, output):
        output.mkdir(exist_ok=True)
        renders = []
        for name in BlenderCanonicalValidationService.EXPECTED_RENDER_NAMES:
            image = output / name
            image.write_bytes(name.encode("ascii"))
            renders.append({"path": str(image), "sha256": _sha256(image)})
        report = {
            "schemaVersion": 1,
            "renderer": "Blender 4.5",
            "lighting": "embedded_base_color_only",
            "hdriInvoked": False,
            "glb": str(glb),
            "glbSha256": _sha256(glb),
            "projectionReport": str(projection),
            "projectionReportSha256": _sha256(projection),
            "renders": renders,
        }
        (output / "blender-runtime-report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    def test_runs_offline_blender_worker_and_accepts_expected_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root, glb, projection, output = self._paths(directory)
            supervisor = mock.Mock()
            supervisor.run.return_value = {"minimum_free_percent": 33.0, "elapsed_seconds": 2.5}
            instance = BlenderCanonicalValidationService(
                engine_dir=Path(__file__).parent,
                snapshot=lambda: {"free_percent": 50.0, "swap_used_mb": 0.0},
                supervisor_factory=lambda snapshot: supervisor,
            )
            with mock.patch.object(service_module.shutil, "which", return_value="/mock/blender"):
                # The mock worker simulates Blender's independent evidence;
                # no Blender binary or render is invoked by this unit test.
                def simulate_worker(*args, **kwargs):
                    self._write_worker_evidence(glb, projection, output)
                    return {"minimum_free_percent": 33.0, "elapsed_seconds": 2.5}

                supervisor.run.side_effect = simulate_worker
                result = instance.run(
                    job_dir=root, glb_path=glb, projection_report_path=projection, output_dir=output
                )
            self.assertTrue(result["passed"])
            self.assertEqual(result["promotion"], "human_review_required")
            command = supervisor.run.call_args.args[0]
            self.assertEqual(command[:3], ["/mock/blender", "--background", "--factory-startup"])
            self.assertIn("--python", command)
            self.assertFalse(supervisor.run.call_args.kwargs["limits"].network_allowed)

    def test_fails_closed_when_blender_is_not_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root, glb, projection, output = self._paths(directory)
            instance = BlenderCanonicalValidationService(engine_dir=Path(__file__).parent)
            with mock.patch.object(service_module.shutil, "which", return_value=None):
                with self.assertRaisesRegex(BlenderValidationError, "blender_unavailable"):
                    instance.run(job_dir=root, glb_path=glb, projection_report_path=projection, output_dir=output)

    def test_rejects_unmanaged_glb_before_launching_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, projection, output = self._paths(directory)
            foreign = Path(directory) / "foreign.glb"
            _write_minimal_glb(foreign)
            instance = BlenderCanonicalValidationService(engine_dir=Path(__file__).parent)
            with self.assertRaisesRegex(BlenderValidationError, "unmanaged_artifact_path"):
                instance.run(job_dir=root, glb_path=foreign, projection_report_path=projection, output_dir=output)

    def test_rejects_report_with_foreign_render_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root, glb, projection, output = self._paths(directory)
            supervisor = mock.Mock()
            instance = BlenderCanonicalValidationService(
                engine_dir=Path(__file__).parent,
                supervisor_factory=lambda snapshot: supervisor,
            )
            foreign = Path(directory) / "foreign.png"
            foreign.write_bytes(b"not-a-render")
            with mock.patch.object(service_module.shutil, "which", return_value="/mock/blender"):
                def simulate_bad_worker(*args, **kwargs):
                    report = self._write_worker_evidence(glb, projection, output)
                    report["renders"][0] = {"path": str(foreign), "sha256": _sha256(foreign)}
                    (output / "blender-runtime-report.json").write_text(json.dumps(report), encoding="utf-8")
                    return {"minimum_free_percent": 30.0, "elapsed_seconds": 1.0}

                supervisor.run.side_effect = simulate_bad_worker
                with self.assertRaisesRegex(BlenderValidationError, "invalid_blender_render_report"):
                    instance.run(
                        job_dir=root, glb_path=glb, projection_report_path=projection, output_dir=output
                    )


if __name__ == "__main__":
    unittest.main()
