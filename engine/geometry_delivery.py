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
    "lowpoly": {"min_face_ratio": 0.08, "aggression": 8},
    "product": {"min_face_ratio": 0.45, "aggression": 4},
    "industrial": {"min_face_ratio": 0.55, "aggression": 3},
    "architecture": {"min_face_ratio": 0.65, "aggression": 2},
}


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
        "preserve_hard_edges": category in HARD_EDGE_CATEGORIES or profile == "lowpoly",
        "min_face_ratio": settings["min_face_ratio"],
        "aggression": settings["aggression"],
    }


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
        path = output_dir / f"{job_id}-{name.lower()}.glb"
        lod_mesh.export(str(path))
        outputs[name] = {
            "path": str(path),
            "target_faces": lod_target,
            "faces": len(getattr(lod_mesh, "faces", [])),
            "simplification": policy,
        }
    return outputs
