"""Fail-closed, deterministic execution for the first typed Buffalo edit.

Only ``replace_material`` is implemented here.  It is deliberately a narrow
metadata edit: geometry, UVs, textures, nodes and the input master are never
modified.  Part localisation is supplied by the master GLB itself through
``node.extras.xrealityPartId`` (or ``node.extras.xreality.part_id``).  This
keeps a semantic edit request from becoming an unbounded DCC script.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path
from typing import Any

from pbr_glb import _read_glb, _write_glb
from secure_artifacts import UnsafeAssetError, validate_glb_container


EDIT_EXECUTOR_VERSION = "xreality-typed-edit-executor-v1"
_DELTA_KEYS = {
    "schema_version", "source_master_hash", "edit_type", "target_part_ids",
    "protected_part_ids", "geometry_operation", "material_operation", "tolerances",
}
_OPERATION_KEYS = {"base_color_factor", "metallic_factor", "roughness_factor", "label"}
_ZERO_TOLERANCES = {
    "protected_geometry_delta", "protected_uv_delta", "protected_material_delta",
}


class EditExecutionError(ValueError):
    """A typed edit cannot safely be applied to this master."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fail(code: str) -> None:
    raise EditExecutionError(code)


def _id_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail(f"{name}_required")
    if any(not isinstance(item, str) or not item or len(item) > 128 for item in value):
        _fail(f"invalid_{name}")
    if len(set(value)) != len(value) or value != sorted(value):
        _fail(f"noncanonical_{name}")
    return list(value)


def _unit_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"invalid_{name}")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        _fail(f"invalid_{name}")
    return number


def validate_replace_material_delta(delta: Any, source_sha256: str) -> dict[str, Any]:
    """Validate the complete bounded contract before reading/modifying assets."""
    if not isinstance(delta, dict) or set(delta) != _DELTA_KEYS:
        _fail("invalid_edit_delta_schema")
    if delta.get("schema_version") != 3 or delta.get("edit_type") != "replace_material":
        _fail("unsupported_edit_type")
    expected_hash = delta.get("source_master_hash")
    if expected_hash != f"sha256:{source_sha256}":
        _fail("source_master_hash_mismatch")
    targets = _id_list(delta.get("target_part_ids"), "target_part_ids")
    protected_raw = delta.get("protected_part_ids")
    if not isinstance(protected_raw, list):
        _fail("invalid_protected_part_ids")
    protected = [] if not protected_raw else _id_list(protected_raw, "protected_part_ids")
    overlap = sorted(set(targets) & set(protected))
    if overlap:
        _fail("target_protected_overlap:" + ",".join(overlap))
    if delta.get("geometry_operation") is not None:
        _fail("geometry_operation_not_allowed")

    tolerances = delta.get("tolerances")
    if not isinstance(tolerances, dict) or set(tolerances) != _ZERO_TOLERANCES:
        _fail("invalid_protected_tolerances")
    for key in sorted(_ZERO_TOLERANCES):
        value = tolerances.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            _fail("invalid_protected_tolerances")
        if float(value) != 0.0:
            _fail("protected_tolerance_must_be_zero")

    operation = delta.get("material_operation")
    if not isinstance(operation, dict) or not operation or set(operation) - _OPERATION_KEYS:
        _fail("invalid_material_operation")
    normalized: dict[str, Any] = {}
    if "base_color_factor" in operation:
        color = operation["base_color_factor"]
        if not isinstance(color, list) or len(color) != 4:
            _fail("invalid_base_color_factor")
        normalized["base_color_factor"] = [_unit_number(value, "base_color_factor") for value in color]
    for key in ("metallic_factor", "roughness_factor"):
        if key in operation:
            normalized[key] = _unit_number(operation[key], key)
    if "label" in operation:
        label = operation["label"]
        if not isinstance(label, str) or not label.strip() or len(label) > 128 or any(ord(char) < 32 for char in label):
            _fail("invalid_material_label")
        normalized["label"] = label.strip()
    if not normalized:
        _fail("empty_material_operation")
    return {"targets": targets, "protected": protected, "operation": normalized}


def _part_id(node: dict[str, Any]) -> str | None:
    extras = node.get("extras")
    if not isinstance(extras, dict):
        return None
    direct = extras.get("xrealityPartId")
    nested = extras.get("xreality")
    candidate = direct if isinstance(direct, str) else (nested or {}).get("part_id") if isinstance(nested, dict) else None
    return candidate if isinstance(candidate, str) and candidate else None


def _resolve_part_primitives(document: dict[str, Any], requested_ids: list[str]) -> dict[str, list[tuple[int, int]]]:
    nodes = document.get("nodes")
    meshes = document.get("meshes")
    if not isinstance(nodes, list) or not isinstance(meshes, list):
        _fail("missing_glb_nodes_or_meshes")
    requested = set(requested_ids)
    resolved = {part_id: [] for part_id in requested_ids}
    for node_index, node in enumerate(nodes):
        if not isinstance(node, dict):
            _fail("invalid_glb_node")
        part_id = _part_id(node)
        if part_id not in requested:
            continue
        mesh_index = node.get("mesh")
        if not isinstance(mesh_index, int) or isinstance(mesh_index, bool) or not 0 <= mesh_index < len(meshes):
            _fail(f"invalid_part_mesh:{part_id}")
        mesh = meshes[mesh_index]
        primitives = mesh.get("primitives") if isinstance(mesh, dict) else None
        if not isinstance(primitives, list) or not primitives:
            _fail(f"part_has_no_primitives:{part_id}")
        for primitive_index, primitive in enumerate(primitives):
            if not isinstance(primitive, dict):
                _fail("invalid_glb_primitive")
            resolved[part_id].append((mesh_index, primitive_index))
    for part_id, references in resolved.items():
        resolved[part_id] = sorted(set(references))
        if not references:
            _fail(f"unresolved_part_id:{part_id}")
    return resolved


def _edited_material(source: dict[str, Any], operation: dict[str, Any], target_id: str) -> dict[str, Any]:
    material = deepcopy(source)
    pbr = material.setdefault("pbrMetallicRoughness", {})
    if not isinstance(pbr, dict):
        _fail("invalid_source_material")
    if "base_color_factor" in operation:
        pbr["baseColorFactor"] = operation["base_color_factor"]
    if "metallic_factor" in operation:
        pbr["metallicFactor"] = operation["metallic_factor"]
    if "roughness_factor" in operation:
        pbr["roughnessFactor"] = operation["roughness_factor"]
    material["name"] = operation.get("label") or f"xreality-replace-material-{target_id}"
    extras = material.setdefault("extras", {})
    if not isinstance(extras, dict):
        _fail("invalid_source_material")
    extras["xrealityTypedEdit"] = {
        "version": EDIT_EXECUTOR_VERSION,
        "editType": "replace_material",
        "targetPartId": target_id,
    }
    return material


def execute_replace_material(source_path: str | Path, output_path: str | Path, delta: dict[str, Any]) -> dict[str, Any]:
    """Create a new GLB with scoped PBR changes, or fail without an output."""
    source = Path(source_path)
    output = Path(output_path)
    if not source.is_file():
        _fail("source_master_missing")
    if source.resolve() == output.resolve():
        _fail("output_must_not_mutate_source")
    if output.exists() or not output.parent.is_dir():
        _fail("output_path_not_new")
    try:
        input_structure = validate_glb_container(source)
    except UnsafeAssetError as exc:
        _fail(f"unsafe_source_glb:{exc}")
    source_hash = _sha256(source)
    contract = validate_replace_material_delta(delta, source_hash)
    document, binary = _read_glb(source)
    if not isinstance(document, dict):
        _fail("invalid_glb_document")
    all_ids = contract["targets"] + contract["protected"]
    locations = _resolve_part_primitives(document, all_ids)
    target_primitives = {reference for part_id in contract["targets"] for reference in locations[part_id]}
    protected_primitives = {reference for part_id in contract["protected"] for reference in locations[part_id]}
    if target_primitives & protected_primitives:
        _fail("target_protected_primitive_overlap")
    target_owners = {
        reference: [part_id for part_id in contract["targets"] if reference in locations[part_id]]
        for reference in target_primitives
    }
    if any(len(owners) != 1 for owners in target_owners.values()):
        _fail("ambiguous_target_primitive_ownership")

    materials = document.get("materials")
    meshes = document.get("meshes")
    if not isinstance(materials, list) or not materials or not isinstance(meshes, list):
        _fail("missing_glb_materials")
    modified = []
    for part_id in contract["targets"]:
        for mesh_index, primitive_index in locations[part_id]:
            primitive = meshes[mesh_index]["primitives"][primitive_index]
            material_index = primitive.get("material")
            if not isinstance(material_index, int) or isinstance(material_index, bool) or not 0 <= material_index < len(materials):
                _fail(f"target_missing_material:{part_id}")
            new_material = _edited_material(materials[material_index], contract["operation"], part_id)
            materials.append(new_material)
            primitive["material"] = len(materials) - 1
            modified.append({"part_id": part_id, "mesh": mesh_index, "primitive": primitive_index, "material": len(materials) - 1})

    if not modified:
        _fail("no_target_primitives")
    _write_glb(output, document, binary)
    try:
        output_structure = validate_glb_container(output)
    except UnsafeAssetError as exc:
        output.unlink(missing_ok=True)
        _fail(f"unsafe_output_glb:{exc}")
    if output_structure["nodes"] != input_structure["nodes"] or output_structure["images"] != input_structure["images"]:
        output.unlink(missing_ok=True)
        _fail("structural_glb_drift")
    if _sha256(source) != source_hash:
        output.unlink(missing_ok=True)
        _fail("source_master_changed_during_edit")
    return {
        "version": EDIT_EXECUTOR_VERSION,
        "edit_type": "replace_material",
        "source_sha256": source_hash,
        "output_sha256": _sha256(output),
        "output": str(output),
        "modified_primitives": modified,
        "structural_validation": output_structure,
    }
