"""Run one revision-pinned dgrauet Hunyuan3D Paint arena case."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import time
from pathlib import Path

import mlx.core as mx

from paint_service import PaintService


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--profile", choices=("1K", "2K"), default="1K")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--category", default="custom")
    parser.add_argument("--material-profile", default="auto")
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
    output = output_dir / "dgrauet-hunyuan-paint.glb"
    swap_before = _swap_used_bytes()
    mx.reset_peak_memory()
    started = time.perf_counter()
    audit = PaintService().run(
        mesh_path=Path(args.mesh).resolve(),
        image_path=Path(args.image).resolve(),
        output_glb_path=output,
        texture_size=args.profile,
        texture_seed=args.seed,
        material_profile=args.material_profile,
        category=args.category,
    )
    elapsed_seconds = time.perf_counter() - started
    report = {
        "status": "pass",
        "model": "dgrauet/hunyuan3d-2.1-mlx",
        "mesh": str(Path(args.mesh).resolve()),
        "image": str(Path(args.image).resolve()),
        "seed": args.seed,
        "profile": args.profile,
        "category": args.category,
        "material_profile": args.material_profile,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "mlx_active_gb": round(mx.get_active_memory() / 1e9, 3),
        "mlx_peak_gb": round(mx.get_peak_memory() / 1e9, 3),
        "process_max_rss_gb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 3
        ),
        "swap_delta_bytes": max(0, _swap_used_bytes() - swap_before),
        "glb": str(output),
        "glb_bytes": output.stat().st_size,
        "glb_sha256": _sha256(output),
        "audit": audit,
    }
    report_path = output_dir / "run-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
