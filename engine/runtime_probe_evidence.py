"""Bind independently executed runtime probes to a sealed local job.

``runtime_certification`` proves a conservative GLB structural profile.  It
does not prove that a browser, headset, phone, or USDZ consumer actually
opened the asset.  This module deliberately does *not* run or emulate such a
consumer.  Instead it accepts an externally-produced, measured probe report
only when the execution identity and every claimed artifact are verifiable
inside the same job directory.

The resulting record is append-only evidence, not an automatic master
promotion.  Missing, stale, foreign, or self-described evidence fails closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from buffalo_runtime import ContractError, atomic_write_json, canonical_json, make_read_only, safe_job_path, sha256_file


RUNTIME_PROBE_SCHEMA_VERSION = 1
SUPPORTED_TARGETS = frozenset({"web", "xr", "mobile", "usdz"})
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class RuntimeProbeEvidenceError(ValueError):
    """A claimed runtime/device probe cannot become durable evidence."""


def _hash(value: Any, reason: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value.lower()) is None:
        raise RuntimeProbeEvidenceError(reason)
    return value.lower()


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _root(job_dir: str | Path) -> Path:
    root = Path(job_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise RuntimeProbeEvidenceError("managed_job_missing")
    return root


def _relative_file(root: Path, relative: Any, *, missing_reason: str, unsafe_reason: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise RuntimeProbeEvidenceError(unsafe_reason)
    try:
        path = safe_job_path(root, relative)
    except ContractError as exc:
        raise RuntimeProbeEvidenceError(unsafe_reason) from exc
    # Resolve only after rejecting symlinks.  A symlink can point at a
    # job-local file today and be retargeted after evidence is written.
    if path.is_symlink() or not path.is_file():
        raise RuntimeProbeEvidenceError(missing_reason)
    resolved = path.resolve()
    if root not in resolved.parents:
        raise RuntimeProbeEvidenceError(unsafe_reason)
    return resolved


def _match_file(root: Path, item: Any, *, role: str) -> dict[str, str | int]:
    if not isinstance(item, Mapping):
        raise RuntimeProbeEvidenceError(f"invalid_{role}_evidence")
    path_value = item.get("path")
    path = _relative_file(
        root,
        path_value,
        missing_reason=f"{role}_evidence_missing",
        unsafe_reason=f"unsafe_{role}_evidence_path",
    )
    declared = _hash(item.get("sha256"), f"invalid_{role}_evidence_hash")
    observed = "sha256:" + sha256_file(path)
    if declared != observed:
        raise RuntimeProbeEvidenceError(f"{role}_evidence_hash_mismatch")
    return {"path": str(path.relative_to(root)), "sha256": observed, "bytes": path.stat().st_size}


def _validate_execution(report: Mapping[str, Any], *, expected_command: Sequence[str], expected_revision: str) -> dict[str, Any]:
    if report.get("schema_version") != RUNTIME_PROBE_SCHEMA_VERSION:
        raise RuntimeProbeEvidenceError("unsupported_probe_report_schema")
    if report.get("status") != "pass":
        raise RuntimeProbeEvidenceError("runtime_probe_not_passed")
    measurement = report.get("measurement")
    if not isinstance(measurement, Mapping) or measurement.get("kind") != "external_runtime_probe" or measurement.get("executed") is not True:
        raise RuntimeProbeEvidenceError("runtime_probe_not_measured")
    runner = report.get("runner")
    if not isinstance(runner, Mapping) or not isinstance(runner.get("producer"), str) or not runner["producer"].strip():
        raise RuntimeProbeEvidenceError("runtime_probe_runner_missing")
    command = runner.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(value, str) or not value for value in command):
        raise RuntimeProbeEvidenceError("runtime_probe_command_missing")
    normalized_command = list(expected_command)
    if not normalized_command or any(not isinstance(value, str) or not value for value in normalized_command):
        raise RuntimeProbeEvidenceError("expected_runner_command_required")
    if command != normalized_command:
        raise RuntimeProbeEvidenceError("runtime_probe_command_mismatch")
    command_sha256 = _canonical_hash(command)
    if _hash(runner.get("command_sha256"), "runtime_probe_command_hash_invalid") != command_sha256:
        raise RuntimeProbeEvidenceError("runtime_probe_command_hash_mismatch")
    revision = _hash(runner.get("revision"), "runtime_probe_revision_invalid")
    if revision != _hash(expected_revision, "expected_runner_revision_invalid"):
        raise RuntimeProbeEvidenceError("runtime_probe_revision_mismatch")
    execution_id = runner.get("execution_id")
    if not isinstance(execution_id, str) or not execution_id.strip():
        raise RuntimeProbeEvidenceError("runtime_probe_execution_id_missing")
    if measurement.get("exit_code") != 0:
        raise RuntimeProbeEvidenceError("runtime_probe_nonzero_exit")
    return {
        "producer": runner["producer"].strip(),
        "execution_id": execution_id.strip(),
        "command": command,
        "command_sha256": command_sha256,
        "revision": revision,
        "measurement": {"kind": "external_runtime_probe", "executed": True, "exit_code": 0},
    }


def bind_runtime_probe_evidence(
    *,
    job_dir: str | Path,
    artifact_path: str,
    probe_report_path: str,
    target: str,
    expected_runner_command: Sequence[str],
    expected_runner_revision: str,
) -> dict[str, Any]:
    """Seal a real target-runtime probe report or reject without a fallback.

    ``expected_runner_*`` is control-plane policy, not a claim supplied by the
    probe.  Binding it prevents an arbitrary local file from rebranding itself
    as a trusted viewer/device execution.  The report and every frame/log must
    be pre-existing regular files relative to the same job directory.
    """
    if target not in SUPPORTED_TARGETS:
        raise RuntimeProbeEvidenceError("unknown_runtime_probe_target")
    root = _root(job_dir)
    artifact = _relative_file(root, artifact_path, missing_reason="runtime_probe_artifact_missing", unsafe_reason="unsafe_runtime_probe_artifact_path")
    report_path = _relative_file(root, probe_report_path, missing_reason="runtime_probe_report_missing", unsafe_reason="unsafe_runtime_probe_report_path")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeProbeEvidenceError("invalid_runtime_probe_report") from exc
    if not isinstance(report, Mapping):
        raise RuntimeProbeEvidenceError("invalid_runtime_probe_report")
    if report.get("target") != target:
        raise RuntimeProbeEvidenceError("runtime_probe_target_mismatch")
    execution = _validate_execution(report, expected_command=expected_runner_command, expected_revision=expected_runner_revision)
    reported_asset = report.get("artifact")
    if not isinstance(reported_asset, Mapping) or reported_asset.get("path") != artifact_path:
        raise RuntimeProbeEvidenceError("runtime_probe_artifact_path_mismatch")
    artifact_hash = "sha256:" + sha256_file(artifact)
    if _hash(reported_asset.get("sha256"), "runtime_probe_artifact_hash_invalid") != artifact_hash:
        raise RuntimeProbeEvidenceError("runtime_probe_artifact_hash_mismatch")
    evidence = report.get("evidence")
    if not isinstance(evidence, Mapping):
        raise RuntimeProbeEvidenceError("runtime_probe_evidence_missing")
    frames = evidence.get("frames")
    logs = evidence.get("logs")
    if not isinstance(frames, list) or not frames:
        raise RuntimeProbeEvidenceError("runtime_probe_frames_missing")
    if not isinstance(logs, list) or not logs:
        raise RuntimeProbeEvidenceError("runtime_probe_logs_missing")
    bound_frames = [_match_file(root, item, role="frame") for item in frames]
    bound_logs = [_match_file(root, item, role="log") for item in logs]
    all_paths = [entry["path"] for entry in bound_frames + bound_logs]
    if len(all_paths) != len(set(all_paths)):
        raise RuntimeProbeEvidenceError("runtime_probe_evidence_paths_not_unique")
    if report_path.relative_to(root).as_posix() in all_paths:
        raise RuntimeProbeEvidenceError("runtime_probe_report_cannot_be_evidence")
    payload = {
        "schema_version": RUNTIME_PROBE_SCHEMA_VERSION,
        "kind": "xreality.runtime_probe_evidence",
        "status": "measured_pass",
        "target": target,
        "artifact": {"path": artifact_path, "sha256": artifact_hash, "bytes": artifact.stat().st_size},
        "runner": execution,
        "probe_report": {
            "path": probe_report_path,
            "sha256": "sha256:" + sha256_file(report_path),
            "contract_sha256": _canonical_hash(report),
        },
        "evidence": {"frames": bound_frames, "logs": bound_logs},
        "promotion": "human_review_required",
    }
    record_id = _canonical_hash(payload)
    record = {**payload, "record_id": record_id, "seal": {"algorithm": "sha256", "value": record_id}}
    destination = safe_job_path(root, f"runtime-probe-evidence/{record_id.removeprefix('sha256:')}.json")
    if destination.exists():
        raise RuntimeProbeEvidenceError("runtime_probe_evidence_already_exists")
    atomic_write_json(destination, record)
    make_read_only(destination)
    return {**record, "path": str(destination)}


def verify_runtime_probe_evidence(*, job_dir: str | Path, record_path: str) -> dict[str, Any]:
    """Revalidate a sealed record against current job-local bytes."""
    root = _root(job_dir)
    path = _relative_file(root, record_path, missing_reason="runtime_probe_evidence_record_missing", unsafe_reason="unsafe_runtime_probe_evidence_record_path")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeProbeEvidenceError("invalid_runtime_probe_evidence_record") from exc
    if not isinstance(record, Mapping) or record.get("kind") != "xreality.runtime_probe_evidence":
        raise RuntimeProbeEvidenceError("invalid_runtime_probe_evidence_record")
    seal = record.get("seal")
    payload = {key: value for key, value in record.items() if key not in {"record_id", "seal", "path"}}
    expected = _canonical_hash(payload)
    if not isinstance(seal, Mapping) or seal.get("algorithm") != "sha256" or seal.get("value") != expected or record.get("record_id") != expected:
        raise RuntimeProbeEvidenceError("runtime_probe_evidence_seal_invalid")
    artifact = _relative_file(root, record.get("artifact", {}).get("path"), missing_reason="runtime_probe_artifact_missing", unsafe_reason="unsafe_runtime_probe_artifact_path")
    if "sha256:" + sha256_file(artifact) != record["artifact"].get("sha256"):
        raise RuntimeProbeEvidenceError("runtime_probe_artifact_hash_mismatch")
    for role in ("frames", "logs"):
        entries = record.get("evidence", {}).get(role)
        if not isinstance(entries, list) or not entries:
            raise RuntimeProbeEvidenceError(f"runtime_probe_{role}_missing")
        for entry in entries:
            _match_file(root, entry, role=role[:-1])
    return dict(record)
