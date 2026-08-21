"""Run the pinned AgenticVibes hybrid MLX/MPS paint lane without ComfyUI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import types
from pathlib import Path


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--paint-model", required=True)
    parser.add_argument("--dino-model", required=True)
    parser.add_argument("--mlx-weights", required=True)
    parser.add_argument("--agentic-repo", default="engine/AgenticVibes-Hunyuan3D-Paint")
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--view-size", type=int, default=512)
    parser.add_argument("--texture-size", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reference-lock", action="store_true")
    parser.add_argument("--min-facing", type=float, default=0.05)
    return parser.parse_args()


def _swap_used_mb():
    output = subprocess.run(
        ["/usr/sbin/sysctl", "-n", "vm.swapusage"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(output.split("used = ", 1)[1].split("M", 1)[0])


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _install_standalone_stubs(torch):
    folder_paths = types.ModuleType("folder_paths")
    sys.modules.setdefault("folder_paths", folder_paths)
    comfy = types.ModuleType("comfy")
    model_management = types.ModuleType("comfy.model_management")
    model_management.soft_empty_cache = torch.mps.empty_cache
    comfy.model_management = model_management
    sys.modules.setdefault("comfy", comfy)
    sys.modules.setdefault("comfy.model_management", model_management)
    lightning = types.ModuleType("pytorch_lightning")
    lightning.LightningModule = torch.nn.Module
    lightning.LightningDataModule = object
    sys.modules.setdefault("pytorch_lightning", lightning)


def main():
    args = _arguments()
    script_path = Path(__file__).resolve()
    repo_root = (
        script_path.parent.parent
        if script_path.parent.name == "engine"
        else script_path.parents[2]
    )
    agentic_repo = (repo_root / args.agentic_repo).resolve()
    rasterizer = agentic_repo / "hy3dpaint" / "custom_rasterizer"
    sys.path[:0] = [str(agentic_repo), str(rasterizer), str(repo_root / "engine")]
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    import mlx.core as mx
    import torch
    import trimesh

    _install_standalone_stubs(torch)
    from hy3dpaint.textureGenPipeline import (
        Hunyuan3DPaintConfig,
        Hunyuan3DPaintPipeline,
    )

    mesh_path = Path(args.mesh).resolve()
    image_path = Path(args.image).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_obj = output_dir / "agenticvibes-paint.obj"
    output_glb = output_obj.with_suffix(".glb")
    swap_before = _swap_used_mb()
    mx.reset_peak_memory()
    started = time.perf_counter()

    config = Hunyuan3DPaintConfig(
        args.view_size,
        [0, 90, 180, 270, 0, 180],
        [0, 0, 0, 0, 90, -90],
        [1, 0.1, 0.5, 0.1, 0.05, 0.05],
        1.0,
        args.texture_size,
        device="mps",
        paint_model_path=str(Path(args.paint_model).resolve()),
        dino_model_path=str(Path(args.dino_model).resolve()),
        mlx_weights_path=str(Path(args.mlx_weights).resolve()),
    )
    config.diffusion_backend = "mlx"
    pipeline = Hunyuan3DPaintPipeline(config)
    mesh = trimesh.load(mesh_path, force="mesh")

    phase = time.perf_counter()
    albedo, mr, _, _ = pipeline(
        mesh=mesh,
        image_path=str(image_path),
        num_steps=args.steps,
        guidance_scale=3.0,
        unwrap=True,
        seed=args.seed,
    )
    diffusion_seconds = time.perf_counter() - phase
    for index, image in enumerate(albedo):
        image.save(output_dir / f"albedo-view-{index}.png")

    phase = time.perf_counter()
    texture, mask, texture_mr, mask_mr = pipeline.bake_from_multiview(
        albedo,
        mr,
        config.candidate_camera_elevs,
        config.candidate_camera_azims,
        config.candidate_view_weights,
    )
    bake_seconds = time.perf_counter() - phase
    texture, texture_mr = pipeline.inpaint(
        texture, mask, texture_mr, mask_mr, False, "NS"
    )
    pipeline.set_texture_albedo(texture)
    pipeline.set_texture_mr(texture_mr)
    previous_cwd = Path.cwd()
    try:
        os.chdir(output_dir)
        pipeline.save_mesh(str(output_obj))
    finally:
        os.chdir(previous_cwd)

    report = {
        "status": "pass",
        "model": "AgenticVibes/hunyuan3d-2.1-mlx",
        "modelRevision": "06ff58f0778649cbfc18f393925373782c6a705b",
        "sourceRevision": "3d8e93106f4b91cfb3b24ffc311a3b432b091a86",
        "optimization": "release_duplicate_pytorch_unet",
        "steps": args.steps,
        "viewSize": args.view_size,
        "textureSize": args.texture_size,
        "seed": args.seed,
        "diffusionSeconds": round(diffusion_seconds, 3),
        "bakeSeconds": round(bake_seconds, 3),
        "elapsedSeconds": round(time.perf_counter() - started, 3),
        "mpsCurrentGb": round(torch.mps.current_allocated_memory() / 1e9, 3),
        "mpsDriverGb": round(torch.mps.driver_allocated_memory() / 1e9, 3),
        "mlxActiveGb": round(mx.get_active_memory() / 1e9, 3),
        "mlxPeakGb": round(mx.get_peak_memory() / 1e9, 3),
        "processMaxRssGb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 3
        ),
        "swapDeltaMb": round(max(0.0, _swap_used_mb() - swap_before), 2),
        "glb": str(output_glb),
        "glbBytes": output_glb.stat().st_size,
        "glbSha256": _sha256(output_glb),
    }
    if args.reference_lock:
        from reference_projection import run_projection

        locked_glb = output_dir / "agenticvibes-reference-locked.glb"
        projection = run_projection(
            output_glb,
            image_path,
            locked_glb,
            output_dir / "reference-lock-evidence",
            minimum_facing_cosine=args.min_facing,
        )
        report["referenceLock"] = projection
    report_path = output_dir / "run-report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
