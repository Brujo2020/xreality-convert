import gc
import secrets
import shutil
import sys
from pathlib import Path

from pbr_glb import validate_pbr_glb


SOURCE = Path(__file__).resolve().parent / "Hunyuan3D-2.1-mlx" / "hy3dpaint"
PAINT_PROFILES = {
    "1K": {"views": 6, "resolution": 512, "steps": 15, "texture_size": 1024, "super_res": False},
    "2K": {"views": 6, "resolution": 512, "steps": 24, "texture_size": 2048, "super_res": True},
}


def paint_profile(texture_size):
    try:
        return dict(PAINT_PROFILES[texture_size])
    except KeyError as exc:
        raise ValueError(f"Unsupported texture size: {texture_size}") from exc


def build_paint_pipeline(texture_size):
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    from textureGenPipeline_mlx import Hunyuan3DPaintConfigMLX, Hunyuan3DPaintPipelineMLX

    profile = paint_profile(texture_size)
    config = Hunyuan3DPaintConfigMLX(profile["views"], profile["resolution"])
    config.mlx_num_inference_steps = profile["steps"]
    config.texture_size = profile["texture_size"]
    config.render_size = profile["texture_size"]
    config.use_mlx_super_res = profile["super_res"]
    return Hunyuan3DPaintPipelineMLX(config)


class PaintService:
    def __init__(self, pipeline_factory=build_paint_pipeline, validator=validate_pbr_glb):
        self.pipeline_factory = pipeline_factory
        self.validator = validator

    def run(
        self,
        mesh_path,
        image_path,
        output_glb_path,
        texture_size="2K",
        texture_seed=None,
        material_profile="auto",
        category="custom",
    ):
        output_glb = Path(output_glb_path)
        output_obj = output_glb.with_suffix(".obj")
        pipeline = self.pipeline_factory(texture_size)
        texture_seed = secrets.randbelow(2**31) if texture_seed is None else int(texture_seed)
        paint_metrics = {}
        if getattr(pipeline, "config", None) is not None:
            pipeline.config.mlx_seed = texture_seed
            pipeline.config.material_profile = material_profile
            pipeline.config.material_category = category
        try:
            pipeline(
                mesh_path=str(mesh_path),
                image_path=str(image_path),
                output_mesh_path=str(output_obj),
                use_remesh=False,
                save_glb=True,
            )
            paint_metrics = getattr(pipeline, "last_paint_metrics", None) or {}
        finally:
            del pipeline
            gc.collect()
            try:
                mx = sys.modules.get("mlx.core")
                if mx is not None:
                    mx.clear_cache()
            except Exception:
                pass

        generated_glb = output_obj.with_suffix(".glb")
        if not generated_glb.is_file():
            raise RuntimeError("Hunyuan Paint did not produce a GLB")
        if generated_glb != output_glb:
            shutil.move(str(generated_glb), str(output_glb))
        report = self.validator(output_glb)
        if not report.get("passed"):
            raise RuntimeError("PBR validation failed: " + ", ".join(report.get("reasons", [])))
        report = {
            **report,
            "texture_seed": texture_seed,
            "paint_profile": paint_profile(texture_size),
            **paint_metrics,
        }
        return report
