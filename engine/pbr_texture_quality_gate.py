"""Fail-closed local measurements for embedded PBR maps in a regional GLB.

This is deliberately a *container and pixel measurement* gate.  It can prove
that an admitted map is embedded, decodable, bounded, non-empty and has a UV
binding; it cannot prove that an albedo is reference-aligned, relightable, or
free of baked illumination.  Those claims require independent render evidence
and stay ``not_measured`` here.
"""

from __future__ import annotations

import hashlib
import io
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from regional_pbr_gate import audit_regional_pbr
from runtime_certification import RuntimeCertificationError, _read_glb
from secure_artifacts import UnsafeAssetError, validate_glb_container


PBR_TEXTURE_QUALITY_SCHEMA_VERSION = 1
MAX_TEXTURE_BYTES = 64 * 1024 * 1024
MAX_TEXTURE_DIMENSION = 16_384
MAX_TEXTURE_PIXELS = 16_000_000
MAX_MEASUREMENT_DIMENSION = 512
_REQUIRED_ROLES = frozenset({"base_color", "metallic_roughness", "normal"})
_ROLE_PATHS = {
    "base_color": ("pbrMetallicRoughness", "baseColorTexture"),
    "metallic_roughness": ("pbrMetallicRoughness", "metallicRoughnessTexture"),
    "normal": (None, "normalTexture"),
    "occlusion": (None, "occlusionTexture"),
    "emissive": (None, "emissiveTexture"),
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _texture_info(material: Mapping[str, Any], role: str) -> Any:
    parent, key = _ROLE_PATHS[role]
    if parent:
        value = material.get(parent)
        return value.get(key) if isinstance(value, Mapping) else None
    return material.get(key)


def _texture_texcoord(info: Mapping[str, Any]) -> int | None:
    extensions = info.get("extensions")
    transform = extensions.get("KHR_texture_transform") if isinstance(extensions, Mapping) else None
    value = transform.get("texCoord", info.get("texCoord", 0)) if isinstance(transform, Mapping) else info.get("texCoord", 0)
    return value if _is_int(value) and value >= 0 else None


def _map_reference(document: Mapping[str, Any], info: Any) -> tuple[int | None, int | None, int | None, str | None]:
    """Return texture/image/view IDs, rejecting every non-embedded reference."""
    if not isinstance(info, Mapping) or not _is_int(info.get("index")):
        return None, None, None, "texture_info_missing_or_invalid"
    textures = document.get("textures")
    images = document.get("images")
    if not isinstance(textures, list) or not isinstance(images, list) or not 0 <= info["index"] < len(textures):
        return None, None, None, "texture_index_out_of_range"
    texture = textures[info["index"]]
    if not isinstance(texture, Mapping) or not _is_int(texture.get("source")) or not 0 <= texture["source"] < len(images):
        return None, None, None, "texture_source_missing_or_invalid"
    image_index = texture["source"]
    image = images[image_index]
    if not isinstance(image, Mapping) or "uri" in image or not _is_int(image.get("bufferView")):
        return None, None, None, "image_not_embedded"
    views = document.get("bufferViews")
    view_index = image["bufferView"]
    if not isinstance(views, list) or not 0 <= view_index < len(views):
        return None, None, None, "image_buffer_view_out_of_range"
    return info["index"], image_index, view_index, None


def _image_payload(document: Mapping[str, Any], binary: bytes, image_index: int, view_index: int) -> tuple[bytes | None, str | None, str | None]:
    images = document.get("images")
    views = document.get("bufferViews")
    if not isinstance(images, list) or not isinstance(views, list):
        return None, None, "images_or_buffer_views_invalid"
    image = images[image_index]
    view = views[view_index]
    if not isinstance(image, Mapping) or not isinstance(view, Mapping) or view.get("buffer", 0) != 0:
        return None, None, "image_buffer_view_invalid"
    offset = view.get("byteOffset", 0)
    length = view.get("byteLength")
    if not _is_int(offset) or offset < 0 or not _is_int(length) or not 0 < length <= MAX_TEXTURE_BYTES:
        return None, None, "image_byte_length_invalid_or_excessive"
    end = offset + length
    if end > len(binary):
        return None, None, "image_payload_out_of_bounds"
    payload = binary[offset:end]
    if not payload:
        return None, None, "image_payload_empty"
    mime = image.get("mimeType")
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        return None, None, "image_mime_type_unsupported"
    return payload, mime, None


def _flatten(image: Image.Image) -> list[tuple[int, ...]]:
    bands = image.getbands()
    raw = list(image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())
    if len(bands) == 1:
        return [(int(value),) for value in raw]
    return [tuple(int(component) for component in value) for value in raw]


def _measure_image(payload: bytes, mime: str) -> tuple[dict[str, Any] | None, str | None]:
    """Decode a bounded image and return factual pixel statistics only."""
    try:
        with Image.open(io.BytesIO(payload)) as opened:
            detected_mime = Image.MIME.get(opened.format)
            width, height = opened.size
            if detected_mime != mime:
                return None, "image_mime_signature_mismatch"
            if width < 1 or height < 1 or width > MAX_TEXTURE_DIMENSION or height > MAX_TEXTURE_DIMENSION:
                return None, "image_dimensions_out_of_policy"
            if width * height > MAX_TEXTURE_PIXELS:
                return None, "image_pixels_out_of_policy"
            opened.load()
            rgba = opened.convert("RGBA")
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None, "image_decode_failed"

    measured = rgba.copy()
    measured.thumbnail((MAX_MEASUREMENT_DIMENSION, MAX_MEASUREMENT_DIMENSION), Image.Resampling.BOX)
    values = _flatten(measured)
    if not values:
        return None, "image_measurement_empty"
    channels = list(zip(*values))
    channel_stats = [
        {"minimum": min(channel), "maximum": max(channel), "unique_values": len(set(channel))}
        for channel in channels
    ]
    alpha = channels[3]
    alpha_min, alpha_max = min(alpha), max(alpha)
    return {
        "mime_type": mime,
        "width": width,
        "height": height,
        "bytes": len(payload),
        "decoded_mode": "RGBA",
        "measurement_dimensions": [measured.width, measured.height],
        "measurement_samples": len(values),
        "channel_statistics_rgba": channel_stats,
        "constant_on_measurement_sample": all(item["minimum"] == item["maximum"] for item in channel_stats),
        "alpha": {
            "has_alpha_channel": True,
            "minimum": alpha_min,
            "maximum": alpha_max,
            "non_opaque_samples": sum(value < 255 for value in alpha),
            "fully_transparent_samples": sum(value == 0 for value in alpha),
        },
    }, None


def _base_report(path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": PBR_TEXTURE_QUALITY_SCHEMA_VERSION,
        "status": "reject",
        "passed": False,
        "artifact": {"path": str(Path(path))},
        "regions": [],
        "failures": [],
        "evidence_scope": {
            "regional_material_binding": "measured_local",
            "embedded_map_payload_and_dimensions": "measured_local",
            "pixel_variation_on_bounded_measurement_sample": "measured_local",
            "uv_accessor_binding": "measured_local",
            "alpha_and_transmission_declarations": "measured_local",
            "reference_alignment": "not_measured",
            "relighting": "not_measured",
            "baked_light_absence": "not_measured",
            "texture_aesthetic_quality": "not_measured",
        },
    }


def _transmission_report(material: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    extensions = material.get("extensions")
    transmission = extensions.get("KHR_materials_transmission") if isinstance(extensions, Mapping) else None
    if transmission is None:
        return {"applicable": False}, []
    if not isinstance(transmission, Mapping):
        return {"applicable": True}, ["transmission_extension_invalid"]
    factor = transmission.get("transmissionFactor", 0.0)
    if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not math.isfinite(float(factor)) or not 0 <= float(factor) <= 1:
        return {"applicable": True, "factor": factor}, ["transmission_factor_invalid"]
    return {"applicable": bool(factor > 0 or "transmissionTexture" in transmission), "factor": float(factor), "texture_declared": "transmissionTexture" in transmission}, []


def audit_pbr_texture_quality(
    glb_path: str | Path,
    semantic_graph: Mapping[str, Any],
    regional_map_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Measure all contracted region maps, failing closed on weak map evidence.

    A constant map is surfaced and rejected by this quality gate.  This does
    not call it physically wrong; it means the asset lacks the spatial texture
    evidence required by this particular master-oriented gate.
    """
    report = _base_report(glb_path)
    regional = audit_regional_pbr(glb_path, semantic_graph, regional_map_contract)
    report["regional_binding"] = regional
    if not regional.get("passed"):
        report["failures"] = [f"regional_binding_failed:{reason}" for reason in regional.get("failures", [])]
        return report
    source = Path(glb_path)
    try:
        container = validate_glb_container(source)
        document, binary = _read_glb(source)
    except (UnsafeAssetError, RuntimeCertificationError, OSError) as exc:
        report["failures"] = [f"unsafe_or_invalid_glb:{exc}"]
        return report
    report["artifact"].update({"sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "container": container})
    materials = document.get("materials")
    meshes = document.get("meshes")
    if not isinstance(materials, list) or not isinstance(meshes, list):
        report["failures"] = ["glb_materials_and_meshes_required"]
        return report

    primitives_by_material: dict[int, list[Mapping[str, Any]]] = {}
    for mesh in meshes:
        primitives = mesh.get("primitives") if isinstance(mesh, Mapping) else None
        if not isinstance(primitives, list):
            continue
        for primitive in primitives:
            if isinstance(primitive, Mapping) and _is_int(primitive.get("material")):
                primitives_by_material.setdefault(primitive["material"], []).append(primitive)

    failures: list[str] = []
    image_measurements: dict[int, tuple[dict[str, Any] | None, str | None]] = {}
    for region in regional["regions"]:
        binding = region.get("binding")
        region_id = region.get("id", "unknown")
        if not isinstance(binding, Mapping) or not _is_int(binding.get("material_index")):
            failures.append(f"region_binding_missing:{region_id}")
            continue
        material_index = binding["material_index"]
        if not 0 <= material_index < len(materials) or not isinstance(materials[material_index], Mapping):
            failures.append(f"region_material_invalid:{region_id}")
            continue
        material = materials[material_index]
        required = set(binding.get("required_maps") or [])
        required.update(_REQUIRED_ROLES & set(_ROLE_PATHS))
        region_report: dict[str, Any] = {
            "id": region_id,
            "material_index": material_index,
            "maps": {},
            "transmission": {},
        }
        transmission, transmission_failures = _transmission_report(material)
        region_report["transmission"] = transmission
        failures.extend(f"{reason}:{region_id}" for reason in transmission_failures)
        if transmission.get("applicable") and transmission.get("texture_declared"):
            # A transmission texture gets the same safe embedded/UV checks.
            material = dict(material)
            material["transmissionTexture"] = (material.get("extensions") or {}).get("KHR_materials_transmission", {}).get("transmissionTexture")
            required.add("transmission")

        for role in sorted(required):
            if role == "transmission":
                info = material.get("transmissionTexture")
            elif role in _ROLE_PATHS:
                info = _texture_info(material, role)
            else:
                failures.append(f"unknown_map_role:{region_id}:{role}")
                continue
            item: dict[str, Any] = {"role": role, "status": "reject"}
            _, image_index, view_index, reason = _map_reference(document, info)
            if reason:
                item["failure"] = reason
                failures.append(f"{reason}:{region_id}:{role}")
                region_report["maps"][role] = item
                continue
            texcoord = _texture_texcoord(info)
            item.update({"image_index": image_index, "texcoord": texcoord})
            if texcoord is None:
                item["failure"] = "texture_texcoord_invalid"
                failures.append(f"texture_texcoord_invalid:{region_id}:{role}")
            else:
                primitive_uvs = []
                for primitive in primitives_by_material.get(material_index, []):
                    attributes = primitive.get("attributes")
                    primitive_uvs.append(isinstance(attributes, Mapping) and f"TEXCOORD_{texcoord}" in attributes)
                item["primitive_uv_accessors_present"] = primitive_uvs
                if not primitive_uvs or not all(primitive_uvs):
                    item["failure"] = "uv_accessor_missing"
                    failures.append(f"uv_accessor_missing:{region_id}:{role}:TEXCOORD_{texcoord}")
            if image_index not in image_measurements:
                payload, mime, payload_reason = _image_payload(document, binary, image_index, view_index)
                image_measurements[image_index] = _measure_image(payload, mime) if payload and mime else (None, payload_reason)
            measurement, measurement_reason = image_measurements[image_index]
            if measurement_reason:
                item["failure"] = measurement_reason
                failures.append(f"{measurement_reason}:{region_id}:{role}")
            else:
                item["measurement"] = measurement
                if measurement and measurement["constant_on_measurement_sample"]:
                    item["failure"] = "constant_texture_measurement"
                    failures.append(f"constant_texture_measurement:{region_id}:{role}")
                if role == "base_color" and material.get("alphaMode", "OPAQUE") == "BLEND" and measurement and not measurement["alpha"]["non_opaque_samples"]:
                    item["failure"] = "blend_material_without_nonopaque_base_color_alpha"
                    failures.append(f"blend_material_without_nonopaque_base_color_alpha:{region_id}")
            item["status"] = "pass" if "failure" not in item else "reject"
            region_report["maps"][role] = item
        report["regions"].append(region_report)

    report["failures"] = sorted(set(failures))
    report["status"] = "pass" if not report["failures"] else "reject"
    report["passed"] = not report["failures"]
    return report
