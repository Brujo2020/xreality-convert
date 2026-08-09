import json
import io
import struct
from pathlib import Path

from PIL import Image


GLB_MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942

TEXTURE_ROLE_PATHS = {
    "base_color": ("pbrMetallicRoughness", "baseColorTexture"),
    "metallic_roughness": ("pbrMetallicRoughness", "metallicRoughnessTexture"),
    "normal": (None, "normalTexture"),
    "occlusion": (None, "occlusionTexture"),
    "emissive": (None, "emissiveTexture"),
}


def _read_glb(path):
    data = Path(path).read_bytes()
    if len(data) < 20 or data[:4] != GLB_MAGIC:
        raise ValueError("invalid_glb_header")
    version, declared_length = struct.unpack_from("<II", data, 4)
    if version != 2 or declared_length != len(data):
        raise ValueError("invalid_glb_header")

    document = None
    binary = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        end = offset + chunk_length
        if end > len(data):
            raise ValueError("invalid_glb_chunk")
        chunk = data[offset:end]
        offset = end
        if chunk_type == JSON_CHUNK:
            document = json.loads(chunk.rstrip(b"\x00 \t\r\n").decode("utf-8"))
        elif chunk_type == BIN_CHUNK:
            binary = chunk
    if document is None:
        raise ValueError("missing_glb_json")
    return document, binary


def _write_glb(path, document, binary):
    """Atomically rewrite a two-chunk GLB after metadata-only material edits."""
    json_payload = json.dumps(
        document, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    json_payload += b" " * ((-len(json_payload)) % 4)
    binary = bytes(binary)
    binary += b"\x00" * ((-len(binary)) % 4)
    chunks = [struct.pack("<II", len(json_payload), JSON_CHUNK), json_payload]
    if binary:
        chunks.extend([struct.pack("<II", len(binary), BIN_CHUNK), binary])
    total_length = 12 + sum(len(chunk) for chunk in chunks)
    payload = b"".join(
        [GLB_MAGIC, struct.pack("<II", 2, total_length), *chunks]
    )
    target = Path(path)
    temporary = target.with_name(f".{target.name}.material-edit.tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)


def apply_material_features(path, material_contract):
    """Add portable glTF material features without baking lighting into albedo."""
    document, binary = _read_glb(path)
    extensions = (material_contract or {}).get("extensions") or {}
    if not extensions:
        return {"applied": False, "extensions": []}
    if not (material_contract or {}).get("allow_global_material_features", True):
        return {
            "applied": False,
            "extensions": [],
            "skipped": "material_region_segmentation_required",
        }

    materials = document.get("materials") or []
    if not materials:
        raise ValueError("missing_materials")
    used = set(document.get("extensionsUsed") or [])
    for material in materials:
        target = material.setdefault("extensions", {})
        for name, values in extensions.items():
            target[name] = dict(values)
            used.add(name)
        pbr = material.setdefault("pbrMetallicRoughness", {})
        if "KHR_materials_transmission" in extensions:
            pbr["metallicFactor"] = 0.0
            pbr["roughnessFactor"] = min(float(pbr.get("roughnessFactor", 1.0)), 0.28)
    document["extensionsUsed"] = sorted(used)
    _write_glb(path, document, binary)
    return {"applied": True, "extensions": sorted(extensions)}


def _embedded_image(document, binary, image_index):
    payload, mime = _embedded_image_payload(document, binary, image_index)
    if payload is None:
        return False
    signatures = {
        "image/png": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": payload.startswith(b"\xff\xd8\xff"),
        "image/webp": payload.startswith(b"RIFF") and payload[8:12] == b"WEBP",
    }
    return signatures.get(mime, False)


def _embedded_image_payload(document, binary, image_index):
    images = document.get("images") or []
    buffer_views = document.get("bufferViews") or []
    if not isinstance(image_index, int) or not 0 <= image_index < len(images):
        return None, None
    image = images[image_index]
    view_index = image.get("bufferView")
    if image.get("uri") or not isinstance(view_index, int) or not 0 <= view_index < len(buffer_views):
        return None, None
    view = buffer_views[view_index]
    if view.get("buffer", 0) != 0:
        return None, None
    start = view.get("byteOffset", 0)
    length = view.get("byteLength", 0)
    if not isinstance(start, int) or not isinstance(length, int) or length <= 0:
        return None, None
    payload = binary[start:start + length]
    if len(payload) != length:
        return None, None
    return payload, image.get("mimeType")


def _texture_source(document, texture_info):
    textures = document.get("textures") or []
    texture_index = texture_info.get("index") if isinstance(texture_info, dict) else None
    if not isinstance(texture_index, int) or not 0 <= texture_index < len(textures):
        return None
    return textures[texture_index].get("source")


def _material_texture_info(material, role):
    parent, key = TEXTURE_ROLE_PATHS[role]
    if parent:
        return (material.get(parent) or {}).get(key)
    return material.get(key)


def _material_has_embedded_role(document, binary, material, role):
    source = _texture_source(document, _material_texture_info(material, role))
    return source is not None and _embedded_image(document, binary, source)


def _mr_statistics(document, binary, material):
    source = _texture_source(
        document,
        _material_texture_info(material, "metallic_roughness"),
    )
    payload, _ = _embedded_image_payload(document, binary, source)
    if payload is None:
        return None
    try:
        with Image.open(io.BytesIO(payload)) as opened:
            image = opened.convert("RGB")
            image.thumbnail((256, 256), Image.Resampling.BILINEAR)
            green_channel = image.getchannel("G")
            blue_channel = image.getchannel("B")
            flatten = lambda channel: (
                channel.get_flattened_data()
                if hasattr(channel, "get_flattened_data")
                else channel.getdata()
            )
            green = list(flatten(green_channel))
            blue = list(flatten(blue_channel))
    except (OSError, ValueError):
        return None
    pbr = material.get("pbrMetallicRoughness") or {}
    roughness_factor = float(pbr.get("roughnessFactor", 1.0))
    metallic_factor = float(pbr.get("metallicFactor", 1.0))
    roughness = [value / 255.0 * roughness_factor for value in green]
    metallic = [value / 255.0 * metallic_factor for value in blue]

    def summarize(values):
        ordered = sorted(values)
        if not ordered:
            return None
        return {
            "minimum": round(ordered[0], 4),
            "p05": round(ordered[int((len(ordered) - 1) * 0.05)], 4),
            "median": round(ordered[int((len(ordered) - 1) * 0.5)], 4),
            "p95": round(ordered[int((len(ordered) - 1) * 0.95)], 4),
            "maximum": round(ordered[-1], 4),
        }

    return {
        "metallic": summarize(metallic),
        "roughness": summarize(roughness),
        "sample_count": len(metallic),
        "_values": {"metallic": metallic, "roughness": roughness},
    }


def _texture_coordinate(document, texture_info):
    if not isinstance(texture_info, dict) or not isinstance(texture_info.get("index"), int):
        return None
    transform = (texture_info.get("extensions") or {}).get("KHR_texture_transform") or {}
    return int(transform.get("texCoord", texture_info.get("texCoord", 0)))


def _texture_coordinate_stats(document):
    materials = document.get("materials") or []
    textured_primitives = 0
    uv_mapped_primitives = 0
    for mesh in document.get("meshes") or []:
        for primitive in mesh.get("primitives") or []:
            material_index = primitive.get("material")
            if not isinstance(material_index, int) or not 0 <= material_index < len(materials):
                continue
            pbr = materials[material_index].get("pbrMetallicRoughness") or {}
            coordinates = {
                coordinate
                for coordinate in (
                    _texture_coordinate(document, pbr.get("baseColorTexture")),
                    _texture_coordinate(document, pbr.get("metallicRoughnessTexture")),
                )
                if coordinate is not None
            }
            if not coordinates:
                continue
            textured_primitives += 1
            attributes = primitive.get("attributes") or {}
            if all(f"TEXCOORD_{coordinate}" in attributes for coordinate in coordinates):
                uv_mapped_primitives += 1
    return textured_primitives, uv_mapped_primitives


def validate_pbr_glb(path):
    glb_path = Path(path)
    if not glb_path.is_file() or glb_path.stat().st_size == 0:
        return {"passed": False, "reasons": ["missing_glb"]}
    try:
        document, binary = _read_glb(glb_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "reasons": [str(exc) or "invalid_glb"]}

    materials = document.get("materials") or []
    base_sources = []
    metallic_roughness_sources = []
    for material in materials:
        pbr = material.get("pbrMetallicRoughness") or {}
        base_sources.append(_texture_source(document, pbr.get("baseColorTexture")))
        metallic_roughness_sources.append(_texture_source(document, pbr.get("metallicRoughnessTexture")))

    has_base_color = any(source is not None for source in base_sources)
    has_metallic_roughness = any(source is not None for source in metallic_roughness_sources)
    embedded_base_color = any(_embedded_image(document, binary, source) for source in base_sources)
    embedded_metallic_roughness = any(
        _embedded_image(document, binary, source) for source in metallic_roughness_sources
    )
    embedded_images = sum(
        _embedded_image(document, binary, index)
        for index in range(len(document.get("images") or []))
    )
    textured_primitives, uv_mapped_primitives = _texture_coordinate_stats(document)

    reasons = []
    if not has_base_color:
        reasons.append("missing_base_color_texture")
    elif not embedded_base_color:
        reasons.append("base_color_texture_not_embedded")
    if not has_metallic_roughness:
        reasons.append("missing_metallic_roughness_texture")
    elif not embedded_metallic_roughness:
        reasons.append("metallic_roughness_texture_not_embedded")
    if not document.get("images"):
        reasons.append("missing_images")
    if not document.get("textures"):
        reasons.append("missing_textures")
    if has_base_color and (not textured_primitives or uv_mapped_primitives != textured_primitives):
        reasons.append("missing_texture_coordinates")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "materials": len(materials),
        "images": len(document.get("images") or []),
        "embedded_images": embedded_images,
        "textures": len(document.get("textures") or []),
        "textured_primitives": textured_primitives,
        "uv_mapped_primitives": uv_mapped_primitives,
        "embedded_base_color": embedded_base_color,
        "embedded_metallic_roughness": embedded_metallic_roughness,
    }


def validate_material_contract(path, contract, enforce_recommended=False):
    """Validate semantic material deliverables, not just a parseable PBR shell."""
    try:
        document, binary = _read_glb(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "premium_ready": False,
            "reasons": [str(exc) or "invalid_glb"],
        }

    materials = document.get("materials") or []
    required_maps = list((contract or {}).get("required_maps") or [])
    recommended_maps = list((contract or {}).get("recommended_maps") or [])
    declared_extensions = sorted(((contract or {}).get("extensions") or {}).keys())
    allow_global_features = (contract or {}).get(
        "allow_global_material_features", True
    )
    required_extensions = declared_extensions if allow_global_features else []
    recommended_extensions = [] if allow_global_features else declared_extensions
    present_maps = {
        role: bool(materials)
        and all(
            _material_has_embedded_role(document, binary, material, role)
            for material in materials
        )
        for role in TEXTURE_ROLE_PATHS
    }
    present_extensions = {
        name: bool(materials)
        and all(name in (material.get("extensions") or {}) for material in materials)
        for name in required_extensions
    }
    present_recommended_extensions = {
        name: any(name in (material.get("extensions") or {}) for material in materials)
        for name in recommended_extensions
    }
    primitives = [
        primitive
        for mesh in document.get("meshes") or []
        for primitive in mesh.get("primitives") or []
    ]
    invalid_material_primitives = sum(
        not isinstance(primitive.get("material"), int)
        or not 0 <= primitive["material"] < len(materials)
        for primitive in primitives
    )
    missing_required = [role for role in required_maps if not present_maps.get(role)]
    missing_extensions = [
        name for name in required_extensions if not present_extensions.get(name)
    ]
    missing_recommended = [
        role for role in recommended_maps if not present_maps.get(role)
    ]
    recommended_material_regions = int(
        (contract or {}).get("recommended_material_regions", 1)
    )
    material_regions_ready = len(materials) >= recommended_material_regions
    expected_ranges = {
        name: list((contract or {}).get(f"{name}_range") or [])
        for name in ("metallic", "roughness")
    }
    if not (contract or {}).get("allow_global_mr_ranges", True):
        expected_ranges = {"metallic": [], "roughness": []}
    range_reports = []
    range_failures = []
    for index, material in enumerate(materials):
        stats = _mr_statistics(document, binary, material)
        public_stats = None
        if stats:
            public_stats = {
                key: value for key, value in stats.items() if key != "_values"
            }
        item = {"material": index, "statistics": public_stats, "checks": {}}
        for name, limits in expected_ranges.items():
            if len(limits) != 2:
                continue
            values = (stats or {}).get("_values", {}).get(name, [])
            low, high = (float(limits[0]), float(limits[1]))
            coverage = (
                sum(low - 1e-6 <= value <= high + 1e-6 for value in values)
                / len(values)
                if values
                else 0.0
            )
            check = {
                "expected": [low, high],
                "coverage": round(coverage, 4),
                "passed": coverage >= 0.8,
            }
            item["checks"][name] = check
            if not check["passed"]:
                range_failures.append(f"material_{index}_{name}_out_of_range")
        range_reports.append(item)
    reasons = [f"missing_required_map:{role}" for role in missing_required]
    if not primitives:
        reasons.append("missing_mesh_primitives")
    elif invalid_material_primitives:
        reasons.append("primitive_without_valid_material")
    reasons.extend(f"missing_material_extension:{name}" for name in missing_extensions)
    reasons.extend(range_failures)
    if enforce_recommended:
        reasons.extend(
            f"missing_master_map:{role}" for role in missing_recommended
        )
        if not material_regions_ready:
            reasons.append("missing_master_material_regions")
        reasons.extend(
            f"missing_master_material_extension:{name}"
            for name, present in present_recommended_extensions.items()
            if not present
        )
    passed = not reasons
    return {
        "passed": passed,
        "premium_ready": (
            passed
            and not missing_recommended
            and material_regions_ready
            and all(present_recommended_extensions.values())
        ),
        "required_maps": required_maps,
        "recommended_maps": recommended_maps,
        "required_extensions": required_extensions,
        "recommended_extensions": recommended_extensions,
        "recommended_material_regions": recommended_material_regions,
        "material_regions_ready": material_regions_ready,
        "present_maps": present_maps,
        "present_extensions": present_extensions,
        "present_recommended_extensions": present_recommended_extensions,
        "primitives": len(primitives),
        "invalid_material_primitives": invalid_material_primitives,
        "missing_required_maps": missing_required,
        "missing_recommended_maps": missing_recommended,
        "missing_extensions": missing_extensions,
        "range_reports": range_reports,
        "reasons": reasons,
    }
