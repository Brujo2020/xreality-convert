"""Fail-closed validation for untrusted asset containers before DCC tooling."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any


MAX_GLB_BYTES = 512 * 1024 * 1024
MAX_GLB_JSON_BYTES = 16 * 1024 * 1024
MAX_GLB_NODES = 20_000
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A


class UnsafeAssetError(ValueError):
    pass


def validate_glb_container(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file() or source.stat().st_size < 20:
        raise UnsafeAssetError("glb_missing_or_too_small")
    if source.stat().st_size > MAX_GLB_BYTES:
        raise UnsafeAssetError("glb_too_large")
    with source.open("rb") as handle:
        header = handle.read(12)
        magic, version, declared_length = struct.unpack("<III", header)
        if magic != GLB_MAGIC or version != 2 or declared_length != source.stat().st_size:
            raise UnsafeAssetError("invalid_glb_header")
        json_header = handle.read(8)
        if len(json_header) != 8:
            raise UnsafeAssetError("missing_glb_json")
        json_length, chunk_type = struct.unpack("<II", json_header)
        if chunk_type != GLB_JSON or json_length > MAX_GLB_JSON_BYTES:
            raise UnsafeAssetError("invalid_glb_json_chunk")
        raw_json = handle.read(json_length)
    try:
        document = json.loads(raw_json.decode("utf-8").rstrip(" \t\r\n\x00"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnsafeAssetError("invalid_glb_json") from exc
    if not isinstance(document, dict):
        raise UnsafeAssetError("invalid_glb_document")
    nodes = document.get("nodes", [])
    if not isinstance(nodes, list) or len(nodes) > MAX_GLB_NODES:
        raise UnsafeAssetError("unsafe_glb_nodes")
    for image in document.get("images", []) or []:
        if not isinstance(image, dict):
            raise UnsafeAssetError("invalid_glb_image")
        uri = image.get("uri")
        if isinstance(uri, str) and not uri.startswith("data:"):
            raise UnsafeAssetError("external_texture_uri")
    return {"nodes": len(nodes), "images": len(document.get("images", []) or []), "bytes": source.stat().st_size}
