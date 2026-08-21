"""Durable, fail-closed human approval records for master assets.

This module deliberately has no HTTP or UI dependency.  A caller supplies a
reviewer registry and a fixed policy which binds every required lane to one
known, job-local JSON evidence file.  An approval is only sealed after each
file has passed, is hash-bound to the reviewed asset, and identifies the
expected producer.  The record is append-only (exclusive create + read-only
permissions) and can subsequently be re-verified before any promotion.

It is an integrity mechanism, not a replacement for an organisational identity
provider or hardware-backed signing key.  In particular, a local filesystem
administrator can always alter local files; this module makes accidental or
untrusted worker evidence fail closed and makes later alteration detectable by
normal verification.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping, Sequence

from buffalo_runtime import ContractError, canonical_json, make_read_only, safe_job_path, sha256_file


HUMAN_REVIEW_SCHEMA_VERSION = 1
APPROVE = "approve"
REJECT = "reject"
MASTER_GATED_LANES = frozenset({
    "input", "security", "geometry", "parts", "topology", "uv", "texture",
    "material", "memory", "package", "runtime", "license",
    "sufficient_real_evidence", "canonical_review",
})


class HumanReviewError(ValueError):
    """A master approval is incomplete, untrusted, or has been altered."""


@dataclass(frozen=True)
class GateEvidenceSpec:
    """One policy-bound evidence source for one promotion lane.

    ``relative_path`` is deliberately part of policy rather than reviewer
    input.  This prevents a reviewer request from pointing at a conveniently
    passing file emitted by an unrelated job or untrusted plugin.
    """

    lane: str
    relative_path: str
    producer: str
    kind: str = "gate_result"
    status_path: tuple[str, ...] = ("status",)
    asset_hash_path: tuple[str, ...] = ("artifact", "sha256")


@dataclass(frozen=True)
class Reviewer:
    """Named, policy-recognised reviewer identity recorded in an approval."""

    reviewer_id: str
    display_name: str


def _normalise_sha256(value: Any, reason: str) -> str:
    if not isinstance(value, str):
        raise HumanReviewError(reason)
    digest = value.removeprefix("sha256:").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise HumanReviewError(reason)
    return digest


def _nonempty_text(value: Any, reason: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise HumanReviewError(reason)
    return value.strip()


def _normalise_relative_path(value: str, reason: str) -> str:
    try:
        raw = Path(value)
    except TypeError as exc:
        raise HumanReviewError(reason) from exc
    if not value or raw.is_absolute() or any(part in {"", ".", ".."} for part in raw.parts):
        raise HumanReviewError(reason)
    return raw.as_posix()


def _json_value_at(document: Mapping[str, Any], path: Sequence[str], reason: str) -> Any:
    current: Any = document
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            raise HumanReviewError(reason)
        current = current[key]
    return current


def _copy_json_mapping(value: Mapping[str, Any], reason: str) -> dict[str, Any]:
    try:
        cloned = json.loads(canonical_json(dict(value)).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise HumanReviewError(reason) from exc
    if not isinstance(cloned, dict):  # Defensive after the JSON round trip.
        raise HumanReviewError(reason)
    return cloned


def _policy_by_lane(required_gates: Sequence[GateEvidenceSpec]) -> dict[str, GateEvidenceSpec]:
    if not isinstance(required_gates, Sequence) or isinstance(required_gates, (str, bytes)) or not required_gates:
        raise HumanReviewError("required_gate_policy_missing")
    policy: dict[str, GateEvidenceSpec] = {}
    for spec in required_gates:
        if not isinstance(spec, GateEvidenceSpec):
            raise HumanReviewError("invalid_gate_policy")
        lane = _nonempty_text(spec.lane, "invalid_gate_lane", maximum=96)
        if lane not in MASTER_GATED_LANES or lane in policy:
            raise HumanReviewError("unknown_or_duplicate_gate_lane")
        relative_path = _normalise_relative_path(spec.relative_path, "unsafe_gate_evidence_path")
        _nonempty_text(spec.producer, "invalid_gate_producer", maximum=160)
        _nonempty_text(spec.kind, "invalid_gate_kind", maximum=96)
        if not spec.status_path or not spec.asset_hash_path:
            raise HumanReviewError("invalid_gate_policy_path")
        if any(not isinstance(key, str) or not key for key in (*spec.status_path, *spec.asset_hash_path)):
            raise HumanReviewError("invalid_gate_policy_path")
        # Store a normalised immutable replacement rather than caller-owned data.
        policy[lane] = GateEvidenceSpec(
            lane=lane,
            relative_path=relative_path,
            producer=spec.producer.strip(),
            kind=spec.kind.strip(),
            status_path=tuple(spec.status_path),
            asset_hash_path=tuple(spec.asset_hash_path),
        )
    return policy


def _reviewers_by_id(reviewers: Sequence[Reviewer]) -> dict[str, Reviewer]:
    if not isinstance(reviewers, Sequence) or isinstance(reviewers, (str, bytes)) or not reviewers:
        raise HumanReviewError("reviewer_registry_missing")
    result: dict[str, Reviewer] = {}
    for reviewer in reviewers:
        if not isinstance(reviewer, Reviewer):
            raise HumanReviewError("invalid_reviewer_registry")
        reviewer_id = _nonempty_text(reviewer.reviewer_id, "invalid_reviewer_id", maximum=160)
        display_name = _nonempty_text(reviewer.display_name, "invalid_reviewer_name", maximum=160)
        if reviewer_id in result:
            raise HumanReviewError("duplicate_reviewer_id")
        result[reviewer_id] = Reviewer(reviewer_id, display_name)
    return result


def _managed_file(job_dir: Path, relative_path: str, reason: str) -> Path:
    raw = job_dir / relative_path
    if raw.is_symlink():
        raise HumanReviewError(reason)
    path = safe_job_path(job_dir, relative_path)
    if not path.is_file():
        raise HumanReviewError(reason)
    return path


def _asset_descriptor(job_dir: Path, asset_path: str | Path) -> dict[str, Any]:
    raw = Path(asset_path)
    candidate = raw if raw.is_absolute() else job_dir / raw
    if candidate.is_symlink():
        raise HumanReviewError("unmanaged_asset")
    resolved = (raw if raw.is_absolute() else job_dir / raw).resolve()
    if resolved == job_dir or job_dir not in resolved.parents or not resolved.is_file():
        raise HumanReviewError("unmanaged_asset")
    return {
        "path": resolved.relative_to(job_dir).as_posix(),
        "bytes": resolved.stat().st_size,
        "sha256": f"sha256:{sha256_file(resolved)}",
    }


def _validate_gate_evidence(job_dir: Path, spec: GateEvidenceSpec, asset_sha256: str) -> dict[str, Any]:
    path = _managed_file(job_dir, spec.relative_path, "gate_evidence_missing_or_unmanaged")
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HumanReviewError(f"invalid_gate_evidence:{spec.lane}") from exc
    if not isinstance(document, Mapping):
        raise HumanReviewError(f"invalid_gate_evidence:{spec.lane}")
    if document.get("schema_version") != HUMAN_REVIEW_SCHEMA_VERSION:
        raise HumanReviewError(f"unknown_gate_evidence_schema:{spec.lane}")
    if document.get("kind") != spec.kind or document.get("producer") != spec.producer:
        raise HumanReviewError(f"unknown_gate_evidence:{spec.lane}")
    if _json_value_at(document, spec.status_path, f"gate_status_missing:{spec.lane}") != "pass":
        raise HumanReviewError(f"gate_not_passed:{spec.lane}")
    observed_hash = _normalise_sha256(
        _json_value_at(document, spec.asset_hash_path, f"gate_asset_hash_missing:{spec.lane}"),
        f"gate_asset_hash_invalid:{spec.lane}",
    )
    if observed_hash != asset_sha256:
        raise HumanReviewError(f"gate_asset_hash_mismatch:{spec.lane}")
    return {
        "lane": spec.lane,
        "path": spec.relative_path,
        "sha256": f"sha256:{hashlib.sha256(raw).hexdigest()}",
        "producer": spec.producer,
        "kind": spec.kind,
        "status": "pass",
        "asset_sha256": f"sha256:{observed_hash}",
    }


def _record_payload(
    *, job_dir: Path, asset: Mapping[str, Any], reviewer: Reviewer, decision: str,
    reviewed_at: float, gates: Sequence[Mapping[str, Any]], note: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": HUMAN_REVIEW_SCHEMA_VERSION,
        "kind": "human_master_approval",
        "job_path": job_dir.name,
        "reviewer": {"id": reviewer.reviewer_id, "display_name": reviewer.display_name},
        "decision": decision,
        "reviewed_at": reviewed_at,
        "asset": dict(asset),
        "gates": list(gates),
        "promotion": "MASTER" if decision == APPROVE else "NON_MASTER",
    }
    if note is not None:
        payload["note"] = note
    return payload


def _record_id(payload: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


def _write_new_read_only(path: Path, record: Mapping[str, Any]) -> None:
    """Persist once; never replace a prior decision or mutable worker output."""
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise HumanReviewError("review_record_already_exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # A partial file must never masquerade as a valid sealed decision.
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    make_read_only(path)


def seal_human_review(
    *,
    job_dir: str | Path,
    asset_path: str | Path,
    reviewer_id: str,
    decision: str,
    required_gates: Sequence[GateEvidenceSpec],
    reviewers: Sequence[Reviewer],
    note: str | None = None,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Create one immutable named decision, returning a verified record.

    ``approve`` is intentionally impossible when even one policy gate is
    absent, unknown, non-passing, points outside the job, or refers to another
    asset.  ``reject`` is preserved as an immutable non-master decision, but
    uses the same full evidence validation so it cannot launder foreign files
    into the job history.
    """
    root = Path(job_dir).resolve()
    if not root.is_dir():
        raise HumanReviewError("managed_job_missing")
    if decision not in {APPROVE, REJECT}:
        raise HumanReviewError("invalid_review_decision")
    reviewer = _reviewers_by_id(reviewers).get(_nonempty_text(reviewer_id, "reviewer_id_required", maximum=160))
    if reviewer is None:
        raise HumanReviewError("unknown_reviewer")
    policy = _policy_by_lane(required_gates)
    asset = _asset_descriptor(root, asset_path)
    asset_sha256 = asset["sha256"].removeprefix("sha256:")
    gates = [_validate_gate_evidence(root, policy[lane], asset_sha256) for lane in sorted(policy)]
    timestamp = clock()
    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp) or timestamp <= 0:
        raise HumanReviewError("invalid_review_time")
    clean_note = None if note is None else _nonempty_text(note, "invalid_review_note", maximum=4_000)
    payload = _record_payload(
        job_dir=root, asset=asset, reviewer=reviewer, decision=decision,
        reviewed_at=float(timestamp), gates=gates, note=clean_note,
    )
    record_id = _record_id(payload)
    record = {**payload, "record_id": record_id}
    review_path = safe_job_path(root, f"human-reviews/{record_id.removeprefix('sha256:')}.json")
    _write_new_read_only(review_path, record)
    # Re-read everything after persistence.  A caller never receives an
    # unverified success just because the write call returned.
    return verify_human_review(
        job_dir=root,
        asset_path=asset_path,
        review_record_path=review_path,
        required_gates=required_gates,
        reviewers=reviewers,
    )


def verify_human_review(
    *,
    job_dir: str | Path,
    asset_path: str | Path,
    review_record_path: str | Path,
    required_gates: Sequence[GateEvidenceSpec],
    reviewers: Sequence[Reviewer],
) -> dict[str, Any]:
    """Verify both the sealed decision and the current gate/asset bindings."""
    root = Path(job_dir).resolve()
    if not root.is_dir():
        raise HumanReviewError("managed_job_missing")
    policy = _policy_by_lane(required_gates)
    registry = _reviewers_by_id(reviewers)
    raw_record = Path(review_record_path)
    candidate = raw_record if raw_record.is_absolute() else root / raw_record
    if candidate.is_symlink():
        raise HumanReviewError("review_record_missing_or_unmanaged")
    path = (raw_record if raw_record.is_absolute() else root / raw_record).resolve()
    if path == root or root not in path.parents or not path.is_file():
        raise HumanReviewError("review_record_missing_or_unmanaged")
    if path.stat().st_mode & 0o222:
        raise HumanReviewError("review_record_not_sealed")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanReviewError("invalid_review_record") from exc
    if not isinstance(record, Mapping) or record.get("schema_version") != HUMAN_REVIEW_SCHEMA_VERSION or record.get("kind") != "human_master_approval":
        raise HumanReviewError("unknown_review_record")
    record_id = record.get("record_id")
    if not isinstance(record_id, str):
        raise HumanReviewError("review_record_id_missing")
    payload = dict(record)
    payload.pop("record_id", None)
    if _record_id(payload) != record_id:
        raise HumanReviewError("review_record_integrity_mismatch")
    reviewer_data = record.get("reviewer")
    if not isinstance(reviewer_data, Mapping):
        raise HumanReviewError("review_record_reviewer_missing")
    reviewer = registry.get(reviewer_data.get("id"))
    if reviewer is None or reviewer.display_name != reviewer_data.get("display_name"):
        raise HumanReviewError("review_record_unknown_reviewer")
    if record.get("decision") not in {APPROVE, REJECT}:
        raise HumanReviewError("review_record_invalid_decision")
    reviewed_at = record.get("reviewed_at")
    if not isinstance(reviewed_at, (int, float)) or isinstance(reviewed_at, bool) or not math.isfinite(reviewed_at) or reviewed_at <= 0:
        raise HumanReviewError("review_record_invalid_time")
    asset = _asset_descriptor(root, asset_path)
    if record.get("asset") != asset:
        raise HumanReviewError("review_record_asset_mismatch")
    asset_sha256 = asset["sha256"].removeprefix("sha256:")
    expected_gates = [_validate_gate_evidence(root, policy[lane], asset_sha256) for lane in sorted(policy)]
    if record.get("gates") != expected_gates:
        raise HumanReviewError("review_record_evidence_mismatch")
    expected_promotion = "MASTER" if record["decision"] == APPROVE else "NON_MASTER"
    if record.get("promotion") != expected_promotion:
        raise HumanReviewError("review_record_promotion_mismatch")
    return _copy_json_mapping(record, "invalid_review_record")


# Clear aliases for orchestration code which models promotion as a gate.
seal_master_approval = seal_human_review
verify_master_approval = verify_human_review
