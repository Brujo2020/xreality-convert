"""Compatibility runner for measuring the legacy resident Shape invocation.

It deliberately uses server.get_pipeline and the former call contract, but is
launched by the benchmark as a child so a native MLX crash cannot kill the
control process or erase evidence.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import server


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--guidance", type=float, required=True)
    parser.add_argument("--octree-resolution", type=int, required=True)
    args = parser.parse_args(argv)
    pipeline = None
    started = time.monotonic()
    try:
        pipeline = server.get_pipeline()
        mesh = server.extract_mesh(pipeline(
            str(args.input.resolve()), num_inference_steps=args.steps,
            guidance_scale=args.guidance, octree_resolution=args.octree_resolution,
        ))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(args.output)
        report = {
            "passed": True,
            "provider": "hunyuan3d-2.1-mlx-resident-compat",
            "output_glb": str(args.output.resolve()),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "runtime": server.m5_optimizer.snapshot() if server.m5_optimizer else {},
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    finally:
        if pipeline is not None:
            server.release_shape_pipeline(pipeline)
            server.settle_shape_memory()


if __name__ == "__main__":
    main()
