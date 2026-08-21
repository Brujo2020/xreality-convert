"""Fail-closed lineage manifests for delivery derivatives.

This module does not generate LODs, compress assets, or invoke a DCC.  It
only records a derivative after the caller has supplied independently measured
evidence.  In particular, a topology-changing derivative may never pretend its
source textures still fit: a successful, hash-bound rebake declaration is
required.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from secure_artifacts import UnsafeAssetError, validate_glb_container


DERIVATIVE_MANIFEST_SCHEMA_VERSION = 1
DELIVERY_TARGETS = frozenset({"lod", "web", "xr", "mobile", "usdz"})
_GLB_TARGETS = frozenset({"lod", "web", "xr", "mobile"})
_REBAKED_ROLES = frozenset({"base_color", "normal", "metallic_roughness", "occlusion", "emissive"})


class DerivativeLineageError(ValueError):
    """The requested delivery asset cannot receive a lineage manifest."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_hash(value: Any, reason: str) -> str:
    if not isinstance(value, str):
        raise DerivativeLineageError(reason)
    raw = value.removeprefix("sha256:")
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw.lower()):
        raise DerivativeLineageError(reason)
    return raw.lower()


def _json_object(value: Any, reason: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DerivativeLineageError(reason)
    try:
        # A canonical JSON round trip both rejects non-JSON values and prevents
        # later mutation of caller-owned nested structures from altering a
        # sealed manifest in memory.
        return json.loads(json.dumps(dict(value), sort_keys=True, separators=(",", ":")))
    except (TypeError, ValueError) as exc:
        raise DerivativeLineageError(reason) from exc


def _artifact(path: str | Path, *, label: str, expected_hash: str | None, require_glb: bool) -> dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        raise DerivativeLineageError(f"{label}_missing")
    if require_glb:
        if artifact.suffix.lower() != ".glb":
            raise DerivativeLineageError(f"{label}_must_be_glb")
        try:
            validate_glb_container(artifact)
        except UnsafeAssetError as exc:
            raise DerivativeLineageError(f"{label}_invalid_glb:{exc}") from exc
    digest = _sha256_file(artifact)
    if expected_hash is not None and _normalise_hash(expected_hash, f"{label}_hash_invalid") != digest:
        raise DerivativeLineageError(f"{label}_hash_mismatch")
    return {"path": artifact.name, "bytes": artifact.stat().st_size, "sha256": f"sha256:{digest}"}


def _validated_certificate(certificate: Any, *, target: str, output_sha256: str) -> dict[str, Any]:
    value = _json_object(certificate, "target_certificate_required")
    if value.get("status") != "pass":
        raise DerivativeLineageError("target_certificate_not_passed")
    if value.get("target") != target:
        raise DerivativeLineageError("target_certificate_target_mismatch")
    artifact = value.get("artifact")
    if not isinstance(artifact, Mapping):
        raise DerivativeLineageError("target_certificate_artifact_missing")
    certificate_hash = _normalise_hash(artifact.get("sha256"), "target_certificate_hash_invalid")
    if certificate_hash != output_sha256:
        raise DerivativeLineageError("target_certificate_hash_mismatch")
    return value


def _validated_rebake_evidence(evidence: Any, *, master_sha256: str, output_sha256: str) -> dict[str, Any]:
    value = _json_object(evidence, "rebake_evidence_required")
    if value.get("status") != "pass":
        raise DerivativeLineageError("rebake_evidence_not_passed")
    if _normalise_hash(value.get("source_master_sha256"), "rebake_source_hash_invalid") != master_sha256:
        raise DerivativeLineageError("rebake_source_hash_mismatch")
    if _normalise_hash(value.get("derivative_sha256"), "rebake_derivative_hash_invalid") != output_sha256:
        raise DerivativeLineageError("rebake_derivative_hash_mismatch")
    tool = value.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise DerivativeLineageError("rebake_tool_required")
    maps = value.get("maps")
    if not isinstance(maps, list) or not maps:
        raise DerivativeLineageError("rebake_maps_required")
    roles: set[str] = set()
    for item in maps:
        if not isinstance(item, Mapping):
            raise DerivativeLineageError("rebake_map_invalid")
        role = item.get("role")
        if role not in _REBAKED_ROLES or role in roles:
            raise DerivativeLineageError("rebake_map_role_invalid")
        _normalise_hash(item.get("sha256"), "rebake_map_hash_invalid")
        roles.add(role)
    return value


def build_derivative_manifest(
    *,
    master_path: str | Path,
    output_path: str | Path,
    target: str,
    topology_changed: bool,
    target_certificate: Mapping[str, Any],
    rebake_evidence: Mapping[str, Any] | None = None,
    expected_master_hash: str | None = None,
    expected_output_hash: str | None = None,
) -> dict[str, Any]:
    """Seal deterministic lineage for one delivery derivative.

    ``target_certificate`` is deliberately supplied rather than generated here:
    it must come from a target-specific validation lane (for example
    ``runtime_certification.certify_glb_for_target``).  A passing certificate
    for another file or target is rejected.
    """
    if target not in DELIVERY_TARGETS:
        raise DerivativeLineageError("unknown_delivery_target")
    if not isinstance(topology_changed, bool):
        raise DerivativeLineageError("topology_changed_required")
    master = Path(master_path)
    output = Path(output_path)
    try:
        if master.resolve() == output.resolve():
            raise DerivativeLineageError("derivative_must_not_overwrite_master")
    except OSError as exc:
        raise DerivativeLineageError("artifact_path_unreadable") from exc
    source = _artifact(master, label="master", expected_hash=expected_master_hash, require_glb=True)
    if target in _GLB_TARGETS:
        derivative = _artifact(output, label="output", expected_hash=expected_output_hash, require_glb=True)
    else:
        if output.suffix.lower() != ".usdz":
            raise DerivativeLineageError("output_must_be_usdz")
        derivative = _artifact(output, label="output", expected_hash=expected_output_hash, require_glb=False)

    master_sha256 = source["sha256"].removeprefix("sha256:")
    output_sha256 = derivative["sha256"].removeprefix("sha256:")
    certificate = _validated_certificate(target_certificate, target=target, output_sha256=output_sha256)
    rebake = (
        _validated_rebake_evidence(rebake_evidence, master_sha256=master_sha256, output_sha256=output_sha256)
        if topology_changed
        else None
    )
    if topology_changed and rebake is None:  # Defensive: kept explicit for auditability.
        raise DerivativeLineageError("rebake_evidence_required")
    return {
        "schema_version": DERIVATIVE_MANIFEST_SCHEMA_VERSION,
        "kind": "delivery_derivative",
        "target": target,
        "source_master": source,
        "output": derivative,
        "topology_changed": topology_changed,
        "rebake_evidence": rebake,
        "target_certificate": certificate,
    }


# A descriptive alias for callers that model this as a sealing operation.
seal_derivative_manifest = build_derivative_manifest
