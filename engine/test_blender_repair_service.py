import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import blender_repair_service as service_module
from blender_repair_service import BlenderRepairError, BlenderRepairService, validate_operation_contract
from stage_supervisor import StageWorkerError


def _write_minimal_glb(path):
    document = json.dumps({"asset": {"version": "2.0"}, "nodes": [{}]}).encode("utf-8")
    document += b" " * ((-len(document)) % 4)
    path.write_bytes(
        struct.pack("<III", 0x46546C67, 2, 20 + len(document))
        + struct.pack("<II", len(document), 0x4E4F534A)
        + document
    )


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class BlenderRepairServiceTests(unittest.TestCase):
    CONTRACT = {
        "schema_version": 1,
        "operation": "repair",
        "parameters": {"weld_distance": 0.0001, "recalculate_normals": True},
        "expected": {"minimum_meshes": 1},
    }

    def _paths(self, directory):
        root = Path(directory) / "job"
        root.mkdir()
        source = root / "master.glb"
        _write_minimal_glb(source)
        return root, source, root / "derivatives" / "repaired.glb"

    def _successful_worker(self, command):
        payload = json.loads(command[-1])
        source = Path(payload["source"])
        output = Path(payload["staging_output"])
        report_path = Path(payload["staging_report"])
        _write_minimal_glb(output)
        report = {
            "schema_version": 1,
            "backend": "blender-transactional-repair",
            "expected_report_sha256": payload["expected_report_sha256"],
            "operation_contract_sha256": payload["operation_contract_sha256"],
            "operation": payload["operation_contract"]["operation"],
            "input": {"path": str(source), "sha256": _sha256(source)},
            "output": {"path": str(output), "sha256": _sha256(output)},
            "mesh_stats": {
                "before": {"mesh_count": 1, "vertices": 8, "polygons": 6},
                "after": {"mesh_count": 1, "vertices": 8, "polygons": 6},
            },
        }
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return {"minimum_free_percent": 42.0, "elapsed_seconds": 1.25}

    def test_runs_one_offline_worker_and_commits_a_new_derivative(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, output = self._paths(directory)
            supervisor = mock.Mock()
            supervisor.run.side_effect = lambda command, **_: self._successful_worker(command)
            instance = BlenderRepairService(
                engine_dir=Path(__file__).parent,
                supervisor_factory=lambda snapshot: supervisor,
            )
            with mock.patch.object(service_module.shutil, "which", return_value="/mock/blender"):
                result = instance.run(
                    job_dir=root,
                    source_glb_path=source,
                    output_glb_path=output,
                    operation_contract=self.CONTRACT,
                )
            self.assertTrue(result["passed"])
            self.assertEqual(result["promotion"], "human_review_required")
            self.assertEqual(_sha256(source), result["input"]["sha256"])
            self.assertEqual(_sha256(output), result["output"]["sha256"])
            self.assertTrue(Path(result["expected_report_path"]).is_file())
            self.assertTrue(Path(result["report_path"]).is_file())
            command = supervisor.run.call_args.args[0]
            self.assertEqual(command[:3], ["/mock/blender", "--background", "--factory-startup"])
            self.assertIn("--python-expr", command)
            self.assertFalse(supervisor.run.call_args.kwargs["limits"].network_allowed)

    def test_never_overwrites_an_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, output = self._paths(directory)
            output.parent.mkdir()
            output.write_bytes(b"existing")
            instance = BlenderRepairService(engine_dir=Path(__file__).parent)
            with self.assertRaisesRegex(BlenderRepairError, "repair_output_not_fresh"):
                instance.run(
                    job_dir=root,
                    source_glb_path="master.glb",
                    output_glb_path=output,
                    operation_contract=self.CONTRACT,
                )
            self.assertEqual(output.read_bytes(), b"existing")

    def test_fails_closed_when_blender_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, output = self._paths(directory)
            instance = BlenderRepairService(engine_dir=Path(__file__).parent)
            with mock.patch.object(service_module.shutil, "which", return_value=None):
                with self.assertRaisesRegex(BlenderRepairError, "blender_unavailable"):
                    instance.run(
                        job_dir=root,
                        source_glb_path=source,
                        output_glb_path=output,
                        operation_contract=self.CONTRACT,
                    )

    def test_rejects_foreign_paths_before_blender_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, _ = self._paths(directory)
            foreign = Path(directory) / "foreign.glb"
            instance = BlenderRepairService(engine_dir=Path(__file__).parent)
            with self.assertRaisesRegex(BlenderRepairError, "unmanaged_artifact_path"):
                instance.run(
                    job_dir=root,
                    source_glb_path=source,
                    output_glb_path=foreign,
                    operation_contract=self.CONTRACT,
                )

    def test_rejects_a_worker_report_with_the_wrong_input_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, output = self._paths(directory)
            supervisor = mock.Mock()
            def wrong_hash(command, **_):
                result = self._successful_worker(command)
                report_path = Path(json.loads(command[-1])["staging_report"])
                report = json.loads(report_path.read_text(encoding="utf-8"))
                report["input"]["sha256"] = "0" * 64
                report_path.write_text(json.dumps(report), encoding="utf-8")
                return result
            supervisor.run.side_effect = wrong_hash
            instance = BlenderRepairService(engine_dir=Path(__file__).parent, supervisor_factory=lambda snapshot: supervisor)
            with mock.patch.object(service_module.shutil, "which", return_value="/mock/blender"):
                with self.assertRaisesRegex(BlenderRepairError, "invalid_blender_repair_report"):
                    instance.run(
                        job_dir=root,
                        source_glb_path=source,
                        output_glb_path=output,
                        operation_contract=self.CONTRACT,
                    )
            self.assertFalse(output.exists())

    def test_maps_watchdog_failure_without_committing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root, source, output = self._paths(directory)
            supervisor = mock.Mock()
            supervisor.run.side_effect = StageWorkerError("memory_pressure")
            instance = BlenderRepairService(engine_dir=Path(__file__).parent, supervisor_factory=lambda snapshot: supervisor)
            with mock.patch.object(service_module.shutil, "which", return_value="/mock/blender"):
                with self.assertRaisesRegex(BlenderRepairError, "blender_repair_worker_failed:memory_pressure"):
                    instance.run(
                        job_dir=root,
                        source_glb_path=source,
                        output_glb_path=output,
                        operation_contract=self.CONTRACT,
                    )
            self.assertFalse(output.exists())

    def test_contract_is_strict_and_bounded(self):
        with self.assertRaisesRegex(BlenderRepairError, "invalid_operation_contract"):
            validate_operation_contract({**self.CONTRACT, "unexpected": True})
        retopo = validate_operation_contract({
            "schema_version": 1,
            "operation": "retopologize",
            "parameters": {"decimate_ratio": 0.5},
            "expected": {"minimum_meshes": 1},
        })
        self.assertEqual(retopo["operation"], "retopologize")


if __name__ == "__main__":
    unittest.main()
