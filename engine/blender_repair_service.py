"""Transactional, offline Blender mesh repair stages.

This module deliberately keeps Blender on a narrow, auditable lane.  It never
opens a user-selected path, never overwrites a source or prior derivative, and
does not treat a successful DCC invocation as a quality certificate.  Blender
is invoked in a short-lived, offline-supervised process and its output is
accepted only after the control plane independently verifies the stage report
and GLB container.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from agentic_paint_service import memory_snapshot
from buffalo_runtime import canonical_json, sha256_file
from secure_artifacts import UnsafeAssetError, validate_glb_container
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError


SCHEMA_VERSION = 1
_OPERATIONS = {"repair", "retopologize", "unwrap_uv"}


class BlenderRepairError(RuntimeError):
    """The requested Blender transformation was not safely committed."""


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _managed_path(job_dir: Path, candidate: str | Path, *, required: bool) -> Path:
    root = Path(job_dir).resolve()
    raw = Path(candidate)
    path = (raw if raw.is_absolute() else root / raw).resolve()
    if path == root or root not in path.parents:
        raise BlenderRepairError("unmanaged_artifact_path")
    if required and not path.is_file():
        raise BlenderRepairError("managed_artifact_missing")
    return path


def _finite_number(value: Any, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BlenderRepairError("invalid_operation_contract")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")) or not minimum <= value <= maximum:
        raise BlenderRepairError("invalid_operation_contract")
    return value


def validate_operation_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one explicit, bounded repair operation.

    A compound or implicit operation is intentionally rejected.  Chaining
    transformations requires separately sealed jobs so a failed simplification
    cannot silently become an accepted UV rewrite.
    """
    if not isinstance(contract, Mapping) or set(contract) != {"schema_version", "operation", "parameters", "expected"}:
        raise BlenderRepairError("invalid_operation_contract")
    if contract.get("schema_version") != SCHEMA_VERSION or contract.get("operation") not in _OPERATIONS:
        raise BlenderRepairError("invalid_operation_contract")
    operation = str(contract["operation"])
    parameters = contract.get("parameters")
    expected = contract.get("expected")
    if not isinstance(parameters, Mapping) or not isinstance(expected, Mapping):
        raise BlenderRepairError("invalid_operation_contract")
    if set(expected) != {"minimum_meshes"} or isinstance(expected.get("minimum_meshes"), bool):
        raise BlenderRepairError("invalid_operation_contract")
    minimum_meshes = expected["minimum_meshes"]
    if not isinstance(minimum_meshes, int) or not 1 <= minimum_meshes <= 1024:
        raise BlenderRepairError("invalid_operation_contract")

    if operation == "repair":
        if set(parameters) != {"weld_distance", "recalculate_normals"} or not isinstance(
            parameters.get("recalculate_normals"), bool
        ):
            raise BlenderRepairError("invalid_operation_contract")
        normalized_parameters = {
            "weld_distance": _finite_number(parameters["weld_distance"], minimum=0.0, maximum=0.1),
            "recalculate_normals": parameters["recalculate_normals"],
        }
    elif operation == "retopologize":
        if set(parameters) != {"decimate_ratio"}:
            raise BlenderRepairError("invalid_operation_contract")
        normalized_parameters = {
            "decimate_ratio": _finite_number(parameters["decimate_ratio"], minimum=0.01, maximum=1.0)
        }
    else:
        if set(parameters) != {"angle_limit_degrees", "island_margin"}:
            raise BlenderRepairError("invalid_operation_contract")
        normalized_parameters = {
            "angle_limit_degrees": _finite_number(parameters["angle_limit_degrees"], minimum=1.0, maximum=89.0),
            "island_margin": _finite_number(parameters["island_margin"], minimum=0.0, maximum=0.1),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "parameters": normalized_parameters,
        "expected": {"minimum_meshes": minimum_meshes},
    }


def _write_json_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    """Create evidence exactly once; never use a replace-based JSON write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise BlenderRepairError("repair_output_not_fresh") from exc


def _copy_exclusive(source: Path, destination: Path) -> None:
    try:
        with source.open("rb") as input_handle, destination.open("xb") as output_handle:
            shutil.copyfileobj(input_handle, output_handle, 1024 * 1024)
            output_handle.flush()
            os.fsync(output_handle.fileno())
    except FileExistsError as exc:
        raise BlenderRepairError("repair_output_not_fresh") from exc


# Kept self-contained so the executable worker has no import path dependency.
# Its paths and expected hashes are still verified by this parent process.
_BLENDER_WORKER = r'''
import bpy, hashlib, json, math, pathlib, sys, traceback

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def mesh_stats(objects):
    return {"mesh_count": len(objects), "vertices": sum(len(o.data.vertices) for o in objects), "polygons": sum(len(o.data.polygons) for o in objects)}

payload = json.loads(sys.argv[sys.argv.index("--") + 1])
source, output, report_path = payload["source"], payload["staging_output"], payload["staging_report"]
operation, params = payload["operation_contract"]["operation"], payload["operation_contract"]["parameters"]
try:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=source)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if len(meshes) < payload["operation_contract"]["expected"]["minimum_meshes"]:
        raise RuntimeError("minimum_meshes_not_met")
    before = mesh_stats(meshes)
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        if operation == "repair":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.remove_doubles(threshold=params["weld_distance"])
            if params["recalculate_normals"]:
                bpy.ops.mesh.normals_make_consistent(inside=False)
            bpy.ops.object.mode_set(mode="OBJECT")
        elif operation == "retopologize":
            modifier = obj.modifiers.new(name="BuffaloTransactionalDecimate", type="DECIMATE")
            modifier.ratio = params["decimate_ratio"]
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        elif operation == "unwrap_uv":
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(params["angle_limit_degrees"]), island_margin=params["island_margin"])
            bpy.ops.object.mode_set(mode="OBJECT")
        else:
            raise RuntimeError("unsupported_operation")
    output_path = pathlib.Path(output)
    if output_path.exists():
        raise RuntimeError("staging_output_exists")
    bpy.ops.export_scene.gltf(filepath=output, export_format="GLB", export_yup=True)
    after_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    report = {
        "schema_version": 1,
        "backend": "blender-transactional-repair",
        "expected_report_sha256": payload["expected_report_sha256"],
        "operation_contract_sha256": payload["operation_contract_sha256"],
        "operation": operation,
        "input": {"path": source, "sha256": digest(source)},
        "output": {"path": output, "sha256": digest(output)},
        "mesh_stats": {"before": before, "after": mesh_stats(after_meshes)},
    }
    with open(report_path, "x", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True)
except Exception:
    traceback.print_exc()
    raise
'''


class BlenderRepairService:
    """Execute one bounded mesh transformation into a new job-local GLB."""

    def __init__(
        self,
        engine_dir: str | Path | None = None,
        *,
        blender_executable: str = "blender",
        snapshot: Callable[[], Mapping[str, float | None]] = memory_snapshot,
        supervisor_factory: Callable[[Callable[[], Mapping[str, float | None]]], StageSupervisor] = StageSupervisor,
    ):
        self.engine_dir = Path(engine_dir or Path(__file__).resolve().parent).resolve()
        self.app_root = self.engine_dir.parent
        self.blender_executable = blender_executable
        self.snapshot = snapshot
        self.supervisor_factory = supervisor_factory

    def _resolve_blender(self) -> str:
        executable = shutil.which(self.blender_executable)
        if not executable:
            raise BlenderRepairError("blender_unavailable")
        return executable

    @staticmethod
    def _report_paths(output: Path) -> tuple[Path, Path]:
        return (
            output.with_suffix(".repair-expected.json"),
            output.with_suffix(".repair-report.json"),
        )

    def _validate_worker_report(
        self,
        report_path: Path,
        *,
        expected: Mapping[str, Any],
        expected_sha256: str,
        source: Path,
        staging_output: Path,
    ) -> dict[str, Any]:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or report.get("schema_version") != SCHEMA_VERSION:
                raise ValueError("schema")
            if report.get("backend") != "blender-transactional-repair":
                raise ValueError("backend")
            if report.get("expected_report_sha256") != expected_sha256:
                raise ValueError("expected_hash")
            if report.get("operation_contract_sha256") != expected["operation_contract_sha256"]:
                raise ValueError("contract_hash")
            if report.get("operation") != expected["operation_contract"]["operation"]:
                raise ValueError("operation")
            if Path(report["input"]["path"]).resolve() != source or report["input"]["sha256"] != _sha256(source):
                raise ValueError("input")
            if Path(report["output"]["path"]).resolve() != staging_output or report["output"]["sha256"] != _sha256(staging_output):
                raise ValueError("output")
            stats = report["mesh_stats"]
            if not isinstance(stats, Mapping):
                raise ValueError("mesh_stats")
            for stage in ("before", "after"):
                values = stats[stage]
                if not isinstance(values, Mapping) or any(
                    isinstance(values.get(key), bool) or not isinstance(values.get(key), int) or values[key] < 0
                    for key in ("mesh_count", "vertices", "polygons")
                ):
                    raise ValueError("mesh_stats")
            if stats["before"]["mesh_count"] < expected["operation_contract"]["expected"]["minimum_meshes"]:
                raise ValueError("minimum_meshes")
            return report
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise BlenderRepairError("invalid_blender_repair_report") from exc

    def run(
        self,
        *,
        job_dir: str | Path,
        source_glb_path: str | Path,
        output_glb_path: str | Path,
        operation_contract: Mapping[str, Any],
        limits: StageLimits | None = None,
    ) -> dict[str, Any]:
        root = Path(job_dir).resolve()
        if not root.is_dir():
            raise BlenderRepairError("managed_job_missing")
        source = _managed_path(root, source_glb_path, required=True)
        output = _managed_path(root, output_glb_path, required=False)
        if source.suffix.lower() != ".glb" or output.suffix.lower() != ".glb" or output == source:
            raise BlenderRepairError("invalid_repair_paths")
        if output.exists():
            raise BlenderRepairError("repair_output_not_fresh")
        normalized_contract = validate_operation_contract(operation_contract)
        try:
            input_container = validate_glb_container(source)
        except UnsafeAssetError as exc:
            raise BlenderRepairError("unsafe_glb_container") from exc
        blender = self._resolve_blender()
        expected_path, final_report_path = self._report_paths(output)
        if expected_path.exists() or final_report_path.exists():
            raise BlenderRepairError("repair_output_not_fresh")
        contract_hash = hashlib.sha256(canonical_json(normalized_contract)).hexdigest()
        expected = {
            "schema_version": SCHEMA_VERSION,
            "stage": "blender_transactional_repair",
            "created_at": time.time(),
            "source": {"path": str(source), "sha256": _sha256(source)},
            "output": {"path": str(output)},
            "operation_contract": normalized_contract,
            "operation_contract_sha256": contract_hash,
        }
        _write_json_exclusive(expected_path, expected)
        expected_sha256 = _sha256(expected_path)
        expected_path.chmod(0o400)

        stage_dir = root / ".blender-repair-staging" / uuid.uuid4().hex
        stage_dir.mkdir(parents=True, exist_ok=False)
        staging_output = stage_dir / "output.glb"
        staging_report = stage_dir / "worker-report.json"
        payload = {
            "source": str(source),
            "staging_output": str(staging_output),
            "staging_report": str(staging_report),
            "expected_report_sha256": expected_sha256,
            "operation_contract_sha256": contract_hash,
            "operation_contract": normalized_contract,
        }
        command = [blender, "--background", "--factory-startup", "--python-expr", _BLENDER_WORKER, "--", json.dumps(payload, sort_keys=True)]
        try:
            watchdog = self.supervisor_factory(self.snapshot).run(
                command,
                cwd=self.app_root,
                limits=limits or StageLimits(
                    timeout_seconds=900,
                    minimum_free_percent=10,
                    maximum_swap_growth_mb=1536,
                    network_allowed=False,
                ),
            )
        except StageWorkerError as exc:
            raise BlenderRepairError(f"blender_repair_worker_failed:{exc.reason_code}") from exc
        if not staging_output.is_file() or not staging_report.is_file():
            raise BlenderRepairError("blender_repair_artifact_missing")
        report = self._validate_worker_report(
            staging_report,
            expected=expected,
            expected_sha256=expected_sha256,
            source=source,
            staging_output=staging_output.resolve(),
        )
        try:
            output_container = validate_glb_container(staging_output)
        except UnsafeAssetError as exc:
            raise BlenderRepairError("unsafe_repair_output") from exc
        output.parent.mkdir(parents=True, exist_ok=True)
        _copy_exclusive(staging_output, output)
        final_report = {
            "schema_version": SCHEMA_VERSION,
            "expected_report_path": str(expected_path),
            "expected_report_sha256": expected_sha256,
            "worker_report": report,
            "committed_output": {"path": str(output), "sha256": _sha256(output)},
            "output_container": output_container,
            "promotion": "human_review_required",
        }
        _write_json_exclusive(final_report_path, final_report)
        output.chmod(0o400)
        final_report_path.chmod(0o400)
        return {
            "passed": True,
            "backend": "blender-transactional-repair",
            "operation": normalized_contract["operation"],
            "input": {"path": str(source), "sha256": _sha256(source), "container": input_container},
            "output": {"path": str(output), "sha256": _sha256(output), "container": output_container},
            "expected_report_path": str(expected_path),
            "report_path": str(final_report_path),
            "memory_watchdog": {
                "minimum_free_percent": watchdog.get("minimum_free_percent"),
                "elapsed_seconds": watchdog.get("elapsed_seconds"),
            },
            "promotion": "human_review_required",
        }
