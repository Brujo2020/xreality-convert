"""One-shot worker for the official Hunyuan3D-2 multi-view Shape model.

This is intentionally a separate PyTorch/MPS candidate, not a claim that the
single-image MLX port has multi-view support. It accepts only sealed local
files, permits no downloads, and supports the four camera labels trained by
the public Hunyuan3D-2mv checkpoint.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from multiview_contract import MultiViewContractError, admit_multiview_shape


HORIZONTAL_VIEWS = ("front", "right", "back", "left")


class MultiViewWorkerError(RuntimeError):
    pass


def load_manifest(path: Path) -> dict[str, Path]:
    """Read and validate a sealed manifest; top/bottom stay evidence-only."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MultiViewWorkerError("multiview_manifest_invalid") from exc
    views = payload.get("views") if isinstance(payload, dict) else None
    profile = payload.get("profile", "xreal") if isinstance(payload, dict) else "xreal"
    try:
        admission = admit_multiview_shape(views, profile=profile)
    except MultiViewContractError as exc:
        raise MultiViewWorkerError(str(exc)) from exc
    if not admission["passed"]:
        raise MultiViewWorkerError("multiview_six_camera_coverage_required")

    paths: dict[str, Path] = {}
    for item in views:
        view_id = item["view_id"]
        file_path = item.get("file_path")
        if view_id in HORIZONTAL_VIEWS:
            if not isinstance(file_path, str) or not Path(file_path).is_file():
                raise MultiViewWorkerError(f"multiview_image_missing:{view_id}")
            resolved = Path(file_path).resolve()
            actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual_hash != item["sha256"]:
                raise MultiViewWorkerError(f"multiview_image_hash_mismatch:{view_id}")
            paths[view_id] = resolved
    if "front" not in paths:
        raise MultiViewWorkerError("multiview_real_front_required")
    return paths


def load_pipeline(weights_dir: Path, source_dir: Path, device: str):
    if not weights_dir.is_dir():
        raise MultiViewWorkerError("multiview_weights_missing")
    if not (source_dir / "hy3dgen").is_dir():
        raise MultiViewWorkerError("multiview_runtime_source_missing")
    sys.path.insert(0, str(source_dir))
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    # The worker must never transform a missing local weight into a download.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    return Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        str(weights_dir),
        subfolder="hunyuan3d-dit-v2-mv",
        use_safetensors=True,
        device=device,
    )


def run(manifest_path: Path, output_path: Path, *, steps: int, guidance: float, octree_resolution: int,
        weights_dir: Path, source_dir: Path, device: str) -> dict:
    started = time.monotonic()
    pipeline = None
    try:
        image_dict = load_manifest(manifest_path)
        pipeline = load_pipeline(weights_dir, source_dir, device)
        result = pipeline(
            image={name: str(path) for name, path in image_dict.items()},
            num_inference_steps=steps,
            guidance_scale=guidance,
            octree_resolution=octree_resolution,
            output_type="trimesh",
        )
        mesh = result[0] if isinstance(result, (list, tuple)) else result
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(output_path))
        return {
            "passed": True,
            "provider": "hunyuan3d-2mv-pytorch",
            "model": str(weights_dir),
            "camera_views_used": [view for view in HORIZONTAL_VIEWS if view in image_dict],
            "evidence_only_views": ["top", "bottom"],
            "output_glb": str(output_path),
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
    finally:
        del pipeline
        gc.collect()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run sealed Hunyuan3D-2mv Shape inference")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--guidance", type=float, required=True)
    parser.add_argument("--octree-resolution", type=int, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--device", default="mps")
    args = parser.parse_args(argv)
    report = run(args.manifest, args.output, steps=args.steps, guidance=args.guidance,
                 octree_resolution=args.octree_resolution, weights_dir=args.weights,
                 source_dir=args.source, device=args.device)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
