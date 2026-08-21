#!/usr/bin/env python3
"""Run real, offline Blender canonical evidence for one sealed Xreality job.

This is deliberately an operator entrypoint, not a fixture generator.  It
accepts only the immutable inputs created by ``/stage-validation-artifacts``
and delegates all rendering to :class:`BlenderCanonicalValidationService`.
It never manufactures a render, substitutes a renderer, or promotes MASTER.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping


APP_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = APP_ROOT / "engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from blender_validation_service import BlenderCanonicalValidationService, BlenderValidationError
from buffalo_runtime import ContractError, JobLedger


class CanonicalE2EAdmissionError(RuntimeError):
    """The local E2E invocation is not entitled to launch Blender."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise CanonicalE2EAdmissionError(reason) from exc
    if not isinstance(value, dict):
        raise CanonicalE2EAdmissionError(reason)
    return value


def _is_read_only(path: Path) -> bool:
    # Immutable-on-disk is the portable seal available to this local runner.
    # ACLs and root privileges are not treated as a stronger proof.
    return path.is_file() and not bool(path.stat().st_mode & 0o222)


def _require_sealed_artifact(path: Path, record: Any, reason: str) -> None:
    if not isinstance(record, Mapping) or not path.is_file() or not _is_read_only(path):
        raise CanonicalE2EAdmissionError(reason)
    try:
        claimed_path = Path(str(record["path"])).resolve()
        claimed_bytes = int(record["bytes"])
        claimed_hash = str(record["sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CanonicalE2EAdmissionError(reason) from exc
    if claimed_path != path.resolve() or claimed_bytes != path.stat().st_size or claimed_hash != _sha256(path):
        raise CanonicalE2EAdmissionError(reason)


def load_staged_inputs(*, jobs_root: str | Path, job_id: str) -> tuple[JobLedger, Path, Path]:
    """Resolve precisely the signed, immutable validation inputs for one job."""
    root = Path(jobs_root).resolve()
    # JobLedger creates its directory by design.  Do the non-mutating check
    # first so an invalid CLI invocation cannot manufacture a job shell.
    candidate = (root / job_id).resolve()
    if (
        not root.is_dir()
        or not job_id
        or any(char not in "0123456789abcdef-" for char in job_id)
        or not candidate.is_dir()
        or not candidate.is_relative_to(root)
    ):
        raise CanonicalE2EAdmissionError("unsafe_or_missing_job")
    try:
        ledger = JobLedger.load(root, job_id)
    except ContractError as exc:
        raise CanonicalE2EAdmissionError("unsafe_or_missing_job") from exc
    if ledger.state == "DRAFT" or not ledger.contract_path.is_file() or not (ledger.job_dir / "evidence-manifest.json").is_file():
        raise CanonicalE2EAdmissionError("job_not_sealed")

    inputs = ledger.job_dir / "validation-inputs"
    asset = inputs / "asset.glb"
    projection = inputs / "projection-report.json"
    stage = _load_json(ledger.job_dir / "stages" / "validation_inputs.json", "validation_inputs_stage_missing")
    if stage.get("job_id") != job_id or stage.get("stage") != "validation_inputs" or stage.get("status") != "passed":
        raise CanonicalE2EAdmissionError("validation_inputs_not_passed")
    metadata = stage.get("metadata")
    if not isinstance(metadata, Mapping):
        raise CanonicalE2EAdmissionError("validation_inputs_not_sealed")
    _require_sealed_artifact(asset, metadata.get("glb"), "sealed_asset_mismatch")
    _require_sealed_artifact(projection, metadata.get("projection_report"), "sealed_projection_mismatch")
    return ledger, asset, projection


def _job_local_output(job_dir: Path, relative_output: str) -> Path:
    candidate = Path(relative_output)
    if candidate.is_absolute() or not relative_output or any(part == ".." for part in candidate.parts):
        raise CanonicalE2EAdmissionError("unsafe_output_directory")
    resolved = (job_dir / candidate).resolve()
    if resolved == job_dir.resolve() or job_dir.resolve() not in resolved.parents:
        raise CanonicalE2EAdmissionError("unsafe_output_directory")
    return resolved


def run_e2e(
    *,
    jobs_root: str | Path,
    job_id: str,
    output_dir: str = "canonical-blender-e2e",
    blender_executable: str = "blender",
    service_factory=BlenderCanonicalValidationService,
) -> dict[str, Any]:
    """Admit and run a single physical Blender validation attempt."""
    ledger, asset, projection = load_staged_inputs(jobs_root=jobs_root, job_id=job_id)
    output = _job_local_output(ledger.job_dir, output_dir)
    blender = shutil.which(blender_executable)
    if not blender:
        raise CanonicalE2EAdmissionError("blender_unavailable")

    result = service_factory(blender_executable=blender).run(
        job_dir=ledger.job_dir,
        glb_path=asset,
        projection_report_path=projection,
        output_dir=output,
    )
    if result.get("passed") is not True or result.get("promotion") != "human_review_required":
        raise CanonicalE2EAdmissionError("canonical_validation_not_human_review_only")
    return {
        "ok": True,
        "job_id": job_id,
        "validation": result,
        "promotion": "human_review_required",
        "network": "disabled_by_blender_validation_service",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs-root", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--output-dir", default="canonical-blender-e2e")
    parser.add_argument("--blender", default="blender")
    args = parser.parse_args(argv)
    try:
        result = run_e2e(
            jobs_root=args.jobs_root,
            job_id=args.job_id,
            output_dir=args.output_dir,
            blender_executable=args.blender,
        )
    except (CanonicalE2EAdmissionError, BlenderValidationError, ContractError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "promotion": "blocked"}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
