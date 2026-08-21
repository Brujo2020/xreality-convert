"""Fail-closed capability check for an executable multi-view Shape backend.

The MLX single-image port and the upstream CUDA project share source files, but
that is not evidence that the installed MLX Shape pipeline consumes camera
labelled image dictionaries. This module keeps that distinction explicit.
"""

from __future__ import annotations

from pathlib import Path
import os


REQUIRED_CAMERA_TAGS = ("front", "right", "back", "left")
MULTIVIEW_SUBFOLDER = "hunyuan3d-dit-v2-mv"


def inspect_hunyuan2mv_install(weights_dir: Path) -> dict:
    """Check for a completed local checkpoint without importing PyTorch."""
    model_dir = weights_dir / MULTIVIEW_SUBFOLDER
    config = model_dir / "config.yaml"
    weights = [model_dir / "model.fp16.safetensors", model_dir / "model.fp16.ckpt"]
    if not weights_dir.is_dir():
        return {"installed": False, "reason_code": "multiview_weights_missing"}
    if not config.is_file():
        return {"installed": False, "reason_code": "multiview_config_missing"}
    if not any(item.is_file() and item.stat().st_size > 1024 ** 3 for item in weights):
        return {"installed": False, "reason_code": "multiview_weights_incomplete"}
    return {
        "installed": True,
        "model": "tencent/Hunyuan3D-2mv",
        "subfolder": MULTIVIEW_SUBFOLDER,
        "weights_dir": str(weights_dir.resolve()),
    }


def inspect_multiview_shape_backend(source_root: Path) -> dict:
    """Return whether the installed MLX Shape runtime can execute real multi-view."""
    weights_dir = Path(os.environ.get("XREALITY_MULTIVIEW_WEIGHTS_DIR", source_root.parent / "models" / "Hunyuan3D-2mv"))
    install = inspect_hunyuan2mv_install(weights_dir)
    if install["installed"]:
        # The checkpoint is a PyTorch/MPS candidate, not an MLX conversion.
        # A physical-Mac arena result is still required before execution is on.
        return {
            "available": False,
            "state": "installed_not_certified",
            "reason_code": "multiview_physical_mac_certification_required",
            "provider_candidate": "hunyuan3d-2mv-pytorch",
            "required_camera_tags": list(REQUIRED_CAMERA_TAGS),
            **install,
        }

    pipeline_path = source_root / "hy3dshape" / "hy3dshape" / "pipeline_mlx.py"
    if not pipeline_path.is_file():
        return {
            "available": False,
            "state": "not_installed",
            "reason_code": "mlx_shape_pipeline_missing",
            "required_camera_tags": list(REQUIRED_CAMERA_TAGS),
        }

    source = pipeline_path.read_text(encoding="utf-8")
    has_multiview_input = "preprocess_multiview" in source or "MVImageProcessor" in source
    has_camera_semantics = all(
        f'"{tag}"' in source or f"'{tag}'" in source for tag in REQUIRED_CAMERA_TAGS
    )
    if has_multiview_input and has_camera_semantics:
        return {
            "available": True,
            "state": "ready",
            "provider": "hunyuan3d-2.1-mlx-multiview",
            "required_camera_tags": list(REQUIRED_CAMERA_TAGS),
        }

    return {
        "available": False,
        "state": "not_installed",
        "reason_code": install["reason_code"],
        "required_camera_tags": list(REQUIRED_CAMERA_TAGS),
        "detail": "El ShapePipeline MLX instalado sólo ejecuta una referencia; no se usarán vistas extra como evidencia de forma.",
    }
