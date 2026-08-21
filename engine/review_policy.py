"""Config-owned, fail-closed policy for named human master review.

This module deliberately does *not* accept a list of gates from an HTTP
request.  A promotion policy belongs to the installed engine configuration,
and its evidence locations are derived from the sealed job's stage namespace:
``<job>/stages/<stage>.json``.  This makes it impossible for a caller to point
an approval at a convenient report from a different job or worker.

It also keeps reviewer identity separate from the server.  The server loads a
locally administered, non-group/world-writable JSON registry and passes the
returned immutable records to the approval component.  Missing, malformed, or
mutable policy/registry files are errors -- never an empty allow-list.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from buffalo_runtime import ContractError, safe_job_path


REVIEW_POLICY_SCHEMA_VERSION = 1
REVIEWER_REGISTRY_SCHEMA_VERSION = 1
REVIEW_POLICY_KIND = "xreality_human_review_policy"
REVIEWER_REGISTRY_KIND = "xreality_reviewer_registry"
MAX_CONFIG_BYTES = 256 * 1024

# Keep this set local rather than deriving it from a caller-provided contract.
# A future policy schema migration must be an intentional code/config change.
MASTER_REVIEW_LANES = frozenset({
    "input", "security", "geometry", "parts", "topology", "uv", "texture",
    "material", "memory", "package", "runtime", "license",
    "sufficient_real_evidence", "canonical_review",
})


class ReviewPolicyError(ValueError):
    """Policy, stage evidence, or named reviewer is not safe to trust."""


def _nonempty_text(value: Any, code: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ReviewPolicyError(code)
    return value.strip()


def _safe_identifier(value: Any, code: str, *, maximum: int = 96) -> str:
    text = _nonempty_text(value, code, maximum=maximum)
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in text):
        raise ReviewPolicyError(code)
    return text


@dataclass(frozen=True)
class ReviewGate:
    """One mandatory review lane bound to exactly one job stage report."""

    lane: str
    stage: str

    @property
    def evidence_relative_path(self) -> str:
        """The only permitted evidence location for this gate.

        This is deliberately computed, rather than loaded from JSON, so custom
        policy configuration cannot introduce ``..``, an absolute path, or a
        worker-selected evidence destination.
        """
        return f"stages/{self.stage}.json"


@dataclass(frozen=True)
class ReviewPolicy:
    """Immutable policy selected by the installed control-plane config."""

    policy_id: str
    version: int
    gates: tuple[ReviewGate, ...]

    def gate_for_lane(self, lane: str) -> ReviewGate:
        for gate in self.gates:
            if gate.lane == lane:
                return gate
        raise ReviewPolicyError("review_lane_not_in_policy")

    def stage_evidence_paths(self, job_dir: str | Path) -> Mapping[str, Path]:
        """Return safe, job-local stage locations without trusting user input."""
        root = Path(job_dir).resolve()
        if not root.is_dir():
            raise ReviewPolicyError("managed_job_missing")
        paths: dict[str, Path] = {}
        for gate in self.gates:
            try:
                path = safe_job_path(root, gate.evidence_relative_path)
            except ContractError as exc:  # Defensive: all paths are computed.
                raise ReviewPolicyError("unsafe_policy_stage_path") from exc
            paths[gate.lane] = path
        return MappingProxyType(paths)

    def require_stage_evidence(self, job_dir: str | Path) -> Mapping[str, Path]:
        """Resolve every required report, rejecting symlinks and omissions."""
        paths = self.stage_evidence_paths(job_dir)
        for lane, path in paths.items():
            if path.is_symlink() or not path.is_file():
                raise ReviewPolicyError(f"required_review_evidence_missing:{lane}")
        return paths


@dataclass(frozen=True)
class RegisteredReviewer:
    """Reviewer identity from a local registry, immutable after validation."""

    reviewer_id: str
    display_name: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class ReviewerRegistry:
    """Locally configured, policy-bound named reviewers."""

    policy_id: str
    reviewers: tuple[RegisteredReviewer, ...]

    def reviewer(self, reviewer_id: str) -> RegisteredReviewer:
        safe_id = _safe_identifier(reviewer_id, "invalid_reviewer_id", maximum=160)
        for reviewer in self.reviewers:
            if reviewer.reviewer_id == safe_id:
                return reviewer
        raise ReviewPolicyError("unknown_reviewer")

    def as_mapping(self) -> Mapping[str, RegisteredReviewer]:
        return MappingProxyType({reviewer.reviewer_id: reviewer for reviewer in self.reviewers})


def _build_policy(policy_id: Any, version: Any, gates: Any) -> ReviewPolicy:
    checked_id = _safe_identifier(policy_id, "invalid_review_policy_id")
    if isinstance(version, bool) or not isinstance(version, int) or version != REVIEW_POLICY_SCHEMA_VERSION:
        raise ReviewPolicyError("unsupported_review_policy_version")
    if not isinstance(gates, list) or not gates:
        raise ReviewPolicyError("review_policy_gates_missing")
    compiled: list[ReviewGate] = []
    seen_lanes: set[str] = set()
    seen_stages: set[str] = set()
    for raw in gates:
        if not isinstance(raw, Mapping) or set(raw) != {"lane", "stage"}:
            raise ReviewPolicyError("invalid_review_policy_gate")
        lane = _safe_identifier(raw.get("lane"), "invalid_review_lane")
        stage = _safe_identifier(raw.get("stage"), "invalid_review_stage")
        if lane not in MASTER_REVIEW_LANES or lane in seen_lanes or stage in seen_stages:
            raise ReviewPolicyError("duplicate_or_unknown_review_gate")
        seen_lanes.add(lane)
        seen_stages.add(stage)
        compiled.append(ReviewGate(lane=lane, stage=stage))
    # A partial policy must not accidentally downgrade the master invariant.
    if seen_lanes != MASTER_REVIEW_LANES:
        raise ReviewPolicyError("incomplete_master_review_policy")
    return ReviewPolicy(policy_id=checked_id, version=version, gates=tuple(compiled))


_DEFAULT_GATE_CONFIG = [
    {"lane": lane, "stage": lane}
    for lane in sorted(MASTER_REVIEW_LANES)
]
DEFAULT_REVIEW_POLICY = _build_policy(
    policy_id="buffalo_mlx_master_v1",
    version=REVIEW_POLICY_SCHEMA_VERSION,
    gates=_DEFAULT_GATE_CONFIG,
)


def default_review_policy() -> ReviewPolicy:
    """Return the code-owned immutable policy used when no override is set."""
    return DEFAULT_REVIEW_POLICY


def _read_local_json(path_value: str | Path, missing_code: str, invalid_code: str) -> tuple[Path, Mapping[str, Any]]:
    if path_value is None:
        raise ReviewPolicyError(missing_code)
    path = Path(path_value)
    if path.suffix.lower() != ".json" or path.is_symlink() or not path.is_file():
        raise ReviewPolicyError(missing_code)
    try:
        stat = path.stat()
    except OSError as exc:
        raise ReviewPolicyError(missing_code) from exc
    if stat.st_size <= 0 or stat.st_size > MAX_CONFIG_BYTES:
        raise ReviewPolicyError(invalid_code)
    # Policy and identity configuration cannot be mutable by another local user
    # or service account. Owner writes are allowed for normal configuration
    # rotation; loaded records themselves remain immutable in this process.
    if stat.st_mode & 0o022:
        raise ReviewPolicyError("review_config_not_owner_controlled")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReviewPolicyError(invalid_code) from exc
    if not isinstance(document, Mapping):
        raise ReviewPolicyError(invalid_code)
    return path.resolve(), document


def load_review_policy(policy_path: str | Path) -> ReviewPolicy:
    """Load one sealed local policy override; never fall back on failure."""
    _, document = _read_local_json(policy_path, "review_policy_missing", "invalid_review_policy")
    if document.get("schema_version") != REVIEW_POLICY_SCHEMA_VERSION or document.get("kind") != REVIEW_POLICY_KIND:
        raise ReviewPolicyError("invalid_review_policy")
    return _build_policy(document.get("policy_id"), document.get("schema_version"), document.get("gates"))


def _compile_reviewers(raw_reviewers: Any) -> tuple[RegisteredReviewer, ...]:
    if not isinstance(raw_reviewers, list) or not raw_reviewers:
        raise ReviewPolicyError("reviewer_registry_missing")
    reviewers: list[RegisteredReviewer] = []
    seen: set[str] = set()
    for raw in raw_reviewers:
        if not isinstance(raw, Mapping) or set(raw) != {"id", "display_name", "roles"}:
            raise ReviewPolicyError("invalid_reviewer_registry")
        reviewer_id = _safe_identifier(raw.get("id"), "invalid_reviewer_id", maximum=160)
        display_name = _nonempty_text(raw.get("display_name"), "invalid_reviewer_name", maximum=160)
        roles = raw.get("roles")
        if not isinstance(roles, list) or not roles:
            raise ReviewPolicyError("invalid_reviewer_roles")
        checked_roles = tuple(sorted({_safe_identifier(role, "invalid_reviewer_role") for role in roles}))
        if len(checked_roles) != len(roles) or reviewer_id in seen:
            raise ReviewPolicyError("duplicate_reviewer_registry_entry")
        seen.add(reviewer_id)
        reviewers.append(RegisteredReviewer(reviewer_id, display_name, checked_roles))
    return tuple(reviewers)


def load_reviewer_registry(registry_path: str | Path, *, policy: ReviewPolicy) -> ReviewerRegistry:
    """Load a local reviewer registry that is explicitly bound to ``policy``.

    The registry is not optional.  In particular, an empty or mismatched file
    never means "any local user may approve this asset".
    """
    if not isinstance(policy, ReviewPolicy):
        raise ReviewPolicyError("review_policy_missing")
    _, document = _read_local_json(registry_path, "reviewer_registry_missing", "invalid_reviewer_registry")
    if document.get("schema_version") != REVIEWER_REGISTRY_SCHEMA_VERSION or document.get("kind") != REVIEWER_REGISTRY_KIND:
        raise ReviewPolicyError("invalid_reviewer_registry")
    policy_id = _safe_identifier(document.get("policy_id"), "invalid_reviewer_registry_policy")
    if policy_id != policy.policy_id:
        raise ReviewPolicyError("reviewer_registry_policy_mismatch")
    return ReviewerRegistry(policy_id=policy_id, reviewers=_compile_reviewers(document.get("reviewers")))


def require_named_reviewer(registry: ReviewerRegistry, reviewer_id: str) -> RegisteredReviewer:
    """Small explicit promotion guard for server/UI orchestration."""
    if not isinstance(registry, ReviewerRegistry):
        raise ReviewPolicyError("reviewer_registry_missing")
    return registry.reviewer(reviewer_id)
