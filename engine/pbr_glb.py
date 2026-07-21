from pathlib import Path

def validate_pbr_glb(path):
    from pygltflib import GLTF2

    glb_path = Path(path)
    if not glb_path.is_file() or glb_path.stat().st_size == 0:
        return {"passed": False, "reasons": ["missing_glb"]}

    gltf = GLTF2().load(str(glb_path))
    materials = gltf.materials or []
    has_base_color = False
    has_metallic_roughness = False
    for material in materials:
        pbr = material.pbrMetallicRoughness
        if not pbr:
            continue
        has_base_color = has_base_color or pbr.baseColorTexture is not None
        has_metallic_roughness = has_metallic_roughness or pbr.metallicRoughnessTexture is not None

    reasons = []
    if not has_base_color:
        reasons.append("missing_base_color_texture")
    if not has_metallic_roughness:
        reasons.append("missing_metallic_roughness_texture")
    if not gltf.images:
        reasons.append("missing_images")
    if not gltf.textures:
        reasons.append("missing_textures")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "materials": len(materials),
        "images": len(gltf.images or []),
        "textures": len(gltf.textures or []),
    }
