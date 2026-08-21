"""Buffalo-inspired semantic orchestration for the local MLX pipeline.

This is not Tencent's Hunyuan3D-Buffalo model and never claims to use its
unreleased weights.  It adopts the useful architectural idea: understand an
asset as named parts and protected regions before generating or simplifying
it.  Deterministic gates, rather than a VLM self-score, own promotion.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math


STRATEGY_VERSION = "xreality-buffalo-mlx-v1"
STRATEGY_NAME = "Buffalo Strategic MLX"
EDIT_TYPES = {
    "add_part",
    "remove_part",
    "reshape_part",
    "replace_material",
    "retexture_region",
    "transform_part",
}


def _part(name, minimum=1, maximum=1, *, critical=True, thin=False):
    return {
        "name": name,
        "minimum_count": int(minimum),
        "maximum_count": int(maximum),
        "critical": bool(critical),
        "thin_structure": bool(thin),
        "evidence": "not_measured",
    }


SEMANTIC_TEMPLATES = {
    "person": [
        _part("torso"), _part("head"), _part("arms", 2, 2),
        _part("hands", 2, 2, thin=True), _part("legs", 2, 2),
        _part("feet", 2, 2, thin=True),
    ],
    "animal": [
        _part("body"), _part("head"), _part("limbs", 2, 8),
        _part("ears", 0, 2, critical=False, thin=True),
        _part("tail", 0, 1, critical=False, thin=True),
    ],
    "vehicle": [
        _part("body"), _part("wheels", 4, 4), _part("windows", 2, 12),
        _part("lights", 2, 8, thin=True), _part("doors", 2, 6),
    ],
    "cargo_vehicle": [
        _part("cab"), _part("cargo_body"), _part("wheels", 4, 12),
        _part("axles", 2, 6, thin=True), _part("windows", 2, 8),
    ],
    "truck": [
        _part("cab"), _part("chassis"), _part("cargo_or_trailer"),
        _part("wheels", 4, 18), _part("axles", 2, 9, thin=True),
        _part("mirrors", 2, 2, thin=True),
    ],
    "crane": [
        _part("carrier_or_base"), _part("cab"), _part("boom"),
        _part("cable", 1, 8, thin=True), _part("hook", 1, 2, thin=True),
        _part("outriggers", 2, 8, thin=True), _part("wheels_or_tracks", 2, 16),
    ],
    "forklift": [
        _part("body"), _part("mast"), _part("forks", 2, 2, thin=True),
        _part("wheels", 3, 6), _part("overhead_guard", 1, 1, thin=True),
        _part("counterweight"),
    ],
    "excavator": [
        _part("undercarriage"), _part("tracks", 2, 2), _part("house"),
        _part("boom"), _part("stick"), _part("bucket"),
        _part("hydraulic_cylinders", 2, 8, thin=True),
    ],
    "motorcycle": [
        _part("frame"), _part("wheels", 2, 2), _part("fork", 1, 1, thin=True),
        _part("handlebar", 1, 1, thin=True), _part("engine"), _part("seat"),
    ],
    "bus": [
        _part("body"), _part("wheels", 4, 10), _part("windows", 4, 40),
        _part("doors", 1, 4), _part("lights", 2, 10, thin=True),
    ],
    "drone": [
        _part("central_body"), _part("arms", 3, 8, thin=True),
        _part("rotors", 3, 8, thin=True), _part("camera", 0, 1, critical=False),
        _part("landing_gear", 0, 4, critical=False, thin=True),
    ],
    "boat": [
        _part("hull"), _part("deck"), _part("cabin", 0, 1, critical=False),
        _part("propulsion", 1, 4), _part("railings", 0, 12, critical=False, thin=True),
    ],
    "electrical": [
        _part("enclosure_or_frame"), _part("conductors", 1, 64, thin=True),
        _part("insulators", 1, 64, thin=True), _part("terminals", 1, 64, thin=True),
        _part("protective_devices", 0, 64, critical=False),
    ],
    "solar": [
        _part("panels", 1, 128), _part("support_frame", 1, 64, thin=True),
        _part("inverter", 0, 8, critical=False), _part("cabling", 0, 128, critical=False, thin=True),
    ],
    "vegetation": [
        _part("trunk_or_stems"), _part("branches", 1, 256, thin=True),
        _part("foliage_clusters", 1, 512), _part("roots", 0, 64, critical=False, thin=True),
    ],
    "building": [
        _part("primary_volume"), _part("roof"), _part("facades", 1, 32),
        _part("openings", 1, 512), _part("accesses", 1, 64),
    ],
    "warehouse": [
        _part("structural_frame"), _part("roof"), _part("wall_panels", 1, 256),
        _part("doors", 1, 32), _part("openings", 1, 128),
    ],
    "architecture": [
        _part("primary_structure"), _part("surfaces", 1, 512),
        _part("openings", 0, 512, critical=False),
    ],
    "construction": [
        _part("primary_structure"), _part("members", 1, 512, thin=True),
        _part("connections", 1, 1024, thin=True),
    ],
    "industrial": [
        _part("primary_assembly"), _part("functional_components", 1, 128),
        _part("guards_and_lines", 0, 128, critical=False, thin=True),
    ],
    "tool": [
        _part("working_end"), _part("handle_or_body"),
        _part("actuator", 0, 4, critical=False, thin=True),
    ],
    "furniture": [
        _part("primary_body"), _part("supports", 1, 16, thin=True),
        _part("joins", 1, 64, thin=True),
    ],
    "product": [_part("primary_body"), _part("functional_details", 0, 32, critical=False, thin=True)],
    "custom": [_part("primary_body")],
}


MATERIAL_REGION_TEMPLATES = {
    "person": ["skin", "hair", "eyes", "clothing"],
    "animal": ["coat_or_skin", "eyes", "claws_or_hooves"],
    "vehicle": ["painted_body", "bare_metal", "rubber", "glass", "lights"],
    "cargo_vehicle": ["painted_body", "cargo_body", "bare_metal", "rubber", "glass", "lights"],
    "truck": ["painted_body", "chassis_metal", "rubber", "glass", "lights"],
    "crane": ["painted_structure", "bare_metal", "cable", "rubber", "glass", "safety_markings"],
    "forklift": ["painted_body", "fork_metal", "rubber", "glass", "safety_markings"],
    "excavator": ["painted_structure", "hydraulics", "tracks", "glass", "wear_regions"],
    "motorcycle": ["painted_body", "metal", "rubber", "glass", "seat"],
    "bus": ["painted_body", "rubber", "glass", "lights", "interior"],
    "drone": ["body", "rotors", "lens", "metal"],
    "boat": ["hull_coating", "deck", "metal", "glass", "rubber"],
    "electrical": ["conductor_metal", "insulator", "enclosure", "labels"],
    "solar": ["panel_glass", "cells", "frame_metal", "cabling", "enclosure"],
    "vegetation": ["bark_or_stem", "foliage"],
    "building": ["concrete_or_masonry", "metal", "glass", "roof", "wood_or_finish"],
    "warehouse": ["structural_metal", "wall_finish", "roof", "glass", "concrete"],
    "architecture": ["structure", "finish", "glass", "metal", "wood"],
    "construction": ["concrete", "structural_metal", "paint", "glass", "rubber"],
    "industrial": ["painted_metal", "bare_metal", "rubber_or_plastic", "labels"],
    "tool": ["working_metal", "painted_body", "grip", "labels"],
    "furniture": ["primary_material", "secondary_material", "hardware"],
    "product": ["primary_material"],
    "custom": ["primary_material"],
}


def build_semantic_contract(category="custom", profile="xreal", material="auto", real_reference_views=1):
    """Create an immutable, explainable part/material contract."""
    category = category if category in SEMANTIC_TEMPLATES else "custom"
    parts = deepcopy(SEMANTIC_TEMPLATES[category])
    regions = list(MATERIAL_REGION_TEMPLATES.get(category, ["primary_material"]))
    assembly_categories = {
        "vehicle", "cargo_vehicle", "truck", "crane", "construction", "warehouse",
        "architecture", "industrial", "electrical", "vegetation", "building", "tool",
        "forklift", "excavator", "motorcycle", "bus", "drone", "boat", "furniture", "solar",
    }
    for part in parts:
        part["part_id"] = hashlib.sha256(f"{category}:{part['name']}".encode()).hexdigest()[:16]
        part["evidence_class"] = "not_measured"
        part["localizers"] = {
            "aabb": None,
            "obb": None,
            "component_ids": [],
            "surface_mask_hash": None,
        }
    material_regions = []
    for name in regions:
        material_regions.append({
            "region_id": hashlib.sha256(f"{category}:material:{name}".encode()).hexdigest()[:16],
            "name": name,
            "evidence": "not_measured",
            "evidence_class": "not_measured",
            "confidence": 0.0,
        })
    return {
        "schema_version": 3,
        "version": STRATEGY_VERSION,
        "name": STRATEGY_NAME,
        "provenance": {
            "inspired_by": "Hunyuan3D-Buffalo 1.0 architectural strategy",
            "official_buffalo_code_or_weights": False,
            "local_shape_backend": "dgrauet/hunyuan3d-2.1-mlx",
        },
        "category": category,
        "profile": profile,
        "dominant_material": material,
        "expected_parts": parts,
        "critical_part_names": [item["name"] for item in parts if item["critical"]],
        "thin_part_names": [item["name"] for item in parts if item["thin_structure"]],
        "material_regions": material_regions,
        "preserve_assembly": category in assembly_categories,
        "real_reference_views": int(real_reference_views),
        "synthetic_views_are_evidence": False,
        "semantic_evidence_status": "not_measured",
    }


def build_edit_delta(
    source_master_hash,
    edit_type,
    target_part_ids,
    *,
    protected_part_ids=(),
    geometry_operation=None,
    material_operation=None,
    tolerances=None,
):
    """Compile a bounded edit request; do not accept executable free-form edits."""
    if edit_type not in EDIT_TYPES:
        raise ValueError(f"unsupported_edit_type:{edit_type}")
    if not isinstance(source_master_hash, str) or not source_master_hash:
        raise ValueError("source_master_hash_required")
    targets = sorted(set(target_part_ids or ()))
    protected = sorted(set(protected_part_ids or ()))
    if not targets:
        raise ValueError("edit_target_required")
    overlap = sorted(set(targets) & set(protected))
    if overlap:
        raise ValueError("target_protected_overlap:" + ",".join(overlap))
    return {
        "schema_version": 3,
        "source_master_hash": source_master_hash,
        "edit_type": edit_type,
        "target_part_ids": targets,
        "protected_part_ids": protected,
        "geometry_operation": deepcopy(geometry_operation) if geometry_operation else None,
        "material_operation": deepcopy(material_operation) if material_operation else None,
        "tolerances": {
            "protected_geometry_delta": 0.0,
            "protected_uv_delta": 0.0,
            "protected_material_delta": 0.0,
            **(deepcopy(tolerances) if tolerances else {}),
        },
    }


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _vector(value):
    try:
        values = list(value)
    except (TypeError, ValueError):
        values = []
    return [round(_finite_number(values[index] if index < len(values) else 0.0), 8) for index in range(3)]


def capture_assembly_fingerprint(mesh):
    """Capture JSON-safe topology and spatial evidence before derivation."""
    try:
        components = list(mesh.split(only_watertight=False))
    except Exception:
        components = [mesh]
    if not components:
        components = [mesh]

    total_faces = sum(len(getattr(component, "faces", [])) for component in components) or 1
    total_area = sum(_finite_number(getattr(component, "area", 0.0)) for component in components) or 1.0
    records = []
    for component in components:
        faces = len(getattr(component, "faces", []))
        area = _finite_number(getattr(component, "area", 0.0))
        extents = _vector(getattr(component, "extents", [0.0, 0.0, 0.0]))
        positive_extents = [value for value in extents if value > 0]
        aspect = (
            round(min(positive_extents) / max(positive_extents), 6)
            if positive_extents else 0.0
        )
        records.append({
            "faces": int(faces),
            "vertices": int(len(getattr(component, "vertices", []))),
            "area": round(area, 8),
            "face_ratio": round(faces / total_faces, 8),
            "area_ratio": round(area / total_area, 8),
            "extents": extents,
            "centroid": _vector(getattr(component, "centroid", [0.0, 0.0, 0.0])),
            "thinness_ratio": aspect,
        })
    records.sort(key=lambda item: (item["area_ratio"], item["face_ratio"]), reverse=True)
    return {
        "version": "xreality-assembly-fingerprint-v1",
        "component_count": len(records),
        "total_faces": int(sum(item["faces"] for item in records)),
        "total_vertices": int(len(getattr(mesh, "vertices", []))),
        "global_extents": _vector(getattr(mesh, "extents", [0.0, 0.0, 0.0])),
        "largest_component_area_ratio": records[0]["area_ratio"] if records else 1.0,
        "components": records,
    }


def validate_assembly_preservation(before, after, semantic_contract):
    """Reject a derived mesh when simplification removes meaningful structure."""
    preserve_assembly = bool(semantic_contract.get("preserve_assembly"))
    threshold = 0.008 if preserve_assembly else 0.015
    before_components = before.get("components") or []
    after_components = after.get("components") or []
    before_significant = sum(
        1 for item in before_components
        if max(item.get("area_ratio", 0.0), item.get("face_ratio", 0.0)) >= threshold
    )
    after_significant = sum(
        1 for item in after_components
        if max(item.get("area_ratio", 0.0), item.get("face_ratio", 0.0)) >= threshold
    )
    reasons = []
    if preserve_assembly and after_significant < before_significant:
        reasons.append("meaningful_component_loss")

    minimum_retention = 0.96 if preserve_assembly else 0.5
    component_retention = min(
        1.0,
        float(after.get("component_count", 0)) / max(1, int(before.get("component_count", 0))),
    )
    if component_retention < minimum_retention:
        reasons.append("component_count_retention_below_contract")

    extent_ratios = []
    for source, derived in zip(before.get("global_extents", []), after.get("global_extents", [])):
        if source > 1e-8:
            extent_ratios.append(round(derived / source, 6))
    if any(ratio < 0.96 or ratio > 1.04 for ratio in extent_ratios):
        reasons.append("global_extent_drift")

    largest_drift = abs(
        _finite_number(after.get("largest_component_area_ratio", 1.0), 1.0)
        - _finite_number(before.get("largest_component_area_ratio", 1.0), 1.0)
    )
    if preserve_assembly and largest_drift > 0.12:
        reasons.append("assembly_balance_drift")

    passed = not reasons
    return {
        "version": "xreality-assembly-preservation-gate-v1",
        "passed": passed,
        "decision": "pass" if passed else "reject",
        "reasons": reasons,
        "thresholds": {
            "minimum_component_retention": minimum_retention,
            "meaningful_component_ratio": threshold,
            "maximum_extent_drift": 0.04,
            "maximum_largest_component_drift": 0.12,
        },
        "metrics": {
            "before_components": int(before.get("component_count", 0)),
            "after_components": int(after.get("component_count", 0)),
            "before_significant_components": before_significant,
            "after_significant_components": after_significant,
            "component_retention": round(component_retention, 6),
            "extent_ratios": extent_ratios,
            "largest_component_drift": round(largest_drift, 6),
        },
    }


def build_apple_execution_graph(runtime=None):
    """Describe the implemented Apple schedule without overlapping Metal models."""
    runtime = runtime or {}
    return {
        "version": "xreality-apple-orchestration-v1",
        "strategy": "buffalo-mlx-metal-serial-cpu-bounded",
        "chip": runtime.get("chip", "Apple Silicon"),
        "logical_cores": int(runtime.get("logicalCores", 1) or 1),
        "performance_cores": int(runtime.get("performanceCores", 1) or 1),
        "validation_workers": int(runtime.get("validationWorkers", 1) or 1),
        "maximum_concurrent_metal_stages": 1,
        "parallel_window": ["shape_weight_load", "reference_preparation", "semantic_contract"],
        "metal_sequence": ["shape_mlx", "release_and_clear", "paint_mlx", "release_and_clear"],
        "postprocess_sequence": ["assembly_gate", "pbr_gate", "glb_delivery_gate"],
        "memory_policy": "fail-closed; no hidden backend escalation",
    }


def build_strategy_report(
    semantic_contract,
    apple_execution,
    preservation,
    *,
    material_report=None,
    input_analysis=None,
    sealed_artifacts=None,
    milestones=None,
):
    """Build a fail-closed lane matrix for reports and UI."""
    material_report = material_report or {}
    input_analysis = input_analysis or {}
    input_status = (
        "reject" if input_analysis.get("status") == "No recomendada"
        else "attention" if input_analysis.get("status") == "Procesable con ajustes"
        else "pass" if input_analysis.get("status")
        else "not_measured"
    )
    material_status = (
        "pass" if material_report.get("passed") is True
        else "reject" if material_report.get("passed") is False
        else "not_measured"
    )
    lanes = {
        "input_reference": input_status,
        "assembly_preservation": "pass" if preservation.get("passed") else "reject",
        "semantic_parts": semantic_contract.get("semantic_evidence_status", "not_measured"),
        "material_regions": material_status,
        "apple_memory_orchestration": "pass",
    }
    return {
        "version": STRATEGY_VERSION,
        "name": STRATEGY_NAME,
        "official_buffalo_backend": False,
        "semantic_contract": semantic_contract,
        "apple_execution": apple_execution,
        "preservation": preservation,
        "lanes": lanes,
        "delivery_blocked": "reject" in lanes.values(),
        "master_promotion_passed": all(status == "pass" for status in lanes.values()),
        "not_measured": [name for name, status in lanes.items() if status == "not_measured"],
        "input_analysis": input_analysis,
        "sealed_artifacts": sealed_artifacts or {},
        "milestones_seconds": milestones or {},
    }


def embed_strategy_metadata(path, semantic_contract, preservation):
    """Embed compact, portable Xreality metadata in the GLB asset extras."""
    from pbr_glb import _read_glb, _write_glb

    document, binary = _read_glb(path)
    asset = document.setdefault("asset", {"version": "2.0"})
    extras = asset.setdefault("extras", {})
    extras["xrealityBuffaloMLX"] = {
        "version": STRATEGY_VERSION,
        "officialBuffaloBackend": False,
        "category": semantic_contract.get("category", "custom"),
        "expectedParts": [
            {
                "name": item.get("name"),
                "minimumCount": item.get("minimum_count"),
                "maximumCount": item.get("maximum_count"),
                "critical": item.get("critical"),
                "evidence": item.get("evidence", "not_measured"),
            }
            for item in semantic_contract.get("expected_parts", [])
        ],
        "materialRegions": [
            item.get("name") for item in semantic_contract.get("material_regions", [])
        ],
        "assemblyPreservationGate": {
            "passed": preservation.get("passed") is True,
            "decision": preservation.get("decision", "not_measured"),
            "fallbackToAcceptedMaster": preservation.get("fallback_to_accepted_master", False),
        },
    }
    _write_glb(path, document, binary)
    verified, _ = _read_glb(path)
    embedded = ((verified.get("asset") or {}).get("extras") or {}).get("xrealityBuffaloMLX")
    if not embedded:
        raise RuntimeError("buffalo_metadata_not_persisted")
    return {
        "embedded": True,
        "key": "asset.extras.xrealityBuffaloMLX",
        "expected_parts": len(embedded.get("expectedParts") or []),
        "material_regions": len(embedded.get("materialRegions") or []),
    }
