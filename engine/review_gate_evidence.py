"""Strict, local evidence protocol for the gates required to promote MASTER.

This is the narrow adapter between a gate worker's *sealed attestation* and
the ``gate_result`` documents consumed by :mod:`human_review`.  It never
turns a generic JobLedger stage checkpoint, an HTTP boolean, or a model score
into a pass.  A gate result can only be issued from the fixed, job-local
``gate-sources/<lane>.json`` attestation namespace after the source is
read-only, self-integrity checked, code-producer/lane bound, and bound to the
exact asset bytes.  Results are exclusively created in ``stages/<stage>.json``
and immediately made read-only.

The protocol is deliberately local and does not claim that POSIX permissions
defeat a machine administrator.  It makes accidental mutation, worker output
confusion, path substitution, and a later changed source fail closed at every
consumer that calls :func:`verify_gate_result`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from buffalo_runtime import ContractError, canonical_json, make_read_only, safe_job_path, sha256_file
from review_policy import MASTER_REVIEW_LANES


GATE_EVIDENCE_SCHEMA_VERSION = 1
GATE_SOURCE_KIND = "xreality_master_gate_source"
GATE_SOURCE_CLASS = "xreality_master_gate_attestation_v1"
GATE_RESULT_KIND = "gate_result"  # Contract consumed by human_review.
GATE_RESULT_CLASS = "xreality_master_gate_result_v1"

# This map is deliberately code-owned.  A request may select neither a
# producer nor a lane outside this exact set.  master_promotion_service can
# import this map rather than trusting a caller supplied producer string.
GATE_PRODUCERS: Mapping[str, str] = {
    "input": "xreality_input_gate_v1",
    "security": "xreality_security_gate_v1",
    "geometry": "xreality_geometry_gate_v1",
    "parts": "xreality_parts_gate_v1",
    "topology": "xreality_topology_gate_v1",
    "uv": "xreality_uv_gate_v1",
    "texture": "xreality_texture_gate_v1",
    "material": "xreality_material_gate_v1",
    "memory": "xreality_memory_gate_v1",
    "package": "xreality_package_gate_v1",
    "runtime": "xreality_runtime_gate_v1",
    "license": "xreality_license_gate_v1",
    "sufficient_real_evidence": "xreality_real_evidence_gate_v1",
    "canonical_review": "xreality_canonical_review_gate_v1",
}


class GateEvidenceError(ValueError):
    """A gate result or its strictly typed source cannot be trusted."""


def _normalise_digest(value: Any, code: str) -> str:
    if not isinstance(value, str):
        raise GateEvidenceError(code)
    digest = value.removeprefix("sha256:").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise GateEvidenceError(code)
    return digest


def _normalise_lane(value: Any) -> str:
    if not isinstance(value, str) or value not in MASTER_REVIEW_LANES or value not in GATE_PRODUCERS:
        raise GateEvidenceError("unknown_gate_lane")
    return value


def _normalise_stage(value: Any, lane: str) -> str:
    stage = lane if value is None else value
    if not isinstance(stage, str) or not stage or len(stage) > 96:
        raise GateEvidenceError("invalid_gate_stage")
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in stage):
        raise GateEvidenceError("invalid_gate_stage")
    return stage


def _record_id(payload: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


def _normalise_job_dir(value: str | Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise GateEvidenceError("managed_job_missing")
    return root


def _managed_path(root: Path, relative: str, *, must_exist: bool, code: str) -> Path:
    """Resolve a generated relative path without accepting symlink hops."""
    raw = Path(relative)
    if raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
        raise GateEvidenceError(code)
    current = root
    for part in raw.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise GateEvidenceError(code)
    try:
        path = safe_job_path(root, raw)
    except ContractError as exc:
        raise GateEvidenceError(code) from exc
    if must_exist and (path.is_symlink() or not path.is_file()):
        raise GateEvidenceError(code)
    return path


def _asset_descriptor(root: Path, asset_path: str | Path) -> dict[str, Any]:
    raw = Path(asset_path)
    candidate = raw if raw.is_absolute() else root / raw
    if candidate.is_symlink():
        raise GateEvidenceError("unmanaged_asset")
    resolved = candidate.resolve()
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise GateEvidenceError("unmanaged_asset")
    return {
        "path": resolved.relative_to(root).as_posix(),
        "bytes": resolved.stat().st_size,
        "sha256": f"sha256:{sha256_file(resolved)}",
    }


def source_relative_path(lane: str) -> str:
    """Return the only accepted source namespace for a code-owned gate."""
    return f"gate-sources/{_normalise_lane(lane)}.json"


def result_relative_path(lane: str, *, stage: str | None = None) -> str:
    """Return a policy-compatible gate-result location under job ``stages``."""
    checked_lane = _normalise_lane(lane)
    return f"stages/{_normalise_stage(stage, checked_lane)}.json"


def _read_json_read_only(path: Path, code: str) -> Mapping[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        raise GateEvidenceError(code) from exc
    if stat.st_mode & 0o222:
        raise GateEvidenceError(f"{code}_not_sealed")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GateEvidenceError(code) from exc
    if not isinstance(value, Mapping):
        raise GateEvidenceError(code)
    return value


def _validate_source(root: Path, lane: str, asset_sha256: str) -> tuple[Path, Mapping[str, Any], str]:
    path = _managed_path(root, source_relative_path(lane), must_exist=True, code="gate_source_missing_or_unmanaged")
    source = _read_json_read_only(path, "invalid_gate_source")
    required = {"schema_version", "kind", "evidence_class", "producer", "lane", "status", "artifact", "source_id"}
    if set(source) != required:
        raise GateEvidenceError("wrong_gate_source_class")
    if (
        source.get("schema_version") != GATE_EVIDENCE_SCHEMA_VERSION
        or source.get("kind") != GATE_SOURCE_KIND
        or source.get("evidence_class") != GATE_SOURCE_CLASS
    ):
        raise GateEvidenceError("wrong_gate_source_class")
    if source.get("lane") != lane or source.get("producer") != GATE_PRODUCERS[lane]:
        raise GateEvidenceError("gate_source_producer_or_lane_mismatch")
    if source.get("status") != "pass":
        raise GateEvidenceError("gate_source_not_passed")
    artifact = source.get("artifact")
    if not isinstance(artifact, Mapping) or set(artifact) != {"sha256"}:
        raise GateEvidenceError("invalid_gate_source_artifact")
    if _normalise_digest(artifact.get("sha256"), "invalid_gate_source_artifact") != asset_sha256:
        raise GateEvidenceError("gate_source_asset_mismatch")
    payload = dict(source)
    source_id = payload.pop("source_id", None)
    if not isinstance(source_id, str) or _record_id(payload) != source_id:
        raise GateEvidenceError("gate_source_integrity_mismatch")
    return path, source, f"sha256:{sha256_file(path)}"


def _result_payload(*, root: Path, lane: str, stage: str, asset: Mapping[str, Any], source: Mapping[str, Any], source_digest: str) -> dict[str, Any]:
    return {
        "schema_version": GATE_EVIDENCE_SCHEMA_VERSION,
        "kind": GATE_RESULT_KIND,
        "evidence_class": GATE_RESULT_CLASS,
        "producer": GATE_PRODUCERS[lane],
        "lane": lane,
        "stage": stage,
        "status": "pass",
        "artifact": {"sha256": asset["sha256"]},
        "source": {
            "path": source_relative_path(lane),
            "sha256": source_digest,
            "source_id": source["source_id"],
            "kind": GATE_SOURCE_KIND,
            "producer": GATE_PRODUCERS[lane],
            "lane": lane,
        },
        "job_path": root.name,
    }


def _write_exclusive_read_only(path: Path, document: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise GateEvidenceError("gate_result_already_exists")
    parent = path.parent
    if parent.is_symlink():
        raise GateEvidenceError("unsafe_gate_result_path")
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        raise GateEvidenceError("unsafe_gate_result_path")
    encoded = json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise GateEvidenceError("gate_result_already_exists") from exc
    except OSError as exc:
        raise GateEvidenceError("unsafe_gate_result_path") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    make_read_only(path)


def seal_gate_result(
    *, job_dir: str | Path, asset_path: str | Path, lane: str, stage: str | None = None,
) -> dict[str, Any]:
    """Issue one exclusive immutable ``gate_result`` from a sealed attestation.

    ``lane`` selects only a code-owned producer and fixed source location.  No
    parameter can nominate an arbitrary report or elevate a caller-provided
    boolean to a pass.  Existing generic stage reports block issuance rather
    than being interpreted as evidence.
    """
    root = _normalise_job_dir(job_dir)
    checked_lane = _normalise_lane(lane)
    checked_stage = _normalise_stage(stage, checked_lane)
    asset = _asset_descriptor(root, asset_path)
    asset_digest = asset["sha256"].removeprefix("sha256:")
    _, source, source_digest = _validate_source(root, checked_lane, asset_digest)
    payload = _result_payload(
        root=root, lane=checked_lane, stage=checked_stage, asset=asset,
        source=source, source_digest=source_digest,
    )
    result = {**payload, "record_id": _record_id(payload)}
    destination = _managed_path(root, result_relative_path(checked_lane, stage=checked_stage), must_exist=False, code="unsafe_gate_result_path")
    _write_exclusive_read_only(destination, result)
    return verify_gate_result(job_dir=root, asset_path=asset_path, lane=checked_lane, stage=checked_stage)


def verify_gate_result(
    *, job_dir: str | Path, asset_path: str | Path, lane: str, stage: str | None = None,
) -> dict[str, Any]:
    """Re-verify final and source evidence before master review consumes it."""
    root = _normalise_job_dir(job_dir)
    checked_lane = _normalise_lane(lane)
    checked_stage = _normalise_stage(stage, checked_lane)
    asset = _asset_descriptor(root, asset_path)
    source_path, source, source_digest = _validate_source(root, checked_lane, asset["sha256"].removeprefix("sha256:"))
    del source_path
    path = _managed_path(root, result_relative_path(checked_lane, stage=checked_stage), must_exist=True, code="gate_result_missing_or_unmanaged")
    result = _read_json_read_only(path, "invalid_gate_result")
    required = {"schema_version", "kind", "evidence_class", "producer", "lane", "stage", "status", "artifact", "source", "job_path", "record_id"}
    if set(result) != required:
        raise GateEvidenceError("wrong_gate_result_class")
    if (
        result.get("schema_version") != GATE_EVIDENCE_SCHEMA_VERSION
        or result.get("kind") != GATE_RESULT_KIND
        or result.get("evidence_class") != GATE_RESULT_CLASS
        or result.get("producer") != GATE_PRODUCERS[checked_lane]
        or result.get("lane") != checked_lane
        or result.get("stage") != checked_stage
        or result.get("status") != "pass"
        or result.get("job_path") != root.name
    ):
        raise GateEvidenceError("wrong_gate_result_class")
    if result.get("artifact") != {"sha256": asset["sha256"]}:
        raise GateEvidenceError("gate_result_asset_mismatch")
    expected = _result_payload(
        root=root, lane=checked_lane, stage=checked_stage, asset=asset,
        source=source, source_digest=source_digest,
    )
    expected_record_id = _record_id(expected)
    if result.get("record_id") != expected_record_id:
        raise GateEvidenceError("gate_result_integrity_mismatch")
    if {key: value for key, value in result.items() if key != "record_id"} != expected:
        raise GateEvidenceError("gate_result_source_mismatch")
    return json.loads(canonical_json(dict(result)).decode("utf-8"))
