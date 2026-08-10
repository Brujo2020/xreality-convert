"""Fail-closed, offline Blender canonical-render validation.

The service deliberately does not certify an asset as a master.  It only
produces independent canonical-render evidence in a short-lived Blender
process.  The caller (normally the control plane) remains responsible for
promotion and for preserving the returned report as a stage artifact.
"""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Callable, Mapping

from agentic_paint_service import memory_snapshot
from secure_artifacts import UnsafeAssetError, validate_glb_container
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError


class BlenderValidationError(RuntimeError):
    """The independent DCC evidence lane was not safely produced."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _managed_path(job_dir: Path, candidate: str | Path, *, required: bool) -> Path:
    root = Path(job_dir).resolve()
    raw = Path(candidate)
    path = (raw if raw.is_absolute() else root / raw).resolve()
    if path == root or root not in path.parents:
        raise BlenderValidationError("unmanaged_artifact_path")
    if required and not path.is_file():
        raise BlenderValidationError("managed_artifact_missing")
    return path


def _projection_is_usable(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        direction = payload["calibration"]["cameraDirection"]
        if not isinstance(direction, list) or len(direction) != 3:
            raise ValueError("camera_direction")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in direction):
            raise ValueError("camera_direction")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise BlenderValidationError("invalid_projection_report") from exc


class BlenderCanonicalValidationService:
    """Run the project's canonical Blender evidence renderer in isolation."""

    EXPECTED_RENDER_NAMES = (
        "blender-front.png",
        "blender-quarter-left.png",
        "blender-quarter-right.png",
    )

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
        self.worker_script = self.engine_dir / "render_glb_reference_validation.py"
        self.blender_executable = blender_executable
        self.snapshot = snapshot
        self.supervisor_factory = supervisor_factory

    def _resolve_blender(self) -> str:
        executable = shutil.which(self.blender_executable)
        if not executable:
            raise BlenderValidationError("blender_unavailable")
        return executable

    def _validate_worker_report(
        self,
        *,
        report_path: Path,
        glb_path: Path,
        projection_report_path: Path,
        output_dir: Path,
    ) -> dict[str, Any]:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or report.get("schemaVersion") != 1:
                raise ValueError("schema")
            if not isinstance(report.get("renderer"), str) or not report["renderer"]:
                raise ValueError("renderer")
            if report.get("lighting") != "embedded_base_color_only" or report.get("hdriInvoked") is not False:
                raise ValueError("lighting")
            if Path(report["glb"]).resolve() != glb_path.resolve():
                raise ValueError("glb_path")
            if report.get("glbSha256") != _sha256(glb_path):
                raise ValueError("glb_hash")
            if Path(report["projectionReport"]).resolve() != projection_report_path.resolve():
                raise ValueError("projection_path")
            if report.get("projectionReportSha256") != _sha256(projection_report_path):
                raise ValueError("projection_hash")
            renders = report.get("renders")
            if not isinstance(renders, list) or len(renders) != len(self.EXPECTED_RENDER_NAMES):
                raise ValueError("renders")
            expected = {output_dir / name for name in self.EXPECTED_RENDER_NAMES}
            observed = set()
            for render in renders:
                if not isinstance(render, dict):
                    raise ValueError("render_item")
                render_path = Path(render["path"]).resolve()
                if render_path not in expected or not render_path.is_file():
                    raise ValueError("render_path")
                if render.get("sha256") != _sha256(render_path):
                    raise ValueError("render_hash")
                observed.add(render_path)
            if observed != expected:
                raise ValueError("render_set")
            return report
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise BlenderValidationError("invalid_blender_render_report") from exc

    def run(
        self,
        *,
        job_dir: str | Path,
        glb_path: str | Path,
        projection_report_path: str | Path,
        output_dir: str | Path,
        limits: StageLimits | None = None,
    ) -> dict[str, Any]:
        """Emit canonical Blender evidence only for sealed job-local artifacts.

        Existing reports are rejected rather than reused: a pass must be tied
        to this subprocess invocation, not to stale evidence from an earlier
        execution or a foreign job.
        """
        root = Path(job_dir).resolve()
        if not root.is_dir():
            raise BlenderValidationError("managed_job_missing")
        glb = _managed_path(root, glb_path, required=True)
        projection = _managed_path(root, projection_report_path, required=True)
        output = _managed_path(root, output_dir, required=False)
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise BlenderValidationError("blender_output_not_fresh")
        if not self.worker_script.is_file():
            raise BlenderValidationError("blender_worker_script_missing")
        try:
            container = validate_glb_container(glb)
        except UnsafeAssetError as exc:
            raise BlenderValidationError("unsafe_glb_container") from exc
        _projection_is_usable(projection)
        blender = self._resolve_blender()
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "blender-runtime-report.json"
        command = [
            blender,
            "--background",
            "--factory-startup",
            "--python",
            str(self.worker_script),
            "--",
            "--glb",
            str(glb),
            "--projection-report",
            str(projection),
            "--output-dir",
            str(output),
        ]
        try:
            watchdog = self.supervisor_factory(self.snapshot).run(
                command,
                cwd=self.app_root,
                limits=limits or StageLimits(
                    timeout_seconds=600,
                    minimum_free_percent=10,
                    maximum_swap_growth_mb=1024,
                    network_allowed=False,
                ),
            )
        except StageWorkerError as exc:
            raise BlenderValidationError(f"blender_worker_failed:{exc.reason_code}") from exc
        if not report_path.is_file():
            raise BlenderValidationError("blender_render_report_missing")
        report = self._validate_worker_report(
            report_path=report_path,
            glb_path=glb,
            projection_report_path=projection,
            output_dir=output,
        )
        return {
            "passed": True,
            "backend": "blender-canonical-validation",
            "glb_container": container,
            "render_report_path": str(report_path),
            "render_report": report,
            "memory_watchdog": {
                "minimum_free_percent": watchdog.get("minimum_free_percent"),
                "elapsed_seconds": watchdog.get("elapsed_seconds"),
            },
            "promotion": "human_review_required",
        }
