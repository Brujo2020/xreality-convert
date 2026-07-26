import json
import struct
from pathlib import Path


GLB_MAGIC = b"glTF"
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


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


def _embedded_image(document, binary, image_index):
    images = document.get("images") or []
    buffer_views = document.get("bufferViews") or []
    if not isinstance(image_index, int) or not 0 <= image_index < len(images):
        return False
    image = images[image_index]
    view_index = image.get("bufferView")
    if image.get("uri") or not isinstance(view_index, int) or not 0 <= view_index < len(buffer_views):
        return False
    view = buffer_views[view_index]
    if view.get("buffer", 0) != 0:
        return False
    start = view.get("byteOffset", 0)
    length = view.get("byteLength", 0)
    if not isinstance(start, int) or not isinstance(length, int) or length <= 0:
        return False
    payload = binary[start:start + length]
    if len(payload) != length:
        return False
    mime = image.get("mimeType")
    signatures = {
        "image/png": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": payload.startswith(b"\xff\xd8\xff"),
        "image/webp": payload.startswith(b"RIFF") and payload[8:12] == b"WEBP",
    }
    return signatures.get(mime, False)


def _texture_source(document, texture_info):
    textures = document.get("textures") or []
    texture_index = texture_info.get("index") if isinstance(texture_info, dict) else None
    if not isinstance(texture_index, int) or not 0 <= texture_index < len(textures):
        return None
    return textures[texture_index].get("source")


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
