"""Local, deterministic, fail-closed GLB LOD derivation.

This module deliberately performs only geometry reduction.  A decimated mesh
does not inherit a claim that its texture maps still fit: callers must create
and validate a new rebake before sealing delivery lineage.  The accepted
master is always read-only input; this module refuses to replace it (or an
existing derivative/report) so a failed derivation cannot erase evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

import numpy as np

from secure_artifacts import UnsafeAssetError, validate_glb_container


LOD_DERIVATION_SCHEMA_VERSION = 1
_MINIMUM_COMPONENT_FACES = 1


class LODDerivationError(ValueError):
    """A local LOD could not be created without weakening an invariant."""


Simplifier = Callable[[Any, int], Any]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _normalise_sha256(value: str | None, *, reason: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LODDerivationError(reason)
    digest = value.removeprefix("sha256:").lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise LODDerivationError(reason)
    return digest


def _require_trimesh():
    try:
        import trimesh
    except ImportError as exc:  # pragma: no cover - exercised on minimal deployments.
        raise LODDerivationError("trimesh_unavailable") from exc
    return trimesh


def _mesh_metrics(mesh: Any, *, name: str) -> dict[str, int]:
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices):
        raise LODDerivationError(f"{name}_vertices_missing")
    if faces.ndim != 2 or faces.shape[1] != 3 or not len(faces):
        raise LODDerivationError(f"{name}_faces_missing")
    if not np.isfinite(vertices).all() or not np.isfinite(faces).all():
        raise LODDerivationError(f"{name}_non_finite_geometry")
    if not np.issubdtype(faces.dtype, np.integer) or int(faces.min()) < 0 or int(faces.max()) >= len(vertices):
        raise LODDerivationError(f"{name}_face_indices_invalid")
    triangles = vertices[faces]
    twice_area = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    if not np.isfinite(twice_area).all() or bool(np.any(twice_area <= 1e-14)):
        raise LODDerivationError(f"{name}_degenerate_faces")
    components = len(mesh.split(only_watertight=False))
    if not components:
        raise LODDerivationError(f"{name}_components_missing")
    return {"vertices": int(len(vertices)), "faces": int(len(faces)), "components": int(components)}


def _allocate_face_budgets(face_counts: list[int], target_faces: int) -> list[int]:
    """Allocate one exact total budget while preserving every input geometry."""
    minimum = [_MINIMUM_COMPONENT_FACES] * len(face_counts)
    if target_faces < sum(minimum):
        raise LODDerivationError("target_faces_cannot_preserve_all_geometries")
    total_faces = sum(face_counts)
    remaining = target_faces - sum(minimum)
    capacity = [count - floor for count, floor in zip(face_counts, minimum)]
    total_capacity = sum(capacity)
    if not total_capacity:
        return minimum
    raw = [remaining * cap / total_capacity for cap in capacity]
    allocation = [floor + min(cap, int(math.floor(value))) for floor, cap, value in zip(minimum, capacity, raw)]
    leftover = target_faces - sum(allocation)
    # Stable tie breaking makes the allocation independent of dictionary order.
    for index in sorted(range(len(face_counts)), key=lambda item: (-(raw[item] - math.floor(raw[item])), item)):
        if not leftover:
            break
        if allocation[index] < face_counts[index]:
            allocation[index] += 1
            leftover -= 1
    if leftover:
        raise LODDerivationError("target_faces_allocation_failed")
    return allocation


def _default_simplifier(mesh: Any, target_faces: int) -> Any:
    try:
        # trimesh forwards this to fast-simplification; it is a deterministic
        # quadric pass for the same mesh/library revision and has no network or
        # model dependency.
        return mesh.simplify_quadric_decimation(face_count=target_faces)
    except Exception as exc:
        raise LODDerivationError("quadric_simplification_failed") from exc


def _safe_path_pair(master: Path, output: Path, report: Path) -> None:
    try:
        resolved_master = master.resolve(strict=True)
        resolved_output = output.resolve(strict=False)
        resolved_report = report.resolve(strict=False)
    except OSError as exc:
        raise LODDerivationError("artifact_path_unreadable") from exc
    if resolved_master == resolved_output or resolved_master == resolved_report:
        raise LODDerivationError("derivative_must_not_overwrite_master")
    if resolved_output == resolved_report:
        raise LODDerivationError("derivative_and_report_paths_must_differ")
    if not output.parent.is_dir() or not report.parent.is_dir():
        raise LODDerivationError("output_parent_missing")
    if output.exists() or report.exists():
        raise LODDerivationError("derivative_or_report_already_exists")


def _export_scene(scene: Any, staging_output: Path) -> None:
    try:
        exported = scene.export(file_type="glb")
    except Exception as exc:
        raise LODDerivationError("glb_export_failed") from exc
    if not isinstance(exported, (bytes, bytearray)) or not exported:
        raise LODDerivationError("glb_export_empty")
    staging_output.write_bytes(bytes(exported))
    try:
        validate_glb_container(staging_output)
    except UnsafeAssetError as exc:
        raise LODDerivationError(f"output_glb_invalid:{exc}") from exc


def derive_glb_lod(
    master_path: str | Path,
    output_path: str | Path,
    *,
    target_faces: int,
    report_path: str | Path | None = None,
    expected_master_sha256: str | None = None,
    simplifier: Simplifier | None = None,
) -> dict[str, Any]:
    """Create a sealed local GLB LOD without modifying its master.

    ``target_faces`` is a hard upper budget, not a percentage hint.  The
    function rejects a request that is not actually lower than the master and
    rejects output which loses a source geometry/component, has non-finite or
    degenerate faces, cannot be simplified, or fails container validation.
    The returned report is also written next to the derivative by default and
    binds both source and output SHA-256 values plus the executed settings.
    """
    if not isinstance(target_faces, int) or isinstance(target_faces, bool) or target_faces < 1:
        raise LODDerivationError("target_faces_must_be_positive_integer")
    master = Path(master_path)
    output = Path(output_path)
    report = Path(report_path) if report_path is not None else output.with_suffix(".lod-report.json")
    if master.suffix.lower() != ".glb" or output.suffix.lower() != ".glb":
        raise LODDerivationError("master_and_output_must_be_glb")
    _safe_path_pair(master, output, report)
    try:
        input_container = validate_glb_container(master)
    except UnsafeAssetError as exc:
        raise LODDerivationError(f"master_glb_invalid:{exc}") from exc
    master_hash = _sha256_file(master)
    expected = _normalise_sha256(expected_master_sha256, reason="expected_master_sha256_invalid")
    if expected is not None and expected != master_hash:
        raise LODDerivationError("expected_master_sha256_mismatch")

    trimesh = _require_trimesh()
    try:
        source_scene = trimesh.load(str(master), force="scene", process=False)
    except Exception as exc:
        raise LODDerivationError("master_glb_load_failed") from exc
    if not isinstance(source_scene, trimesh.Scene) or not source_scene.geometry:
        raise LODDerivationError("master_glb_has_no_scene_geometry")

    source_items = [(name, mesh) for name, mesh in sorted(source_scene.geometry.items()) if isinstance(mesh, trimesh.Trimesh)]
    if not source_items or len(source_items) != len(source_scene.geometry):
        raise LODDerivationError("master_glb_geometry_invalid")
    source_metrics = [_mesh_metrics(mesh, name=f"master_{index}") for index, (_, mesh) in enumerate(source_items)]
    source_faces = sum(item["faces"] for item in source_metrics)
    if target_faces >= source_faces:
        raise LODDerivationError("target_faces_must_be_lower_than_master")
    budgets = _allocate_face_budgets([item["faces"] for item in source_metrics], target_faces)

    result_scene = source_scene.copy()
    simplify = simplifier or _default_simplifier
    output_metrics: list[dict[str, int]] = []
    try:
        for index, ((name, mesh), before, budget) in enumerate(zip(source_items, source_metrics, budgets)):
            if budget >= before["faces"]:
                derived = mesh.copy()
            else:
                derived = simplify(mesh.copy(), budget)
            if not isinstance(derived, trimesh.Trimesh):
                raise LODDerivationError("simplifier_returned_invalid_mesh")
            after = _mesh_metrics(derived, name=f"lod_{index}")
            if after["faces"] > budget:
                raise LODDerivationError("simplifier_exceeded_target_faces")
            if after["faces"] >= before["faces"]:
                raise LODDerivationError("simplifier_did_not_reduce_geometry")
            if after["components"] != before["components"]:
                raise LODDerivationError("simplifier_changed_component_count")
            result_scene.geometry[name] = derived
            output_metrics.append(after)
    except LODDerivationError:
        raise
    except Exception as exc:
        raise LODDerivationError("simplification_failed") from exc

    actual_faces = sum(item["faces"] for item in output_metrics)
    if not 0 < actual_faces <= target_faces or actual_faces >= source_faces:
        raise LODDerivationError("output_face_budget_invalid")

    staging_directory = output.parent
    staging_output: Path | None = None
    staging_report: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=f".{output.stem}.lod-", suffix=".glb", dir=staging_directory, delete=False) as handle:
            staging_output = Path(handle.name)
        _export_scene(result_scene, staging_output)
        output_hash = _sha256_file(staging_output)
        report_payload: dict[str, Any] = {
            "schema_version": LOD_DERIVATION_SCHEMA_VERSION,
            "kind": "local_glb_lod_derivation",
            "status": "pass",
            "deterministic": True,
            "algorithm": "trimesh_quadric_decimation",
            "source_master": {
                "path": master.name,
                "sha256": f"sha256:{master_hash}",
                "container": input_container,
                "faces": source_faces,
            },
            "output": {
                "path": output.name,
                "sha256": f"sha256:{output_hash}",
                "faces": actual_faces,
            },
            "settings": {"target_faces": target_faces, "per_geometry_target_faces": budgets},
            "geometry": {"source": source_metrics, "output": output_metrics},
            "limitations": "geometry_only; topology changed and PBR textures require independent rebake and runtime validation",
        }
        seal_input = dict(report_payload)
        report_payload["seal"] = {"algorithm": "sha256", "value": f"sha256:{hashlib.sha256(_canonical_json(seal_input)).hexdigest()}"}
        with tempfile.NamedTemporaryFile(prefix=f".{report.stem}.", suffix=".json", dir=report.parent, delete=False, mode="wb") as handle:
            staging_report = Path(handle.name)
            handle.write(_canonical_json(report_payload))
            handle.write(b"\n")
        # Both artifacts were fully generated and validated before either
        # visible name changes.  Existing names were rejected above.
        os.replace(staging_output, output)
        staging_output = None
        os.replace(staging_report, report)
        staging_report = None
        return report_payload
    except LODDerivationError:
        raise
    except OSError as exc:
        raise LODDerivationError("derivative_commit_failed") from exc
    finally:
        for temporary in (staging_output, staging_report):
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


# Intentional descriptive alias for workflow code.
derive_local_glb_lod = derive_glb_lod
