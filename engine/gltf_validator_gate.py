"""Independent, local glTF Validator gate for sealed Buffalo job artifacts.

This gate is deliberately narrow: it only accepts the Khronos-compatible
``gltf-validator`` CLI when it is installed locally.  It never substitutes a
JSON parser, a Blender import, or an in-process heuristic for the validator.
An absent executable is therefore an explicit ``not_measured`` rejection,
never a pass.  A passing invocation produces a hash-bound, read-only report
and a second verifier record so later promotion code can re-check precisely
what was measured.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Mapping

from agentic_paint_service import memory_snapshot
from buffalo_runtime import canonical_json, make_read_only, safe_job_path, sha256_file
from secure_artifacts import UnsafeAssetError, validate_glb_container
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError


GLTF_VALIDATOR_GATE_SCHEMA_VERSION = 1
_REPORT_NAME = "gltf-validator-report.json"
_VERIFIER_NAME = "gltf-validator-verifier.json"
_RAW_NAME = "gltf-validator-raw.json"


class GlTFValidatorGateError(RuntimeError):
    """The independent validator lane could not safely produce evidence."""


def _sha256(path: Path) -> str:
    return "sha256:" + sha256_file(path)


def _managed_file(root: Path, candidate: str | Path) -> Path:
    raw = Path(candidate)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        path = safe_job_path(root, raw)
    if path == root or root not in path.parents or path.is_symlink() or not path.is_file():
        raise GlTFValidatorGateError("unmanaged_glb_path")
    return path


def _managed_empty_output(root: Path, candidate: str | Path) -> Path:
    raw = Path(candidate)
    if raw.is_absolute():
        path = raw.resolve()
    else:
        path = safe_job_path(root, raw)
    if path == root or root not in path.parents or path.is_symlink():
        raise GlTFValidatorGateError("unmanaged_validator_output")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise GlTFValidatorGateError("validator_output_not_fresh")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_new_read_only(path: Path, value: Mapping[str, Any]) -> None:
    """Exclusive write prevents a worker from replacing sealed evidence."""
    encoded = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise GlTFValidatorGateError("validator_evidence_already_exists") from exc
    make_read_only(path)


def _nonempty_text(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise GlTFValidatorGateError(reason)
    return value.strip()


def _validator_passed(raw_path: Path) -> dict[str, Any]:
    """Accept only the CLI's structured zero-error result, not its exit code."""
    try:
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlTFValidatorGateError("validator_raw_report_missing_or_invalid") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("issues"), dict):
        raise GlTFValidatorGateError("validator_raw_report_contract_invalid")
    issues = raw["issues"]
    errors = issues.get("numErrors")
    warnings = issues.get("numWarnings", 0)
    if isinstance(errors, bool) or not isinstance(errors, int) or errors < 0:
        raise GlTFValidatorGateError("validator_error_count_invalid")
    if isinstance(warnings, bool) or not isinstance(warnings, int) or warnings < 0:
        raise GlTFValidatorGateError("validator_warning_count_invalid")
    if errors != 0:
        raise GlTFValidatorGateError("gltf_validator_rejected_asset")
    return {"num_errors": errors, "num_warnings": warnings}


def _record_id(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


class GlTFValidatorGate:
    """Execute installed glTF Validator in a short-lived offline subprocess."""

    def __init__(
        self,
        engine_dir: str | Path | None = None,
        *,
        validator_executable: str = "gltf-validator",
        snapshot: Callable[[], Mapping[str, float | None]] = memory_snapshot,
        supervisor_factory: Callable[[Callable[[], Mapping[str, float | None]]], StageSupervisor] = StageSupervisor,
    ):
        self.engine_dir = Path(engine_dir or Path(__file__).resolve().parent).resolve()
        self.app_root = self.engine_dir.parent
        self.validator_executable = validator_executable
        self.snapshot = snapshot
        self.supervisor_factory = supervisor_factory

    def _resolve(self) -> str | None:
        return shutil.which(self.validator_executable)

    def _run(self, command: list[str], limits: StageLimits) -> dict[str, Any]:
        try:
            return self.supervisor_factory(self.snapshot).run(
                command, cwd=self.app_root, limits=limits,
            )
        except StageWorkerError as exc:
            raise GlTFValidatorGateError(f"gltf_validator_worker_failed:{exc.reason_code}") from exc

    def run(
        self,
        *,
        job_dir: str | Path,
        glb_path: str | Path,
        output_dir: str | Path = "gltf-validator",
        limits: StageLimits | None = None,
    ) -> dict[str, Any]:
        """Return sealed validator evidence, or an explicit unmeasured reject.

        The CLI contract is the documented local ``gltf-validator -i FILE -o
        FILE`` JSON mode.  Its raw report must claim exactly zero errors.  A
        nonzero exit, invalid JSON, stale output, or absent binary cannot be
        converted into a substitute structural pass.
        """
        root = Path(job_dir).resolve()
        if not root.is_dir() or root.is_symlink():
            raise GlTFValidatorGateError("managed_job_missing")
        glb = _managed_file(root, glb_path)
        try:
            container = validate_glb_container(glb)
        except UnsafeAssetError as exc:
            raise GlTFValidatorGateError("unsafe_glb_container") from exc
        validator = self._resolve()
        if not validator:
            return {
                "passed": False,
                "status": "not_measured",
                "reason": "gltf_validator_unavailable",
                "promotion": "rejected",
                "artifact": {"path": glb.relative_to(root).as_posix(), "sha256": _sha256(glb)},
            }
        output = _managed_empty_output(root, output_dir)
        raw_path = output / _RAW_NAME
        report_path = output / _REPORT_NAME
        verifier_path = output / _VERIFIER_NAME
        stage_limits = limits or StageLimits(
            timeout_seconds=120,
            minimum_free_percent=10,
            maximum_swap_growth_mb=512,
            network_allowed=False,
        )
        revision_command = [validator, "--version"]
        revision_run = self._run(revision_command, stage_limits)
        revision = _nonempty_text(revision_run.get("stdout"), "gltf_validator_revision_missing")
        command = [validator, "-i", str(glb), "-o", str(raw_path)]
        worker = self._run(command, stage_limits)
        issues = _validator_passed(raw_path)
        artifact = {
            "path": glb.relative_to(root).as_posix(),
            "sha256": _sha256(glb),
            "bytes": glb.stat().st_size,
        }
        raw_descriptor = {"path": _RAW_NAME, "sha256": _sha256(raw_path), "bytes": raw_path.stat().st_size}
        report = {
            "schema_version": GLTF_VALIDATOR_GATE_SCHEMA_VERSION,
            "kind": "xreality.gltf_validator_gate",
            "producer": "gltf-validator-cli",
            "status": "pass",
            "measurement": {"executed": True, "exit_code": 0},
            "artifact": artifact,
            "container": container,
            "validator": {
                "executable": validator,
                "revision": revision,
                "revision_command": revision_command,
                "command": command,
                "raw_report": raw_descriptor,
            },
            "issues": issues,
            "watchdog": {
                "elapsed_seconds": worker.get("elapsed_seconds"),
                "minimum_free_percent": worker.get("minimum_free_percent"),
                "network_allowed": False,
            },
            "promotion": "human_review_required",
        }
        report["record_id"] = _record_id(report)
        _write_new_read_only(report_path, report)
        make_read_only(raw_path)
        verifier = {
            "schema_version": GLTF_VALIDATOR_GATE_SCHEMA_VERSION,
            "kind": "xreality.gltf_validator_gate_verifier",
            "report_path": _REPORT_NAME,
            "report_sha256": _sha256(report_path),
            "artifact": {"path": artifact["path"], "sha256": artifact["sha256"]},
            "raw_report": raw_descriptor,
        }
        verifier["record_id"] = _record_id(verifier)
        _write_new_read_only(verifier_path, verifier)
        return {
            "passed": True,
            "status": "pass",
            "promotion": "human_review_required",
            "report_path": report_path.relative_to(root).as_posix(),
            "verifier_path": verifier_path.relative_to(root).as_posix(),
            "report": report,
        }


def verify_gltf_validator_evidence(*, job_dir: str | Path, report_path: str, verifier_path: str) -> dict[str, Any]:
    """Re-check a sealed report against its exact job-local GLB and raw JSON."""
    root = Path(job_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise GlTFValidatorGateError("managed_job_missing")
    report_file = _managed_file(root, report_path)
    verifier_file = _managed_file(root, verifier_path)
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
        verifier = json.loads(verifier_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GlTFValidatorGateError("validator_evidence_invalid") from exc
    if not isinstance(report, dict) or not isinstance(verifier, dict):
        raise GlTFValidatorGateError("validator_evidence_invalid")
    if report.get("schema_version") != GLTF_VALIDATOR_GATE_SCHEMA_VERSION or report.get("kind") != "xreality.gltf_validator_gate":
        raise GlTFValidatorGateError("validator_report_schema_invalid")
    if report.get("status") != "pass" or report.get("record_id") != _record_id({k: v for k, v in report.items() if k != "record_id"}):
        raise GlTFValidatorGateError("validator_report_integrity_invalid")
    if verifier.get("kind") != "xreality.gltf_validator_gate_verifier" or verifier.get("report_sha256") != _sha256(report_file):
        raise GlTFValidatorGateError("validator_verifier_integrity_invalid")
    artifact = report.get("artifact")
    raw = report.get("validator", {}).get("raw_report") if isinstance(report.get("validator"), dict) else None
    if not isinstance(artifact, dict) or not isinstance(raw, dict):
        raise GlTFValidatorGateError("validator_evidence_invalid")
    glb = _managed_file(root, artifact.get("path", ""))
    raw_file = _managed_file(root, Path(report_path).parent / raw.get("path", ""))
    if artifact.get("sha256") != _sha256(glb) or raw.get("sha256") != _sha256(raw_file):
        raise GlTFValidatorGateError("validator_evidence_hash_mismatch")
    _validator_passed(raw_file)
    if verifier.get("artifact") != {"path": artifact["path"], "sha256": artifact["sha256"]} or verifier.get("raw_report") != raw:
        raise GlTFValidatorGateError("validator_verifier_binding_invalid")
    if verifier.get("record_id") != _record_id({k: v for k, v in verifier.items() if k != "record_id"}):
        raise GlTFValidatorGateError("validator_verifier_integrity_invalid")
    return {"passed": True, "status": "pass", "report": report, "verifier": verifier}
