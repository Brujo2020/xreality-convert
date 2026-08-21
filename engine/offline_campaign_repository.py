"""Durable, local-only storage for one sealed 30-case campaign.

``offline_campaign`` owns the evidence contract and aggregate mathematics.
This module owns the deliberately smaller persistence boundary: a repository
can contain a manifest, exactly one already-sealed report for each fixed case,
and one immutable final aggregate.  It neither starts workers nor treats a
filesystem file as evidence merely because it happens to be JSON.

The implementation rejects symlinks and caller-selected filenames throughout.
This is an accidental-mutation and path-substitution guard, not a claim that
file permissions constrain a machine administrator.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from offline_campaign import (
    CAMPAIGN_SCHEMA_VERSION,
    EXPECTED_CASE_IDS,
    CampaignIntegrityError,
    evaluate_offline_campaign,
    validate_campaign_manifest,
    verify_campaign_manifest_seal,
    verify_case_report_seal,
)


CAMPAIGN_REPOSITORY_SCHEMA_VERSION = 1
CAMPAIGN_FINAL_KIND = "xreality_offline_campaign_final"
_CAMPAIGN_ID = re.compile(r"^[a-z][a-z0-9_-]{0,95}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class CampaignRepositoryError(ValueError):
    """A local campaign repository violates its exclusive evidence contract."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _normalise_campaign_id(value: Any) -> str:
    if not isinstance(value, str) or _CAMPAIGN_ID.fullmatch(value) is None:
        raise CampaignRepositoryError("campaign_repository_id_invalid")
    return value


def _root(value: str | Path) -> Path:
    """Accept only an existing real directory, without silently following it."""
    raw = Path(value)
    if raw.is_symlink() or not raw.is_dir():
        raise CampaignRepositoryError("campaign_repository_root_unsafe")
    root = raw.absolute()
    # Reject symlink hops from the selected root down.  Parent symlinks are
    # outside this managed boundary; accepting them would make temporary test
    # roots and application sandboxes needlessly unusable.
    if root.is_symlink():
        raise CampaignRepositoryError("campaign_repository_root_unsafe")
    return root


def _safe_child(root: Path, *parts: str, must_exist: bool = False) -> Path:
    current = root
    for part in parts:
        if not isinstance(part, str) or not part or part in {".", ".."} or "/" in part or "\\" in part:
            raise CampaignRepositoryError("campaign_repository_path_unsafe")
        current = current / part
        if current.exists() and current.is_symlink():
            raise CampaignRepositoryError("campaign_repository_path_unsafe")
    if must_exist and (current.is_symlink() or not current.is_file()):
        raise CampaignRepositoryError("campaign_repository_record_missing")
    try:
        current.relative_to(root)
    except ValueError as exc:  # defensive even though parts are restricted
        raise CampaignRepositoryError("campaign_repository_path_unsafe") from exc
    return current


def _campaign_dir(repository_root: str | Path, campaign_id: str, *, required: bool) -> Path:
    root = _root(repository_root)
    campaign_id = _normalise_campaign_id(campaign_id)
    parent = _safe_child(root, "campaigns")
    if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
        raise CampaignRepositoryError("campaign_repository_path_unsafe")
    directory = _safe_child(root, "campaigns", campaign_id)
    if required and (directory.is_symlink() or not directory.is_dir()):
        raise CampaignRepositoryError("campaign_repository_campaign_missing")
    return directory


def _verify_repository_layout(directory: Path) -> None:
    """Reject surprise files before treating a directory as campaign evidence."""
    allowed = {"manifest.json", "reports", "final.json"}
    try:
        children = tuple(directory.iterdir())
    except OSError as exc:
        raise CampaignRepositoryError("campaign_repository_path_unsafe") from exc
    for child in children:
        if child.is_symlink() or child.name not in allowed:
            raise CampaignRepositoryError("campaign_repository_path_unsafe")
        if child.name == "reports":
            if not child.is_dir():
                raise CampaignRepositoryError("campaign_repository_path_unsafe")
            try:
                reports = tuple(child.iterdir())
            except OSError as exc:
                raise CampaignRepositoryError("campaign_repository_path_unsafe") from exc
            expected = {f"{case_id}.json" for case_id in EXPECTED_CASE_IDS}
            for report in reports:
                if report.is_symlink() or not report.is_file() or report.name not in expected:
                    raise CampaignRepositoryError("campaign_repository_path_unsafe")
        elif not child.is_file():
            raise CampaignRepositoryError("campaign_repository_path_unsafe")


def _write_exclusive_sealed(path: Path, value: Mapping[str, Any], *, exists_code: str) -> None:
    if path.exists() or path.is_symlink() or path.parent.is_symlink():
        raise CampaignRepositoryError(exists_code if path.exists() else "campaign_repository_path_unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise CampaignRepositoryError("campaign_repository_path_unsafe")
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o400)
    except FileExistsError as exc:
        raise CampaignRepositoryError(exists_code) from exc
    except OSError as exc:
        raise CampaignRepositoryError("campaign_repository_path_unsafe") from exc
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


def _read_sealed_json(path: Path, *, invalid_code: str) -> Mapping[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CampaignRepositoryError(invalid_code)
    try:
        if path.stat().st_mode & 0o222:
            raise CampaignRepositoryError("campaign_repository_record_not_sealed")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignRepositoryError(invalid_code) from exc
    if not isinstance(value, Mapping):
        raise CampaignRepositoryError(invalid_code)
    return value


def _manifest_path(directory: Path) -> Path:
    return _safe_child(directory, "manifest.json")


def _report_path(directory: Path, case_id: str) -> Path:
    if case_id not in EXPECTED_CASE_IDS:
        raise CampaignRepositoryError("campaign_repository_case_invalid")
    return _safe_child(directory, "reports", f"{case_id}.json")


def _final_path(directory: Path) -> Path:
    return _safe_child(directory, "final.json")


def seal_campaign_manifest_in_repository(
    *, repository_root: str | Path, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one campaign directory and seal its already-sealed manifest.

    The caller cannot choose a file name, overwrite a campaign, or create an
    unsealed manifest.  Reports are deliberately not accepted here.
    """
    if not verify_campaign_manifest_seal(manifest):
        raise CampaignRepositoryError("campaign_repository_manifest_seal_invalid")
    try:
        normalized = validate_campaign_manifest({key: value for key, value in manifest.items() if key != "seal"})
    except CampaignIntegrityError as exc:
        raise CampaignRepositoryError("campaign_repository_manifest_invalid") from exc
    campaign_id = _normalise_campaign_id(normalized["campaign_id"])
    directory = _campaign_dir(repository_root, campaign_id, required=False)
    if directory.exists() or directory.is_symlink():
        raise CampaignRepositoryError("campaign_repository_campaign_already_exists")
    parent = directory.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise CampaignRepositoryError("campaign_repository_path_unsafe")
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise CampaignRepositoryError("campaign_repository_campaign_already_exists") from exc
    try:
        _write_exclusive_sealed(_manifest_path(directory), dict(manifest), exists_code="campaign_repository_manifest_already_exists")
    except BaseException:
        # A failed initial write must not leave a reusable campaign namespace.
        # Do not recursively remove: it may have been altered concurrently.
        try:
            if directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()):
                directory.rmdir()
        finally:
            raise
    return load_campaign_manifest(repository_root=repository_root, campaign_id=campaign_id)


def load_campaign_manifest(*, repository_root: str | Path, campaign_id: str) -> dict[str, Any]:
    """Read the fixed manifest only if the persisted bytes remain sealed."""
    directory = _campaign_dir(repository_root, campaign_id, required=True)
    _verify_repository_layout(directory)
    manifest = _read_sealed_json(_manifest_path(directory), invalid_code="campaign_repository_manifest_missing_or_invalid")
    if not verify_campaign_manifest_seal(manifest):
        raise CampaignRepositoryError("campaign_repository_manifest_seal_invalid")
    try:
        normalized = validate_campaign_manifest({key: value for key, value in manifest.items() if key != "seal"})
    except CampaignIntegrityError as exc:
        raise CampaignRepositoryError("campaign_repository_manifest_invalid") from exc
    if normalized["campaign_id"] != campaign_id:
        raise CampaignRepositoryError("campaign_repository_manifest_identity_mismatch")
    return deepcopy(dict(manifest))


def seal_case_report_in_repository(
    *, repository_root: str | Path, campaign_id: str, report: Mapping[str, Any],
) -> dict[str, Any]:
    """Store one pre-sealed report at its deterministic expected-case path."""
    manifest = load_campaign_manifest(repository_root=repository_root, campaign_id=campaign_id)
    directory = _campaign_dir(repository_root, campaign_id, required=True)
    _verify_repository_layout(directory)
    if _final_path(directory).exists() or _final_path(directory).is_symlink():
        raise CampaignRepositoryError("campaign_repository_already_finalized")
    if not verify_case_report_seal(report):
        raise CampaignRepositoryError("campaign_repository_report_seal_invalid")
    case_id = report.get("case_id") if isinstance(report, Mapping) else None
    if not isinstance(case_id, str) or case_id not in EXPECTED_CASE_IDS:
        raise CampaignRepositoryError("campaign_repository_case_invalid")
    if report.get("campaign_id") != campaign_id:
        raise CampaignRepositoryError("campaign_repository_cross_campaign_report")
    # Let the canonical evaluator vet this report against the exact manifest
    # without accepting a partial campaign as a result.  The direct checks
    # below give the repository a precise case identity before persistence.
    expected = next(item for item in manifest["cases"] if item["case_id"] == case_id)
    if report.get("asset", {}).get("sha256") != expected["asset"]["sha256"]:
        raise CampaignRepositoryError("campaign_repository_report_asset_mismatch")
    destination = _report_path(directory, case_id)
    _write_exclusive_sealed(destination, dict(report), exists_code="campaign_repository_duplicate_case_report")
    return load_case_report(repository_root=repository_root, campaign_id=campaign_id, case_id=case_id)


def load_case_report(*, repository_root: str | Path, campaign_id: str, case_id: str) -> dict[str, Any]:
    """Read one report, still requiring its original worker seal."""
    load_campaign_manifest(repository_root=repository_root, campaign_id=campaign_id)
    directory = _campaign_dir(repository_root, campaign_id, required=True)
    report = _read_sealed_json(_report_path(directory, case_id), invalid_code="campaign_repository_report_missing_or_invalid")
    if not verify_case_report_seal(report):
        raise CampaignRepositoryError("campaign_repository_report_seal_invalid")
    if report.get("campaign_id") != campaign_id or report.get("case_id") != case_id:
        raise CampaignRepositoryError("campaign_repository_report_identity_mismatch")
    return deepcopy(dict(report))


def _final_payload(manifest: Mapping[str, Any], aggregate: Mapping[str, Any]) -> dict[str, Any]:
    case_hashes = [
        {"case_id": case["case_id"], "report_sha256": case["report_sha256"]}
        for case in aggregate["cases"]
    ]
    return {
        "schema_version": CAMPAIGN_REPOSITORY_SCHEMA_VERSION,
        "kind": CAMPAIGN_FINAL_KIND,
        "campaign_id": manifest["campaign_id"],
        "manifest_sha256": manifest["seal"]["value"],
        "report_count": len(case_hashes),
        "reports": case_hashes,
        "aggregate": deepcopy(dict(aggregate)),
    }


def finalize_campaign_repository(*, repository_root: str | Path, campaign_id: str) -> dict[str, Any]:
    """Aggregate precisely the 30 sealed stored reports and seal final.json."""
    manifest = load_campaign_manifest(repository_root=repository_root, campaign_id=campaign_id)
    directory = _campaign_dir(repository_root, campaign_id, required=True)
    _verify_repository_layout(directory)
    final = _final_path(directory)
    if final.exists() or final.is_symlink():
        raise CampaignRepositoryError("campaign_repository_already_finalized")
    reports = [
        load_case_report(repository_root=repository_root, campaign_id=campaign_id, case_id=case_id)
        for case_id in EXPECTED_CASE_IDS
    ]
    try:
        aggregate = evaluate_offline_campaign(manifest, reports)
    except CampaignIntegrityError as exc:
        raise CampaignRepositoryError(f"campaign_repository_aggregate_invalid:{exc}") from exc
    payload = _final_payload(manifest, aggregate)
    payload["final_sha256"] = _digest(payload)
    _write_exclusive_sealed(final, payload, exists_code="campaign_repository_already_finalized")
    return verify_finalized_campaign(repository_root=repository_root, campaign_id=campaign_id)


def verify_finalized_campaign(*, repository_root: str | Path, campaign_id: str) -> dict[str, Any]:
    """Recompute aggregate from every stored report and bind it to final.json."""
    manifest = load_campaign_manifest(repository_root=repository_root, campaign_id=campaign_id)
    directory = _campaign_dir(repository_root, campaign_id, required=True)
    _verify_repository_layout(directory)
    record = _read_sealed_json(_final_path(directory), invalid_code="campaign_repository_final_missing_or_invalid")
    final_hash = record.get("final_sha256")
    if not isinstance(final_hash, str) or _SHA256.fullmatch(final_hash) is None:
        raise CampaignRepositoryError("campaign_repository_final_hash_invalid")
    unsigned = dict(record)
    unsigned.pop("final_sha256", None)
    if _digest(unsigned) != final_hash:
        raise CampaignRepositoryError("campaign_repository_final_integrity_mismatch")
    reports = [
        load_case_report(repository_root=repository_root, campaign_id=campaign_id, case_id=case_id)
        for case_id in EXPECTED_CASE_IDS
    ]
    try:
        aggregate = evaluate_offline_campaign(manifest, reports)
    except CampaignIntegrityError as exc:
        raise CampaignRepositoryError(f"campaign_repository_aggregate_invalid:{exc}") from exc
    expected = _final_payload(manifest, aggregate)
    expected["final_sha256"] = _digest(expected)
    if dict(record) != expected:
        raise CampaignRepositoryError("campaign_repository_final_content_mismatch")
    return deepcopy(expected)


__all__ = [
    "CAMPAIGN_FINAL_KIND", "CAMPAIGN_REPOSITORY_SCHEMA_VERSION", "CampaignRepositoryError",
    "finalize_campaign_repository", "load_campaign_manifest", "load_case_report",
    "seal_campaign_manifest_in_repository", "seal_case_report_in_repository",
    "verify_finalized_campaign",
]
