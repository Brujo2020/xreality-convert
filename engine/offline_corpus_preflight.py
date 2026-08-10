"""Fail-closed, local preflight for the fixed 30-case acceptance corpus.

This is intentionally an *input inventory*, not an evaluator or an inference
runner.  It reads only caller-selected regular files below a local corpus root,
hashes them, records provenance/legal evidence, and seals the resulting
manifest.  Network, model loading, and synthetic completion are out of scope.

The corpus is allowed to contain synthetic or provider-supplied references for
non-master experimentation, but a master candidate needs sufficient evidence:
at least two independently declared real observed views, a real source stratum,
and explicit legal/consent records.  A seal means the manifest content was
unchanged; ``verify_preflight_against_corpus`` additionally proves that the
local inputs still match the sealed bytes.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from offline_campaign import EXPECTED_CASE_IDS


PREFLIGHT_SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAMPAIGN_ID = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")
_STRATA = frozenset({"real", "synthetic", "provider"})
_INTENTS = frozenset({"preview", "mobile", "xr", "hi_fi", "master"})
_KINDS = frozenset({"image", "asset"})


class CorpusPreflightError(ValueError):
    """The local corpus cannot be used as sealed acceptance evidence."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _without_seal(value: Mapping[str, Any]) -> dict[str, Any]:
    copied = deepcopy(dict(value))
    copied.pop("seal", None)
    return copied


def _text(value: Any, code: str, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip() != value or len(value) > maximum:
        raise CorpusPreflightError(code)
    return value


def _root(value: str | Path) -> Path:
    root = Path(value)
    if root.is_symlink() or not root.is_dir():
        raise CorpusPreflightError("corpus_root_unsafe")
    return root.absolute()


def _relative_path(value: Any) -> tuple[str, ...]:
    raw = _text(value, "input_relative_path_invalid", maximum=700)
    candidate = Path(raw)
    if candidate.is_absolute() or "\\" in raw or not candidate.parts:
        raise CorpusPreflightError("input_relative_path_invalid")
    parts = candidate.parts
    if any(part in {"", ".", ".."} for part in parts):
        raise CorpusPreflightError("input_relative_path_invalid")
    return parts


def _regular_child(root: Path, relative_path: Any) -> tuple[Path, str]:
    parts = _relative_path(relative_path)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise CorpusPreflightError("input_path_unsafe")
    try:
        current.relative_to(root)
    except ValueError as exc:
        raise CorpusPreflightError("input_path_unsafe") from exc
    if not current.is_file() or current.is_symlink():
        raise CorpusPreflightError("input_file_missing")
    return current, "/".join(parts)


def _file_sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise CorpusPreflightError("input_file_unreadable") from exc
    return "sha256:" + digest.hexdigest(), size


def _legal(value: Any, *, case_id: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, Mapping) or set(value) != {"license", "consent"}:
        raise CorpusPreflightError(f"legal_evidence_invalid:{case_id}")
    normalized: dict[str, dict[str, str]] = {}
    for field in ("license", "consent"):
        entry = value[field]
        if not isinstance(entry, Mapping) or set(entry) != {"status", "reference"}:
            raise CorpusPreflightError(f"legal_evidence_invalid:{case_id}:{field}")
        status = entry["status"]
        allowed = {"verified"} if field == "license" else {"verified", "not_required"}
        if status not in allowed:
            raise CorpusPreflightError(f"legal_status_invalid:{case_id}:{field}")
        normalized[field] = {"status": status, "reference": _text(entry["reference"], f"legal_reference_invalid:{case_id}:{field}")}
    return normalized


def _normalise_input(root: Path, value: Any, *, case_id: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"relative_path", "kind", "identity_stratum", "observed"}:
        raise CorpusPreflightError(f"input_contract_invalid:{case_id}")
    kind = value["kind"]
    stratum = value["identity_stratum"]
    if kind not in _KINDS or stratum not in _STRATA or not isinstance(value["observed"], bool):
        raise CorpusPreflightError(f"input_contract_invalid:{case_id}")
    path, relative_path = _regular_child(root, value["relative_path"])
    sha256, size_bytes = _file_sha256(path)
    return {
        "relative_path": relative_path,
        "kind": kind,
        "identity_stratum": stratum,
        "observed": value["observed"],
        "sha256": sha256,
        "size_bytes": size_bytes,
    }


def _normalise_case(root: Path, value: Any, *, expected_case_id: str) -> dict[str, Any]:
    required = {"case_id", "delivery_intent", "source_identity_stratum", "legal", "evidence", "observed_view_count", "inputs"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("case_id") != expected_case_id:
        raise CorpusPreflightError(f"case_contract_invalid:{expected_case_id}")
    intent = value["delivery_intent"]
    source_stratum = value["source_identity_stratum"]
    if intent not in _INTENTS or source_stratum not in _STRATA:
        raise CorpusPreflightError(f"case_contract_invalid:{expected_case_id}")
    evidence = value["evidence"]
    if not isinstance(evidence, Mapping) or set(evidence) != {"sufficiency", "reference"} or evidence["sufficiency"] not in {"sufficient", "insufficient"}:
        raise CorpusPreflightError(f"evidence_contract_invalid:{expected_case_id}")
    normalized_evidence = {
        "sufficiency": evidence["sufficiency"],
        "reference": _text(evidence["reference"], f"evidence_reference_invalid:{expected_case_id}"),
    }
    if not isinstance(value["observed_view_count"], int) or isinstance(value["observed_view_count"], bool) or value["observed_view_count"] < 0:
        raise CorpusPreflightError(f"observed_view_count_invalid:{expected_case_id}")
    raw_inputs = value["inputs"]
    if not isinstance(raw_inputs, list) or not raw_inputs:
        raise CorpusPreflightError(f"input_inventory_missing:{expected_case_id}")
    inputs = [_normalise_input(root, raw, case_id=expected_case_id) for raw in raw_inputs]
    paths = [item["relative_path"] for item in inputs]
    if len(paths) != len(set(paths)):
        raise CorpusPreflightError(f"input_inventory_duplicate_path:{expected_case_id}")
    observed = [item for item in inputs if item["observed"]]
    if value["observed_view_count"] != len(observed):
        raise CorpusPreflightError(f"observed_view_count_mismatch:{expected_case_id}")
    # The campaign asset is explicitly the first input rather than an opaque
    # bundle hash, so downstream offline_campaign can bind every worker report
    # to bytes that a reviewer can locate in this inventory.
    primary = inputs[0]
    if primary["kind"] != "image":
        raise CorpusPreflightError(f"primary_input_must_be_image:{expected_case_id}")
    if intent == "master":
        real_observed = [item for item in observed if item["identity_stratum"] == "real"]
        if source_stratum != "real" or len(real_observed) < 2:
            raise CorpusPreflightError(f"master_requires_two_real_observed_views:{expected_case_id}")
        if normalized_evidence["sufficiency"] != "sufficient":
            raise CorpusPreflightError(f"master_evidence_insufficient:{expected_case_id}")
    return {
        "case_id": expected_case_id,
        "delivery_intent": intent,
        "source_identity_stratum": source_stratum,
        "legal": _legal(value["legal"], case_id=expected_case_id),
        "evidence": normalized_evidence,
        "observed_view_count": value["observed_view_count"],
        "asset": {"sha256": primary["sha256"], "relative_path": primary["relative_path"]},
        "inputs": inputs,
    }


def build_preflight_manifest(*, campaign_id: str, corpus_root: str | Path, cases: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Hash and seal the exact campaign inventory; it never downloads or runs ML."""
    if not isinstance(campaign_id, str) or _CAMPAIGN_ID.fullmatch(campaign_id) is None:
        raise CorpusPreflightError("campaign_id_invalid")
    if not isinstance(cases, Mapping) or set(cases) != set(EXPECTED_CASE_IDS):
        raise CorpusPreflightError("preflight_case_inventory_mismatch")
    root = _root(corpus_root)
    manifest = {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "execution": {"offline": True, "network_allowed": False, "inference_performed": False},
        "cases": [_normalise_case(root, cases[case_id], expected_case_id=case_id) for case_id in EXPECTED_CASE_IDS],
    }
    manifest["seal"] = {"algorithm": "sha256", "value": _digest(manifest)}
    return manifest


def campaign_asset_hashes(manifest: Mapping[str, Any]) -> dict[str, str]:
    """Return the exact image hashes needed by ``offline_campaign``'s manifest."""
    normalized = _validate_manifest_shape(_without_seal(manifest))
    return {case["case_id"]: case["asset"]["sha256"] for case in normalized["cases"]}


def _validate_manifest_shape(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema_version") != PREFLIGHT_SCHEMA_VERSION:
        raise CorpusPreflightError("preflight_schema_invalid")
    if not isinstance(value.get("campaign_id"), str) or _CAMPAIGN_ID.fullmatch(value["campaign_id"]) is None:
        raise CorpusPreflightError("campaign_id_invalid")
    if value.get("execution") != {"offline": True, "network_allowed": False, "inference_performed": False}:
        raise CorpusPreflightError("preflight_must_be_local_offline")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != len(EXPECTED_CASE_IDS):
        raise CorpusPreflightError("preflight_case_inventory_mismatch")
    # Re-use the strict shape validators against a temporary *nonexistent*
    # root is not possible because they hash files.  Verify the sealed output
    # directly and leave byte revalidation to verify_preflight_against_corpus.
    normalized = deepcopy(dict(value))
    if [case.get("case_id") if isinstance(case, Mapping) else None for case in cases] != list(EXPECTED_CASE_IDS):
        raise CorpusPreflightError("preflight_case_inventory_mismatch")
    for case in cases:
        if not isinstance(case, Mapping) or set(case) != {"case_id", "delivery_intent", "source_identity_stratum", "legal", "evidence", "observed_view_count", "asset", "inputs"}:
            raise CorpusPreflightError("preflight_case_contract_invalid")
        if case["delivery_intent"] not in _INTENTS or case["source_identity_stratum"] not in _STRATA:
            raise CorpusPreflightError("preflight_case_contract_invalid")
        if not isinstance(case["observed_view_count"], int) or isinstance(case["observed_view_count"], bool) or case["observed_view_count"] < 0:
            raise CorpusPreflightError("observed_view_count_invalid")
        if not isinstance(case["inputs"], list) or not case["inputs"]:
            raise CorpusPreflightError("input_inventory_missing")
        observed = 0
        real_observed = 0
        paths: set[str] = set()
        for item in case["inputs"]:
            if not isinstance(item, Mapping) or set(item) != {"relative_path", "kind", "identity_stratum", "observed", "sha256", "size_bytes"}:
                raise CorpusPreflightError("preflight_input_contract_invalid")
            _relative_path(item["relative_path"])
            if item["kind"] not in _KINDS or item["identity_stratum"] not in _STRATA or not isinstance(item["observed"], bool):
                raise CorpusPreflightError("preflight_input_contract_invalid")
            if not isinstance(item["sha256"], str) or _SHA256.fullmatch(item["sha256"]) is None or not isinstance(item["size_bytes"], int) or isinstance(item["size_bytes"], bool) or item["size_bytes"] < 0:
                raise CorpusPreflightError("preflight_input_contract_invalid")
            if item["relative_path"] in paths:
                raise CorpusPreflightError("input_inventory_duplicate_path")
            paths.add(item["relative_path"])
            observed += int(item["observed"])
            real_observed += int(item["observed"] and item["identity_stratum"] == "real")
        if observed != case["observed_view_count"]:
            raise CorpusPreflightError("observed_view_count_mismatch")
        asset = case["asset"]
        if not isinstance(asset, Mapping) or set(asset) != {"sha256", "relative_path"} or asset.get("sha256") != case["inputs"][0]["sha256"] or asset.get("relative_path") != case["inputs"][0]["relative_path"]:
            raise CorpusPreflightError("preflight_asset_binding_invalid")
        _legal(case["legal"], case_id=case["case_id"])
        evidence = case["evidence"]
        if not isinstance(evidence, Mapping) or set(evidence) != {"sufficiency", "reference"} or evidence["sufficiency"] not in {"sufficient", "insufficient"}:
            raise CorpusPreflightError("evidence_contract_invalid")
        _text(evidence["reference"], "evidence_reference_invalid")
        if case["delivery_intent"] == "master" and (case["source_identity_stratum"] != "real" or real_observed < 2 or evidence["sufficiency"] != "sufficient"):
            raise CorpusPreflightError("master_evidence_invalid")
    return normalized


def verify_preflight_manifest_seal(manifest: Mapping[str, Any]) -> bool:
    try:
        seal = manifest.get("seal")
        return (
            isinstance(seal, Mapping)
            and seal.get("algorithm") == "sha256"
            and isinstance(seal.get("value"), str)
            and _SHA256.fullmatch(seal["value"]) is not None
            and seal["value"] == _digest(_validate_manifest_shape(_without_seal(manifest)))
        )
    except (AttributeError, CorpusPreflightError):
        return False


def verify_preflight_against_corpus(*, manifest: Mapping[str, Any], corpus_root: str | Path) -> bool:
    """Require a valid seal *and* recompute every local input hash and size."""
    if not verify_preflight_manifest_seal(manifest):
        return False
    try:
        root = _root(corpus_root)
        for case in manifest["cases"]:
            for item in case["inputs"]:
                path, relative_path = _regular_child(root, item["relative_path"])
                actual_hash, actual_size = _file_sha256(path)
                if relative_path != item["relative_path"] or actual_hash != item["sha256"] or actual_size != item["size_bytes"]:
                    return False
        return True
    except CorpusPreflightError:
        return False


def write_preflight_manifest(*, manifest: Mapping[str, Any], destination: str | Path) -> Path:
    """Persist a sealed manifest exactly once, read-only, without overwriting."""
    if not verify_preflight_manifest_seal(manifest):
        raise CorpusPreflightError("preflight_manifest_seal_invalid")
    path = Path(destination)
    if path.is_symlink() or path.exists() or path.parent.is_symlink() or not path.parent.is_dir():
        raise CorpusPreflightError("preflight_destination_unsafe_or_exists")
    encoded = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o400)
    except OSError as exc:
        raise CorpusPreflightError("preflight_destination_unsafe_or_exists") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o400)
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise
    return path
