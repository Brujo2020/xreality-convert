"""Deterministic technical-art director for local Image-to-3D jobs.

The local LLM may describe an asset, but it never owns promotion.  This module
turns an explicit asset category, delivery profile, and material hint into a
reproducible routing decision and a fail-closed quality contract.
"""

from __future__ import annotations

from copy import deepcopy

from buffalo_strategy import build_semantic_contract


CATEGORY_ALIASES = {
    "hifi": "custom",
    "human": "person",
    "humano": "person",
    "persona": "person",
    "animal": "animal",
    "industrial": "industrial",
    "construction": "construction",
    "construccion": "construction",
    "construcción": "construction",
    "warehouse": "warehouse",
    "bodega": "warehouse",
    "architecture": "architecture",
    "arquitectura": "architecture",
    "auto": "vehicle",
    "car": "vehicle",
    "cars": "vehicle",
    "vehicle": "vehicle",
    "vehiculo": "vehicle",
    "vehículo": "vehicle",
    "cargo_vehicle": "cargo_vehicle",
    "vehiculo_de_carga": "cargo_vehicle",
    "vehículo_de_carga": "cargo_vehicle",
    "truck": "truck",
    "camion": "truck",
    "camión": "truck",
    "crane": "crane",
    "grua": "crane",
    "grúa": "crane",
    "electrical": "electrical",
    "instalacion_electrica": "electrical",
    "instalación_eléctrica": "electrical",
    "vegetation": "vegetation",
    "vegetacion": "vegetation",
    "vegetación": "vegetation",
    "building": "building",
    "edificio": "building",
    "tool": "tool",
    "herramienta": "tool",
    "forklift": "forklift",
    "montacargas": "forklift",
    "grua_horquilla": "forklift",
    "grúa_horquilla": "forklift",
    "excavator": "excavator",
    "excavadora": "excavator",
    "motorcycle": "motorcycle",
    "motocicleta": "motorcycle",
    "moto": "motorcycle",
    "bus": "bus",
    "autobus": "bus",
    "autobús": "bus",
    "drone": "drone",
    "dron": "drone",
    "boat": "boat",
    "embarcacion": "boat",
    "embarcación": "boat",
    "furniture": "furniture",
    "mobiliario": "furniture",
    "solar": "solar",
    "energia_solar": "solar",
    "energía_solar": "solar",
    "low-poly": "lowpoly",
    "low_poly": "lowpoly",
}

MATERIAL_ALIASES = {
    "acero": "metal",
    "alformbra": "carpet",
    "alfombra": "carpet",
    "cabello": "hair",
    "ceramica": "ceramic",
    "cerámica": "ceramic",
    "cristal": "glass",
    "fabric": "fabric",
    "fur": "fur",
    "goma": "rubber",
    "hormigon": "concrete",
    "hormigón": "concrete",
    "iron": "metal",
    "loza": "ceramic",
    "madera": "wood",
    "metal_pintado": "painted_metal",
    "painted-metal": "painted_metal",
    "pelo": "hair",
    "pelaje": "fur",
    "piel": "skin",
    "plastico": "plastic",
    "plástico": "plastic",
    "porcelana": "porcelain",
    "tela": "fabric",
    "vidrio": "glass",
}


ASSET_CONTRACTS = {
    "lowpoly": {
        "archetype": "lowpoly",
        "default_material": "matte_paint",
        "minimum_faces": 500,
        "minimum_vertices": 300,
        "maximum_components": 6,
        "minimum_largest_component_ratio": 0.55,
        "require_watertight": False,
        "preserve_assembly": False,
        "recommended_material_regions": 1,
        "minimum_master_views": 1,
    },
    "person": {
        "archetype": "organic",
        "default_material": "skin",
        "minimum_faces": 3000,
        "minimum_vertices": 1500,
        "maximum_components": 4,
        "minimum_largest_component_ratio": 0.72,
        "require_watertight": True,
        "preserve_assembly": False,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "animal": {
        "archetype": "organic",
        "default_material": "fur",
        "minimum_faces": 3000,
        "minimum_vertices": 1500,
        "maximum_components": 4,
        "minimum_largest_component_ratio": 0.72,
        "require_watertight": True,
        "preserve_assembly": False,
        "recommended_material_regions": 2,
        "minimum_master_views": 2,
    },
    "product": {
        "archetype": "product",
        "default_material": "plastic",
        "minimum_faces": 1000,
        "minimum_vertices": 500,
        "maximum_components": 8,
        "minimum_largest_component_ratio": 0.55,
        "require_watertight": True,
        "preserve_assembly": False,
        "recommended_material_regions": 1,
        "minimum_master_views": 1,
    },
    "industrial": {
        "archetype": "hard_surface",
        "default_material": "painted_metal",
        "minimum_faces": 1500,
        "minimum_vertices": 700,
        "maximum_components": 24,
        "minimum_largest_component_ratio": 0.35,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "vehicle": {
        "archetype": "hard_surface",
        "default_material": "painted_metal",
        "minimum_faces": 2500,
        "minimum_vertices": 1200,
        "maximum_components": 18,
        "minimum_largest_component_ratio": 0.45,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 3,
    },
    "cargo_vehicle": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 3000,
        "minimum_vertices": 1400,
        "maximum_components": 28,
        "minimum_largest_component_ratio": 0.32,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "truck": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 3000,
        "minimum_vertices": 1400,
        "maximum_components": 28,
        "minimum_largest_component_ratio": 0.32,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "crane": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 2500,
        "minimum_vertices": 1200,
        "maximum_components": 32,
        "minimum_largest_component_ratio": 0.25,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "construction": {
        "archetype": "structure",
        "default_material": "concrete",
        "minimum_faces": 1200,
        "minimum_vertices": 600,
        "maximum_components": 48,
        "minimum_largest_component_ratio": 0.2,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "warehouse": {
        "archetype": "architecture",
        "default_material": "painted_metal",
        "minimum_faces": 1200,
        "minimum_vertices": 600,
        "maximum_components": 64,
        "minimum_largest_component_ratio": 0.18,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 3,
    },
    "architecture": {
        "archetype": "architecture",
        "default_material": "matte_paint",
        "minimum_faces": 1000,
        "minimum_vertices": 500,
        "maximum_components": 64,
        "minimum_largest_component_ratio": 0.18,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 2,
        "minimum_master_views": 3,
    },
    "electrical": {
        "archetype": "technical_assembly",
        "default_material": "plastic",
        "minimum_faces": 1200,
        "minimum_vertices": 600,
        "maximum_components": 48,
        "minimum_largest_component_ratio": 0.18,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 2,
    },
    "vegetation": {
        "archetype": "organic_assembly",
        "default_material": "foliage",
        "minimum_faces": 1800,
        "minimum_vertices": 900,
        "maximum_components": 64,
        "minimum_largest_component_ratio": 0.12,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 2,
        "minimum_master_views": 2,
    },
    "building": {
        "archetype": "architecture",
        "default_material": "concrete",
        "minimum_faces": 1500,
        "minimum_vertices": 700,
        "maximum_components": 96,
        "minimum_largest_component_ratio": 0.12,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "tool": {
        "archetype": "hard_surface",
        "default_material": "painted_metal",
        "minimum_faces": 1000,
        "minimum_vertices": 500,
        "maximum_components": 16,
        "minimum_largest_component_ratio": 0.42,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "forklift": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 2200,
        "minimum_vertices": 1000,
        "maximum_components": 26,
        "minimum_largest_component_ratio": 0.3,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "excavator": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 2600,
        "minimum_vertices": 1200,
        "maximum_components": 32,
        "minimum_largest_component_ratio": 0.26,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "motorcycle": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 2200,
        "minimum_vertices": 1000,
        "maximum_components": 22,
        "minimum_largest_component_ratio": 0.28,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "bus": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 3000,
        "minimum_vertices": 1400,
        "maximum_components": 34,
        "minimum_largest_component_ratio": 0.34,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "drone": {
        "archetype": "technical_assembly",
        "default_material": "plastic",
        "minimum_faces": 1600,
        "minimum_vertices": 750,
        "maximum_components": 20,
        "minimum_largest_component_ratio": 0.28,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "boat": {
        "archetype": "hard_surface_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 2400,
        "minimum_vertices": 1100,
        "maximum_components": 30,
        "minimum_largest_component_ratio": 0.36,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 3,
    },
    "furniture": {
        "archetype": "product_assembly",
        "default_material": "wood",
        "minimum_faces": 1200,
        "minimum_vertices": 600,
        "maximum_components": 24,
        "minimum_largest_component_ratio": 0.3,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 3,
        "minimum_master_views": 2,
    },
    "solar": {
        "archetype": "technical_assembly",
        "default_material": "painted_metal",
        "minimum_faces": 1400,
        "minimum_vertices": 650,
        "maximum_components": 48,
        "minimum_largest_component_ratio": 0.2,
        "require_watertight": False,
        "preserve_assembly": True,
        "recommended_material_regions": 4,
        "minimum_master_views": 2,
    },
    "custom": {
        "archetype": "general",
        "default_material": "auto",
        "minimum_faces": 800,
        "minimum_vertices": 500,
        "maximum_components": 8,
        "minimum_largest_component_ratio": 0.55,
        "require_watertight": False,
        "preserve_assembly": False,
        "recommended_material_regions": 1,
        "minimum_master_views": 1,
    },
}


MATERIAL_CONTRACTS = {
    "auto": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": [],
        "extensions": {},
        "risk": "unknown_material",
    },
    "skin": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {},
        "metallic_range": [0.0, 0.03],
        "roughness_range": [0.38, 0.78],
        "risk": "waxy_skin_or_baked_highlights",
    },
    "hair": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_sheen": {
                "sheenColorFactor": [0.12, 0.12, 0.12],
                "sheenRoughnessFactor": 0.72,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.42, 0.82],
        "risk": "helmet_hair_or_missing_strand_direction",
    },
    "fur": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_sheen": {
                "sheenColorFactor": [0.08, 0.08, 0.08],
                "sheenRoughnessFactor": 0.82,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.62, 0.95],
        "risk": "plastic_fur_or_painted_detail",
    },
    "foliage": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_sheen": {
                "sheenColorFactor": [0.04, 0.08, 0.03],
                "sheenRoughnessFactor": 0.78,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.5, 0.92],
        "risk": "opaque_or_metallic_foliage",
    },
    "metal": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {},
        "metallic_range": [0.72, 1.0],
        "roughness_range": [0.14, 0.68],
        "risk": "gray_plastic_or_baked_reflection",
    },
    "painted_metal": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_clearcoat": {
                "clearcoatFactor": 0.12,
                "clearcoatRoughnessFactor": 0.45,
            }
        },
        "metallic_range": [0.0, 0.15],
        "roughness_range": [0.38, 0.82],
        "risk": "metallic_paint_without_dielectric_coat",
    },
    "rust": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal", "occlusion"],
        "extensions": {},
        "metallic_range": [0.0, 0.25],
        "roughness_range": [0.72, 1.0],
        "risk": "uniform_or_metallic_rust",
    },
    "carpet": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal", "occlusion"],
        "extensions": {
            "KHR_materials_sheen": {
                "sheenColorFactor": [0.16, 0.16, 0.16],
                "sheenRoughnessFactor": 0.9,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.76, 1.0],
        "risk": "flat_print_without_fibers",
    },
    "fabric": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_sheen": {
                "sheenColorFactor": [0.12, 0.12, 0.12],
                "sheenRoughnessFactor": 0.84,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.58, 0.95],
        "risk": "plastic_cloth_or_scale_mismatch",
    },
    "plastic": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {},
        "metallic_range": [0.0, 0.03],
        "roughness_range": [0.24, 0.8],
        "risk": "metallic_plastic_or_baked_highlights",
    },
    "rubber": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {},
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.68, 0.98],
        "risk": "wet_rubber",
    },
    "ceramic": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_clearcoat": {
                "clearcoatFactor": 0.46,
                "clearcoatRoughnessFactor": 0.14,
            }
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.18, 0.72],
        "risk": "plastic_ceramic_or_missing_glaze",
    },
    "porcelain": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_clearcoat": {
                "clearcoatFactor": 0.72,
                "clearcoatRoughnessFactor": 0.08,
            },
            "KHR_materials_ior": {"ior": 1.52},
        },
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.12, 0.48],
        "risk": "plastic_porcelain_or_baked_glaze",
    },
    "glass": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {
            "KHR_materials_transmission": {"transmissionFactor": 1.0},
            "KHR_materials_volume": {
                "thicknessFactor": 0.02,
                "attenuationDistance": 4.0,
                "attenuationColor": [1.0, 1.0, 1.0],
            },
            "KHR_materials_ior": {"ior": 1.5},
        },
        "metallic_range": [0.0, 0.0],
        "roughness_range": [0.02, 0.28],
        "risk": "transparent_plastic_or_opaque_glass",
    },
    "concrete": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal", "occlusion"],
        "extensions": {},
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.72, 1.0],
        "risk": "flat_concrete_without_scale_detail",
    },
    "wood": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": ["normal"],
        "extensions": {},
        "metallic_range": [0.0, 0.02],
        "roughness_range": [0.48, 0.92],
        "risk": "wood_grain_without_direction_or_scale",
    },
    "matte_paint": {
        "required_maps": ["base_color", "metallic_roughness"],
        "recommended_maps": [],
        "extensions": {},
        "metallic_range": [0.0, 0.05],
        "roughness_range": [0.66, 0.96],
        "risk": "baked_lighting",
    },
}


QUALITY_TIERS = {
    "lowpoly": "preview",
    "mobile": "production",
    "quest": "production",
    "vrready": "production",
    "smart": "production",
    "xreal": "premium",
    "pcvr": "premium",
    "maxquality": "master",
}


DELIVERY_CAPS = {
    "lowpoly": {
        "steps": 24,
        "octree_resolution": 128,
        "target_faces": 15000,
        "texture_resolution": 1024,
        "paint_backend": "fast",
        "preserve_master": True,
    },
    "vrready": {
        "steps": 32,
        "octree_resolution": 192,
        "target_faces": 45000,
        "texture_resolution": 1024,
        "paint_backend": "fast",
        "preserve_master": True,
    },
}

AGENTIC_CATEGORIES = {
    "animal",
    "person",
    "vehicle",
    "crane",
    "construction",
    "warehouse",
}
AGENTIC_MATERIALS = {
    "skin",
    "hair",
    "fur",
    "metal",
    "painted_metal",
    "rust",
    "carpet",
    "fabric",
    "ceramic",
    "porcelain",
    "glass",
    "concrete",
    "wood",
}


def normalize_category(value="custom", profile="xreal"):
    normalized = str(value or "custom").strip().lower().replace(" ", "_")
    normalized = CATEGORY_ALIASES.get(normalized, normalized)
    return normalized if normalized in ASSET_CONTRACTS else "custom"


def normalize_material(value="auto"):
    normalized = str(value or "auto").strip().lower().replace(" ", "_")
    normalized = MATERIAL_ALIASES.get(normalized, normalized)
    return normalized if normalized in MATERIAL_CONTRACTS else "auto"


def optimize_delivery_settings(
    *,
    profile="xreal",
    steps=30,
    octree_resolution=192,
    target_faces=50000,
    texture_resolution=1024,
    paint_backend="fast",
    unified_memory_gb=None,
):
    """Resolve deterministic delivery caps without adding a second ML pass."""
    requested = {
        "steps": int(steps),
        "octree_resolution": int(octree_resolution),
        "target_faces": int(target_faces),
        "texture_resolution": int(texture_resolution),
        "paint_backend": paint_backend if paint_backend in {"fast", "agentic"} else "fast",
    }
    cap = deepcopy(DELIVERY_CAPS.get(profile, {}))
    strategy = "requested"
    if profile == "smart":
        memory = float(unified_memory_gb or 16)
        if memory <= 18:
            cap = {
                "steps": 28,
                "octree_resolution": 192,
                "target_faces": 35000,
                "texture_resolution": 1024,
                "paint_backend": "fast",
                "preserve_master": True,
            }
            strategy = "smart_memory_guard"
        elif memory <= 40:
            cap = {
                "steps": 32,
                "octree_resolution": 192,
                "target_faces": 60000,
                "texture_resolution": 1024,
                "paint_backend": "fast",
                "preserve_master": True,
            }
            strategy = "smart_balanced"
        else:
            cap = {
                "steps": 35,
                "octree_resolution": 192,
                "target_faces": 80000,
                "texture_resolution": 1024,
                "paint_backend": "fast",
                "preserve_master": True,
            }
            strategy = "smart_throughput"
    elif cap:
        strategy = f"{profile}_delivery_cap"

    executed = dict(requested)
    for field in ("steps", "octree_resolution", "target_faces", "texture_resolution"):
        if field in cap:
            executed[field] = min(executed[field], int(cap[field]))
    if cap.get("paint_backend"):
        executed["paint_backend"] = cap["paint_backend"]
    executed["preserve_master"] = bool(cap.get("preserve_master", False))
    executed["strategy"] = strategy
    executed["requested"] = requested
    executed["adjusted"] = any(
        executed[field] != requested[field]
        for field in requested
    )
    return executed


def plan_asset(
    *,
    category="custom",
    material_hint="auto",
    profile="xreal",
    requested_paint_backend="fast",
    texture_enabled=True,
    unified_memory_gb=None,
    real_reference_views=1,
):
    """Return an explainable pipeline route and its immutable quality contract."""
    category = normalize_category(category, profile)
    asset_contract = deepcopy(ASSET_CONTRACTS[category])
    requested_material = normalize_material(material_hint)
    material = (
        asset_contract["default_material"]
        if requested_material == "auto"
        else requested_material
    )
    material_contract = deepcopy(MATERIAL_CONTRACTS[material])
    material_contract["recommended_material_regions"] = asset_contract[
        "recommended_material_regions"
    ]
    material_contract["allow_global_material_features"] = (
        asset_contract["recommended_material_regions"] == 1
    )
    material_contract["allow_global_mr_ranges"] = (
        asset_contract["recommended_material_regions"] == 1
    )
    tier = QUALITY_TIERS.get(profile, "premium")
    # Watertightness is a destination constraint, not a universal GLB rule.
    # Closed organic/product assets should prefer it for XR, while only master
    # promotion (and the independent STL exporter) makes it a hard blocker.
    prefers_watertight = bool(asset_contract.get("require_watertight", False))
    asset_contract["prefer_watertight"] = prefers_watertight
    asset_contract["require_watertight"] = prefers_watertight and tier == "master"
    asset_contract["watertight_policy"] = (
        "strict_master"
        if asset_contract["require_watertight"]
        else "preferred_xr"
        if prefers_watertight
        else "not_required_for_assembly"
    )
    semantic_contract = build_semantic_contract(
        category=category,
        profile=profile,
        material=material,
        real_reference_views=real_reference_views,
    )

    requested_backend = requested_paint_backend if requested_paint_backend in {"fast", "agentic"} else "fast"
    if category == "lowpoly" or tier == "preview" or not texture_enabled:
        paint_backend = "fast" if texture_enabled else None
    else:
        # The UI choice is an execution contract. Never turn a fast request
        # into a second, slower Agentic pass behind the user's back. Master
        # presets request Agentic explicitly.
        paint_backend = requested_backend

    minimum_memory = 24 if paint_backend == "agentic" else 12 if texture_enabled else 8
    blockers = []
    if unified_memory_gb is not None and unified_memory_gb < minimum_memory:
        blockers.append(
            f"unified_memory_below_{minimum_memory}gb_for_{paint_backend or 'shape'}"
        )
    minimum_master_views = int(asset_contract["minimum_master_views"])
    if tier == "master" and int(real_reference_views) < minimum_master_views:
        blockers.append(
            f"master_requires_{minimum_master_views}_real_reference_views"
        )

    reasons = [
        "shape_winner_dgrauet_mlx",
        "buffalo_strategy_semantic_contract",
        "transactional_assembly_preservation_gate",
    ]
    if paint_backend == "agentic":
        reasons.extend(["paint_winner_agenticvibes_mlx", "reference_lock_required"])
    elif paint_backend == "fast":
        reasons.append("fast_paint_admitted_by_contract")
    if asset_contract["preserve_assembly"]:
        reasons.append("preserve_meaningful_components")
    if material_contract["extensions"]:
        reasons.append("material_specific_gltf_extensions")

    return {
        "version": 2,
        "category": category,
        "archetype": asset_contract["archetype"],
        "quality_tier": tier,
        "delivery_intent": profile,
        "material": material,
        "requested_material": requested_material,
        "shape_backend": "dgrauet/hunyuan3d-2.1-mlx",
        "paint_backend": paint_backend,
        "reference_lock": paint_backend == "agentic",
        "minimum_unified_memory_gb": minimum_memory,
        "input_contract": {
            "real_reference_views": int(real_reference_views),
            "minimum_master_views": minimum_master_views,
            "synthetic_views_are_evidence": False,
        },
        "geometry_contract": asset_contract,
        "material_contract": material_contract,
        "semantic_contract": semantic_contract,
        "enforce_recommended_maps": tier == "master",
        "blocked": bool(blockers),
        "blockers": blockers,
        "reasons": reasons,
    }


def material_profile_for_paint(material):
    """Map the richer art-director vocabulary to the current MR prior engine."""
    normalized = normalize_material(material)
    return {
        "skin": "person",
        "hair": "person",
        "fur": "animal",
        "foliage": "matte_paint",
        "metal": "metal",
        "painted_metal": "matte_paint",
        "rust": "rust",
        "carpet": "matte_paint",
        "fabric": "matte_paint",
        "plastic": "plastic",
        "rubber": "rubber",
        "ceramic": "ceramic",
        "porcelain": "porcelain",
        "glass": "glass",
        "concrete": "concrete",
        "wood": "wood",
        "matte_paint": "matte_paint",
    }.get(normalized, "auto")


def component_policy(category="custom", profile="xreal"):
    contract = ASSET_CONTRACTS[normalize_category(category, profile)]
    return {
        "preserve_assembly": contract["preserve_assembly"],
        "minimum_component_area_ratio": 0.008 if contract["preserve_assembly"] else 0.015,
    }
