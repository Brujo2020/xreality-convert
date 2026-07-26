from pathlib import Path
from math import isfinite


UNIT_SCALE = {
    "m": 1.0,
    "cm": 100.0,
    "mm": 1000.0,
}

LOD_RATIOS = {
    "LOD0": 1.0,
    "LOD1": 0.5,
    "LOD2": 0.25,
}

HARD_EDGE_CATEGORIES = {"product", "industrial", "architecture"}

SIMPLIFICATION_POLICIES = {
    "lowpoly": {"min_face_ratio": 0.08, "aggression": 4},
    "product": {"min_face_ratio": 0.45, "aggression": 4},
    "industrial": {"min_face_ratio": 0.55, "aggression": 3},
    "architecture": {"min_face_ratio": 0.65, "aggression": 2},
}

ROUNDED_CATEGORIES = {"animal", "person", "custom"}


def normalize_delivery_options(pivot="center", up_axis="y", units="m", pivot_custom=None):
    if pivot not in {"center", "base", "custom"}:
        pivot = "center"
    normalized_custom = None
    if pivot == "custom":
        try:
            normalized_custom = [float(value) for value in pivot_custom[:3]]
        except (TypeError, ValueError):
            normalized_custom = None
        if normalized_custom is None or len(normalized_custom) != 3 or not all(isfinite(value) for value in normalized_custom):
            pivot = "center"
            normalized_custom = None
    if up_axis not in {"y", "z"}:
        up_axis = "y"
    if units not in UNIT_SCALE:
        units = "m"
    return {"pivot": pivot, "up_axis": up_axis, "units": units, "pivot_custom": normalized_custom}


def simplification_policy(category, target_faces, current_faces, profile="xreal"):
    source_category = category
    category = "lowpoly" if profile == "lowpoly" else category if category in SIMPLIFICATION_POLICIES else "custom"
    requested = max(1, int(target_faces or current_faces or 1))
    faces = max(0, int(current_faces or 0))
    settings = SIMPLIFICATION_POLICIES.get(category, {"min_face_ratio": 0.0, "aggression": 7})
    minimum = int(faces * settings["min_face_ratio"]) if faces else 0
    effective = max(requested, minimum)
    if faces:
        effective = min(effective, faces)
    return {
        "category": category,
        "requested_target_faces": requested,
        "target_faces": effective,
        "preserve_hard_edges": source_category in HARD_EDGE_CATEGORIES,
        "min_face_ratio": settings["min_face_ratio"],
        "aggression": settings["aggression"],
    }


def refinement_policy(category, profile="lowpoly"):
    enabled = profile == "lowpoly"
    preserve_hard_edges = category in HARD_EDGE_CATEGORIES
    return {
        "enabled": enabled,
        "preserve_hard_edges": preserve_hard_edges,
        "smoothing_iterations": 3 if enabled and category in ROUNDED_CATEGORIES else 0,
        "component_strategy": "threshold" if category == "architecture" else "largest",
        "min_component_ratio": 0.01,
    }


def _clean_topology(mesh):
    if hasattr(mesh, "merge_vertices"):
        mesh.merge_vertices(merge_tex=True, merge_norm=True, digits_vertex=7)
    if hasattr(mesh, "nondegenerate_faces") and hasattr(mesh, "update_faces"):
        try:
            mesh.update_faces(mesh.nondegenerate_faces())
        except Exception:
            pass
    if hasattr(mesh, "unique_faces") and hasattr(mesh, "update_faces"):
        try:
            mesh.update_faces(mesh.unique_faces())
        except Exception:
            pass
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    return mesh


def _surface_metrics(mesh):
    metrics = {
        "faces": len(getattr(mesh, "faces", [])),
        "components": 1,
        "degenerate_faces": 0,
        "edge_max_p95": 0.0,
    }
    try:
        components = mesh.split(only_watertight=False)
        metrics["components"] = len(components) or 1
    except Exception:
        pass
    try:
        import numpy as np

        areas = np.asarray(mesh.area_faces)
        if len(areas):
            threshold = max(float(np.median(areas)) * 1e-6, 1e-14)
            metrics["degenerate_faces"] = int(np.sum(areas <= threshold))
        edges = np.asarray(mesh.edges_unique_length)
        if len(edges):
            p95 = float(np.percentile(edges, 95))
            metrics["edge_max_p95"] = round(float(edges.max() / p95), 3) if p95 else 0.0
    except Exception:
        pass
    return metrics


def point_cloud_fidelity(source_points, delivered_points, source_normals=None, delivered_normals=None, *, diagonal=None):
    import numpy as np
    from scipy.spatial import cKDTree

    source = np.asarray(source_points, dtype=float)
    delivered = np.asarray(delivered_points, dtype=float)
    if source.ndim != 2 or delivered.ndim != 2 or source.shape[1:] != (3,) or delivered.shape[1:] != (3,):
        raise ValueError("surface samples must be non-empty Nx3 arrays")
    if not len(source) or not len(delivered):
        raise ValueError("surface samples must be non-empty Nx3 arrays")

    scale = float(diagonal or np.linalg.norm(np.ptp(source, axis=0)) or 1.0)
    source_to_delivered_distance, source_to_delivered = cKDTree(delivered).query(source, k=1)
    delivered_to_source_distance, delivered_to_source = cKDTree(source).query(delivered, k=1)
    distances = np.concatenate((source_to_delivered_distance, delivered_to_source_distance)) / scale
    report = {
        "sample_count": int(len(source) + len(delivered)),
        "sampled_hausdorff_ratio": round(float(np.max(distances)), 6),
        "surface_distance_p95_ratio": round(float(np.percentile(distances, 95)), 6),
        "normal_error_p95_degrees": None,
    }

    if source_normals is not None and delivered_normals is not None:
        source_normal = np.asarray(source_normals, dtype=float)
        delivered_normal = np.asarray(delivered_normals, dtype=float)
        if len(source_normal) == len(source) and len(delivered_normal) == len(delivered):
            source_normal /= np.maximum(np.linalg.norm(source_normal, axis=1, keepdims=True), 1e-12)
            delivered_normal /= np.maximum(np.linalg.norm(delivered_normal, axis=1, keepdims=True), 1e-12)
            forward = np.sum(source_normal * delivered_normal[source_to_delivered], axis=1)
            backward = np.sum(delivered_normal * source_normal[delivered_to_source], axis=1)
            angles = np.degrees(np.arccos(np.clip(np.concatenate((forward, backward)), -1.0, 1.0)))
            report["normal_error_p95_degrees"] = round(float(np.percentile(angles, 95)), 3)
    return report


def _sample_mesh_surface(mesh, sample_count):
    import numpy as np

    triangles = np.asarray(mesh.triangles, dtype=float)
    normals = np.asarray(mesh.face_normals, dtype=float)
    areas = np.asarray(mesh.area_faces, dtype=float)
    valid = np.isfinite(areas) & (areas > 1e-14)
    triangles, normals, areas = triangles[valid], normals[valid], areas[valid]
    if not len(triangles):
        raise ValueError("mesh has no sampleable surface")

    count = max(64, int(sample_count))
    area_positions = (np.arange(count, dtype=float) + 0.5) * (float(areas.sum()) / count)
    face_indices = np.searchsorted(np.cumsum(areas), area_positions, side="left")
    selected = triangles[np.minimum(face_indices, len(triangles) - 1)]
    sequence = np.arange(count, dtype=float) + 0.5
    root = np.sqrt(np.mod(sequence * 0.6180339887498949, 1.0))
    second = np.mod(sequence * 0.7548776662466927, 1.0)
    points = (
        (1.0 - root)[:, None] * selected[:, 0]
        + (root * (1.0 - second))[:, None] * selected[:, 1]
        + (root * second)[:, None] * selected[:, 2]
    )
    return points, normals[np.minimum(face_indices, len(normals) - 1)]


def measure_lowpoly_fidelity(source_mesh, delivered_mesh, category="custom", sample_count=2048):
    import numpy as np

    source_points, source_normals = _sample_mesh_surface(source_mesh, sample_count)
    delivered_points, delivered_normals = _sample_mesh_surface(delivered_mesh, sample_count)
    bounds = np.asarray(source_mesh.bounds, dtype=float)
    diagonal = float(np.linalg.norm(bounds[1] - bounds[0])) if bounds.shape == (2, 3) else None
    thresholds = {
        "sampled_hausdorff_ratio": 0.04,
        "surface_distance_p95_ratio": 0.02,
        "normal_error_p95_degrees": 35.0 if category in HARD_EDGE_CATEGORIES else 60.0,
    }
    return {
        **point_cloud_fidelity(
            source_points,
            delivered_points,
            source_normals,
            delivered_normals,
            diagonal=diagonal,
        ),
        "method": "deterministic_area_samples_kdtree",
        "thresholds": thresholds,
    }


def lowpoly_fidelity_reasons(report):
    thresholds = report.get("thresholds") or {}
    reasons = []
    if report.get("sampled_hausdorff_ratio", 0.0) > thresholds.get("sampled_hausdorff_ratio", float("inf")):
        reasons.append("silueta_deformada")
    if report.get("surface_distance_p95_ratio", 0.0) > thresholds.get("surface_distance_p95_ratio", float("inf")):
        reasons.append("superficie_irregular")
    normal_error = report.get("normal_error_p95_degrees")
    if normal_error is not None and normal_error > thresholds.get("normal_error_p95_degrees", float("inf")):
        reasons.append("normales_inconsistentes")
    return reasons


def refine_lowpoly_mesh(mesh, category="custom", *, smoother=None):
    policy = refinement_policy(category, "lowpoly")
    faces_before = len(getattr(mesh, "faces", []))
    mesh = _clean_topology(mesh)
    try:
        components = list(mesh.split(only_watertight=False))
    except Exception:
        components = [mesh]
    if not components:
        components = [mesh]

    if len(components) > 1 and policy["component_strategy"] == "largest":
        mesh = max(components, key=lambda item: (float(getattr(item, "area", 0.0) or 0.0), len(getattr(item, "faces", []))))
    elif len(components) > 1:
        largest_area = max(float(getattr(item, "area", 0.0) or 0.0) for item in components) or 1.0
        kept = [item for item in components if float(getattr(item, "area", 0.0) or 0.0) >= largest_area * policy["min_component_ratio"]]
        if len(kept) == 1:
            mesh = kept[0]
        elif kept:
            import trimesh

            mesh = trimesh.util.concatenate(kept)

    mesh = _clean_topology(mesh)
    iterations = policy["smoothing_iterations"]
    if iterations:
        if smoother is None:
            from trimesh.smoothing import filter_taubin

            smoother = filter_taubin
        smoother(mesh, lamb=0.35, nu=0.34, iterations=iterations)
        mesh = _clean_topology(mesh)
    try:
        mesh.fix_normals()
    except Exception:
        pass

    final_metrics = _surface_metrics(mesh)
    return mesh, {
        **policy,
        "faces_before": faces_before,
        "faces_after": len(getattr(mesh, "faces", [])),
        "input_components": len(components),
        "output_components": final_metrics["components"],
        "removed_components": max(0, len(components) - final_metrics["components"]),
        "degenerate_faces": final_metrics["degenerate_faces"],
        "edge_max_p95": final_metrics["edge_max_p95"],
    }


def lowpoly_refinement_reasons(report):
    reasons = []
    if report.get("output_components", 1) > 1:
        reasons.append("fragmentos_desconectados")
    if report.get("degenerate_faces", 0) > 0:
        reasons.append("triangulos_degenerados")
    if report.get("edge_max_p95", 0.0) > 4.0:
        reasons.append("puntas_geometricas")
    reasons.extend(lowpoly_fidelity_reasons(report.get("fidelity") or {}))
    return reasons


def _decimate(mesh, target_faces, policy):
    if policy["preserve_hard_edges"]:
        try:
            return mesh.simplify_quadric_decimation(
                face_count=int(target_faces),
                aggression=policy["aggression"],
                preserve_boundary=True,
            )
        except TypeError:
            pass
    try:
        return mesh.simplify_quadric_decimation(face_count=int(target_faces))
    except TypeError:
        return mesh.simplify_quadric_decimation(int(target_faces))


def simplify_mesh(mesh, target_faces, category="custom", profile="xreal"):
    faces = len(getattr(mesh, "faces", []))
    policy = simplification_policy(category, target_faces, faces, profile)
    if not target_faces or faces <= policy["target_faces"]:
        return mesh
    return _decimate(mesh, policy["target_faces"], policy)


def apply_delivery_transform(mesh, *, scale_meters, pivot, up_axis, units, pivot_custom=None):
    longest = max(getattr(mesh, "extents", [1])) or 1
    mesh.apply_scale(scale_meters / longest)
    if units != "m":
        mesh.apply_scale(UNIT_SCALE[units])
    if up_axis == "z":
        mesh.apply_transform(
            [
                [1, 0, 0, 0],
                [0, 0, -1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
            ]
        )
    bounds = getattr(mesh, "bounds", None)
    if bounds is not None:
        min_corner, max_corner = bounds
        center = [(min_corner[index] + max_corner[index]) / 2 for index in range(3)]
        translation = [-center[0], -center[1], -center[2]]
        if pivot == "base":
            up_index = 2 if up_axis == "z" else 1
            translation[up_index] = -min_corner[up_index]
        elif pivot == "custom" and pivot_custom:
            translation = [-pivot_custom[0], -pivot_custom[1], -pivot_custom[2]]
        mesh.apply_translation(translation)
    return mesh


def export_lods(mesh, output_dir: Path, job_id: str, target_faces: int, primary_path=None, category="custom", profile="xreal"):
    outputs = {
        "LOD0": {
            "path": str(primary_path or output_dir / f"{job_id}.glb"),
            "target_faces": int(target_faces),
            "faces": len(getattr(mesh, "faces", [])),
            "simplification": simplification_policy(category, target_faces, len(getattr(mesh, "faces", [])), profile),
        }
    }
    lod_mesh = mesh.copy()
    for name in ("LOD1", "LOD2"):
        ratio = LOD_RATIOS[name]
        lod_target = max(1000, int(target_faces * ratio))
        policy = simplification_policy(category, lod_target, len(getattr(lod_mesh, "faces", [])), profile)
        lod_mesh = simplify_mesh(lod_mesh, lod_target, category, profile)
        refinement = None
        if profile == "lowpoly":
            lod_mesh, refinement = refine_lowpoly_mesh(lod_mesh, category)
        path = output_dir / f"{job_id}-{name.lower()}.glb"
        lod_mesh.export(str(path))
        outputs[name] = {
            "path": str(path),
            "target_faces": lod_target,
            "faces": len(getattr(lod_mesh, "faces", [])),
            "simplification": policy,
            "refinement": refinement,
        }
    return outputs
