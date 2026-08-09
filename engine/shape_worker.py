"""One-shot, offline Hunyuan3D Shape worker for unified-memory Macs.

The parent process owns job state and validation.  This executable owns only
the MLX model lifetime: it loads Shape, emits one GLB, and exits so Metal and
Python allocations are reclaimed before Paint begins.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Hunyuan3D-2.1-mlx"
if SOURCE.exists():
    sys.path.insert(0, str(SOURCE))


def _extract_mesh(result):
    return result[0] if isinstance(result, (list, tuple)) else result


def _patch_mlx_runtime():
    """Keep isolated output numerically aligned with the resident MLX path."""
    model_file = SOURCE / "hy3dshape" / "hy3dshape" / "models" / "autoencoders" / "model_mlx.py"
    if not model_file.exists():
        return
    source = model_file.read_text()
    broken = "grid_logits[grid_logits == -10000.0] = float('nan')"
    fixed = (
        "grid_logits[grid_logits == -10000.0] = -100.0\\n"
        "        grid_logits = np.nan_to_num(grid_logits, nan=-100.0, posinf=100.0, neginf=-100.0)"
    )
    if broken in source:
        model_file.write_text(source.replace(broken, fixed))


def _load_pipeline():
    # Keep this process fully local. StageSupervisor also supplies these
    # variables, but setting defaults makes manual invocation equally safe.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from m5_optimizer import apply_m5_optimizations
    from hy3dshape.hy3dshape.pipeline_mlx import ShapePipeline

    optimizer = apply_m5_optimizations()
    _patch_mlx_runtime()
    model_id = os.environ.get("HUNYUAN3D_MLX_WEIGHTS_DIR") or "dgrauet/hunyuan3d-2.1-mlx"
    return ShapePipeline.from_pretrained(model_id), optimizer, model_id


def run(input_path, output_path, *, steps, guidance, octree_resolution):
    started = time.monotonic()
    pipeline = optimizer = None
    try:
        pipeline, optimizer, model_id = _load_pipeline()
        mesh = _extract_mesh(
            pipeline(
                str(input_path),
                num_inference_steps=steps,
                guidance_scale=guidance,
                octree_resolution=octree_resolution,
            )
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_path))
        runtime = optimizer.snapshot() if optimizer is not None else {}
        return {
            "passed": True,
            "provider": "hunyuan3d-2.1-mlx",
            "model": model_id,
            "output_glb": str(output_path),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "runtime": runtime,
        }
    finally:
        del pipeline
        gc.collect()
        if optimizer is not None:
            optimizer.clear_cache()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run a local Hunyuan3D MLX Shape stage")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--guidance", type=float, required=True)
    parser.add_argument("--octree-resolution", type=int, required=True)
    args = parser.parse_args(argv)
    if not args.input.is_file():
        raise SystemExit("input_missing")
    report = run(
        args.input.resolve(), args.output.resolve(), steps=args.steps,
        guidance=args.guidance, octree_resolution=args.octree_resolution,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
