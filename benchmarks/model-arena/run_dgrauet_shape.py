"""Run one revision-pinned dgrauet Hunyuan3D Shape arena case."""

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import mlx.core as mx

from hy3dshape.pipeline_mlx import ShapePipeline


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--octree-resolution", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def _swap_used_bytes():
    output = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "vm.swapusage"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    used_mb = float(output.split("used = ", 1)[1].split("M", 1)[0])
    return round(used_mb * 1024 * 1024)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    args = _arguments()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "dgrauet-hunyuan-shape.glb"
    swap_before = _swap_used_bytes()
    mx.reset_peak_memory()
    load_started = time.perf_counter()
    pipeline = ShapePipeline.from_pretrained(str(Path(args.weights).resolve()))
    load_seconds = time.perf_counter() - load_started
    started = time.perf_counter()
    mesh = pipeline(
        str(Path(args.image).resolve()),
        num_inference_steps=args.steps,
        octree_resolution=args.octree_resolution,
        seed=args.seed,
    )
    inference_seconds = time.perf_counter() - started
    mesh.export(output)
    report = {
        "status": "pass",
        "model": "dgrauet/hunyuan3d-2.1-mlx",
        "source": str(Path(args.image).resolve()),
        "weights": str(Path(args.weights).resolve()),
        "seed": args.seed,
        "steps": args.steps,
        "octree_resolution": args.octree_resolution,
        "load_seconds": round(load_seconds, 3),
        "inference_seconds": round(inference_seconds, 3),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "mlx_active_gb": round(mx.get_active_memory() / 1e9, 3),
        "mlx_peak_gb": round(mx.get_peak_memory() / 1e9, 3),
        "process_max_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 3),
        "swap_delta_bytes": max(0, _swap_used_bytes() - swap_before),
        "glb": str(output),
        "glb_bytes": output.stat().st_size,
        "glb_sha256": _sha256(output),
    }
    report_path = output_dir / "run-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
