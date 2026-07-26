"""Category-aware PBR priors applied without changing mesh geometry or albedo."""

import numpy as np


MATERIAL_PROFILES = {
    "person": {"metallic": (0.0, 0.03, 0.0), "roughness": (0.42, 0.82, 0.62)},
    "animal": {"metallic": (0.0, 0.02, 0.0), "roughness": (0.62, 0.95, 0.82)},
    "wood": {"metallic": (0.0, 0.02, 0.0), "roughness": (0.52, 0.92, 0.72)},
    "iron": {"metallic": (0.72, 1.0, 0.9), "roughness": (0.32, 0.72, 0.52)},
    "metal": {"metallic": (0.62, 1.0, 0.86), "roughness": (0.18, 0.62, 0.4)},
    "matte_paint": {"metallic": (0.0, 0.08, 0.0), "roughness": (0.7, 0.96, 0.84)},
    "rust": {"metallic": (0.0, 0.22, 0.08), "roughness": (0.76, 0.98, 0.9)},
    "organic_grass": {"metallic": (0.0, 0.01, 0.0), "roughness": (0.78, 0.98, 0.9)},
    "synthetic_grass": {"metallic": (0.0, 0.03, 0.0), "roughness": (0.58, 0.9, 0.76)},
}


def resolve_material_profile(requested="auto", category="custom"):
    if requested in MATERIAL_PROFILES:
        return requested
    return {"person": "person", "animal": "animal"}.get(category, "auto")


def apply_material_prior(texture_mr, requested="auto", category="custom"):
    profile = resolve_material_profile(requested, category)
    if profile == "auto":
        return texture_mr, {"material_profile": "auto", "material_prior_applied": False}

    result = np.asarray(texture_mr, dtype=np.float32).copy()
    if result.ndim != 3 or result.shape[2] < 2:
        raise ValueError("metallic_roughness_texture_must_have_two_channels")

    policy = MATERIAL_PROFILES[profile]
    for channel, key in ((0, "metallic"), (1, "roughness")):
        low, high, target = policy[key]
        result[..., channel] = np.clip(result[..., channel] * 0.25 + target * 0.75, low, high)
    return result, {
        "material_profile": profile,
        "material_prior_applied": True,
        "metallic_range": list(policy["metallic"][:2]),
        "roughness_range": list(policy["roughness"][:2]),
    }
