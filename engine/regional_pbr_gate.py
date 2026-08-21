"""Fail-closed audit for region-aware PBR assets.

``validate_material_contract`` answers whether a GLB has a usable set of PBR
maps.  This gate answers the stricter question needed before a master is
promoted: does each *declared semantic material region* map to a distinct,
textured GLB material?  It intentionally verifies declarations and container
facts only.  Texture-to-surface alignment, map contents and relighting remain
``not_measured`` until an independent UV/render review supplies evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from runtime_certification import RuntimeCertificationError, _read_glb
from secure_artifacts import UnsafeAssetError, validate_glb_container


REGIONAL_PBR_SCHEMA_VERSION = 1
REGIONAL_CONTRACT_SCHEMA_VERSION = 1
MAP_ROLES = frozenset({"base_color", "metallic_roughness", "normal", "occlusion", "emissive"})
MINIMUM_PBR_ROLES = frozenset({"base_color", "metallic_roughness"})
GLOBAL_REGION_NAMES = frozenset({
    "all", "global", "global_material", "whole_asset", "entire_asset", "dominant_material",
})


class RegionalPBRAuditError(ValueError):
    """A supplied graph or regional map contract is not safe to audit."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_list(value: Any) -> list[Any] | None:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else None


def _semantic_regions(graph: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return [], ["semantic_graph_nodes_required"]
    regions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping) or node.get("kind") != "material_region":
            continue
        region_id = node.get("id")
        name = node.get("canonical_name")
        if not isinstance(region_id, str) or not region_id:
            errors.append("semantic_region_id_required")
            continue
        if region_id in seen:
            errors.append(f"duplicate_semantic_region:{region_id}")
            continue
        seen.add(region_id)
        if not isinstance(name, str) or not name:
            errors.append(f"semantic_region_name_required:{region_id}")
            continue
        if name.strip().lower() in GLOBAL_REGION_NAMES:
            errors.append(f"global_region_conflation:{region_id}")
            continue
        regions.append({
            "id": region_id,
            "name": name,
            "evidence_class": node.get("evidence_class", "not_measured"),
        })
    if not regions and not errors:
        errors.append("semantic_material_regions_required")
    return sorted(regions, key=lambda item: item["id"]), sorted(set(errors))


def _contract_regions(
    contract: Mapping[str, Any], semantic_region_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Normalize an explicit, one-region-to-one-material map contract."""
    errors: list[str] = []
    if contract.get("schema_version") != REGIONAL_CONTRACT_SCHEMA_VERSION:
        errors.append("regional_contract_schema_version_required")
    region_count = contract.get("region_count")
    if not _is_int(region_count) or region_count < 1:
        errors.append("regional_contract_region_count_required")
    elif region_count != len(semantic_region_ids):
        errors.append("regional_contract_region_count_mismatch")
    raw_regions = contract.get("region_maps")
    if not isinstance(raw_regions, Mapping):
        return {}, sorted(set(errors + ["regional_contract_region_maps_required"]))
    supplied_ids = set(raw_regions)
    if supplied_ids != semantic_region_ids:
        errors.append("regional_contract_region_coverage_mismatch")

    normalized: dict[str, dict[str, Any]] = {}
    for region_id in sorted(semantic_region_ids & supplied_ids):
        value = raw_regions[region_id]
        if not isinstance(value, Mapping):
            errors.append(f"regional_contract_invalid_region:{region_id}")
            continue
        material_index = value.get("material_index")
        if not _is_int(material_index) or material_index < 0:
            errors.append(f"regional_contract_material_index_required:{region_id}")
            continue
        roles = _as_list(value.get("required_maps"))
        if not roles:
            errors.append(f"regional_contract_required_maps_required:{region_id}")
            continue
        if any(not isinstance(role, str) or role not in MAP_ROLES for role in roles):
            errors.append(f"regional_contract_unknown_map_role:{region_id}")
            continue
        role_set = frozenset(roles)
        if len(role_set) != len(roles):
            errors.append(f"regional_contract_duplicate_map_role:{region_id}")
            continue
        if not MINIMUM_PBR_ROLES.issubset(role_set):
            errors.append(f"regional_contract_minimum_pbr_maps_required:{region_id}")
            continue
        normalized[region_id] = {"material_index": material_index, "required_maps": sorted(role_set)}

    indices = [item["material_index"] for item in normalized.values()]
    if len(indices) != len(set(indices)):
        errors.append("global_material_conflation")
    return normalized, sorted(set(errors))


def _texture_info(material: Mapping[str, Any], role: str) -> Any:
    pbr = material.get("pbrMetallicRoughness")
    pbr = pbr if isinstance(pbr, Mapping) else {}
    if role == "base_color":
        return pbr.get("baseColorTexture")
    if role == "metallic_roughness":
        return pbr.get("metallicRoughnessTexture")
    return material.get({"normal": "normalTexture", "occlusion": "occlusionTexture", "emissive": "emissiveTexture"}[role])


def _texture_is_embedded(document: Mapping[str, Any], info: Any) -> tuple[bool, int | None]:
    if not isinstance(info, Mapping) or not _is_int(info.get("index")):
        return False, None
    textures = document.get("textures")
    images = document.get("images")
    index = info["index"]
    if not isinstance(textures, list) or not isinstance(images, list) or not 0 <= index < len(textures):
        return False, None
    texture = textures[index]
    source = texture.get("source") if isinstance(texture, Mapping) else None
    if not _is_int(source) or not 0 <= source < len(images):
        return False, None
    image = images[source]
    if not isinstance(image, Mapping) or "uri" in image or not _is_int(image.get("bufferView")):
        return False, None
    views = document.get("bufferViews")
    if not isinstance(views, list) or not 0 <= image["bufferView"] < len(views):
        return False, None
    return True, _texture_texcoord(info)


def _texture_texcoord(info: Mapping[str, Any]) -> int | None:
    transform = info.get("extensions")
    transform = transform.get("KHR_texture_transform") if isinstance(transform, Mapping) else None
    coordinate = transform.get("texCoord", info.get("texCoord", 0)) if isinstance(transform, Mapping) else info.get("texCoord", 0)
    return coordinate if _is_int(coordinate) and coordinate >= 0 else None


def _base_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return {
        "schema_version": REGIONAL_PBR_SCHEMA_VERSION,
        "status": "reject",
        "passed": False,
        "artifact": {"path": str(source)},
        "regions": [],
        "failures": [],
        "evidence_scope": {
            "semantic_to_glb_material_binding": "measured_local",
            "embedded_map_presence": "measured_local",
            "primitive_uv_binding": "measured_local",
            "texture_to_surface_region_alignment": "not_measured",
            "map_content_physical_plausibility": "not_measured",
            "uv_overlap_stretch_and_gutters": "not_measured",
            "relighting_and_visual_quality": "not_measured",
        },
    }


def audit_regional_pbr(
    glb_path: str | Path,
    semantic_graph: Mapping[str, Any],
    regional_map_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit explicitly bound semantic regions against embedded GLB PBR maps.

    ``regional_map_contract`` is deliberately mandatory and has this shape::

        {"schema_version": 1, "region_count": 2, "region_maps": {
          "semantic-region-id": {"material_index": 0,
             "required_maps": ["base_color", "metallic_roughness", "normal"]}
        }}

    Every semantic region must bind a different GLB material.  A texture factor,
    an unbound material, a shared material, or an absent embedded texture is a
    rejection.  A pass must never be read as proof that the texture pixels are
    correctly segmented or physically plausible; those lanes remain explicit
    ``not_measured`` evidence.
    """
    report = _base_report(glb_path)
    if not isinstance(semantic_graph, Mapping):
        report["failures"] = ["semantic_graph_required"]
        return report
    if not isinstance(regional_map_contract, Mapping):
        report["failures"] = ["regional_map_contract_required"]
        return report
    regions, graph_errors = _semantic_regions(semantic_graph)
    normalized, contract_errors = _contract_regions(regional_map_contract, {item["id"] for item in regions})
    report["regions"] = [{**item, "binding": normalized.get(item["id"])} for item in regions]
    if graph_errors or contract_errors:
        report["failures"] = sorted(set(graph_errors + contract_errors))
        return report

    source = Path(glb_path)
    try:
        container = validate_glb_container(source)
        document, _ = _read_glb(source)
    except (UnsafeAssetError, RuntimeCertificationError, OSError) as exc:
        report["failures"] = [f"unsafe_or_invalid_glb:{exc}"]
        return report
    report["artifact"].update({"sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "container": container})
    materials = document.get("materials")
    meshes = document.get("meshes")
    if not isinstance(materials, list) or not isinstance(meshes, list):
        report["failures"] = ["glb_materials_and_meshes_required"]
        return report

    failures: list[str] = []
    usage: dict[int, list[Mapping[str, Any]]] = {}
    for mesh in meshes:
        primitives = mesh.get("primitives") if isinstance(mesh, Mapping) else None
        if not isinstance(primitives, list):
            failures.append("invalid_mesh_primitives")
            continue
        for primitive in primitives:
            if not isinstance(primitive, Mapping):
                failures.append("invalid_primitive")
                continue
            index = primitive.get("material")
            if not _is_int(index) or not 0 <= index < len(materials):
                failures.append("primitive_without_valid_material")
                continue
            usage.setdefault(index, []).append(primitive)
    if not usage:
        failures.append("materialized_primitives_required")

    bound_indices = {binding["material_index"] for binding in normalized.values()}
    for index in sorted(usage):
        if index not in bound_indices:
            failures.append(f"unbound_glb_material:{index}")
    for region_id, binding in sorted(normalized.items()):
        index = binding["material_index"]
        if not 0 <= index < len(materials):
            failures.append(f"bound_material_out_of_range:{region_id}")
            continue
        primitives = usage.get(index, [])
        if not primitives:
            failures.append(f"unreferenced_region_material:{region_id}")
        material = materials[index]
        if not isinstance(material, Mapping):
            failures.append(f"invalid_region_material:{region_id}")
            continue
        for role in binding["required_maps"]:
            embedded, texcoord = _texture_is_embedded(document, _texture_info(material, role))
            if not embedded:
                failures.append(f"missing_embedded_map:{region_id}:{role}")
                continue
            if texcoord is None:
                failures.append(f"invalid_map_texcoord:{region_id}:{role}")
                continue
            for primitive in primitives:
                attributes = primitive.get("attributes")
                if not isinstance(attributes, Mapping) or f"TEXCOORD_{texcoord}" not in attributes:
                    failures.append(f"missing_uv_for_map:{region_id}:{role}:TEXCOORD_{texcoord}")

    report["failures"] = sorted(set(failures))
    report["status"] = "pass" if not report["failures"] else "reject"
    report["passed"] = not report["failures"]
    return report

