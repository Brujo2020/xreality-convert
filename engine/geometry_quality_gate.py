"""Deterministic, local geometry admission gate for mesh and GLB artifacts.

This is intentionally a *structural* gate.  It can prove local facts such as
valid triangles, bounds, components and (when requested) watertightness.  It
does not pretend that a mesh has the right silhouette, surviving thin details,
no self-intersections, or semantically correct hidden geometry: those require
independent render/reference or specialist geometric evidence and remain
explicitly ``not_measured`` here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from secure_artifacts import UnsafeAssetError, validate_glb_container


GEOMETRY_QUALITY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GeometryQualityPolicy:
    """Local structural limits; all thresholds are inclusive where sensible."""

    min_vertices: int = 3
    min_faces: int = 1
    min_components: int = 1
    max_components: int = 256
    min_extent: float = 1e-6
    max_extent: float = 1e6
    min_triangle_area: float = 1e-14
    require_winding_consistent: bool = True
    require_watertight: bool = False


class GeometryQualityError(ValueError):
    """The supplied audit request is malformed or unsafe to execute."""


def _require_trimesh() -> Any:
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover - minimal installations.
        raise GeometryQualityError("trimesh_unavailable") from exc
    return trimesh


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_policy(value: GeometryQualityPolicy | Mapping[str, Any] | None) -> GeometryQualityPolicy:
    if value is None:
        policy = GeometryQualityPolicy()
    elif isinstance(value, GeometryQualityPolicy):
        policy = value
    elif isinstance(value, Mapping):
        allowed = set(GeometryQualityPolicy.__dataclass_fields__)
        unknown = set(value) - allowed
        if unknown:
            raise GeometryQualityError("geometry_policy_unknown_fields")
        try:
            policy = GeometryQualityPolicy(**dict(value))
        except (TypeError, ValueError) as exc:
            raise GeometryQualityError("geometry_policy_invalid") from exc
    else:
        raise GeometryQualityError("geometry_policy_invalid")
    if (
        any(not isinstance(getattr(policy, key), int) or isinstance(getattr(policy, key), bool)
            for key in ("min_vertices", "min_faces", "min_components", "max_components"))
        or policy.min_vertices < 3
        or policy.min_faces < 1
        or policy.min_components < 1
        or policy.max_components < policy.min_components
    ):
        raise GeometryQualityError("geometry_policy_integer_limits_invalid")
    if any(not isinstance(getattr(policy, key), (int, float)) or isinstance(getattr(policy, key), bool)
           for key in ("min_extent", "max_extent", "min_triangle_area")):
        raise GeometryQualityError("geometry_policy_numeric_limits_invalid")
    if not all(np.isfinite(float(getattr(policy, key))) for key in ("min_extent", "max_extent", "min_triangle_area")):
        raise GeometryQualityError("geometry_policy_non_finite_limit")
    if policy.min_extent <= 0 or policy.max_extent < policy.min_extent or policy.min_triangle_area < 0:
        raise GeometryQualityError("geometry_policy_range_invalid")
    if not isinstance(policy.require_winding_consistent, bool) or not isinstance(policy.require_watertight, bool):
        raise GeometryQualityError("geometry_policy_boolean_limits_invalid")
    return policy


def _base_report(policy: GeometryQualityPolicy) -> dict[str, Any]:
    return {
        "schema_version": GEOMETRY_QUALITY_SCHEMA_VERSION,
        "status": "reject",
        "passed": False,
        "policy": asdict(policy),
        "artifact": {},
        "metrics": {},
        "components": [],
        "failures": [],
        "evidence_scope": {
            "finite_vertices": "measured_local",
            "face_indices": "measured_local",
            "degenerate_faces": "measured_local",
            "component_inventory": "measured_local",
            "bounds_and_scale": "measured_local",
            "winding_consistency": "measured_local",
            "watertightness": "measured_local",
            "self_intersection": "not_measured",
            "thin_part_survival": "not_measured",
            "silhouette_against_reference": "not_measured",
            "semantic_geometry_correctness": "not_measured",
        },
    }


def _load_asset(asset: Any, report: dict[str, Any]) -> Any:
    trimesh = _require_trimesh()
    if isinstance(asset, (str, Path)):
        source = Path(asset)
        report["artifact"] = {"path": str(source), "kind": "glb"}
        if source.suffix.lower() != ".glb":
            raise GeometryQualityError("geometry_path_must_be_glb")
        try:
            report["artifact"].update({
                "sha256": _sha256_file(source),
                "container": validate_glb_container(source),
            })
            scene = trimesh.load(str(source), force="scene", process=False)
        except (OSError, UnsafeAssetError, Exception) as exc:
            # ``trimesh`` has several parser exception types; the public
            # report deliberately exposes a stable, non-parser-specific code.
            raise GeometryQualityError("unsafe_or_invalid_glb") from exc
        if not isinstance(scene, trimesh.Scene) or not scene.geometry:
            raise GeometryQualityError("glb_scene_geometry_required")
        try:
            # ``to_mesh`` applies scene transforms without relying on the
            # deprecated ``Scene.dump(concatenate=True)`` API.
            mesh = scene.to_mesh()
        except Exception as exc:
            raise GeometryQualityError("glb_scene_flatten_failed") from exc
    else:
        mesh = asset
        report["artifact"] = {"kind": "mesh_object"}
    if not isinstance(mesh, trimesh.Trimesh):
        raise GeometryQualityError("geometry_mesh_required")
    return mesh


def _component_inventory(mesh: Any) -> list[dict[str, Any]]:
    try:
        components = list(mesh.split(only_watertight=False))
    except Exception as exc:
        raise GeometryQualityError("component_inventory_failed") from exc
    inventory: list[dict[str, Any]] = []
    for component in components:
        vertices = np.asarray(component.vertices)
        faces = np.asarray(component.faces)
        if vertices.ndim != 2 or vertices.shape[1] != 3 or faces.ndim != 2 or faces.shape[1] != 3:
            raise GeometryQualityError("component_geometry_invalid")
        bounds = np.asarray(component.bounds, dtype=float)
        inventory.append({
            "vertices": int(len(vertices)),
            "faces": int(len(faces)),
            "extent": [float(value) for value in (bounds[1] - bounds[0])],
            "watertight": bool(component.is_watertight),
        })
    return sorted(inventory, key=lambda item: (item["vertices"], item["faces"], item["extent"]))


def audit_geometry_quality(
    asset: Any,
    *,
    policy: GeometryQualityPolicy | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable local structural verdict for a ``trimesh`` mesh or GLB.

    Request/policy mistakes raise :class:`GeometryQualityError`.  Untrusted
    artifact or geometry failures are represented by a deterministic rejected
    report so callers can seal the negative evidence alongside the job.
    """
    checked_policy = _normalise_policy(policy)
    report = _base_report(checked_policy)
    try:
        mesh = _load_asset(asset, report)
    except GeometryQualityError as exc:
        report["failures"] = [str(exc)]
        return report

    failures: list[str] = []
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or len(vertices) < checked_policy.min_vertices:
        failures.append("vertices_missing_or_below_minimum")
    if faces.ndim != 2 or faces.shape[1] != 3 or len(faces) < checked_policy.min_faces:
        failures.append("faces_missing_or_below_minimum")
    if failures:
        report["failures"] = failures
        return report
    if not np.issubdtype(vertices.dtype, np.number) or not np.isfinite(vertices).all():
        failures.append("non_finite_vertices")
    if not np.issubdtype(faces.dtype, np.integer):
        failures.append("face_indices_not_integer")
    elif int(faces.min()) < 0 or int(faces.max()) >= len(vertices):
        failures.append("face_indices_invalid")
    if failures:
        report["failures"] = sorted(set(failures))
        return report

    triangles = vertices[faces]
    twice_area = np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    degenerate = int(np.count_nonzero(~np.isfinite(twice_area) | (twice_area <= 2.0 * checked_policy.min_triangle_area)))
    if degenerate:
        failures.append("degenerate_faces")
    bounds = np.asarray(mesh.bounds, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        failures.append("bounds_non_finite")
        extent = np.array([np.nan, np.nan, np.nan])
    else:
        extent = bounds[1] - bounds[0]
        if not np.isfinite(extent).all() or np.any(extent < checked_policy.min_extent):
            failures.append("scale_below_minimum_extent")
        if np.any(extent > checked_policy.max_extent):
            failures.append("scale_above_maximum_extent")
    try:
        components = _component_inventory(mesh)
    except GeometryQualityError as exc:
        components = []
        failures.append(str(exc))
    if not checked_policy.min_components <= len(components) <= checked_policy.max_components:
        failures.append("component_count_out_of_policy")
    winding_consistent = bool(mesh.is_winding_consistent)
    watertight = bool(mesh.is_watertight)
    if checked_policy.require_winding_consistent and not winding_consistent:
        failures.append("winding_inconsistent")
    if checked_policy.require_watertight and not watertight:
        failures.append("watertightness_required")

    report["metrics"] = {
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "degenerate_faces": degenerate,
        "component_count": len(components),
        "bounds": [[float(value) for value in row] for row in bounds] if bounds.shape == (2, 3) else None,
        "extent": [float(value) for value in extent],
        "winding_consistent": winding_consistent,
        "watertight": watertight,
    }
    report["components"] = components
    report["failures"] = sorted(set(failures))
    if not failures:
        report["status"] = "pass"
        report["passed"] = True
    return report
