"""Conservative visual gates for source-image texture projection."""

import math

import numpy as np
from PIL import Image


def _foreground_mask(image):
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    border = np.concatenate(
        (rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]),
        axis=0,
    )
    background = np.median(border, axis=0)
    distance = np.linalg.norm(rgb - background, axis=2) / 441.673
    return distance > 0.08, tuple(int(value) for value in background)


def _bbox(mask):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def align_reference_to_geometry(reference, geometry_render, size):
    """Align the photographed subject to the rendered 3D silhouette.

    Returns ``(aligned_image, report)``. A failed report deliberately returns
    ``None`` so callers keep the generated multiview albedo instead of
    projecting a visibly incompatible photograph onto the mesh.
    """
    reference = reference.convert("RGB")
    geometry_render = geometry_render.convert("RGB").resize(size)
    source_mask, source_background = _foreground_mask(reference)
    geometry_mask, _ = _foreground_mask(geometry_render)
    source_bbox = _bbox(source_mask)
    geometry_bbox = _bbox(geometry_mask)

    report = {
        "passed": False,
        "reason": None,
        "silhouette_iou": 0.0,
        "aspect_ratio_delta": None,
    }
    if source_bbox is None or geometry_bbox is None:
        report["reason"] = "foreground_not_detected"
        return None, report

    source_fraction = float(source_mask.mean())
    geometry_fraction = float(geometry_mask.mean())
    report["source_foreground_ratio"] = source_fraction
    report["geometry_foreground_ratio"] = geometry_fraction
    if not 0.01 <= source_fraction <= 0.95 or not 0.01 <= geometry_fraction <= 0.95:
        report["reason"] = "foreground_area_unreliable"
        return None, report

    sx0, sy0, sx1, sy1 = source_bbox
    gx0, gy0, gx1, gy1 = geometry_bbox
    source_width, source_height = sx1 - sx0, sy1 - sy0
    target_width, target_height = gx1 - gx0, gy1 - gy0
    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    aspect_delta = abs(math.log(source_aspect / target_aspect))
    report["aspect_ratio_delta"] = float(aspect_delta)
    if aspect_delta > 0.9:
        report["reason"] = "silhouette_aspect_mismatch"
        return None, report

    scale = min(target_width / source_width, target_height / source_height)
    fitted_size = (
        max(1, round(source_width * scale)),
        max(1, round(source_height * scale)),
    )
    paste_x = gx0 + (target_width - fitted_size[0]) // 2
    paste_y = gy0 + (target_height - fitted_size[1]) // 2

    resampling = getattr(Image, "Resampling", Image)
    source_crop = reference.crop(source_bbox).resize(
        fitted_size,
        resampling.LANCZOS,
    )
    fitted_mask = Image.fromarray(
        (source_mask[sy0:sy1, sx0:sx1] * 255).astype(np.uint8),
    ).resize(fitted_size, resampling.NEAREST)
    aligned = Image.new("RGB", size, source_background)
    aligned.paste(source_crop, (paste_x, paste_y), fitted_mask)

    aligned_mask = np.zeros((size[1], size[0]), dtype=bool)
    resized_mask = np.asarray(fitted_mask) > 127
    aligned_mask[
        paste_y:paste_y + fitted_size[1],
        paste_x:paste_x + fitted_size[0],
    ] = resized_mask
    union = np.logical_or(aligned_mask, geometry_mask).sum()
    intersection = np.logical_and(aligned_mask, geometry_mask).sum()
    silhouette_iou = float(intersection / union) if union else 0.0
    report["silhouette_iou"] = silhouette_iou
    if silhouette_iou < 0.35:
        report["reason"] = "silhouette_overlap_too_low"
        return None, report

    report["passed"] = True
    report["reason"] = None
    return aligned, report
