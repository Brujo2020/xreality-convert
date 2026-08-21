#!/usr/bin/env python3
"""Run the fixed Buffalo corpus locally, one isolated worker at a time.

This is intentionally a thin *orchestrator*, not a benchmark implementation:
the supplied command owns inference and must write an already sealed
``offline_campaign`` case report.  The runner binds those reports to a sealed
corpus preflight and stores them in the immutable campaign repository.

The supervisor supplies the project's offline environment (including
``HF_HUB_OFFLINE=1``) and memory/swap watchdog.  It removes normal proxy
paths, but callers that need a kernel-level network denial must also run this
command in an OS network sandbox.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
from typing import Any, Callable, Mapping, Sequence


ENGINE_DIR = Path(__file__).resolve().parents[1] / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from agentic_paint_service import memory_snapshot
from offline_campaign import (
    build_campaign_manifest,
    verify_case_report_seal,
)
from offline_campaign_repository import (
    CampaignRepositoryError,
    finalize_campaign_repository,
    load_campaign_manifest,
    load_case_report,
    seal_campaign_manifest_in_repository,
    seal_case_report_in_repository,
)
from offline_corpus_preflight import (
    CorpusPreflightError,
    campaign_asset_hashes,
    verify_preflight_against_corpus,
    verify_preflight_manifest_seal,
)
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError


class OfflineCampaignRunnerError(RuntimeError):
    """The runner cannot safely execute or persist a campaign."""


_ALLOWED_FIELDS = frozenset({
    "campaign_id", "case_id", "corpus_root", "input_path", "output_path", "preflight_path",
})
_REQUIRED_FIELDS = frozenset({"case_id", "output_path"})


def _regular_directory(value: str | Path, *, code: str) -> Path:
    path = Path(value)
    if path.is_symlink() or not path.is_dir():
        raise OfflineCampaignRunnerError(code)
    return path.absolute()


def _read_json(path: str | Path, *, code: str) -> dict[str, Any]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise OfflineCampaignRunnerError(code)
    try:
        value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfflineCampaignRunnerError(code) from exc
    if not isinstance(value, dict):
        raise OfflineCampaignRunnerError(code)
    return value


def _template_fields(tokens: Sequence[str]) -> set[str]:
    fields: set[str] = set()
    formatter = __import__("string").Formatter()
    for token in tokens:
        try:
            parsed = tuple(formatter.parse(token))
        except ValueError as exc:
            raise OfflineCampaignRunnerError("command_template_invalid") from exc
        for _, field, format_spec, conversion in parsed:
            if field is None:
                continue
            # Attribute/index traversal and conversions provide no useful
            # capability here, and turn a simple command contract into a
            # surprising evaluator.
            if field not in _ALLOWED_FIELDS or format_spec or conversion:
                raise OfflineCampaignRunnerError("command_template_field_invalid")
            fields.add(field)
    return fields


def parse_command_template(template: str) -> tuple[str, ...]:
    """Accept an argv template, never a shell expression.

    Required fields guarantee that a worker is told both its exact case and
    its exclusive output path.  Since ``StageSupervisor`` receives argv, shell
    metacharacters are data rather than an injection route.
    """
    if not isinstance(template, str) or not template.strip():
        raise OfflineCampaignRunnerError("command_template_required")
    try:
        tokens = tuple(shlex.split(template))
    except ValueError as exc:
        raise OfflineCampaignRunnerError("command_template_invalid") from exc
    if not tokens:
        raise OfflineCampaignRunnerError("command_template_required")
    missing = _REQUIRED_FIELDS - _template_fields(tokens)
    if missing:
        raise OfflineCampaignRunnerError("command_template_missing_fields:" + ",".join(sorted(missing)))
    return tokens


def _render_command(tokens: Sequence[str], values: Mapping[str, str]) -> list[str]:
    try:
        return [token.format_map(values) for token in tokens]
    except (KeyError, ValueError) as exc:  # defensive after parse_command_template
        raise OfflineCampaignRunnerError("command_template_render_failed") from exc


def _load_preflight(*, preflight_path: str | Path, corpus_root: str | Path) -> dict[str, Any]:
    preflight = _read_json(preflight_path, code="preflight_manifest_missing_or_invalid")
    if not verify_preflight_manifest_seal(preflight):
        raise OfflineCampaignRunnerError("preflight_manifest_seal_invalid")
    if not verify_preflight_against_corpus(manifest=preflight, corpus_root=corpus_root):
        raise OfflineCampaignRunnerError("preflight_corpus_binding_invalid")
    return preflight


def _campaign_manifest_from_preflight(preflight: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return build_campaign_manifest(preflight["campaign_id"], campaign_asset_hashes(preflight))
    except (KeyError, CorpusPreflightError, ValueError) as exc:
        raise OfflineCampaignRunnerError("preflight_campaign_contract_invalid") from exc


def _open_or_seal_repository(*, repository_root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return seal_campaign_manifest_in_repository(repository_root=repository_root, manifest=manifest)
    except CampaignRepositoryError as exc:
        if "campaign_already_exists" not in str(exc):
            raise OfflineCampaignRunnerError(f"campaign_repository_failed:{exc}") from exc
    try:
        existing = load_campaign_manifest(repository_root=repository_root, campaign_id=manifest["campaign_id"])
    except (CampaignRepositoryError, KeyError) as exc:
        raise OfflineCampaignRunnerError("campaign_repository_existing_manifest_invalid") from exc
    if existing != manifest:
        raise OfflineCampaignRunnerError("campaign_repository_manifest_conflict")
    return existing


def _worker_output_path(*, workspace_root: Path, campaign_id: str, case_id: str) -> Path:
    # The runner owns a distinct transient directory.  It is intentionally not
    # inside the repository's campaign directory, whose layout is evidence-only.
    directory = workspace_root / "offline-campaign-worker-output" / campaign_id
    if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
        raise OfflineCampaignRunnerError("worker_output_directory_unsafe")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or not directory.is_dir():
        raise OfflineCampaignRunnerError("worker_output_directory_unsafe")
    output = directory / f"{case_id}.json"
    if output.exists() or output.is_symlink():
        raise OfflineCampaignRunnerError(f"worker_output_already_exists:{case_id}")
    return output


def _case_primary_input(preflight: Mapping[str, Any], case_id: str, corpus_root: Path) -> Path:
    case = next((item for item in preflight["cases"] if item["case_id"] == case_id), None)
    if not isinstance(case, Mapping) or not isinstance(case.get("asset"), Mapping):
        raise OfflineCampaignRunnerError(f"preflight_case_missing:{case_id}")
    relative = case["asset"].get("relative_path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise OfflineCampaignRunnerError(f"preflight_asset_path_invalid:{case_id}")
    path = corpus_root / relative
    try:
        path.relative_to(corpus_root)
    except ValueError as exc:
        raise OfflineCampaignRunnerError(f"preflight_asset_path_invalid:{case_id}") from exc
    if path.is_symlink() or not path.is_file():
        raise OfflineCampaignRunnerError(f"preflight_asset_path_invalid:{case_id}")
    return path


def run_offline_campaign(
    *,
    preflight_path: str | Path,
    corpus_root: str | Path,
    repository_root: str | Path,
    command_template: str,
    workspace_root: str | Path | None = None,
    limits: StageLimits = StageLimits(),
    snapshot: Callable[[], Mapping[str, float | None]] = memory_snapshot,
    supervisor_factory: Callable[[Callable[[], Mapping[str, float | None]]], StageSupervisor] = StageSupervisor,
) -> dict[str, Any]:
    """Execute missing cases serially and finalize the immutable repository.

    A pre-existing matching repository is resumed only by skipping its sealed
    reports; it never overwrites evidence or re-runs an already recorded case.
    Any worker failure stops the campaign before later cases start.
    """
    corpus = _regular_directory(corpus_root, code="corpus_root_unsafe")
    repository = _regular_directory(repository_root, code="repository_root_unsafe")
    workspace = _regular_directory(workspace_root or repository, code="workspace_root_unsafe")
    preflight_file = Path(preflight_path)
    preflight = _load_preflight(preflight_path=preflight_file, corpus_root=corpus)
    manifest = _campaign_manifest_from_preflight(preflight)
    manifest = _open_or_seal_repository(repository_root=repository, manifest=manifest)
    tokens = parse_command_template(command_template)

    completed: list[dict[str, Any]] = []
    for case in manifest["cases"]:
        case_id = case["case_id"]
        try:
            existing = load_case_report(
                repository_root=repository, campaign_id=manifest["campaign_id"], case_id=case_id,
            )
        except CampaignRepositoryError as exc:
            if "report_missing_or_invalid" not in str(exc):
                raise OfflineCampaignRunnerError(f"campaign_repository_report_invalid:{case_id}") from exc
        else:
            completed.append({"case_id": case_id, "status": "already_sealed", "report_sha256": existing["seal"]["value"]})
            continue

        output = _worker_output_path(workspace_root=workspace, campaign_id=manifest["campaign_id"], case_id=case_id)
        input_path = _case_primary_input(preflight, case_id, corpus)
        command = _render_command(tokens, {
            "campaign_id": manifest["campaign_id"],
            "case_id": case_id,
            "corpus_root": str(corpus),
            "input_path": str(input_path),
            "output_path": str(output),
            "preflight_path": str(preflight_file.absolute()),
        })
        try:
            telemetry = supervisor_factory(snapshot).run(
                command, cwd=corpus, limits=limits,
            )
        except StageWorkerError as exc:
            raise OfflineCampaignRunnerError(f"case_worker_failed:{case_id}:{exc.reason_code}") from exc
        report = _read_json(output, code=f"case_report_missing_or_invalid:{case_id}")
        if not verify_case_report_seal(report):
            raise OfflineCampaignRunnerError(f"case_report_seal_invalid:{case_id}")
        try:
            stored = seal_case_report_in_repository(
                repository_root=repository, campaign_id=manifest["campaign_id"], report=report,
            )
        except CampaignRepositoryError as exc:
            raise OfflineCampaignRunnerError(f"case_report_rejected:{case_id}:{exc}") from exc
        completed.append({
            "case_id": case_id,
            "status": "sealed",
            "report_sha256": stored["seal"]["value"],
            "worker": telemetry,
        })

    try:
        final = finalize_campaign_repository(repository_root=repository, campaign_id=manifest["campaign_id"])
    except CampaignRepositoryError as exc:
        raise OfflineCampaignRunnerError(f"campaign_finalize_failed:{exc}") from exc
    return {"campaign_id": manifest["campaign_id"], "completed_cases": completed, "final": final}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run sealed 30-case Buffalo corpus locally and sequentially.")
    parser.add_argument("--preflight", required=True, help="Read-only sealed preflight JSON")
    parser.add_argument("--corpus-root", required=True, help="Local corpus root bound by preflight")
    parser.add_argument("--repository-root", required=True, help="Existing local evidence repository root")
    parser.add_argument("--workspace-root", help="Existing local transient worker-output root (defaults to repository root)")
    parser.add_argument("--command-template", required=True, help="argv template; needs {case_id} and {output_path}")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--minimum-free-percent", type=float, default=8.0)
    parser.add_argument("--maximum-swap-growth-mb", type=float, default=2048.0)
    args = parser.parse_args(argv)
    try:
        result = run_offline_campaign(
            preflight_path=args.preflight,
            corpus_root=args.corpus_root,
            repository_root=args.repository_root,
            workspace_root=args.workspace_root,
            command_template=args.command_template,
            limits=StageLimits(
                timeout_seconds=args.timeout_seconds,
                minimum_free_percent=args.minimum_free_percent,
                maximum_swap_growth_mb=args.maximum_swap_growth_mb,
                network_allowed=False,
            ),
        )
    except OfflineCampaignRunnerError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps({"status": "completed", **result}, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
