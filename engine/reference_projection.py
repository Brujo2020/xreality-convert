"""Camera-calibrated reference projection for an existing textured GLB.

Observed pixels are back-projected through the mesh z-buffer into its existing
UV atlas. Unseen texels keep their original value; no generative model runs.
"""

import argparse
import hashlib
import io
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import trimesh
from PIL import Image, ImageDraw
from pygltflib import BufferView, GLTF2
from scipy import ndimage


PROJECTION_VERSION = "xreality-reference-projection-v3"
GATE_VERSION = "xreality-aligned-fidelity-v2"
DEFAULT_MIN_FACING_COSINE = 0.10
MIN_COLOR_SIMILARITY = 0.85
MIN_SILHOUETTE_IOU = 0.80
MIN_NATIVE_PAINT_SILHOUETTE_IOU = 0.80
MAX_WHITE_LEAKAGE = 0.02
MAX_LOCALIZED_ERROR_RATIO = 0.05
LOCALIZED_ERROR_THRESHOLD = 0.20
SEVERE_SEAM_THRESHOLD = 0.20
MAX_SEVERE_SEAM_RATIO = 0.03
MIN_PAINT_SPATIAL_CORRELATION = 0.80
MIN_QUARTER_PALETTE_SIMILARITY = 0.80
MIN_QUARTER_COLOR_RETENTION = 0.80
MAX_GATE_RENDER_SIZE = 512


class ProjectionInputError(ValueError):
    pass


def _round(value):
    return round(float(value), 4)


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_rgba(path):
    image_path = Path(path)
    if not image_path.is_file():
        raise ProjectionInputError("missing_image")
    with Image.open(image_path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def _largest_component(mask):
    labels, count = ndimage.label(mask, structure=np.ones((3, 3), dtype=bool))
    if not count:
        return np.zeros_like(mask, dtype=bool)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    return labels == int(sizes.argmax())


def _foreground_mask(rgba):
    alpha = rgba[:, :, 3]
    if np.any(alpha < 250):
        return _largest_component(alpha > 16)
    rgb = rgba[:, :, :3].astype(np.float32)
    border = np.concatenate((rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]), axis=0)
    background = np.median(border, axis=0)
    distance = np.sqrt(np.mean(np.square(rgb - background), axis=2))
    mask = ndimage.binary_closing(distance > 14.0, iterations=2)
    return _largest_component(mask)


def _camera_basis(yaw_degrees, elevation_degrees):
    yaw = math.radians(float(yaw_degrees))
    elevation = math.radians(float(elevation_degrees))
    camera_direction = np.array(
        [
            math.sin(yaw) * math.cos(elevation),
            math.sin(elevation),
            math.cos(yaw) * math.cos(elevation),
        ],
        dtype=np.float64,
    )
    forward = -camera_direction
    right = np.cross(forward, np.array([0.0, 1.0, 0.0]))
    right /= max(np.linalg.norm(right), 1e-12)
    up = np.cross(right, forward)
    up /= max(np.linalg.norm(up), 1e-12)
    return camera_direction, right, up


def _project_vertices(vertices, calibration):
    camera_direction, right, up = _camera_basis(
        calibration["yawDegrees"], calibration["elevationDegrees"]
    )
    scale = calibration["scalePixelsPerUnit"]
    x = vertices @ right * scale + calibration["offsetX"]
    y = -(vertices @ up) * scale + calibration["offsetY"]
    depth = vertices @ camera_direction
    return np.column_stack((x, y)), depth, camera_direction


def _mask_bbox(mask):
    y, x = np.nonzero(mask)
    if not len(x):
        raise ProjectionInputError("empty_foreground")
    return float(x.min()), float(y.min()), float(x.max()), float(y.max())


def _fit_calibration(vertices, mask, yaw, elevation):
    _, right, up = _camera_basis(yaw, elevation)
    raw_x = vertices @ right
    raw_y = vertices @ up
    left, top, right_px, bottom = _mask_bbox(mask)
    width = max(right_px - left, 1.0)
    height = max(bottom - top, 1.0)
    mesh_width = max(float(np.ptp(raw_x)), 1e-9)
    mesh_height = max(float(np.ptp(raw_y)), 1e-9)
    scale = min(width / mesh_width, height / mesh_height)
    mesh_center_x = (float(raw_x.min()) + float(raw_x.max())) * 0.5
    mesh_center_y = (float(raw_y.min()) + float(raw_y.max())) * 0.5
    return {
        "yawDegrees": float(yaw) % 360.0,
        "elevationDegrees": float(elevation),
        "scalePixelsPerUnit": float(scale),
        "offsetX": (left + right_px) * 0.5 - mesh_center_x * scale,
        "offsetY": (top + bottom) * 0.5 + mesh_center_y * scale,
    }


def _rasterize_silhouette(projected, faces, shape):
    height, width = shape
    canvas = np.zeros((height, width), dtype=np.uint8)
    points = np.rint(projected[faces]).astype(np.int32)
    first = points[:, 1] - points[:, 0]
    second = points[:, 2] - points[:, 0]
    valid = np.abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]) > 0
    for triangle in points[valid]:
        cv2.fillConvexPoly(canvas, triangle, 1)
    return canvas.astype(bool)


def _iou(left, right):
    union = np.logical_or(left, right).sum()
    return float(np.logical_and(left, right).sum() / union) if union else 0.0


def calibrate_camera(vertices, faces, reference_mask, calibration_size=256):
    height, width = reference_mask.shape
    ratio = min(1.0, calibration_size / max(height, width))
    small_size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
    small_mask = cv2.resize(
        reference_mask.astype(np.uint8), small_size, interpolation=cv2.INTER_NEAREST
    ).astype(bool)

    best = None
    for yaw in range(0, 360, 15):
        for elevation in (-12, 0, 12):
            candidate = _fit_calibration(vertices, small_mask, yaw, elevation)
            projected, _, _ = _project_vertices(vertices, candidate)
            score = _iou(_rasterize_silhouette(projected, faces, small_mask.shape), small_mask)
            if best is None or score > best[0]:
                best = (score, yaw, elevation)

    _, coarse_yaw, coarse_elevation = best
    for yaw in range(coarse_yaw - 10, coarse_yaw + 11, 5):
        for elevation in range(coarse_elevation - 8, coarse_elevation + 9, 4):
            candidate = _fit_calibration(vertices, small_mask, yaw, elevation)
            projected, _, _ = _project_vertices(vertices, candidate)
            score = _iou(_rasterize_silhouette(projected, faces, small_mask.shape), small_mask)
            if score > best[0]:
                best = (score, yaw, elevation)

    calibration = _fit_calibration(vertices, reference_mask, best[1], best[2])
    projected, _, camera_direction = _project_vertices(vertices, calibration)
    silhouette = _rasterize_silhouette(projected, faces, reference_mask.shape)
    calibration.update(
        {
            "silhouetteIoU": _round(_iou(silhouette, reference_mask)),
            "cameraDirection": [_round(value) for value in camera_direction],
            "referenceSize": [width, height],
        }
    )
    return calibration, silhouette


def _triangle_grid(points, width, height):
    x0 = max(0, int(math.floor(float(points[:, 0].min()))))
    x1 = min(width - 1, int(math.ceil(float(points[:, 0].max()))))
    y0 = max(0, int(math.floor(float(points[:, 1].min()))))
    y1 = min(height - 1, int(math.ceil(float(points[:, 1].max()))))
    if x1 < x0 or y1 < y0:
        return None
    px, py = np.meshgrid(
        np.arange(x0, x1 + 1, dtype=np.float64) + 0.5,
        np.arange(y0, y1 + 1, dtype=np.float64) + 0.5,
    )
    ax, ay = points[0]
    bx, by = points[1]
    cx, cy = points[2]
    denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denominator) < 1e-10:
        return None
    w0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
    w1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
    w2 = 1.0 - w0 - w1
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    return y0, y1, x0, x1, w0, w1, w2, inside


def _depth_buffer(projected, depths, faces, shape):
    height, width = shape
    zbuffer = np.full((height, width), -np.inf, dtype=np.float64)
    for face in faces:
        grid = _triangle_grid(projected[face], width, height)
        if grid is None:
            continue
        y0, y1, x0, x1, w0, w1, w2, inside = grid
        depth = w0 * depths[face[0]] + w1 * depths[face[1]] + w2 * depths[face[2]]
        region = zbuffer[y0 : y1 + 1, x0 : x1 + 1]
        visible = inside & (depth > region)
        region[visible] = depth[visible]
    return zbuffer


def _bilinear_sample(image, x, y):
    height, width = image.shape[:2]
    x = np.clip(x, 0.0, width - 1.0)
    y = np.clip(y, 0.0, height - 1.0)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (x - x0)[..., None]
    wy = (y - y0)[..., None]
    top = image[y0, x0] * (1.0 - wx) + image[y0, x1] * wx
    bottom = image[y1, x0] * (1.0 - wx) + image[y1, x1] * wx
    return top * (1.0 - wy) + bottom * wy


def measure_uv_seams(vertices, faces, uv, texture, inset=0.02):
    edges = {}
    rounded = np.round(vertices, 6)
    for face_index, face in enumerate(faces):
        keys = [tuple(rounded[index]) for index in face]
        for first, second in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((keys[first], keys[second])))
            edges.setdefault(key, []).append((face_index, first, second))
    errors = []
    texture_float = texture[:, :, :3].astype(np.float64)
    height, width = texture.shape[:2]
    for entries in edges.values():
        if len(entries) != 2:
            continue
        colors = []
        for face_index, first, second in entries:
            weights = np.full(3, inset, dtype=np.float64)
            weights[first] = (1.0 - inset) * 0.5
            weights[second] = (1.0 - inset) * 0.5
            face_uv = uv[faces[face_index]]
            sample_uv = weights @ face_uv
            color = _bilinear_sample(
                texture_float,
                np.asarray(sample_uv[0] * (width - 1)),
                np.asarray((1.0 - sample_uv[1]) * (height - 1)),
            )
            colors.append(color)
        errors.append(float(np.abs(colors[0] - colors[1]).mean() / 255.0))
    if not errors:
        return {
            "adjacentEdges": 0,
            "meanSeamError": 0.0,
            "p95SeamError": 0.0,
            "severeSeamRatio": 0.0,
        }
    errors = np.asarray(errors)
    return {
        "adjacentEdges": int(len(errors)),
        "meanSeamError": _round(errors.mean()),
        "p95SeamError": _round(np.quantile(errors, 0.95)),
        "severeSeamRatio": _round((errors > SEVERE_SEAM_THRESHOLD).mean()),
    }


def _reconcile_uv_seams(vertices, faces, uv, texture, confidence, radius=2):
    rounded = np.round(vertices, 6)
    edges = {}
    for face in faces:
        keys = [tuple(rounded[index]) for index in face]
        for first, second in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((keys[first], keys[second])))
            corners = {keys[first]: int(face[first]), keys[second]: int(face[second])}
            edges.setdefault(key, []).append(corners)
    height, width = texture.shape[:2]
    modified = np.zeros((height, width), dtype=np.uint8)
    for key, entries in edges.items():
        if len(entries) != 2:
            continue
        first_key, second_key = key
        first_uv = []
        second_uv = []
        for entry in entries:
            first_uv.append(uv[entry[first_key]])
            second_uv.append(uv[entry[second_key]])
        edge_pixels = max(
            np.linalg.norm((first_uv[0] - second_uv[0]) * (width, height)),
            np.linalg.norm((first_uv[1] - second_uv[1]) * (width, height)),
        )
        samples = min(96, max(2, int(math.ceil(edge_pixels))))
        for position in np.linspace(0.0, 1.0, samples):
            points = [
                first_uv[index] * (1.0 - position) + second_uv[index] * position
                for index in range(2)
            ]
            pixels = [
                (
                    int(np.clip(round(point[0] * (width - 1)), 0, width - 1)),
                    int(np.clip(round((1.0 - point[1]) * (height - 1)), 0, height - 1)),
                )
                for point in points
            ]
            strengths = [confidence[y, x] for x, y in pixels]
            source_index = int(np.argmax(strengths))
            target_index = 1 - source_index
            if strengths[source_index] < 64 or strengths[target_index] >= 64:
                continue
            source_x, source_y = pixels[source_index]
            target_x, target_y = pixels[target_index]
            color = tuple(float(value) for value in texture[source_y, source_x])
            cv2.circle(texture, (target_x, target_y), radius, color, thickness=-1)
            cv2.circle(modified, (target_x, target_y), radius, 1, thickness=-1)
    return int(modified.sum())


def project_reference_to_texture(
    vertices,
    faces,
    uv,
    base_rgba,
    reference_rgba,
    calibration,
    min_facing=DEFAULT_MIN_FACING_COSINE,
):
    reference_mask = _foreground_mask(reference_rgba)
    projected, depths, camera_direction = _project_vertices(vertices, calibration)
    zbuffer = _depth_buffer(projected, depths, faces, reference_mask.shape)
    distance = ndimage.distance_transform_edt(reference_mask)
    output = base_rgba.astype(np.float64).copy()
    confidence = np.zeros(base_rgba.shape[:2], dtype=np.float64)
    texture_height, texture_width = confidence.shape
    depth_tolerance = max(float(np.ptp(depths)) * 0.01, 1e-6)
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    normals = np.divide(normals, lengths[:, None], out=np.zeros_like(normals), where=lengths[:, None] > 0)
    facing_values = normals @ camera_direction
    front_facing_faces = int(np.sum(facing_values > 0.0))
    grazing_rejected_faces = int(
        np.sum((facing_values > 0.0) & (facing_values <= min_facing))
    )

    for face_index, face in enumerate(faces):
        facing = float(facing_values[face_index])
        if facing <= min_facing:
            continue
        uv_points = np.column_stack(
            (
                uv[face, 0] * (texture_width - 1),
                (1.0 - uv[face, 1]) * (texture_height - 1),
            )
        )
        grid = _triangle_grid(uv_points, texture_width, texture_height)
        if grid is None:
            continue
        y0, y1, x0, x1, w0, w1, w2, inside = grid
        source_x = w0 * projected[face[0], 0] + w1 * projected[face[1], 0] + w2 * projected[face[2], 0]
        source_y = w0 * projected[face[0], 1] + w1 * projected[face[1], 1] + w2 * projected[face[2], 1]
        source_depth = w0 * depths[face[0]] + w1 * depths[face[1]] + w2 * depths[face[2]]
        in_source = (
            (source_x >= 0)
            & (source_x < reference_rgba.shape[1])
            & (source_y >= 0)
            & (source_y < reference_rgba.shape[0])
        )
        sample_x = np.clip(np.rint(source_x).astype(np.int64), 0, reference_rgba.shape[1] - 1)
        sample_y = np.clip(np.rint(source_y).astype(np.int64), 0, reference_rgba.shape[0] - 1)
        visible = np.abs(source_depth - zbuffer[sample_y, sample_x]) <= depth_tolerance
        edge_weight = np.clip(distance[sample_y, sample_x] / 3.0, 0.0, 1.0)
        facing_weight = min(1.0, max(0.0, (facing - min_facing) / 0.35))
        weight = edge_weight * facing_weight
        valid = inside & in_source & visible & (edge_weight > 0.05)
        region_confidence = confidence[y0 : y1 + 1, x0 : x1 + 1]
        replace = valid & (weight > region_confidence)
        if not np.any(replace):
            continue
        sampled = _bilinear_sample(reference_rgba[:, :, :3].astype(np.float64), source_x, source_y)
        region = output[y0 : y1 + 1, x0 : x1 + 1]
        blend = weight[..., None]
        blended = sampled * blend + region[:, :, :3] * (1.0 - blend)
        region[:, :, :3][replace] = blended[replace]
        region[:, :, 3][replace] = 255
        region_confidence[replace] = weight[replace]

    projected_mask = confidence > 0.05
    output_uint8 = np.clip(np.rint(output), 0, 255).astype(np.uint8)
    confidence_uint8 = np.rint(confidence * 255).astype(np.uint8)
    seam_texels = _reconcile_uv_seams(
        vertices, faces, uv, output_uint8, confidence_uint8
    )
    seam_metrics = measure_uv_seams(vertices, faces, uv, output_uint8)
    metrics = {
        "projectedTexelRatio": _round(projected_mask.mean()),
        "highConfidenceTexelRatio": _round((confidence >= 0.95).mean()),
        "syntheticCompletionApplied": False,
        "seamBoundaryPropagationTexels": seam_texels,
        "seams": seam_metrics,
        "minimumFacingCosine": min_facing,
        "frontFacingFaces": front_facing_faces,
        "grazingRejectedFaces": grazing_rejected_faces,
        "grazingRejectedFaceRatio": _round(
            grazing_rejected_faces / max(front_facing_faces, 1)
        ),
    }
    return output_uint8, confidence_uint8, metrics


def _texture_png(rgba):
    stream = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def _replace_base_color_image(input_glb, output_glb, rgba):
    document = GLTF2().load_binary(str(input_glb))
    source_index = None
    for material in document.materials or []:
        pbr = material.pbrMetallicRoughness
        texture_info = pbr.baseColorTexture if pbr else None
        if texture_info is None:
            continue
        texture = document.textures[texture_info.index]
        source_index = texture.source
        break
    if source_index is None:
        raise ProjectionInputError("missing_base_color_texture")

    payload = _texture_png(rgba)
    binary = bytearray(document.binary_blob() or b"")
    binary.extend(b"\x00" * ((-len(binary)) % 4))
    offset = len(binary)
    binary.extend(payload)
    binary.extend(b"\x00" * ((-len(binary)) % 4))
    document.bufferViews.append(
        BufferView(buffer=0, byteOffset=offset, byteLength=len(payload))
    )
    image = document.images[source_index]
    image.bufferView = len(document.bufferViews) - 1
    image.mimeType = "image/png"
    image.uri = None
    document.buffers[0].byteLength = len(binary)
    document.set_binary_blob(bytes(binary))
    Path(output_glb).parent.mkdir(parents=True, exist_ok=True)
    document.save_binary(str(output_glb))


def _render_texture(vertices, faces, uv, texture, calibration, face_normals=None):
    width, height = calibration["referenceSize"]
    projected, depths, camera_direction = _project_vertices(vertices, calibration)
    zbuffer = np.full((height, width), -np.inf, dtype=np.float64)
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    texture_float = texture.astype(np.float64)
    texture_height, texture_width = texture.shape[:2]
    if face_normals is None:
        triangles = vertices[faces]
        face_normals = np.cross(
            triangles[:, 1] - triangles[:, 0],
            triangles[:, 2] - triangles[:, 0],
        )
        lengths = np.linalg.norm(face_normals, axis=1)
        face_normals = face_normals / np.maximum(lengths[:, None], 1e-12)
    projected_faces = projected[faces]
    front_facing = (face_normals @ camera_direction) > 1e-8
    on_canvas = (
        (projected_faces[:, :, 0].max(axis=1) >= 0)
        & (projected_faces[:, :, 0].min(axis=1) < width)
        & (projected_faces[:, :, 1].max(axis=1) >= 0)
        & (projected_faces[:, :, 1].min(axis=1) < height)
    )
    for face in faces[front_facing & on_canvas]:
        grid = _triangle_grid(projected[face], width, height)
        if grid is None:
            continue
        y0, y1, x0, x1, w0, w1, w2, inside = grid
        depth = w0 * depths[face[0]] + w1 * depths[face[1]] + w2 * depths[face[2]]
        zregion = zbuffer[y0 : y1 + 1, x0 : x1 + 1]
        visible = inside & (depth > zregion)
        if not np.any(visible):
            continue
        tex_x = (w0 * uv[face[0], 0] + w1 * uv[face[1], 0] + w2 * uv[face[2], 0]) * (texture_width - 1)
        tex_y = (1.0 - (w0 * uv[face[0], 1] + w1 * uv[face[1], 1] + w2 * uv[face[2], 1])) * (texture_height - 1)
        sampled = np.clip(np.rint(_bilinear_sample(texture_float, tex_x, tex_y)), 0, 255).astype(np.uint8)
        canvas_region = canvas[y0 : y1 + 1, x0 : x1 + 1]
        canvas_region[visible] = sampled[visible]
        canvas_region[:, :, 3][visible] = 255
        zregion[visible] = depth[visible]
    return canvas


def evaluate_aligned_fidelity(reference_path, render_path):
    reference = _load_rgba(reference_path)
    render = _load_rgba(render_path)
    if render.shape[:2] != reference.shape[:2]:
        render = cv2.resize(render, (reference.shape[1], reference.shape[0]), interpolation=cv2.INTER_AREA)
    reference_mask = _foreground_mask(reference)
    render_mask = _foreground_mask(render)
    intersection = reference_mask & render_mask
    union = reference_mask | render_mask
    if not np.any(intersection):
        return {
            "gateVersion": GATE_VERSION,
            "passed": False,
            "decision": "reject",
            "reasons": ["no_aligned_foreground"],
            "metrics": {},
        }

    reference_rgb = reference[:, :, :3].astype(np.float64) / 255.0
    render_rgb = render[:, :, :3].astype(np.float64) / 255.0
    pixel_error = np.abs(reference_rgb - render_rgb).mean(axis=2)
    color_similarity = 1.0 - float(pixel_error[intersection].mean())
    localized_error_ratio = float((pixel_error[intersection] > LOCALIZED_ERROR_THRESHOLD).mean())
    reference_max = reference_rgb.max(axis=2)
    reference_min = reference_rgb.min(axis=2)
    reference_saturation = (reference_max - reference_min) / np.maximum(reference_max, 1e-6)
    render_max = render_rgb.max(axis=2)
    render_min = render_rgb.min(axis=2)
    render_saturation = (render_max - render_min) / np.maximum(render_max, 1e-6)
    reference_luminance = reference_rgb @ np.array([0.2126, 0.7152, 0.0722])
    render_luminance = render_rgb @ np.array([0.2126, 0.7152, 0.0722])
    eligible = intersection & (reference_saturation > 0.30) & (reference_luminance < 0.85)
    white = eligible & (render_saturation < 0.15) & (render_luminance > 0.85)
    white_leakage = float(white.sum() / max(int(eligible.sum()), 1))
    silhouette_iou = float(intersection.sum() / max(int(union.sum()), 1))
    metrics = {
        "silhouetteIoU": _round(silhouette_iou),
        "colorSimilarity": _round(color_similarity),
        "localizedErrorRatio": _round(localized_error_ratio),
        "p95ColorError": _round(np.quantile(pixel_error[intersection], 0.95)),
        "whiteLeakageRatio": _round(white_leakage),
        "referenceCoverage": _round(intersection.sum() / max(int(reference_mask.sum()), 1)),
    }
    reasons = []
    if silhouette_iou < MIN_SILHOUETTE_IOU:
        reasons.append("silhouette_mismatch")
    if color_similarity < MIN_COLOR_SIMILARITY:
        reasons.append("reference_color_mismatch")
    if localized_error_ratio > MAX_LOCALIZED_ERROR_RATIO:
        reasons.append("localized_texture_mismatch")
    if white_leakage > MAX_WHITE_LEAKAGE:
        reasons.append("white_leakage")
    return {
        "gateVersion": GATE_VERSION,
        "passed": not reasons,
        "decision": "pass" if not reasons else "reject",
        "reasons": reasons,
        "thresholds": {
            "minimumSilhouetteIoU": MIN_SILHOUETTE_IOU,
            "minimumColorSimilarity": MIN_COLOR_SIMILARITY,
            "maximumLocalizedErrorRatio": MAX_LOCALIZED_ERROR_RATIO,
            "localizedErrorThreshold": LOCALIZED_ERROR_THRESHOLD,
            "maximumWhiteLeakageRatio": MAX_WHITE_LEAKAGE,
        },
        "metrics": metrics,
    }


def _low_frequency_color_correlation(reference, render, mask, size=16):
    if not np.any(mask):
        return 0.0

    channels = []
    for rgba in (reference, render):
        lab = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2LAB).astype(np.float64)
        for channel in range(3):
            lab[:, :, channel][~mask] = float(lab[:, :, channel][mask].mean())
        channels.append(cv2.resize(lab, (size, size), interpolation=cv2.INTER_AREA))

    correlations = []
    for channel in range(3):
        left = channels[0][:, :, channel].ravel()
        right = channels[1][:, :, channel].ravel()
        if left.std() < 1e-8 or right.std() < 1e-8:
            correlations.append(1.0 if np.allclose(left, right) else 0.0)
        else:
            correlations.append(float(np.corrcoef(left, right)[0, 1]))
    return float(np.mean(correlations))


def _gate_sized_reference(reference, maximum=MAX_GATE_RENDER_SIZE):
    height, width = reference.shape[:2]
    scale = min(1.0, maximum / max(height, width))
    if scale == 1.0:
        return reference
    return cv2.resize(
        reference,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _foreground_palette(rgba):
    mask = _foreground_mask(rgba)
    rgb = rgba[:, :, :3][mask]
    if not len(rgb):
        return np.zeros(512, dtype=np.float64), 0.0
    bins = np.floor_divide(rgb, 32).clip(0, 7)
    indices = bins[:, 0] * 64 + bins[:, 1] * 8 + bins[:, 2]
    histogram = np.bincount(indices, minlength=512).astype(np.float64)
    histogram /= max(histogram.sum(), 1.0)
    spread = rgb.max(axis=1).astype(np.float64) - rgb.min(axis=1)
    color_ratio = float((spread > 28).mean())
    return histogram, color_ratio


def evaluate_quarter_texture_stability(front, quarters):
    """Reject quarter views that lose the front view's painted color regions.

    This is an artifact gate, not a semantic back-view comparison: a single
    reference cannot prove unseen markings. It catches blank/flat quarters and
    gross palette discontinuities without pretending to validate unseen truth.
    """
    front_histogram, front_color_ratio = _foreground_palette(front)
    metrics = {}
    reasons = []
    for label, rendered in quarters.items():
        histogram, color_ratio = _foreground_palette(rendered)
        palette_similarity = float(np.minimum(front_histogram, histogram).sum())
        color_retention = (
            1.0
            if front_color_ratio < 0.08
            else min(1.0, color_ratio / max(front_color_ratio, 1e-8))
        )
        metrics[label] = {
            "paletteSimilarity": _round(palette_similarity),
            "colorRatio": _round(color_ratio),
            "colorRetention": _round(color_retention),
        }
        if palette_similarity < MIN_QUARTER_PALETTE_SIMILARITY:
            reasons.append(f"{label}_palette_discontinuity")
        if color_retention < MIN_QUARTER_COLOR_RETENTION:
            reasons.append(f"{label}_paint_loss")
    return {
        "gateVersion": "xreality-quarter-artifact-v1",
        "passed": not reasons,
        "decision": "pass" if not reasons else "reject",
        "reasons": reasons,
        "thresholds": {
            "minimumPaletteSimilarity": MIN_QUARTER_PALETTE_SIMILARITY,
            "minimumColorRetention": MIN_QUARTER_COLOR_RETENTION,
        },
        "metrics": metrics,
    }


def evaluate_native_paint_fidelity(reference, render):
    if render.shape[:2] != reference.shape[:2]:
        render = cv2.resize(
            render,
            (reference.shape[1], reference.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
    reference_mask = _foreground_mask(reference)
    render_mask = _foreground_mask(render)
    intersection = reference_mask & render_mask
    union = reference_mask | render_mask
    silhouette_iou = float(intersection.sum() / max(int(union.sum()), 1))
    correlation = _low_frequency_color_correlation(
        reference, render, intersection
    )
    reasons = []
    if silhouette_iou < MIN_NATIVE_PAINT_SILHOUETTE_IOU:
        reasons.append("silhouette_mismatch")
    if correlation < MIN_PAINT_SPATIAL_CORRELATION:
        reasons.append("spatial_texture_mismatch")
    return {
        "gateVersion": "xreality-native-paint-v2",
        "passed": not reasons,
        "decision": "pass" if not reasons else "reject",
        "reasons": reasons,
        "thresholds": {
            "minimumSilhouetteIoU": MIN_NATIVE_PAINT_SILHOUETTE_IOU,
            "minimumSpatialColorCorrelation": MIN_PAINT_SPATIAL_CORRELATION,
        },
        "metrics": {
            "silhouetteIoU": _round(silhouette_iou),
            "spatialColorCorrelation": _round(correlation),
        },
    }


def validate_native_paint_glb(input_glb, reference_path, evidence_dir, fail_closed=True):
    input_glb = Path(input_glb).resolve()
    reference_path = Path(reference_path).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    scene = trimesh.load(input_glb, force="scene")
    mesh = scene.to_geometry()
    if not isinstance(mesh, trimesh.Trimesh) or mesh.visual.kind != "texture":
        raise ProjectionInputError("textured_mesh_required")
    uv = np.asarray(mesh.visual.uv, dtype=np.float64)
    base_image = mesh.visual.material.baseColorTexture
    if uv.shape != (len(mesh.vertices), 2) or base_image is None:
        raise ProjectionInputError("base_color_texture_required")

    reference = _gate_sized_reference(_load_rgba(reference_path))
    faces = np.asarray(mesh.faces, dtype=np.int64)
    component_faces = _largest_face_component(mesh)
    calibration, _ = calibrate_camera(
        np.asarray(mesh.vertices, dtype=np.float64),
        faces[component_faces],
        _foreground_mask(reference),
    )
    texture = np.asarray(base_image.convert("RGBA"), dtype=np.uint8)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    calibrations = {"front": calibration}
    for label, yaw in (
        ("quarter-left", calibration["yawDegrees"] - 30),
        ("quarter-right", calibration["yawDegrees"] + 30),
    ):
        view = _fit_calibration(
            vertices,
            _foreground_mask(reference),
            yaw,
            calibration["elevationDegrees"],
        )
        view["referenceSize"] = calibration["referenceSize"]
        calibrations[label] = view

    triangles = vertices[faces]
    face_normals = np.cross(
        triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    )
    face_normals /= np.maximum(np.linalg.norm(face_normals, axis=1)[:, None], 1e-12)
    # Rasterization has a Python face loop; threads contend on that loop on
    # macOS. Keep renders serial, while independent file hashes run in parallel.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="paint-proof") as executor:
        glb_hash = executor.submit(_sha256, input_glb)
        reference_hash = executor.submit(_sha256, reference_path)
        rendered_views = {
            label: _render_texture(
                vertices, faces, uv, texture, view, face_normals=face_normals
            )
            for label, view in calibrations.items()
        }

    renders = {}
    workers = max(1, min(3, int(os.environ.get("XREALITY_VALIDATION_WORKERS", "3"))))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="paint-evidence") as executor:
        pending_saves = {}
        for label, rendered in rendered_views.items():
            path = evidence_dir / f"native-paint-{label}.png"
            renders[label] = str(path)
            pending_saves[label] = executor.submit(
                Image.fromarray(rendered, mode="RGBA").save, path
            )
        for future in pending_saves.values():
            future.result()

    front_gate = evaluate_native_paint_fidelity(reference, rendered_views["front"])
    quarter_gate = evaluate_quarter_texture_stability(
        rendered_views["front"],
        {
            label: rendered
            for label, rendered in rendered_views.items()
            if label != "front"
        },
    )
    reasons = front_gate["reasons"] + quarter_gate["reasons"]
    gate = {
        "gateVersion": "xreality-native-paint-v3",
        "passed": not reasons,
        "decision": "pass" if not reasons else "reject",
        "reasons": reasons,
        "front": front_gate,
        "quarters": quarter_gate,
    }
    report = {
        "schemaVersion": 1,
        "paintGateVersion": gate["gateVersion"],
        "inputGlb": str(input_glb),
        "inputGlbSha256": glb_hash.result(),
        "reference": str(reference_path),
        "referenceSha256": reference_hash.result(),
        "renderer": "trimesh_uv_raster",
        "renderMaximumDimension": MAX_GATE_RENDER_SIZE,
        "renderWorkers": workers,
        "lighting": "embedded_base_color_only",
        "hdriInvoked": False,
        "calibration": calibration,
        "gate": gate,
        "artifacts": renders,
    }
    report_path = evidence_dir / "native-paint-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if not gate["passed"] and fail_closed:
        labels = {
            "silhouette_mismatch": "la geometría no coincide con la silueta de referencia",
            "spatial_texture_mismatch": "la textura perdió la distribución visual de la referencia",
            "quarter-left_palette_discontinuity": "la vista izquierda perdió continuidad de color",
            "quarter-right_palette_discontinuity": "la vista derecha perdió continuidad de color",
            "quarter-left_paint_loss": "la vista izquierda contiene zonas sin pintar",
            "quarter-right_paint_loss": "la vista derecha contiene zonas sin pintar",
        }
        reasons = "; ".join(
            labels.get(reason, reason)
            for reason in (gate["reasons"] or ["native_paint_gate_failed"])
        )
        raise RuntimeError(f"Textura rechazada por control visual: {reasons}")
    return report


def _difference(reference, render):
    difference = np.abs(reference[:, :, :3].astype(np.int16) - render[:, :, :3].astype(np.int16))
    heat = np.zeros_like(reference)
    magnitude = np.clip(difference.mean(axis=2) * 3.0, 0, 255).astype(np.uint8)
    heat[:, :, 0] = magnitude
    heat[:, :, 1] = magnitude // 5
    heat[:, :, 3] = np.where(_foreground_mask(reference) | _foreground_mask(render), 255, 0)
    return heat


def _sheet(items, output_path, cell_size=384):
    columns = 3
    rows = math.ceil(len(items) / columns)
    label_height = 34
    sheet = Image.new("RGB", (columns * cell_size, rows * (cell_size + label_height)), (16, 18, 22))
    draw = ImageDraw.Draw(sheet)
    for index, (label, rgba) in enumerate(items):
        image = Image.fromarray(rgba, mode="RGBA")
        image.thumbnail((cell_size, cell_size), Image.Resampling.LANCZOS)
        background = Image.new("RGBA", (cell_size, cell_size), (28, 31, 38, 255))
        background.alpha_composite(image, ((cell_size - image.width) // 2, (cell_size - image.height) // 2))
        x = (index % columns) * cell_size
        y = (index // columns) * (cell_size + label_height)
        sheet.paste(background.convert("RGB"), (x, y + label_height))
        draw.text((x + 12, y + 10), label, fill=(235, 238, 244))
    sheet.save(output_path)


def _largest_face_component(mesh):
    spatial = mesh.copy()
    spatial.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=6)
    components = trimesh.graph.connected_components(
        spatial.face_adjacency, nodes=np.arange(len(spatial.faces)), min_len=1
    )
    return np.asarray(max(components, key=len), dtype=np.int64)


def run_projection(
    input_glb,
    reference_path,
    output_glb,
    evidence_dir,
    *,
    minimum_facing_cosine=DEFAULT_MIN_FACING_COSINE,
):
    input_glb = Path(input_glb).resolve()
    reference_path = Path(reference_path).resolve()
    output_glb = Path(output_glb).resolve()
    evidence_dir = Path(evidence_dir).resolve()
    if input_glb == output_glb:
        raise ProjectionInputError("output_must_not_overwrite_input")
    scene = trimesh.load(input_glb, force="scene")
    mesh = scene.to_geometry()
    if not isinstance(mesh, trimesh.Trimesh) or mesh.visual.kind != "texture":
        raise ProjectionInputError("textured_mesh_required")
    uv = np.asarray(mesh.visual.uv, dtype=np.float64)
    if uv.shape != (len(mesh.vertices), 2):
        raise ProjectionInputError("uv_coordinates_required")
    base_image = mesh.visual.material.baseColorTexture
    if base_image is None:
        raise ProjectionInputError("base_color_texture_required")
    base_rgba = np.asarray(base_image.convert("RGBA"), dtype=np.uint8)
    reference = _load_rgba(reference_path)
    reference_mask = _foreground_mask(reference)
    component_faces = _largest_face_component(mesh)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    calibration, silhouette = calibrate_camera(
        np.asarray(mesh.vertices, dtype=np.float64), faces[component_faces], reference_mask
    )
    projected, confidence, projection_metrics = project_reference_to_texture(
        np.asarray(mesh.vertices, dtype=np.float64),
        faces[component_faces],
        uv,
        base_rgba,
        reference,
        calibration,
        min_facing=minimum_facing_cosine,
    )
    _replace_base_color_image(input_glb, output_glb, projected)

    evidence_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(projected, mode="RGBA").save(evidence_dir / "projected-atlas.png")
    Image.fromarray(confidence, mode="L").save(evidence_dir / "projection-confidence.png")
    silhouette_rgba = np.zeros_like(reference)
    silhouette_rgba[:, :, :3] = 255
    silhouette_rgba[:, :, 3] = silhouette.astype(np.uint8) * 255
    Image.fromarray(silhouette_rgba, mode="RGBA").save(evidence_dir / "calibrated-silhouette.png")

    front = _render_texture(np.asarray(mesh.vertices), faces, uv, projected, calibration)
    left_calibration = _fit_calibration(
        np.asarray(mesh.vertices), reference_mask, calibration["yawDegrees"] - 30, calibration["elevationDegrees"]
    )
    right_calibration = _fit_calibration(
        np.asarray(mesh.vertices), reference_mask, calibration["yawDegrees"] + 30, calibration["elevationDegrees"]
    )
    for view in (left_calibration, right_calibration):
        view["referenceSize"] = calibration["referenceSize"]
    left = _render_texture(np.asarray(mesh.vertices), faces, uv, projected, left_calibration)
    right = _render_texture(np.asarray(mesh.vertices), faces, uv, projected, right_calibration)
    front_path = evidence_dir / "matched-front.png"
    Image.fromarray(front, mode="RGBA").save(front_path)
    Image.fromarray(left, mode="RGBA").save(evidence_dir / "quarter-left.png")
    Image.fromarray(right, mode="RGBA").save(evidence_dir / "quarter-right.png")
    difference = _difference(reference, front)
    Image.fromarray(difference, mode="RGBA").save(evidence_dir / "difference-heatmap.png")
    _sheet(
        [
            ("Fuente", reference),
            ("Reproyeccion frontal", front),
            ("Diferencia", difference),
            ("Vista 3/4 izquierda", left),
            ("Vista 3/4 derecha", right),
            ("Cobertura proyectada", np.dstack((confidence, confidence, confidence, np.full_like(confidence, 255)))),
        ],
        evidence_dir / "fidelity-evidence-sheet.png",
    )
    gate = evaluate_aligned_fidelity(reference_path, front_path)
    seam_metrics = projection_metrics["seams"]
    gate["metrics"] = {**gate.get("metrics", {}), **seam_metrics}
    gate["thresholds"] = {
        **gate.get("thresholds", {}),
        "maximumSevereSeamRatio": MAX_SEVERE_SEAM_RATIO,
        "severeSeamThreshold": SEVERE_SEAM_THRESHOLD,
    }
    if seam_metrics["severeSeamRatio"] > MAX_SEVERE_SEAM_RATIO:
        gate["reasons"] = [*gate.get("reasons", []), "uv_seam_discontinuity"]
        gate["passed"] = False
        gate["decision"] = "reject"
    report = {
        "schemaVersion": 1,
        "projectionVersion": PROJECTION_VERSION,
        "inputGlb": str(input_glb),
        "inputGlbSha256": _sha256(input_glb),
        "outputGlb": str(output_glb),
        "outputGlbSha256": _sha256(output_glb),
        "reference": str(reference_path),
        "referenceSha256": _sha256(reference_path),
        "paintInvoked": False,
        "projectionMode": "camera_calibrated_zbuffer_uv",
        "componentFaceRatio": _round(len(component_faces) / len(faces)),
        "calibration": calibration,
        "projection": projection_metrics,
        "gate": gate,
        "artifacts": {
            "sheet": str(evidence_dir / "fidelity-evidence-sheet.png"),
            "front": str(front_path),
            "left": str(evidence_dir / "quarter-left.png"),
            "right": str(evidence_dir / "quarter-right.png"),
            "difference": str(evidence_dir / "difference-heatmap.png"),
            "confidence": str(evidence_dir / "projection-confidence.png"),
        },
    }
    report_path = evidence_dir / "projection-report.json"
    temporary = report_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(report_path)
    return report


def apply_reference_fidelity(
    input_glb,
    reference_path,
    output_glb,
    evidence_dir,
    *,
    projector=run_projection,
    validator=None,
):
    report = projector(input_glb, reference_path, output_glb, evidence_dir)
    gate = report.get("gate") or {}
    if not gate.get("passed"):
        reasons = ", ".join(gate.get("reasons") or ["aligned_gate_failed"])
        raise RuntimeError(f"Reference fidelity gate failed: {reasons}")
    if validator is None:
        from pbr_glb import validate_pbr_glb

        validator = validate_pbr_glb
    structural_gate = validator(output_glb)
    if not structural_gate.get("passed"):
        reasons = ", ".join(structural_gate.get("reasons") or ["pbr_gate_failed"])
        raise RuntimeError(f"Projected GLB validation failed: {reasons}")
    report["structuralGate"] = structural_gate
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Project observed reference pixels into an existing GLB UV atlas")
    subparsers = parser.add_subparsers(dest="command", required=True)
    project = subparsers.add_parser("project")
    project.add_argument("--input-glb", required=True)
    project.add_argument("--reference", required=True)
    project.add_argument("--output-glb", required=True)
    project.add_argument("--evidence-dir", required=True)
    project.add_argument(
        "--min-facing", type=float, default=DEFAULT_MIN_FACING_COSINE
    )
    gate = subparsers.add_parser("gate")
    gate.add_argument("--reference", required=True)
    gate.add_argument("--front", required=True)
    args = parser.parse_args(argv)
    if args.command == "gate":
        report = evaluate_aligned_fidelity(args.reference, args.front)
    else:
        if not 0.0 <= args.min_facing <= 0.8:
            parser.error("--min-facing must be between 0.0 and 0.8")
        report = run_projection(
            args.input_glb,
            args.reference,
            args.output_glb,
            args.evidence_dir,
            minimum_facing_cosine=args.min_facing,
        )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("passed", report.get("gate", {}).get("passed")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
