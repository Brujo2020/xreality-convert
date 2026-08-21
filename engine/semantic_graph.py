"""Deterministic semantic part/material graph compiler.

This module deliberately compiles a *contract*, not a model prediction.  A
caller may attach measured localizers later, but ambiguous identities,
unrecognised evidence states, and a material declaration that tries to erase
regional distinctions are rejected before Shape or Paint can consume it.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


GRAPH_SCHEMA_VERSION = 1
EVIDENCE_CLASSES = frozenset({
    "measured", "user_asserted", "inferred", "synthetic", "not_measured",
})
LOCALIZER_KEYS = frozenset({"aabb", "obb", "component_ids", "surface_mask_hash"})
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{7,127}$")
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,95}$")
_SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_GLOBAL_MATERIAL_NAMES = frozenset({
    "all", "global", "global_material", "whole_asset", "entire_asset",
    "dominant_material",
})


class SemanticGraphError(ValueError):
    """A semantic contract is unsafe or too ambiguous to compile."""


def stable_semantic_id(category: str, kind: str, canonical_name: str) -> str:
    """Return the stable local identity used by the Buffalo semantic contract.

    The two namespaces intentionally retain the original contract's part and
    material hashing format, so a graph can be built from pre-existing sealed
    contracts without an ID migration.
    """
    if kind == "part":
        source = f"{category}:{canonical_name}"
    elif kind == "material":
        source = f"{category}:material:{canonical_name}"
    else:
        raise SemanticGraphError(f"unsupported_node_kind:{kind}")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _error(code: str) -> None:
    raise SemanticGraphError(code)


def _require_mapping(value: Any, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _error(code)
    return value


def _name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_NAME.fullmatch(value):
        _error(f"invalid_{field}")
    return value


def _safe_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        _error(f"invalid_{field}")
    return value


def _finite_vector(value: Any, size: int, code: str) -> list[float]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence) or len(value) != size:
        _error(code)
    result = []
    for item in value:
        if isinstance(item, bool):
            _error(code)
        try:
            number = float(item)
        except (TypeError, ValueError):
            _error(code)
        if not math.isfinite(number):
            _error(code)
        result.append(number)
    return result


def _localizers(value: Any, evidence_class: str, node_id: str) -> dict[str, Any]:
    localizers = _require_mapping(value, f"localizers_required:{node_id}")
    unknown = sorted(set(localizers) - LOCALIZER_KEYS)
    missing = sorted(LOCALIZER_KEYS - set(localizers))
    if unknown:
        _error(f"unknown_localizer:{node_id}:{unknown[0]}")
    if missing:
        _error(f"missing_localizer:{node_id}:{missing[0]}")

    aabb = localizers["aabb"]
    if aabb is not None:
        aabb = _finite_vector(aabb, 6, f"invalid_aabb:{node_id}")
        if any(aabb[index] > aabb[index + 3] for index in range(3)):
            _error(f"invalid_aabb_bounds:{node_id}")

    obb = localizers["obb"]
    if obb is not None:
        obb = _require_mapping(obb, f"invalid_obb:{node_id}")
        if set(obb) != {"center", "extents"}:
            _error(f"invalid_obb_fields:{node_id}")
        center = _finite_vector(obb["center"], 3, f"invalid_obb_center:{node_id}")
        extents = _finite_vector(obb["extents"], 3, f"invalid_obb_extents:{node_id}")
        if any(item < 0 for item in extents):
            _error(f"invalid_obb_extents:{node_id}")
        obb = {"center": center, "extents": extents}

    component_ids = localizers["component_ids"]
    if not isinstance(component_ids, list):
        _error(f"invalid_component_ids:{node_id}")
    normalized_components = sorted({_safe_id(item, "component_id") for item in component_ids})
    if len(normalized_components) != len(component_ids):
        _error(f"ambiguous_component_ids:{node_id}")

    mask_hash = localizers["surface_mask_hash"]
    if mask_hash is not None and (not isinstance(mask_hash, str) or not _SHA256.fullmatch(mask_hash)):
        _error(f"invalid_surface_mask_hash:{node_id}")

    has_localizer = aabb is not None or obb is not None or bool(normalized_components) or mask_hash is not None
    if evidence_class == "measured" and not has_localizer:
        _error(f"measured_without_localizer:{node_id}")
    if evidence_class == "not_measured" and has_localizer:
        _error(f"unmeasured_with_localizer:{node_id}")
    return {
        "aabb": aabb,
        "obb": obb,
        "component_ids": normalized_components,
        "surface_mask_hash": mask_hash,
    }


def _evidence_class(item: Mapping[str, Any], node_id: str) -> str:
    supplied = {
        str(item[key])
        for key in ("evidence_class", "evidence_state", "evidence")
        if key in item and item[key] is not None
    }
    if len(supplied) > 1:
        _error(f"conflicting_evidence_class:{node_id}")
    evidence = next(iter(supplied), "not_measured")
    if evidence not in EVIDENCE_CLASSES:
        _error(f"invalid_evidence_class:{node_id}:{evidence}")
    return evidence


def _confidence(value: Any, node_id: str) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        _error(f"invalid_confidence:{node_id}")
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        _error(f"invalid_confidence:{node_id}")
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        _error(f"invalid_confidence:{node_id}")
    return confidence


def _part_node(category: str, raw: Any) -> dict[str, Any]:
    part = _require_mapping(raw, "invalid_part")
    name = _name(part.get("canonical_name", part.get("name")), "part_name")
    part_id = _safe_id(part.get("part_id"), "part_id")
    if part_id != stable_semantic_id(category, "part", name):
        _error(f"unstable_part_id:{name}")
    evidence = _evidence_class(part, part_id)
    return {
        "id": part_id,
        "kind": "part",
        "canonical_name": name,
        "critical": bool(part.get("critical", False)),
        "thin_structure": bool(part.get("thin_structure", part.get("thin", False))),
        "minimum_count": int(part.get("minimum_count", (part.get("count") or {}).get("minimum", 1))),
        "maximum_count": int(part.get("maximum_count", (part.get("count") or {}).get("maximum", 1))),
        "evidence_class": evidence,
        "confidence": _confidence(part.get("confidence"), part_id),
        "localizers": _localizers(part.get("localizers"), evidence, part_id),
    }


def _material_node(category: str, raw: Any, *, requires_regionality: bool) -> dict[str, Any]:
    material = _require_mapping(raw, "invalid_material_region")
    name = _name(material.get("name"), "material_name")
    region_id = _safe_id(material.get("region_id"), "material_region_id")
    if region_id != stable_semantic_id(category, "material", name):
        _error(f"unstable_material_region_id:{name}")
    if requires_regionality and (name in _GLOBAL_MATERIAL_NAMES or material.get("scope") == "global"):
        _error(f"material_global_conflation:{name}")
    evidence = _evidence_class(material, region_id)
    raw_localizers = material.get("localizers")
    if raw_localizers is None:
        raw_localizers = {key: [] if key == "component_ids" else None for key in LOCALIZER_KEYS}
    return {
        "id": region_id,
        "kind": "material_region",
        "canonical_name": name,
        "evidence_class": evidence,
        "confidence": _confidence(material.get("confidence"), region_id),
        "localizers": _localizers(raw_localizers, evidence, region_id),
    }


def compile_semantic_graph(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one sealed semantic contract into a canonical, deterministic graph.

    The result contains no caller-owned mutable values.  Node and edge sorting,
    together with a SHA-256 graph identity, makes equal contracts byte-stable
    across executions.  It intentionally does not invent part-to-material
    relationships: a missing localisation remains ``not_measured``.
    """
    contract = _require_mapping(contract, "semantic_contract_required")
    category = _name(contract.get("category"), "category")
    parts = contract.get("expected_parts")
    materials = contract.get("material_regions")
    if not isinstance(parts, list) or not parts:
        _error("expected_parts_required")
    if not isinstance(materials, list) or not materials:
        _error("material_regions_required")

    part_nodes = [_part_node(category, item) for item in parts]
    material_nodes = [
        _material_node(category, item, requires_regionality=len(materials) > 1)
        for item in materials
    ]
    all_ids = [node["id"] for node in part_nodes + material_nodes]
    if len(set(all_ids)) != len(all_ids):
        duplicates = sorted(node_id for node_id in set(all_ids) if all_ids.count(node_id) > 1)
        _error(f"ambiguous_node_id:{duplicates[0]}")
    part_names = [node["canonical_name"] for node in part_nodes]
    material_names = [node["canonical_name"] for node in material_nodes]
    if len(set(part_names)) != len(part_names):
        _error("ambiguous_part_name")
    if len(set(material_names)) != len(material_names):
        _error("ambiguous_material_name")

    root_id = "category:" + hashlib.sha256(category.encode("utf-8")).hexdigest()[:16]
    nodes = [{"id": root_id, "kind": "category", "canonical_name": category}]
    nodes.extend(sorted(part_nodes, key=lambda node: node["id"]))
    nodes.extend(sorted(material_nodes, key=lambda node: node["id"]))
    edges = [
        {"source": root_id, "target": node["id"], "type": "contains_part"}
        for node in sorted(part_nodes, key=lambda node: node["id"])
    ]
    edges.extend(
        {"source": root_id, "target": node["id"], "type": "contains_material_region"}
        for node in sorted(material_nodes, key=lambda node: node["id"])
    )
    payload = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "category": category,
        "root_id": root_id,
        "nodes": nodes,
        "edges": edges,
    }
    graph_id = "sha256:" + hashlib.sha256(_canonical_json(payload)).hexdigest()
    return deepcopy({**payload, "graph_id": graph_id})
