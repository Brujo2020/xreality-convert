"""Deterministic evaluator for the 30-case local Buffalo acceptance campaign.

This module deliberately does *not* run a model, read a device sensor, or
download anything.  Isolated workers produce per-case reports elsewhere.  The
campaign evaluator merely verifies their content-addressed statements against
a sealed manifest and aggregates evidence without turning absent measurement
into an optimistic score.

The fixed case inventory prevents a convenient subset of examples from being
presented as a full benchmark.  A changed asset, missing gate, extra case, or
post-seal edit is a contract error, rather than a soft warning.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


CAMPAIGN_SCHEMA_VERSION = 1
EXPECTED_CASE_IDS = (
    "product-ceramic-mug", "product-glass-bottle", "product-metal-tool",
    "product-painted-electronics", "product-plastic-toy", "product-sneaker",
    "product-watch", "product-wood-furniture", "vehicle-bicycle", "vehicle-car",
    "industrial-crane", "industrial-machine", "architecture-facade", "architecture-room",
    "construction-excavator", "construction-scaffold", "warehouse-rack", "warehouse-pallet",
    "organic-human", "organic-animal", "organic-hair-detail", "organic-foliage",
    "thin-part-cable", "thin-part-chair", "reflective-chrome", "transmissive-glass",
    "text-logo-orientation", "multimaterial-product", "hidden-geometry-limited", "low-light-reference",
)
REQUIRED_GATES = ("geometry", "uv", "texture", "material", "memory", "canonical_review")
GATE_STATUSES = frozenset({"pass", "fail", "inconclusive", "not_measured"})
MEASURED_GATE_STATUSES = frozenset({"pass", "fail", "inconclusive"})
METRICS = ("latency_seconds", "peak_memory_bytes")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class CampaignIntegrityError(ValueError):
    """A campaign, case report, or cryptographic binding is malformed."""


@dataclass(frozen=True)
class CampaignCase:
    """One fixed local acceptance case bound to its expected input asset."""

    case_id: str
    asset_sha256: str
    required_gates: tuple[str, ...] = REQUIRED_GATES


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _without_seal(value: Mapping[str, Any]) -> dict[str, Any]:
    copied = deepcopy(dict(value))
    copied.pop("seal", None)
    return copied


def _require_text(value: Any, reason: str, *, maximum: int = 160) -> str:
    if not isinstance(value, str) or not value.strip() or value.strip() != value or len(value) > maximum:
        raise CampaignIntegrityError(reason)
    return value


def _require_hash(value: Any, reason: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise CampaignIntegrityError(reason)
    return value


def _normalise_gates(value: Any, *, case_id: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise CampaignIntegrityError(f"required_gates_missing:{case_id}")
    if any(not isinstance(gate, str) for gate in value):
        raise CampaignIntegrityError(f"invalid_required_gate:{case_id}")
    gates = sorted(set(value))
    if len(gates) != len(value) or tuple(gates) != tuple(sorted(REQUIRED_GATES)):
        raise CampaignIntegrityError(f"required_gates_mismatch:{case_id}")
    return gates


def default_campaign_cases(asset_hashes: Mapping[str, str]) -> tuple[CampaignCase, ...]:
    """Create the exact 30 cases, rejecting an incomplete or surplus map."""
    if not isinstance(asset_hashes, Mapping) or set(asset_hashes) != set(EXPECTED_CASE_IDS):
        raise CampaignIntegrityError("campaign_asset_inventory_mismatch")
    return tuple(CampaignCase(case_id, _require_hash(asset_hashes[case_id], f"asset_hash_invalid:{case_id}")) for case_id in EXPECTED_CASE_IDS)


def build_campaign_manifest(campaign_id: str, asset_hashes: Mapping[str, str]) -> dict[str, Any]:
    """Build a sealable local-only manifest for the full immutable inventory."""
    campaign_id = _require_text(campaign_id, "campaign_id_required")
    cases = default_campaign_cases(asset_hashes)
    return seal_campaign_manifest({
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "execution": {"offline": True, "network_allowed": False},
        "cases": [
            {"case_id": case.case_id, "asset": {"sha256": case.asset_sha256}, "required_gates": list(case.required_gates)}
            for case in cases
        ],
    })


def validate_campaign_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalise a manifest before trusting any case report."""
    if not isinstance(manifest, Mapping) or manifest.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
        raise CampaignIntegrityError("unsupported_campaign_schema_version")
    campaign_id = _require_text(manifest.get("campaign_id"), "campaign_id_required")
    execution = manifest.get("execution")
    if not isinstance(execution, Mapping) or execution.get("offline") is not True or execution.get("network_allowed") is not False:
        raise CampaignIntegrityError("campaign_must_be_local_offline")
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != len(EXPECTED_CASE_IDS):
        raise CampaignIntegrityError("campaign_must_contain_exactly_30_cases")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise CampaignIntegrityError("invalid_campaign_case")
        case_id = _require_text(raw_case.get("case_id"), "case_id_required")
        if case_id in normalized or case_id not in EXPECTED_CASE_IDS:
            raise CampaignIntegrityError(f"unexpected_or_duplicate_case:{case_id}")
        asset = raw_case.get("asset")
        if not isinstance(asset, Mapping):
            raise CampaignIntegrityError(f"case_asset_missing:{case_id}")
        normalized[case_id] = {
            "case_id": case_id,
            "asset": {"sha256": _require_hash(asset.get("sha256"), f"asset_hash_invalid:{case_id}")},
            "required_gates": _normalise_gates(raw_case.get("required_gates"), case_id=case_id),
        }
    if tuple(normalized) != EXPECTED_CASE_IDS:
        raise CampaignIntegrityError("campaign_case_inventory_mismatch")
    return {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "execution": {"offline": True, "network_allowed": False},
        "cases": [normalized[case_id] for case_id in EXPECTED_CASE_IDS],
    }


def seal_campaign_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    normalized = validate_campaign_manifest(_without_seal(manifest))
    normalized["seal"] = {"algorithm": "sha256", "value": _digest(normalized)}
    return normalized


def verify_campaign_manifest_seal(manifest: Mapping[str, Any]) -> bool:
    try:
        seal = manifest.get("seal")
        return (
            isinstance(seal, Mapping) and seal.get("algorithm") == "sha256"
            and isinstance(seal.get("value"), str) and SHA256.fullmatch(seal["value"]) is not None
            and seal["value"] == _digest(validate_campaign_manifest(_without_seal(manifest)))
        )
    except (CampaignIntegrityError, AttributeError):
        return False


def seal_case_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Content-address a completed local worker report; it is not an approval."""
    copied = _without_seal(report)
    copied["seal"] = {"algorithm": "sha256", "value": _digest(copied)}
    return copied


def verify_case_report_seal(report: Mapping[str, Any]) -> bool:
    try:
        seal = report.get("seal")
        return (
            isinstance(seal, Mapping) and seal.get("algorithm") == "sha256"
            and isinstance(seal.get("value"), str) and SHA256.fullmatch(seal["value"]) is not None
            and seal["value"] == _digest(_without_seal(report))
        )
    except (AttributeError, TypeError):
        return False


def _normalise_gate(value: Any, *, gate: str, asset_sha256: str, case_id: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise CampaignIntegrityError(f"gate_missing:{case_id}:{gate}")
    status = value.get("status")
    evidence_class = value.get("evidence_class")
    if status not in GATE_STATUSES:
        raise CampaignIntegrityError(f"gate_status_invalid:{case_id}:{gate}")
    if status in MEASURED_GATE_STATUSES and evidence_class != "measured":
        raise CampaignIntegrityError(f"gate_measurement_class_invalid:{case_id}:{gate}")
    if status == "not_measured" and evidence_class != "not_measured":
        raise CampaignIntegrityError(f"gate_not_measured_class_invalid:{case_id}:{gate}")
    if _require_hash(value.get("asset_sha256"), f"gate_asset_hash_invalid:{case_id}:{gate}") != asset_sha256:
        raise CampaignIntegrityError(f"gate_asset_hash_mismatch:{case_id}:{gate}")
    return {"status": status, "evidence_class": evidence_class, "asset_sha256": asset_sha256}


def _normalise_metrics(value: Any, *, case_id: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != set(METRICS):
        raise CampaignIntegrityError(f"campaign_metrics_inventory_mismatch:{case_id}")
    normalized: dict[str, dict[str, Any]] = {}
    for metric in METRICS:
        entry = value[metric]
        if not isinstance(entry, Mapping) or entry.get("status") not in {"measured", "not_measured"}:
            raise CampaignIntegrityError(f"metric_status_invalid:{case_id}:{metric}")
        if entry["status"] == "not_measured":
            if set(entry) != {"status"}:
                raise CampaignIntegrityError(f"metric_not_measured_payload_invalid:{case_id}:{metric}")
            normalized[metric] = {"status": "not_measured"}
            continue
        if set(entry) != {"status", "value"} or isinstance(entry["value"], bool) or not isinstance(entry["value"], (int, float)):
            raise CampaignIntegrityError(f"metric_value_invalid:{case_id}:{metric}")
        number = float(entry["value"])
        if not math.isfinite(number) or number < 0:
            raise CampaignIntegrityError(f"metric_value_invalid:{case_id}:{metric}")
        if metric == "peak_memory_bytes" and not number.is_integer():
            raise CampaignIntegrityError(f"metric_value_invalid:{case_id}:{metric}")
        normalized[metric] = {"status": "measured", "value": int(number) if metric == "peak_memory_bytes" else number}
    return normalized


def _normalise_case_report(report: Any, case: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    case_id = case["case_id"]
    if not isinstance(report, Mapping):
        raise CampaignIntegrityError(f"case_report_missing:{case_id}")
    if not verify_case_report_seal(report):
        raise CampaignIntegrityError(f"case_report_seal_invalid:{case_id}")
    if report.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
        raise CampaignIntegrityError(f"case_report_schema_invalid:{case_id}")
    if report.get("campaign_id") != manifest["campaign_id"] or report.get("case_id") != case_id:
        raise CampaignIntegrityError(f"case_report_identity_mismatch:{case_id}")
    execution = report.get("execution")
    if not isinstance(execution, Mapping) or execution.get("offline") is not True or execution.get("network_allowed") is not False:
        raise CampaignIntegrityError(f"case_report_not_local_offline:{case_id}")
    asset = report.get("asset")
    expected_hash = case["asset"]["sha256"]
    if not isinstance(asset, Mapping) or _require_hash(asset.get("sha256"), f"case_asset_hash_invalid:{case_id}") != expected_hash:
        raise CampaignIntegrityError(f"case_asset_hash_mismatch:{case_id}")
    gates = report.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != set(case["required_gates"]):
        raise CampaignIntegrityError(f"case_gate_inventory_mismatch:{case_id}")
    normalized_gates = {gate: _normalise_gate(gates[gate], gate=gate, asset_sha256=expected_hash, case_id=case_id) for gate in case["required_gates"]}
    return {
        "case_id": case_id,
        "asset": {"sha256": expected_hash},
        "gates": normalized_gates,
        "metrics": _normalise_metrics(report.get("metrics"), case_id=case_id),
        "report_sha256": report["seal"]["value"],
    }


def _metric_summary(cases: Sequence[Mapping[str, Any]], metric: str) -> dict[str, Any]:
    values = [case["metrics"][metric]["value"] for case in cases if case["metrics"][metric]["status"] == "measured"]
    missing = len(cases) - len(values)
    summary: dict[str, Any] = {"measured_cases": len(values), "not_measured_cases": missing}
    if values:
        summary.update({"min": min(values), "max": max(values), "mean": round(sum(values) / len(values), 8)})
    return summary


def evaluate_offline_campaign(manifest: Mapping[str, Any], reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Evaluate exactly one full 30-case local campaign, fail-closed.

    ``reports`` must contain one sealed report for every manifest case.  A
    status of ``not_measured`` is recorded separately and makes the strict
    campaign fail; it is never recast as an inferred pass.
    """
    if not verify_campaign_manifest_seal(manifest):
        raise CampaignIntegrityError("campaign_manifest_seal_invalid")
    normalized_manifest = validate_campaign_manifest(_without_seal(manifest))
    if not isinstance(reports, Sequence) or isinstance(reports, (str, bytes)) or len(reports) != len(EXPECTED_CASE_IDS):
        raise CampaignIntegrityError("campaign_reports_must_contain_exactly_30_cases")
    supplied: dict[str, Mapping[str, Any]] = {}
    for report in reports:
        if not isinstance(report, Mapping):
            raise CampaignIntegrityError("invalid_case_report")
        case_id = report.get("case_id")
        if not isinstance(case_id, str) or case_id in supplied or case_id not in EXPECTED_CASE_IDS:
            raise CampaignIntegrityError("unexpected_or_duplicate_case_report")
        supplied[case_id] = report
    if tuple(supplied) != EXPECTED_CASE_IDS:
        raise CampaignIntegrityError("campaign_report_inventory_mismatch")
    cases = [_normalise_case_report(supplied[case["case_id"]], case, normalized_manifest) for case in normalized_manifest["cases"]]
    gate_counts = {"measured_pass": 0, "measured_fail": 0, "measured_inconclusive": 0, "not_measured": 0}
    failed_cases: list[dict[str, str]] = []
    for case in cases:
        for gate, evidence in case["gates"].items():
            status = evidence["status"]
            if status == "pass":
                gate_counts["measured_pass"] += 1
            elif status == "fail":
                gate_counts["measured_fail"] += 1
                failed_cases.append({"case_id": case["case_id"], "gate": gate, "status": status})
            elif status == "inconclusive":
                gate_counts["measured_inconclusive"] += 1
                failed_cases.append({"case_id": case["case_id"], "gate": gate, "status": status})
            else:
                gate_counts["not_measured"] += 1
                failed_cases.append({"case_id": case["case_id"], "gate": gate, "status": status})
    payload = {
        "schema_version": CAMPAIGN_SCHEMA_VERSION,
        "campaign_id": normalized_manifest["campaign_id"],
        "execution": {"offline": True, "network_allowed": False},
        "manifest_sha256": manifest["seal"]["value"],
        "case_count": len(cases),
        "cases": cases,
        "gate_aggregate": {"total": sum(gate_counts.values()), **gate_counts},
        "metrics": {metric: _metric_summary(cases, metric) for metric in METRICS},
        "passed": not failed_cases,
        "failed_or_incomplete_gates": failed_cases,
    }
    payload["campaign_sha256"] = _digest(payload)
    return payload
