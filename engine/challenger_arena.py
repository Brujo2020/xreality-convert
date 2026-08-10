"""Sealed, local-only shadow arena for Image-to-3D providers.

The arena is deliberately *not* a routing mechanism.  It consumes sealed
provider reports for an already-sealed corpus, checks that the exact pinned
provider and its offline preflight were used, then produces a deterministic
shadow ranking.  A ranking is evidence for a human decision, never permission
to replace the Hunyuan incumbent or to promote an output to master.

No network, model loading, or subprocess execution is performed here.  Those
actions belong to the individual isolated workers; this module only judges the
facts they record.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


ARENA_SCHEMA_VERSION = 1
HEX40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
ROLES = {"incumbent", "challenger"}
LANES = {"geometry", "uv", "textures", "materials", "visual"}


class ArenaContractError(ValueError):
    """Raised when an arena declaration, not a provider result, is unsafe."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _without_seal(value: Mapping[str, Any]) -> dict[str, Any]:
    copied = deepcopy(dict(value))
    copied.pop("seal", None)
    return copied


def seal_provider_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a content-addressed immutable-form provider report.

    Workers should call this only after their output, metrics, and preflight
    facts have been written.  Re-sealing a valid report is deterministic.
    """
    sealed = _without_seal(report)
    sealed["seal"] = {"algorithm": "sha256", "value": _digest(sealed)}
    return sealed


def verify_provider_report_seal(report: Mapping[str, Any]) -> bool:
    seal = report.get("seal")
    return (
        isinstance(seal, Mapping)
        and seal.get("algorithm") == "sha256"
        and isinstance(seal.get("value"), str)
        and SHA256.fullmatch(seal["value"]) is not None
        and seal["value"] == _digest(_without_seal(report))
    )


def _require_id(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ArenaContractError(reason)
    return value


def _require_revision(value: Any, reason: str) -> str:
    if not isinstance(value, str) or HEX40.fullmatch(value) is None:
        raise ArenaContractError(reason)
    return value


def _normalise_pins(pins: Any, *, prefix: str) -> dict[str, Any]:
    if not isinstance(pins, Mapping):
        raise ArenaContractError(f"{prefix}_pins_required")
    model = pins.get("model")
    if not isinstance(model, Mapping):
        raise ArenaContractError(f"{prefix}_model_pin_required")
    repo = _require_id(model.get("repo"), f"{prefix}_model_repo_required")
    revision = _require_revision(model.get("revision"), f"{prefix}_model_revision_unpinned")
    result: dict[str, Any] = {"model": {"repo": repo, "revision": revision}}
    code = pins.get("code")
    if code is not None:
        if not isinstance(code, Mapping):
            raise ArenaContractError(f"{prefix}_code_pin_invalid")
        result["code"] = {"revision": _require_revision(code.get("revision"), f"{prefix}_code_revision_unpinned")}
    return result


def validate_arena_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an arena declaration before accepting reports."""
    if not isinstance(spec, Mapping) or spec.get("schema_version") != ARENA_SCHEMA_VERSION:
        raise ArenaContractError("unsupported_arena_schema_version")
    arena_id = _require_id(spec.get("arena_id"), "arena_id_required")
    corpus_sha256 = spec.get("corpus_sha256")
    if not isinstance(corpus_sha256, str) or SHA256.fullmatch(corpus_sha256) is None:
        raise ArenaContractError("sealed_corpus_sha256_required")
    raw_cases = spec.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ArenaContractError("arena_cases_required")
    cases: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, Mapping):
            raise ArenaContractError("invalid_arena_case")
        case_id = _require_id(raw_case.get("id"), "case_id_required")
        if case_id in seen_cases:
            raise ArenaContractError(f"duplicate_case:{case_id}")
        seen_cases.add(case_id)
        required_lanes = raw_case.get("required_lanes")
        if not isinstance(required_lanes, list) or not required_lanes:
            raise ArenaContractError(f"case_lanes_required:{case_id}")
        if any(not isinstance(lane, str) for lane in required_lanes):
            raise ArenaContractError(f"invalid_case_lane:{case_id}")
        lanes = sorted(set(required_lanes))
        if any(lane not in LANES for lane in lanes):
            raise ArenaContractError(f"unknown_case_lane:{case_id}")
        cases.append({"id": case_id, "required_lanes": lanes})

    raw_providers = spec.get("providers")
    if not isinstance(raw_providers, list) or len(raw_providers) < 2:
        raise ArenaContractError("arena_providers_required")
    providers: list[dict[str, Any]] = []
    seen_providers: set[str] = set()
    incumbents = challengers = 0
    for raw_provider in raw_providers:
        if not isinstance(raw_provider, Mapping):
            raise ArenaContractError("invalid_provider")
        provider_id = _require_id(raw_provider.get("id"), "provider_id_required")
        if provider_id in seen_providers:
            raise ArenaContractError(f"duplicate_provider:{provider_id}")
        seen_providers.add(provider_id)
        role = raw_provider.get("role")
        if role not in ROLES:
            raise ArenaContractError(f"invalid_provider_role:{provider_id}")
        incumbents += role == "incumbent"
        challengers += role == "challenger"
        providers.append({"id": provider_id, "role": role, "pins": _normalise_pins(raw_provider.get("pins"), prefix="provider")})
    if incumbents != 1:
        raise ArenaContractError("exactly_one_incumbent_required")
    if challengers < 1:
        raise ArenaContractError("challenger_required")
    return {
        "schema_version": ARENA_SCHEMA_VERSION,
        "arena_id": arena_id,
        "corpus_sha256": corpus_sha256,
        "cases": sorted(cases, key=lambda item: item["id"]),
        "providers": sorted(providers, key=lambda item: item["id"]),
    }


def _report_reasons(spec_provider: Mapping[str, Any], spec: Mapping[str, Any], report: Any) -> tuple[list[str], dict[str, Any] | None]:
    """Validate a submitted provider report without trusting its self-claims."""
    if not isinstance(report, Mapping):
        return ["report_missing"], None
    reasons: list[str] = []
    if report.get("schema_version") != ARENA_SCHEMA_VERSION:
        reasons.append("unsupported_report_schema_version")
    if report.get("arena_id") != spec["arena_id"]:
        reasons.append("arena_id_mismatch")
    if report.get("provider_id") != spec_provider["id"]:
        reasons.append("provider_id_mismatch")
    if not verify_provider_report_seal(report):
        reasons.append("invalid_or_missing_report_seal")

    try:
        pins = _normalise_pins(report.get("pins"), prefix="report")
    except ArenaContractError as exc:
        reasons.append(str(exc))
        pins = None
    if pins is not None and pins != spec_provider["pins"]:
        reasons.append("provider_pin_mismatch")

    preflight = report.get("preflight")
    if not isinstance(preflight, Mapping):
        reasons.append("preflight_missing")
    else:
        if preflight.get("eligible") is not True:
            reasons.append("preflight_not_eligible")
        if preflight.get("promotion_ready") is not True:
            reasons.append("preflight_not_ready")
        if not isinstance(preflight.get("reasons"), list) or preflight["reasons"]:
            reasons.append("preflight_reasons_present")

    execution = report.get("execution")
    if not isinstance(execution, Mapping):
        reasons.append("execution_facts_missing")
    else:
        if execution.get("offline") is not True:
            reasons.append("execution_not_offline")
        if execution.get("network_allowed") is not False:
            reasons.append("execution_network_not_disabled")

    if report.get("corpus_sha256") != spec["corpus_sha256"]:
        reasons.append("corpus_hash_mismatch")
    cases, case_reasons = _validate_cases(spec, report.get("cases"))
    reasons.extend(case_reasons)
    if reasons:
        return sorted(set(reasons)), None

    quality_values = [score for case in cases for score in case["lane_scores"].values()]
    total_latency = sum(case["latency_seconds"] for case in cases)
    peak_memory = max(case["peak_memory_bytes"] for case in cases)
    return [], {
        "provider": spec_provider["id"],
        "role": spec_provider["role"],
        "cases": len(cases),
        "quality_score": round(sum(quality_values) / len(quality_values), 8),
        "mean_latency_seconds": round(total_latency / len(cases), 8),
        "peak_memory_bytes": peak_memory,
        "report_sha256": report["seal"]["value"],
    }


def _validate_cases(spec: Mapping[str, Any], submitted: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(submitted, list):
        return [], ["case_reports_missing"]
    expected = {case["id"]: case for case in spec["cases"]}
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    reasons: list[str] = []
    for raw_case in submitted:
        if not isinstance(raw_case, Mapping):
            reasons.append("invalid_case_report")
            continue
        case_id = raw_case.get("case_id")
        if not isinstance(case_id, str) or case_id not in expected or case_id in seen:
            reasons.append("unexpected_or_duplicate_case_report")
            continue
        seen.add(case_id)
        artifact = raw_case.get("artifact")
        if not isinstance(artifact, Mapping) or not isinstance(artifact.get("sha256"), str) or SHA256.fullmatch(artifact["sha256"]) is None:
            reasons.append(f"artifact_hash_missing:{case_id}")
        raw_lanes = raw_case.get("lanes")
        if not isinstance(raw_lanes, Mapping):
            reasons.append(f"lane_evidence_missing:{case_id}")
            continue
        lane_scores: dict[str, float] = {}
        for lane in expected[case_id]["required_lanes"]:
            evidence = raw_lanes.get(lane)
            if not isinstance(evidence, Mapping):
                reasons.append(f"lane_evidence_missing:{case_id}:{lane}")
                continue
            score = evidence.get("score")
            if evidence.get("status") != "pass" or evidence.get("evidence_class") != "measured" or isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
                reasons.append(f"lane_not_measured_pass:{case_id}:{lane}")
                continue
            if lane == "visual" and evidence.get("human_decision") != "pass":
                reasons.append(f"visual_human_review_missing:{case_id}")
                continue
            lane_scores[lane] = float(score)
        metrics = raw_case.get("metrics")
        if not isinstance(metrics, Mapping):
            reasons.append(f"metrics_missing:{case_id}")
            continue
        latency = metrics.get("latency_seconds")
        memory = metrics.get("peak_memory_bytes")
        if isinstance(latency, bool) or not isinstance(latency, (int, float)) or float(latency) < 0:
            reasons.append(f"invalid_latency:{case_id}")
        if not isinstance(memory, int) or isinstance(memory, bool) or memory < 0:
            reasons.append(f"invalid_peak_memory:{case_id}")
        if len(lane_scores) == len(expected[case_id]["required_lanes"]) and isinstance(latency, (int, float)) and not isinstance(latency, bool) and float(latency) >= 0 and isinstance(memory, int) and not isinstance(memory, bool) and memory >= 0:
            validated.append({
                "case_id": case_id,
                "lane_scores": lane_scores,
                "latency_seconds": float(latency),
                "peak_memory_bytes": memory,
            })
    for case_id in sorted(set(expected) - seen):
        reasons.append(f"case_report_missing:{case_id}")
    return sorted(validated, key=lambda item: item["case_id"]), reasons


def validate_provider_report(spec: Mapping[str, Any], report: Any) -> dict[str, Any]:
    """Return a fail-closed provider validation result for an expected report."""
    normalized = validate_arena_spec(spec)
    provider_id = report.get("provider_id") if isinstance(report, Mapping) else None
    provider = next((item for item in normalized["providers"] if item["id"] == provider_id), None)
    if provider is None:
        return {"eligible": False, "provider": provider_id, "reasons": ["unknown_provider"]}
    reasons, summary = _report_reasons(provider, normalized, report)
    return {"eligible": not reasons, "provider": provider["id"], "reasons": reasons, "summary": summary}


def run_local_arena(spec: Mapping[str, Any], reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rank fully evidenced providers in shadow mode; never change routing.

    A missing, duplicated, tampered, non-local, or incompletely preflighted
    report is ineligible.  It cannot win by being faster or by omitting an
    inconvenient measurement.
    """
    normalized = validate_arena_spec(spec)
    expected_provider_ids = {provider["id"] for provider in normalized["providers"]}
    by_provider: dict[str, Mapping[str, Any]] = {}
    duplicate_ids: set[str] = set()
    unrecognized_reports: list[str] = []
    for report in reports:
        provider_id = report.get("provider_id") if isinstance(report, Mapping) else None
        if not isinstance(provider_id, str) or provider_id not in expected_provider_ids:
            unrecognized_reports.append(provider_id if isinstance(provider_id, str) else "missing_provider_id")
            continue
        if provider_id in by_provider:
            duplicate_ids.add(provider_id)
        else:
            by_provider[provider_id] = report

    outcomes: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for provider in normalized["providers"]:
        if provider["id"] in duplicate_ids:
            outcome = {"provider": provider["id"], "role": provider["role"], "eligible": False, "reasons": ["duplicate_provider_reports"]}
        elif provider["id"] not in by_provider:
            outcome = {"provider": provider["id"], "role": provider["role"], "eligible": False, "reasons": ["provider_report_missing"]}
        else:
            reasons, summary = _report_reasons(provider, normalized, by_provider[provider["id"]])
            outcome = {"provider": provider["id"], "role": provider["role"], "eligible": not reasons, "reasons": reasons, "summary": summary}
            if not reasons and summary is not None:
                eligible.append(summary)
        outcomes.append(outcome)

    # Quality evidence leads. Performance breaks ties only after each required
    # lane has passed; provider id makes exact ties reproducible.
    ranking = sorted(
        eligible,
        key=lambda item: (-item["quality_score"], item["mean_latency_seconds"], item["peak_memory_bytes"], item["provider"]),
    )
    incumbent = next(item["id"] for item in normalized["providers"] if item["role"] == "incumbent")
    incumbent_rank = next((item for item in ranking if item["provider"] == incumbent), None)
    challenger_ranks = [item for item in ranking if item["role"] == "challenger"]
    if unrecognized_reports:
        shadow = {"status": "inconclusive", "reason": "unrecognized_provider_reports", "shadow_winner": None}
    elif incumbent_rank is None or not challenger_ranks:
        shadow = {"status": "inconclusive", "reason": "incumbent_or_challenger_evidence_ineligible", "shadow_winner": None}
    else:
        shadow_winner = ranking[0]["provider"]
        shadow = {
            "status": "challenger_outperforms_incumbent" if shadow_winner != incumbent else "incumbent_retains_shadow_lead",
            "reason": "deterministic_sealed_evidence_ranking",
            "shadow_winner": shadow_winner,
        }
    result = {
        "schema_version": ARENA_SCHEMA_VERSION,
        "arena_id": normalized["arena_id"],
        "corpus_sha256": normalized["corpus_sha256"],
        "mode": "local_sealed_shadow_only",
        "provider_results": outcomes,
        "unrecognized_provider_reports": sorted(unrecognized_reports),
        "ranking": ranking,
        "shadow_outcome": shadow,
        "promotion": {
            "allowed": False,
            "status": "human_review_required",
            "reason": "arena_ranking_never_changes_provider_routing_or_master_status",
        },
    }
    result["seal"] = {"algorithm": "sha256", "value": _digest(result)}
    return result


# A short name is convenient for callers while retaining the safety semantics
# in the public documentation and result mode.
run_arena = run_local_arena


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="sealed local arena declaration JSON")
    parser.add_argument("--report", action="append", required=True, help="sealed provider report JSON; repeat per provider")
    parser.add_argument("--output", help="optional local result JSON path")
    args = parser.parse_args(argv)
    result = run_local_arena(_load_json(args.spec), [_load_json(path) for path in args.report])
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
