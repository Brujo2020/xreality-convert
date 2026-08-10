"""Local, deterministic GLB delivery checks for constrained runtime targets.

This module deliberately certifies only a bounded structural subset of glTF 2.0
and local delivery budgets.  It does *not* open a browser, headset, mobile
device, or WebGL renderer: a passing result is not evidence of visual or
runtime rendering quality.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import struct
from typing import Any

from secure_artifacts import UnsafeAssetError, validate_glb_container


CERTIFICATION_SCHEMA_VERSION = 1
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A
GLB_BIN = 0x004E4942


class RuntimeCertificationError(ValueError):
    """The artifact cannot receive a local target-runtime certificate."""


@dataclass(frozen=True)
class TargetBudget:
    name: str
    max_bytes: int
    max_triangles: int
    max_vertices: int
    max_nodes: int
    max_meshes: int
    max_primitives: int
    max_materials: int
    max_images: int
    max_textures: int


# These are conservative delivery policies, rather than vendor promises.  A
# caller can display the exact profile in its UI and choose a lighter derivative
# when it does not pass.
TARGET_BUDGETS: dict[str, TargetBudget] = {
    "web": TargetBudget("web", 25 * 1024 * 1024, 250_000, 250_000, 2_048, 256, 512, 128, 64, 64),
    "xr": TargetBudget("xr", 12 * 1024 * 1024, 120_000, 120_000, 512, 64, 128, 32, 32, 32),
    "mobile": TargetBudget("mobile", 8 * 1024 * 1024, 75_000, 75_000, 256, 32, 64, 16, 16, 16),
}

_COMPONENT_BYTES = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
_TYPE_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_INDEX_COMPONENT_TYPES = {5121, 5123, 5125}
_TRIANGLE_MODES = {4, 5, 6}  # TRIANGLES, TRIANGLE_STRIP, TRIANGLE_FAN


def _positive_int(value: Any, reason: str, *, zero: bool = True) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < (0 if zero else 1):
        raise RuntimeCertificationError(reason)
    return value


def _list(document: dict[str, Any], key: str) -> list[Any]:
    value = document.get(key, [])
    if not isinstance(value, list):
        raise RuntimeCertificationError(f"invalid_{key}")
    return value


def _read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read a complete GLB, rejecting trailing or malformed chunks."""
    raw = path.read_bytes()
    if len(raw) < 20:
        raise RuntimeCertificationError("glb_missing_or_too_small")
    magic, version, declared_length = struct.unpack_from("<III", raw, 0)
    if magic != GLB_MAGIC or version != 2 or declared_length != len(raw):
        raise RuntimeCertificationError("invalid_glb_header")
    json_length, json_type = struct.unpack_from("<II", raw, 12)
    json_end = 20 + json_length
    if json_type != GLB_JSON or json_end > len(raw):
        raise RuntimeCertificationError("invalid_glb_json_chunk")
    try:
        document = json.loads(raw[20:json_end].decode("utf-8").rstrip(" \t\r\n\x00"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeCertificationError("invalid_glb_json") from exc
    if not isinstance(document, dict):
        raise RuntimeCertificationError("invalid_glb_document")
    if json_end == len(raw):
        return document, b""
    if json_end + 8 > len(raw):
        raise RuntimeCertificationError("truncated_glb_bin")
    binary_length, binary_type = struct.unpack_from("<II", raw, json_end)
    binary_start = json_end + 8
    binary_end = binary_start + binary_length
    if binary_type != GLB_BIN or binary_end != len(raw):
        raise RuntimeCertificationError("invalid_glb_bin_chunk")
    return document, raw[binary_start:binary_end]


def _accessor_count(accessors: list[Any], index: Any, reason: str) -> int:
    if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(accessors):
        raise RuntimeCertificationError(reason)
    accessor = accessors[index]
    if not isinstance(accessor, dict):
        raise RuntimeCertificationError("invalid_accessor")
    return _positive_int(accessor.get("count"), "invalid_accessor_count", zero=False)


def _validate_structure(document: dict[str, Any], binary: bytes) -> dict[str, int]:
    asset = document.get("asset")
    if not isinstance(asset, dict) or asset.get("version") != "2.0":
        raise RuntimeCertificationError("unsupported_gltf_version")

    buffers = _list(document, "buffers")
    buffer_views = _list(document, "bufferViews")
    accessors = _list(document, "accessors")
    meshes = _list(document, "meshes")
    nodes = _list(document, "nodes")
    materials = _list(document, "materials")
    images = _list(document, "images")
    textures = _list(document, "textures")
    scenes = _list(document, "scenes")
    if len(buffers) != 1 or not isinstance(buffers[0], dict) or "uri" in buffers[0]:
        raise RuntimeCertificationError("glb_requires_single_embedded_buffer")
    buffer_bytes = _positive_int(buffers[0].get("byteLength"), "invalid_buffer_length")
    if buffer_bytes > len(binary):
        raise RuntimeCertificationError("truncated_buffer_data")

    for view in buffer_views:
        if not isinstance(view, dict) or view.get("buffer") != 0:
            raise RuntimeCertificationError("invalid_buffer_view")
        offset = _positive_int(view.get("byteOffset", 0), "invalid_buffer_view_offset")
        length = _positive_int(view.get("byteLength"), "invalid_buffer_view_length", zero=False)
        if offset + length > buffer_bytes:
            raise RuntimeCertificationError("buffer_view_out_of_bounds")

    for accessor in accessors:
        if not isinstance(accessor, dict) or "sparse" in accessor:
            raise RuntimeCertificationError("unsupported_or_invalid_accessor")
        view_index = accessor.get("bufferView")
        if not isinstance(view_index, int) or isinstance(view_index, bool) or not 0 <= view_index < len(buffer_views):
            raise RuntimeCertificationError("accessor_missing_buffer_view")
        component_type = accessor.get("componentType")
        value_type = accessor.get("type")
        if component_type not in _COMPONENT_BYTES or value_type not in _TYPE_COMPONENTS:
            raise RuntimeCertificationError("unsupported_accessor_format")
        count = _positive_int(accessor.get("count"), "invalid_accessor_count", zero=False)
        offset = _positive_int(accessor.get("byteOffset", 0), "invalid_accessor_offset")
        view = buffer_views[view_index]
        stride = view.get("byteStride", _COMPONENT_BYTES[component_type] * _TYPE_COMPONENTS[value_type])
        stride = _positive_int(stride, "invalid_accessor_stride", zero=False)
        element_bytes = _COMPONENT_BYTES[component_type] * _TYPE_COMPONENTS[value_type]
        if stride < element_bytes or offset + (count - 1) * stride + element_bytes > view["byteLength"]:
            raise RuntimeCertificationError("accessor_out_of_bounds")

    if not meshes:
        raise RuntimeCertificationError("missing_meshes")
    total_primitives = total_triangles = total_vertices = 0
    for mesh in meshes:
        if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives"), list) or not mesh["primitives"]:
            raise RuntimeCertificationError("invalid_mesh_primitives")
        for primitive in mesh["primitives"]:
            if not isinstance(primitive, dict) or not isinstance(primitive.get("attributes"), dict):
                raise RuntimeCertificationError("invalid_primitive")
            position = primitive["attributes"].get("POSITION")
            vertices = _accessor_count(accessors, position, "primitive_missing_position")
            mode = primitive.get("mode", 4)
            if mode not in _TRIANGLE_MODES:
                raise RuntimeCertificationError("unsupported_primitive_mode")
            drawn = _accessor_count(accessors, primitive["indices"], "invalid_primitive_indices") if "indices" in primitive else vertices
            if "indices" in primitive and accessors[primitive["indices"]].get("componentType") not in _INDEX_COMPONENT_TYPES:
                raise RuntimeCertificationError("invalid_index_component_type")
            triangles = drawn // 3 if mode == 4 else max(0, drawn - 2)
            material = primitive.get("material")
            if material is not None and (not isinstance(material, int) or isinstance(material, bool) or not 0 <= material < len(materials)):
                raise RuntimeCertificationError("invalid_primitive_material")
            total_primitives += 1
            total_vertices += vertices
            total_triangles += triangles

    for node in nodes:
        if not isinstance(node, dict):
            raise RuntimeCertificationError("invalid_node")
        mesh = node.get("mesh")
        if mesh is not None and (not isinstance(mesh, int) or isinstance(mesh, bool) or not 0 <= mesh < len(meshes)):
            raise RuntimeCertificationError("invalid_node_mesh")
    if not scenes:
        raise RuntimeCertificationError("missing_scene")
    scene_index = document.get("scene", 0)
    if not isinstance(scene_index, int) or isinstance(scene_index, bool) or not 0 <= scene_index < len(scenes):
        raise RuntimeCertificationError("invalid_default_scene")
    roots = scenes[scene_index].get("nodes") if isinstance(scenes[scene_index], dict) else None
    if not isinstance(roots, list) or not roots:
        raise RuntimeCertificationError("empty_default_scene")
    for root in roots:
        if not isinstance(root, int) or isinstance(root, bool) or not 0 <= root < len(nodes):
            raise RuntimeCertificationError("invalid_scene_node")

    return {
        "triangles": total_triangles,
        "vertices": total_vertices,
        "nodes": len(nodes),
        "meshes": len(meshes),
        "primitives": total_primitives,
        "materials": len(materials),
        "images": len(images),
        "textures": len(textures),
    }


def _budget_checks(facts: dict[str, int], artifact_bytes: int, budget: TargetBudget) -> dict[str, dict[str, int | str]]:
    observed = {"bytes": artifact_bytes, **facts}
    limits = {
        "bytes": budget.max_bytes, "triangles": budget.max_triangles, "vertices": budget.max_vertices,
        "nodes": budget.max_nodes, "meshes": budget.max_meshes, "primitives": budget.max_primitives,
        "materials": budget.max_materials, "images": budget.max_images, "textures": budget.max_textures,
    }
    return {key: {"status": "pass" if observed[key] <= limit else "fail", "observed": observed[key], "limit": limit}
            for key, limit in limits.items()}


def certify_glb_for_target(path: str | Path, target: str) -> dict[str, Any]:
    """Fail closed unless ``path`` fits the declared local delivery profile.

    The returned certificate intentionally records render and device validation
    as ``not_measured``.  It must not be used to claim a successful viewer run.
    """
    if target not in TARGET_BUDGETS:
        raise RuntimeCertificationError("unknown_runtime_target")
    source = Path(path)
    try:
        validate_glb_container(source)
        document, binary = _read_glb(source)
    except UnsafeAssetError as exc:
        raise RuntimeCertificationError(f"invalid_artifact:{exc}") from exc
    except OSError as exc:
        raise RuntimeCertificationError("invalid_artifact:unreadable") from exc
    facts = _validate_structure(document, binary)
    checks = _budget_checks(facts, source.stat().st_size, TARGET_BUDGETS[target])
    failures = [name for name, check in checks.items() if check["status"] != "pass"]
    if failures:
        raise RuntimeCertificationError("runtime_budget_exceeded:" + ",".join(failures))
    return {
        "schema_version": CERTIFICATION_SCHEMA_VERSION,
        "status": "pass",
        "target": target,
        "target_budget": asdict(TARGET_BUDGETS[target]),
        "artifact": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "facts": {"bytes": source.stat().st_size, **facts},
        "checks": checks,
        "evidence_scope": {
            "glb_structure": "measured_local",
            "target_budget": "measured_local",
            "viewer_rendering": "not_measured",
            "device_runtime": "not_measured",
        },
    }
