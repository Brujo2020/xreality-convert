"""Deterministic, structural parity gate for resident versus isolated Shape."""

from __future__ import annotations

import math

import numpy as np
import trimesh


DEFAULT_POLICY = {
    "max_relative_faces_delta": 0.05,
    "max_relative_vertices_delta": 0.05,
    "max_component_delta": 1,
    "max_relative_extent_delta": 0.03,
    "max_worker_latency_ratio": 1.20,
}


def mesh_metrics(mesh):
    """Measure only geometry facts; no image or aesthetic claim is made here."""
    if isinstance(mesh, trimesh.Scene):
        geometries = [item for item in mesh.geometry.values() if isinstance(item, trimesh.Trimesh)]
        mesh = trimesh.util.concatenate(geometries) if geometries else trimesh.Trimesh()
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)
    finite = bool(len(vertices)) and bool(np.isfinite(vertices).all())
    components = len(mesh.split(only_watertight=False)) if len(faces) else 0
    extents = np.asarray(mesh.extents, dtype=float) if len(vertices) else np.zeros(3)
    return {
        "vertices": int(len(vertices)),
        "faces": int(len(faces)),
        "finite_vertices": finite,
        "components": int(components),
        "extents": [round(float(value), 8) for value in extents],
        "watertight": bool(mesh.is_watertight),
    }


def _relative_delta(left, right):
    return abs(float(left) - float(right)) / max(1.0, abs(float(left)))


def compare(resident, worker, *, resident_seconds, worker_seconds, policy=None):
    policy = {**DEFAULT_POLICY, **(policy or {})}
    resident_metrics = mesh_metrics(resident)
    worker_metrics = mesh_metrics(worker)
    face_delta = _relative_delta(resident_metrics["faces"], worker_metrics["faces"])
    vertex_delta = _relative_delta(resident_metrics["vertices"], worker_metrics["vertices"])
    extent_delta = max(
        (_relative_delta(left, right) for left, right in zip(resident_metrics["extents"], worker_metrics["extents"])),
        default=0.0,
    )
    latency_ratio = float(worker_seconds) / max(0.001, float(resident_seconds))
    checks = {
        "resident_finite": resident_metrics["finite_vertices"],
        "worker_finite": worker_metrics["finite_vertices"],
        "faces": face_delta <= policy["max_relative_faces_delta"],
        "vertices": vertex_delta <= policy["max_relative_vertices_delta"],
        "components": abs(resident_metrics["components"] - worker_metrics["components"]) <= policy["max_component_delta"],
        "extents": extent_delta <= policy["max_relative_extent_delta"],
        "latency": latency_ratio <= policy["max_worker_latency_ratio"],
    }
    return {
        "schema_version": 1,
        "policy": policy,
        "resident": {"seconds": round(float(resident_seconds), 3), "mesh": resident_metrics},
        "worker": {"seconds": round(float(worker_seconds), 3), "mesh": worker_metrics},
        "deltas": {
            "faces_relative": round(face_delta, 6),
            "vertices_relative": round(vertex_delta, 6),
            "extents_relative": round(extent_delta, 6),
            "latency_ratio": round(latency_ratio, 6),
        },
        "checks": checks,
        "promotion_recommended": all(checks.values()),
        "scope": "structural_and_latency_only; visual parity and corpus evidence remain required",
    }
