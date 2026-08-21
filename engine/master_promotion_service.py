"""Fail-closed local orchestration for the only path to ``MASTER``.

This is intentionally a small composition layer over :mod:`review_policy`
and :mod:`human_review`.  It does not have an HTTP dependency and it never
uses a model score, a worker report, or a default user as an approver.  A
promotion requires all of the following at the moment it is sealed *and*
again when it is consumed:

* a read-only local review policy and reviewer registry;
* every policy-derived, job-local gate report, content-bound to the asset;
* a named reviewer in that registry and an explicit ``approve`` decision; and
* an immutable promotion record binding the policy, registry, review record,
  evidence and exact asset digest.

The worker gate protocol used here is deliberately narrow.  A policy maps a
lane to ``stages/<stage>.json``; that document must use the ``gate_result``
schema understood by ``human_review``.  Existing generic stage checkpoints are
not silently treated as master evidence just because they say ``passed``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable, Mapping

from buffalo_runtime import canonical_json, make_read_only, safe_job_path, sha256_file
from human_review import (
    APPROVE,
    REJECT,
    GateEvidenceSpec,
    HumanReviewError,
    Reviewer,
    seal_human_review,
    verify_human_review,
)
from review_policy import (
    MASTER_REVIEW_LANES,
    ReviewPolicy,
    ReviewPolicyError,
    ReviewerRegistry,
    load_review_policy,
    load_reviewer_registry,
)
from review_gate_evidence import GateEvidenceError, GATE_PRODUCERS, verify_gate_result


MASTER_PROMOTION_SCHEMA_VERSION = 1
MASTER_PROMOTION_KIND = "xreality_master_promotion"

# These producers are code-owned rather than caller-provided.  They describe
# the independently deployed gate adapters which write the narrow evidence
# protocol above.  Adding a lane or accepting a new producer is a source
# change, policy review, and corpus exercise -- never an HTTP option.
# Backward-compatible exported name; its contents live in the stricter issuer
# module, so the promotion layer cannot drift from source/result verification.
DEFAULT_GATE_PRODUCERS: Mapping[str, str] = GATE_PRODUCERS


class MasterPromotionError(ValueError):
    """Promotion is incomplete, not locally sealed, or later mutated."""


def _normalise_job_dir(value: str | Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir():
        raise MasterPromotionError("managed_job_missing")
    return root


def _sealed_config_digest(path_value: str | Path, *, label: str) -> tuple[Path, str]:
    """Return a digest only for an immutable, regular local config file."""
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise MasterPromotionError(f"{label}_missing")
    try:
        stat = path.stat()
    except OSError as exc:
        raise MasterPromotionError(f"{label}_missing") from exc
    # review_policy permits owner-writable files to make administration
    # practical.  Promotion is stricter: its policy/registry must be sealed.
    if stat.st_mode & 0o222:
        raise MasterPromotionError(f"{label}_not_sealed")
    return path.resolve(), f"sha256:{sha256_file(path)}"


def _record_id(payload: Mapping[str, Any]) -> str:
    return f"sha256:{hashlib.sha256(canonical_json(payload)).hexdigest()}"


def _relative_managed_file(job_dir: Path, value: str | Path, *, error: str) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else job_dir / raw
    if candidate.is_symlink():
        raise MasterPromotionError(error)
    resolved = candidate.resolve()
    if resolved == job_dir or job_dir not in resolved.parents or not resolved.is_file():
        raise MasterPromotionError(error)
    return resolved


def _asset_descriptor(job_dir: Path, asset_path: str | Path) -> dict[str, Any]:
    asset = _relative_managed_file(job_dir, asset_path, error="unmanaged_asset")
    return {
        "path": asset.relative_to(job_dir).as_posix(),
        "bytes": asset.stat().st_size,
        "sha256": f"sha256:{sha256_file(asset)}",
    }


def _gate_specs(policy: ReviewPolicy) -> tuple[GateEvidenceSpec, ...]:
    if not isinstance(policy, ReviewPolicy):
        raise MasterPromotionError("review_policy_missing")
    policy_lanes = {gate.lane for gate in policy.gates}
    if policy_lanes != MASTER_REVIEW_LANES or set(DEFAULT_GATE_PRODUCERS) != MASTER_REVIEW_LANES:
        raise MasterPromotionError("incomplete_master_review_policy")
    return tuple(
        GateEvidenceSpec(
            lane=gate.lane,
            relative_path=gate.evidence_relative_path,
            producer=DEFAULT_GATE_PRODUCERS[gate.lane],
        )
        for gate in sorted(policy.gates, key=lambda item: item.lane)
    )


def _reviewers(registry: ReviewerRegistry) -> tuple[Reviewer, ...]:
    if not isinstance(registry, ReviewerRegistry):
        raise MasterPromotionError("reviewer_registry_missing")
    return tuple(Reviewer(item.reviewer_id, item.display_name) for item in registry.reviewers)


def _verify_gate_results(*, job_dir: Path, asset_path: str | Path, policy: ReviewPolicy) -> None:
    """Reject legacy/generic stage JSON before human review reads it.

    ``human_review`` validates the narrow `gate_result` contract.  This adds
    the missing provenance hop: each result must itself derive from a sealed,
    code-owned source attestation for the same bytes and policy stage.
    """
    for gate in policy.gates:
        try:
            verify_gate_result(
                job_dir=job_dir,
                asset_path=asset_path,
                lane=gate.lane,
                stage=gate.stage,
            )
        except GateEvidenceError as exc:
            raise MasterPromotionError(f"gate_evidence_invalid:{gate.lane}:{exc}") from exc


def _load_context(
    *, policy_path: str | Path, reviewer_registry_path: str | Path,
) -> tuple[ReviewPolicy, ReviewerRegistry, Path, str, Path, str]:
    policy_file, policy_digest = _sealed_config_digest(policy_path, label="review_policy")
    registry_file, registry_digest = _sealed_config_digest(reviewer_registry_path, label="reviewer_registry")
    try:
        policy = load_review_policy(policy_file)
        registry = load_reviewer_registry(registry_file, policy=policy)
    except ReviewPolicyError as exc:
        raise MasterPromotionError(str(exc)) from exc
    _gate_specs(policy)
    _reviewers(registry)
    return policy, registry, policy_file, policy_digest, registry_file, registry_digest


def _write_new_sealed_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise MasterPromotionError("master_promotion_already_exists") from exc
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


def _read_promotion_record(job_dir: Path, path_value: str | Path) -> tuple[Path, Mapping[str, Any]]:
    path = _relative_managed_file(job_dir, path_value, error="master_promotion_missing_or_unmanaged")
    if path.stat().st_mode & 0o222:
        raise MasterPromotionError("master_promotion_not_sealed")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MasterPromotionError("invalid_master_promotion") from exc
    if not isinstance(value, Mapping):
        raise MasterPromotionError("invalid_master_promotion")
    return path, value


def _verify_promotion_shape(record: Mapping[str, Any], *, job_dir: Path) -> None:
    if record.get("schema_version") != MASTER_PROMOTION_SCHEMA_VERSION or record.get("kind") != MASTER_PROMOTION_KIND:
        raise MasterPromotionError("unknown_master_promotion")
    if record.get("job_path") != job_dir.name:
        raise MasterPromotionError("master_promotion_job_mismatch")
    record_id = record.get("record_id")
    if not isinstance(record_id, str):
        raise MasterPromotionError("master_promotion_id_missing")
    payload = dict(record)
    payload.pop("record_id", None)
    if _record_id(payload) != record_id:
        raise MasterPromotionError("master_promotion_integrity_mismatch")
    created_at = record.get("created_at")
    if not isinstance(created_at, (int, float)) or isinstance(created_at, bool) or not math.isfinite(created_at) or created_at <= 0:
        raise MasterPromotionError("master_promotion_invalid_time")


def seal_master_promotion(
    *,
    job_dir: str | Path,
    asset_path: str | Path,
    reviewer_id: str,
    decision: str,
    policy_path: str | Path,
    reviewer_registry_path: str | Path,
    note: str | None = None,
    clock: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Seal one human decision; only explicit named approval yields ``MASTER``.

    No implicit decision exists.  Callers must supply ``APPROVE`` or ``REJECT``
    and a reviewer ID registered in the sealed local registry.  The rejection
    path is retained for a durable negative decision but can never become a
    master record on later verification.
    """
    root = _normalise_job_dir(job_dir)
    policy, registry, policy_file, policy_digest, registry_file, registry_digest = _load_context(
        policy_path=policy_path, reviewer_registry_path=reviewer_registry_path,
    )
    specs = _gate_specs(policy)
    reviewers = _reviewers(registry)
    if decision not in {APPROVE, REJECT}:
        raise MasterPromotionError("explicit_review_decision_required")
    # A promotion directory is a single-decision namespace.  Prevent a later
    # reviewer from superseding an approved/rejected record by changing time.
    promotion_dir = root / "master-promotions"
    if promotion_dir.exists() and any(promotion_dir.glob("*.json")):
        raise MasterPromotionError("master_promotion_already_exists")
    _verify_gate_results(job_dir=root, asset_path=asset_path, policy=policy)
    try:
        human_record = seal_human_review(
            job_dir=root,
            asset_path=asset_path,
            reviewer_id=reviewer_id,
            decision=decision,
            required_gates=specs,
            reviewers=reviewers,
            note=note,
            clock=clock,
        )
    except HumanReviewError as exc:
        raise MasterPromotionError(str(exc)) from exc
    asset = _asset_descriptor(root, asset_path)
    human_id = human_record["record_id"]
    human_path = safe_job_path(root, f"human-reviews/{human_id.removeprefix('sha256:')}.json")
    reviewed_at = clock()
    if not isinstance(reviewed_at, (int, float)) or isinstance(reviewed_at, bool) or not math.isfinite(reviewed_at) or reviewed_at <= 0:
        raise MasterPromotionError("invalid_promotion_time")
    payload = {
        "schema_version": MASTER_PROMOTION_SCHEMA_VERSION,
        "kind": MASTER_PROMOTION_KIND,
        "job_path": root.name,
        "created_at": float(reviewed_at),
        "asset": asset,
        "policy": {
            "policy_id": policy.policy_id,
            "version": policy.version,
            "sha256": policy_digest,
            "source": policy_file.name,
        },
        "reviewer_registry": {
            "policy_id": registry.policy_id,
            "sha256": registry_digest,
            "source": registry_file.name,
        },
        "human_review": {
            "path": human_path.relative_to(root).as_posix(),
            "sha256": f"sha256:{sha256_file(human_path)}",
            "record_id": human_id,
            "reviewer_id": reviewer_id,
            "decision": decision,
        },
        "promotion": "MASTER" if decision == APPROVE else "NON_MASTER",
        "approval": "named_human" if decision == APPROVE else "named_human_rejection",
    }
    record = {**payload, "record_id": _record_id(payload)}
    destination = safe_job_path(root, f"master-promotions/{record['record_id'].removeprefix('sha256:')}.json")
    _write_new_sealed_json(destination, record)
    return verify_master_promotion(
        job_dir=root,
        asset_path=asset_path,
        promotion_record_path=destination,
        policy_path=policy_path,
        reviewer_registry_path=reviewer_registry_path,
    )


def verify_master_promotion(
    *,
    job_dir: str | Path,
    asset_path: str | Path,
    promotion_record_path: str | Path,
    policy_path: str | Path,
    reviewer_registry_path: str | Path,
) -> dict[str, Any]:
    """Re-verify an immutable promotion before any delivery state changes."""
    root = _normalise_job_dir(job_dir)
    policy, registry, policy_file, policy_digest, registry_file, registry_digest = _load_context(
        policy_path=policy_path, reviewer_registry_path=reviewer_registry_path,
    )
    path, record = _read_promotion_record(root, promotion_record_path)
    _verify_promotion_shape(record, job_dir=root)
    expected_policy = {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "sha256": policy_digest,
        "source": policy_file.name,
    }
    expected_registry = {
        "policy_id": registry.policy_id,
        "sha256": registry_digest,
        "source": registry_file.name,
    }
    if record.get("policy") != expected_policy:
        raise MasterPromotionError("master_promotion_policy_mismatch")
    if record.get("reviewer_registry") != expected_registry:
        raise MasterPromotionError("master_promotion_reviewer_registry_mismatch")
    asset = _asset_descriptor(root, asset_path)
    if record.get("asset") != asset:
        raise MasterPromotionError("master_promotion_asset_mismatch")
    _verify_gate_results(job_dir=root, asset_path=asset_path, policy=policy)
    human = record.get("human_review")
    if not isinstance(human, Mapping):
        raise MasterPromotionError("master_promotion_human_review_missing")
    human_path = _relative_managed_file(root, human.get("path", ""), error="master_promotion_human_review_missing")
    if human.get("sha256") != f"sha256:{sha256_file(human_path)}":
        raise MasterPromotionError("master_promotion_human_review_mutated")
    try:
        verified_review = verify_human_review(
            job_dir=root,
            asset_path=asset_path,
            review_record_path=human_path,
            required_gates=_gate_specs(policy),
            reviewers=_reviewers(registry),
        )
    except HumanReviewError as exc:
        raise MasterPromotionError(str(exc)) from exc
    if human.get("record_id") != verified_review.get("record_id"):
        raise MasterPromotionError("master_promotion_human_review_mismatch")
    decision = verified_review.get("decision")
    if human.get("decision") != decision or human.get("reviewer_id") != verified_review.get("reviewer", {}).get("id"):
        raise MasterPromotionError("master_promotion_human_review_mismatch")
    expected_promotion = "MASTER" if decision == APPROVE else "NON_MASTER"
    expected_approval = "named_human" if decision == APPROVE else "named_human_rejection"
    if record.get("promotion") != expected_promotion or record.get("approval") != expected_approval:
        raise MasterPromotionError("master_promotion_decision_mismatch")
    return json.loads(canonical_json(dict(record)).decode("utf-8"))
