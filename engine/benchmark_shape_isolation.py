"""Run one local, apples-to-apples resident-vs-worker Shape parity trial."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

import trimesh
import server
from shape_parity import compare
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError
from agentic_paint_service import memory_snapshot
from secure_artifacts import validate_glb_container


def run_resident_compatibility(job_id, input_path, request):
    """Run legacy resident call in a child; native crashes become evidence."""
    output = server.JOBS_DIR / f"{job_id}-resident.glb"
    report_path = server.JOBS_DIR / f"{job_id}-resident-report.json"
    command = [
        server.sys.executable, str(server.ROOT / "resident_shape_runner.py"),
        "--input", str(Path(input_path).resolve()), "--output", str(output.resolve()),
        "--report", str(report_path.resolve()), "--steps", str(request.steps),
        "--guidance", str(request.guidance), "--octree-resolution", str(request.octree_resolution),
    ]
    try:
        StageSupervisor(memory_snapshot).run(
            command, cwd=server.ROOT.parent,
            limits=StageLimits(timeout_seconds=1800, minimum_free_percent=8, maximum_swap_growth_mb=2048),
        )
    except StageWorkerError as exc:
        raise RuntimeError(f"resident_compat_failed:{exc.reason_code}") from exc
    if not output.is_file() or not report_path.is_file():
        raise RuntimeError("resident_compat_missing_artifact")
    validate_glb_container(output)
    result = json.loads(report_path.read_text(encoding="utf-8"))
    if not result.get("passed") or Path(result.get("output_glb", "")).resolve() != output.resolve():
        raise RuntimeError("resident_compat_invalid_contract")
    return trimesh.load(str(output), force="mesh"), result, output, report_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark local Hunyuan Shape worker isolation")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--guidance", type=float, default=6.0)
    parser.add_argument("--octree-resolution", type=int, default=96)
    args = parser.parse_args(argv)
    if not args.input.is_file():
        raise SystemExit("input_missing")
    request = server.GenerateRequest(
        image_base64="a" * 32, steps=args.steps, guidance=args.guidance,
        octree_resolution=args.octree_resolution, texture=False,
    )
    job_id = f"parity-{uuid.uuid4().hex}"
    resident_glb = server.JOBS_DIR / f"{job_id}-resident.glb"
    resident_report = server.JOBS_DIR / f"{job_id}-resident-report.json"
    raw = server.JOBS_DIR / f"{job_id}-shape-worker.glb"
    worker_report = server.JOBS_DIR / f"{job_id}-shape-worker-report.json"
    try:
        resident, resident_run, _, _ = run_resident_compatibility(job_id, args.input.resolve(), request)
        worker, isolation = server.run_isolated_shape_worker(job_id, args.input.resolve(), request)
        report = compare(
            resident, worker, resident_seconds=resident_run["elapsed_seconds"],
            worker_seconds=isolation["worker"]["elapsed_seconds"],
        )
        report["artifacts"] = {"resident": str(resident_glb), "worker": str(raw)}
        report["resident_runtime"] = resident_run.get("runtime", {})
        report["worker_runtime"] = isolation["worker"].get("runtime", {})
        report["benchmark_scope"] = "cold child-process compatibility; persistent-server residency remains a separate measurement"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["promotion_recommended"] else 2
    except Exception as exc:
        # A denied admission or native child crash is a benchmark result, not
        # an invitation to retry until the host becomes unstable.
        report = {
            "schema_version": 1,
            "promotion_recommended": False,
            "reason_code": str(exc).split(":", 1)[0],
            "error": str(exc),
            "benchmark_scope": "cold child-process compatibility; failure is preserved for scheduling policy",
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    finally:
        resident_glb.unlink(missing_ok=True)
        resident_report.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
        worker_report.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
