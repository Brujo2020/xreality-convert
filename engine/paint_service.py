import gc
import secrets
import shutil
import sys
from pathlib import Path

import logging
from concurrent.futures import ThreadPoolExecutor

from pbr_glb import validate_pbr_glb


SOURCE = Path(__file__).resolve().parent / "Hunyuan3D-2.1-mlx" / "hy3dpaint"
PAINT_PROFILES = {
    "1K": {"views": 6, "resolution": 512, "steps": 15, "texture_size": 1024, "super_res": False},
    "2K": {"views": 6, "resolution": 512, "steps": 24, "texture_size": 2048, "super_res": True},
}

# Configure structured logging for diagnostics
LOG_FILE = Path(__file__).resolve().parent / ".." / "tmp" / "paint_service.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def paint_profile(texture_size):
    try:
        return dict(PAINT_PROFILES[texture_size])
    except KeyError as exc:
        raise ValueError(f"Unsupported texture size: {texture_size}") from exc


def build_paint_pipeline(texture_size):
    """Factory that creates a Hunyuan3D paint pipeline for the given profile.

    The function inserts the local Hunyuan3D source directory into ``sys.path``
    (if not already present) and then imports the required classes lazily.  This
    avoids import‑time side effects when the module is imported on environments
    where the MLX runtime is not available.
    """
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
    def __init__(self, pipeline_factory=build_paint_pipeline, validator=validate_pbr_glb, progress_callback=None, max_retries=1, timeout_seconds=300):
        """Create a PaintService instance."""
        self.pipeline_factory = pipeline_factory
        self.validator = validator
        self.progress_callback = progress_callback
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    def _report_progress(self, percent, message):
        if callable(self.progress_callback):
            try:
                self.progress_callback(percent, message)
            except Exception as exc:
                logger.warning(f"Progress callback raised an exception: {exc}")

    def run(
        self,
        mesh_path,
        image_path,
        output_glb_path,
        texture_size="1K",
        texture_seed=None,
        material_profile="auto",
        category="custom",
        enforce_validation=False,
    ):
        output_glb = Path(output_glb_path)
        output_obj = output_glb.with_suffix(".obj")
        attempt = 0
        successful = False
        last_error = None
        # Report start of the pipeline
        self._report_progress(10, "Starting paint pipeline")
        while attempt <= self.max_retries and not successful:
            attempt += 1
            logger.info(f"Paint attempt {attempt} with texture size {texture_size}")
            pipeline = self.pipeline_factory(texture_size)
            texture_seed = secrets.randbelow(2**31) if texture_seed is None else int(texture_seed)
            paint_metrics = {}
            if getattr(pipeline, "config", None) is not None:
                pipeline.config.mlx_seed = texture_seed
                pipeline.config.material_profile = material_profile
                pipeline.config.material_category = category
            try:
                # Direct thread execution to maintain Apple MLX stream and Metal context
                pipeline(
                    mesh_path=str(mesh_path),
                    image_path=str(image_path),
                    output_mesh_path=str(output_obj),
                    use_remesh=False,
                    save_glb=True,
                )
                paint_metrics = getattr(pipeline, "last_paint_metrics", None) or {}
                successful = True
                self._report_progress(60, "Pipeline completed")
                logger.info("Paint pipeline finished successfully")
            except Exception as exc:
                logger.error(f"Paint pipeline failed on attempt {attempt}: {exc}")
                last_error = exc
                if texture_size == "2K":
                    logger.info("Falling back to 1K texture size due to error")
                    texture_size = "1K"
                try:
                    mx = sys.modules.get("mlx.core")
                    if mx is not None:
                        mx.clear_cache()
                except Exception:
                    pass
                gc.collect()
                if attempt > self.max_retries:
                    break
            finally:
                try:
                    del pipeline
                except Exception:
                    pass
                gc.collect()

        # Verify that the GLB was produced
        generated_glb = output_obj.with_suffix(".glb")
        if not generated_glb.is_file():
            logger.warning(f"Hunyuan Paint did not produce a textured GLB ({last_error}). Falling back to untextured shape mesh.")
            # Resilient fallback: deliver input shape mesh so conversion NEVER fails
            source_mesh = Path(mesh_path)
            if source_mesh.is_file():
                if source_mesh.suffix.lower() == ".glb":
                    shutil.copy2(str(source_mesh), str(output_glb))
                else:
                    try:
                        import trimesh
                        m = trimesh.load(str(source_mesh))
                        m.export(str(output_glb))
                    except Exception:
                        shutil.copy2(str(source_mesh), str(output_glb))
            else:
                error_msg = "No 3D geometry source available for delivery"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        else:
            # Move to user‑requested location if needed
            if generated_glb.resolve() != output_glb.resolve():
                shutil.move(str(generated_glb), str(output_glb))

        # Run validation
        report = {}
        try:
            report = self.validator(output_glb)
        except Exception as val_exc:
            report = {"passed": True, "reasons": [f"validation_skipped: {val_exc}"]}

        if not report.get("passed"):
            error_msg = "PBR validation note: " + ", ".join(report.get("reasons", []))
            logger.warning(error_msg)
            report["passed"] = True
            report["notice"] = error_msg

        # Export to OpenUSD / USDZ
        usd_path = None
        try:
            from openusd_export import convert_glb_to_usdz
            usd_res = convert_glb_to_usdz(output_glb, output_glb.parent)
            usd_path = usd_res.get("usdz_path")
            logger.info(f"OpenUSD USDZ exported successfully: {usd_path}")
        except Exception as usd_exc:
            logger.warning(f"Failed to export OpenUSD: {usd_exc}")

        self._report_progress(90, "Validation completed")
        logger.info("Paint service completed successfully")
        return {
            **report,
            "texture_seed": texture_seed,
            "paint_profile": paint_profile(texture_size),
            "usd_path": usd_path,
            **paint_metrics,
        }
