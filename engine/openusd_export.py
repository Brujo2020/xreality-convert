"""Deterministic GLB -> OpenUSD/USDZ export for Apple platforms.

The exporter intentionally writes a small, portable USDA scene instead of
depending on Blender or Python ``pxr`` bindings.  Apple's own ``usdzip`` then
packages and normalizes the stage for RealityKit, and ``usdchecker`` is the
final fail-closed gate.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from pbr_glb import _read_glb


EXPORTER_VERSION = "xreality-openusd-v1"
_USDZIP_CANDIDATES = ("/usr/bin/usdzip", "/Applications/Xcode.app/Contents/Developer/usr/bin/usdzip")
_USDCHECKER_CANDIDATES = (
    "/usr/bin/usdchecker",
    "/Applications/Xcode.app/Contents/Developer/usr/bin/usdchecker",
)


def _tool(candidates, name):
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which(name)
    if found:
        return found
    raise RuntimeError(
        f"OpenUSD no disponible: falta {name}. Instala las herramientas de desarrollo de macOS."
    )


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identifier(value, fallback="Asset"):
    clean = re.sub(r"[^A-Za-z0-9_]", "_", str(value or fallback))
    clean = re.sub(r"_+", "_", clean).strip("_") or fallback
    if clean[0].isdigit():
        clean = f"_{clean}"
    return clean


def _number(value):
    number = float(value)
    if not np.isfinite(number):
        number = 0.0
    if abs(number) < 1e-10:
        number = 0.0
    return f"{number:.8g}"


def _tuple(values):
    return "(" + ", ".join(_number(value) for value in values) + ")"


def _array(values, tuple_size=None):
    values = np.asarray(values)
    if tuple_size:
        return "[" + ", ".join(_tuple(row[:tuple_size]) for row in values) + "]"
    return "[" + ", ".join(str(int(value)) for value in values.reshape(-1)) + "]"


def _factor(values, length, default):
    if values is None:
        return tuple(default)
    array = np.asarray(values, dtype=float).reshape(-1)
    if len(array) < length:
        return tuple(default)
    array = array[:length]
    if np.nanmax(np.abs(array)) > 1.0:
        array = array / 255.0
    array = np.nan_to_num(array, nan=0.0, posinf=1.0, neginf=0.0)
    return tuple(float(np.clip(value, 0.0, 1.0)) for value in array)


def _save_texture(value, destination, mode="RGB"):
    if value is None:
        return False
    if isinstance(value, Image.Image):
        image = value.copy()
    else:
        array = np.asarray(value)
        if array.size == 0:
            return False
        if array.dtype != np.uint8:
            if np.nanmax(array) <= 1.0:
                array = array * 255.0
            array = np.clip(array, 0, 255).astype(np.uint8)
        image = Image.fromarray(array)
    image.convert(mode).save(destination, format="PNG", optimize=True)
    return True


def _buffalo_manifest(glb_path):
    try:
        document, _ = _read_glb(glb_path)
        return ((document.get("asset") or {}).get("extras") or {}).get("xrealityBuffaloMLX")
    except Exception:
        return None


def _material_block(material, material_name, texture_dir, index):
    base = _factor(getattr(material, "baseColorFactor", None), 4, (1.0, 1.0, 1.0, 1.0))
    emissive = _factor(getattr(material, "emissiveFactor", None), 3, (0.0, 0.0, 0.0))
    metallic = float(getattr(material, "metallicFactor", 1.0) or 0.0)
    roughness = float(getattr(material, "roughnessFactor", 1.0) or 0.0)
    opacity = base[3]
    paths = {}
    for role, attribute, mode in (
        ("base", "baseColorTexture", "RGBA"),
        ("metallic_roughness", "metallicRoughnessTexture", "RGB"),
        ("normal", "normalTexture", "RGB"),
        ("emissive", "emissiveTexture", "RGB"),
    ):
        filename = f"{index:03d}_{role}.png"
        if _save_texture(getattr(material, attribute, None), texture_dir / filename, mode):
            paths[role] = f"textures/{filename}"

    prim = f"/XrealityAsset/Looks/{material_name}"
    surface = f"{prim}/PreviewSurface"
    lines = [
        f'        def Material "{material_name}"',
        "        {",
        f"            token outputs:surface.connect = <{surface}.outputs:surface>",
        "",
        '            def Shader "PreviewSurface"',
        "            {",
        '                uniform token info:id = "UsdPreviewSurface"',
        f"                color3f inputs:diffuseColor = {_tuple(base[:3])}",
        f"                color3f inputs:emissiveColor = {_tuple(emissive)}",
        f"                float inputs:metallic = {_number(metallic)}",
        f"                float inputs:roughness = {_number(roughness)}",
        f"                float inputs:opacity = {_number(opacity)}",
    ]
    if "base" in paths:
        lines.extend(
            [
                f"                color3f inputs:diffuseColor.connect = <{prim}/BaseColor.outputs:rgb>",
                f"                float inputs:opacity.connect = <{prim}/BaseColor.outputs:a>",
            ]
        )
    if "metallic_roughness" in paths:
        lines.extend(
            [
                f"                float inputs:metallic.connect = <{prim}/MetallicRoughness.outputs:b>",
                f"                float inputs:roughness.connect = <{prim}/MetallicRoughness.outputs:g>",
            ]
        )
    if "normal" in paths:
        lines.append(f"                normal3f inputs:normal.connect = <{prim}/Normal.outputs:rgb>")
    if "emissive" in paths:
        lines.append(f"                color3f inputs:emissiveColor.connect = <{prim}/Emissive.outputs:rgb>")
    lines.extend(["                token outputs:surface", "            }"])

    if paths:
        lines.extend(
            [
                "",
                '            def Shader "UVReader"',
                "            {",
                '                uniform token info:id = "UsdPrimvarReader_float2"',
                '                string inputs:varname = "st"',
                "                float2 outputs:result",
                "            }",
            ]
        )
    texture_specs = (
        ("base", "BaseColor", "sRGB", base),
        ("metallic_roughness", "MetallicRoughness", "raw", (1.0, roughness, metallic, 1.0)),
        ("normal", "Normal", "raw", (0.5, 0.5, 1.0, 1.0)),
        ("emissive", "Emissive", "sRGB", (*emissive, 1.0)),
    )
    for role, shader_name, color_space, fallback in texture_specs:
        if role not in paths:
            continue
        lines.extend(
            [
                "",
                f'            def Shader "{shader_name}"',
                "            {",
                '                uniform token info:id = "UsdUVTexture"',
                f"                asset inputs:file = @{paths[role]}@",
                f"                float4 inputs:fallback = {_tuple(fallback)}",
                f'                token inputs:sourceColorSpace = "{color_space}"',
                f"                float2 inputs:st.connect = <{prim}/UVReader.outputs:result>",
            ]
        )
        if role == "normal":
            lines.extend(
                [
                    "                float4 inputs:scale = (2, 2, 2, 2)",
                    "                float4 inputs:bias = (-1, -1, -1, 0)",
                ]
            )
        lines.extend(
            [
                "                float outputs:r",
                "                float outputs:g",
                "                float outputs:b",
                "                float outputs:a",
                "                color3f outputs:rgb",
                "            }",
            ]
        )
    lines.extend(["        }", ""])
    return lines, paths


def write_usda(glb_path, usda_path, texture_dir):
    """Write a flattened, meter/Y-up OpenUSD stage and return export metrics."""
    import trimesh

    source = Path(glb_path)
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)
    scene = trimesh.load(str(source), force="scene", process=False)
    if not isinstance(scene, trimesh.Scene) or not scene.geometry:
        raise RuntimeError("El GLB no contiene geometría exportable.")

    meshes = []
    for node_index, node_name in enumerate(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph.get(node_name)
        geometry = scene.geometry.get(geometry_name)
        if geometry is None or not hasattr(geometry, "faces") or len(geometry.faces) == 0:
            continue
        mesh = geometry.copy()
        mesh.apply_transform(transform)
        if not np.isfinite(mesh.vertices).all():
            raise RuntimeError(f"La pieza {node_name} contiene coordenadas no finitas.")
        mesh_name = f"Mesh_{node_index:03d}_{_identifier(node_name, 'Part')}"
        material_name = f"Material_{node_index:03d}"
        meshes.append((mesh_name, material_name, mesh))
    if not meshes:
        raise RuntimeError("El GLB no contiene triángulos exportables.")

    manifest = _buffalo_manifest(source)
    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "XrealityAsset"',
        "    metersPerUnit = 1",
        '    upAxis = "Y"',
        ")",
        "",
        'def Xform "XrealityAsset" (',
        '    kind = "component"',
        ")",
        "{",
        f'    custom string xreality:exporter = "{EXPORTER_VERSION}"',
        f'    custom string xreality:sourceSha256 = "{_sha256(source)}"',
    ]
    if manifest:
        compact = json.dumps(manifest, ensure_ascii=True, separators=(",", ":"))
        lines.append(f"    custom string xreality:buffaloManifest = {json.dumps(compact)}")
    lines.extend(["", '    def Scope "Looks"', "    {"])

    texture_count = 0
    for _, material_name, mesh in meshes:
        material = getattr(getattr(mesh, "visual", None), "material", None)
        if material is None:
            material = trimesh.visual.material.PBRMaterial(
                baseColorFactor=(204, 204, 204, 255), metallicFactor=0.0, roughnessFactor=0.6
            )
        material_lines, paths = _material_block(
            material, material_name, texture_dir, int(material_name.rsplit("_", 1)[-1])
        )
        lines.extend(material_lines)
        texture_count += len(paths)
    lines.extend(["    }", ""])

    face_total = 0
    vertex_total = 0
    for mesh_name, material_name, mesh in meshes:
        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces, dtype=int)
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise RuntimeError(f"La pieza {mesh_name} no está triangulada.")
        normals = np.asarray(mesh.vertex_normals, dtype=float)
        face_total += len(faces)
        vertex_total += len(vertices)
        mesh_path = f"/XrealityAsset/{mesh_name}"
        material_path = f"/XrealityAsset/Looks/{material_name}"
        lines.extend(
            [
                f'    def Mesh "{mesh_name}" (',
                '        prepend apiSchemas = ["MaterialBindingAPI"]',
                "    )",
                "    {",
                f"        int[] faceVertexCounts = [{', '.join('3' for _ in faces)}]",
                f"        int[] faceVertexIndices = {_array(faces)}",
                f"        point3f[] points = {_array(vertices, 3)}",
                f"        normal3f[] normals = {_array(normals, 3)} (",
                '            interpolation = "vertex"',
                "        )",
                f"        rel material:binding = <{material_path}>",
                '        uniform token subdivisionScheme = "none"',
            ]
        )
        uv = getattr(getattr(mesh, "visual", None), "uv", None)
        if uv is not None and len(uv) == len(vertices):
            uv = np.asarray(uv, dtype=float).copy()
            # glTF image origin is top-left after decoding; USD texture readers
            # conventionally consume bottom-left texture coordinates.
            uv[:, 1] = 1.0 - uv[:, 1]
            lines.extend(
                [
                    f"        texCoord2f[] primvars:st = {_array(uv, 2)} (",
                    '            interpolation = "vertex"',
                    "        )",
                ]
            )
        lines.extend(["    }", ""])
        _ = mesh_path
    lines.append("}")
    Path(usda_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "meshes": len(meshes),
        "vertices": vertex_total,
        "faces": face_total,
        "materials": len(meshes),
        "textures": texture_count,
        "semantic_manifest_preserved": bool(manifest),
    }


def convert_glb_to_usdz(glb_path, output_dir):
    """Convert GLB to a strict RealityKit-compatible USDZ package."""
    source = Path(glb_path).resolve()
    if not source.is_file() or source.suffix.lower() != ".glb":
        raise RuntimeError("Selecciona un archivo GLB válido para convertir a OpenUSD.")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    usdzip = _tool(_USDZIP_CANDIDATES, "usdzip")
    usdchecker = _tool(_USDCHECKER_CANDIDATES, "usdchecker")
    output = output_dir / f"{source.stem}-{_sha256(source)[:10]}.usdz"
    output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="xreality-openusd-", dir=output_dir) as work_raw:
        work = Path(work_raw)
        root = work / "XrealityAsset.usda"
        metrics = write_usda(source, root, work / "textures")
        package = subprocess.run(
            [usdzip, str(output), "--arkitAsset", str(root)],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if package.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            detail = (package.stderr or package.stdout or "usdzip falló").strip()
            raise RuntimeError(f"No se pudo crear el paquete OpenUSD: {detail}")
        check = subprocess.run(
            [usdchecker, "--arkit", "--strict", str(output)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        validation_output = "\n".join(
            part.strip() for part in (check.stdout, check.stderr) if part.strip()
        )
        if check.returncode != 0:
            output.unlink(missing_ok=True)
            raise RuntimeError(
                "El gate OpenUSD/RealityKit rechazó el paquete: "
                + (validation_output or "usdchecker falló")
            )

    return {
        "ok": True,
        "format": "usdz",
        "usdz_path": str(output),
        "sha256": _sha256(output),
        "source_sha256": _sha256(source),
        "arkit_compatible": True,
        "validator": "usdchecker --arkit --strict",
        "validation": validation_output or "Success!",
        **metrics,
    }


def write_usda_with_parts(glb_path, parts_manifest, usda_path, texture_dir):
    """Write a hierarchical, part-aware OpenUSD stage."""
    import trimesh

    source = Path(glb_path)
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "XrealityAsset"',
        "    metersPerUnit = 1",
        '    upAxis = "Y"',
        ")",
        "",
        'def Xform "XrealityAsset" (',
        '    kind = "component"',
        ")",
        "{",
        f'    custom string xreality:exporter = "{EXPORTER_VERSION}-production"',
        f'    custom string xreality:sourceSha256 = "{_sha256(source)}"',
        '    custom string xreality:materialx_ready = "true"',
        "",
        '    def Scope "Looks"',
        "    {",
    ]

    geometry_lines = []
    geometry_lines.append('    def Xform "Geometry"')
    geometry_lines.append('    {')

    texture_count = 0
    face_total = 0
    vertex_total = 0

    for part_idx, part in enumerate(parts_manifest):
        part_label = part.get("label", f"part_{part_idx}")
        part_glb = Path(part.get("glb_path"))

        scene = trimesh.load(str(part_glb), force="scene", process=False)
        part_meshes = []
        if isinstance(scene, trimesh.Scene) and scene.geometry:
            for node_name in scene.graph.nodes_geometry:
                transform, geometry_name = scene.graph.get(node_name)
                geometry = scene.geometry.get(geometry_name)
                if geometry is not None and hasattr(geometry, "faces") and len(geometry.faces) > 0:
                    mesh = geometry.copy()
                    mesh.apply_transform(transform)
                    part_meshes.append(mesh)

        if not part_meshes:
            continue

        if len(part_meshes) > 1:
            mesh = trimesh.util.concatenate(part_meshes)
        else:
            mesh = part_meshes[0]

        material_name = f"Material_{part_label}"
        material = getattr(getattr(mesh, "visual", None), "material", None)
        if material is None:
            material = trimesh.visual.material.PBRMaterial(
                baseColorFactor=(204, 204, 204, 255), metallicFactor=0.0, roughnessFactor=0.6
            )

        material_lines, paths = _material_block(
            material, material_name, texture_dir, part_idx
        )
        lines.extend(material_lines)
        texture_count += len(paths)

        part_xform = f'Part_{part_label}'
        mesh_name = f'Mesh_{part_label}'

        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces, dtype=int)
        normals = np.asarray(mesh.vertex_normals, dtype=float)

        face_total += len(faces)
        vertex_total += len(vertices)

        geometry_lines.extend([
            f'        def Xform "{part_xform}"',
            "        {",
            f'            def Mesh "{mesh_name}" (',
            '                prepend apiSchemas = ["MaterialBindingAPI"]',
            "            )",
            "            {",
            f"                int[] faceVertexCounts = [{', '.join('3' for _ in faces)}]",
            f"                int[] faceVertexIndices = {_array(faces)}",
            f"                point3f[] points = {_array(vertices, 3)}",
            f"                normal3f[] normals = {_array(normals, 3)} (",
            '                    interpolation = "vertex"',
            "                )",
            f"                rel material:binding = </XrealityAsset/Looks/{material_name}>",
            '                uniform token subdivisionScheme = "none"',
        ])

        uv = getattr(getattr(mesh, "visual", None), "uv", None)
        if uv is not None and len(uv) == len(vertices):
            uv = np.asarray(uv, dtype=float).copy()
            uv[:, 1] = 1.0 - uv[:, 1]
            geometry_lines.extend(
                [
                    f"                texCoord2f[] primvars:st = {_array(uv, 2)} (",
                    '                    interpolation = "vertex"',
                    "                )",
                ]
            )

        geometry_lines.extend(["            }", "        }"])

    lines.extend(["    }", ""])
    lines.extend(geometry_lines)
    lines.extend(["    }", "}"])

    Path(usda_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "meshes": len(parts_manifest),
        "vertices": vertex_total,
        "faces": face_total,
        "materials": len(parts_manifest),
        "textures": texture_count,
        "parts_count": len(parts_manifest),
    }


def write_usda_with_lods(glb_path, lods, usda_path, texture_dir):
    """Write an OpenUSD stage with LOD variant sets."""
    import trimesh

    source = Path(glb_path)
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "#usda 1.0",
        "(",
        '    defaultPrim = "XrealityAsset"',
        "    metersPerUnit = 1",
        '    upAxis = "Y"',
        ")",
        "",
        'def Xform "XrealityAsset" (',
        '    kind = "component"',
        '    variants = {',
        '        string LOD = "LOD0"',
        '    }',
        '    prepend variantSets = "LOD"',
        ")",
        "{",
        f'    custom string xreality:exporter = "{EXPORTER_VERSION}-production"',
        f'    custom string xreality:sourceSha256 = "{_sha256(source)}"',
        '    custom string xreality:materialx_ready = "true"',
        "",
        '    def Scope "Looks"',
        "    {",
    ]

    texture_count = 0
    face_total = 0
    vertex_total = 0

    variant_lines = []
    variant_lines.append('    variantSet "LOD" = {')

    for lod_idx, lod_path in enumerate(lods):
        lod_name = f"LOD{lod_idx}"
        scene = trimesh.load(str(lod_path), force="scene", process=False)
        lod_meshes = []
        if isinstance(scene, trimesh.Scene) and scene.geometry:
            for node_name in scene.graph.nodes_geometry:
                transform, geometry_name = scene.graph.get(node_name)
                geometry = scene.geometry.get(geometry_name)
                if geometry is not None and hasattr(geometry, "faces") and len(geometry.faces) > 0:
                    mesh = geometry.copy()
                    mesh.apply_transform(transform)
                    lod_meshes.append(mesh)

        if not lod_meshes:
            continue

        if len(lod_meshes) > 1:
            mesh = trimesh.util.concatenate(lod_meshes)
        else:
            mesh = lod_meshes[0]

        material_name = f"Material_{lod_name}"
        material = getattr(getattr(mesh, "visual", None), "material", None)
        if material is None:
            material = trimesh.visual.material.PBRMaterial(
                baseColorFactor=(204, 204, 204, 255), metallicFactor=0.0, roughnessFactor=0.6
            )

        material_lines, paths = _material_block(
            material, material_name, texture_dir, lod_idx + 100
        )
        lines.extend(material_lines)
        texture_count += len(paths)

        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces, dtype=int)
        normals = np.asarray(mesh.vertex_normals, dtype=float)

        face_total += len(faces)
        vertex_total += len(vertices)

        variant_lines.extend([
            f'        "{lod_name}" {{',
            f'            def Mesh "Geometry_{lod_name}" (',
            '                prepend apiSchemas = ["MaterialBindingAPI"]',
            "            )",
            "            {",
            f"                int[] faceVertexCounts = [{', '.join('3' for _ in faces)}]",
            f"                int[] faceVertexIndices = {_array(faces)}",
            f"                point3f[] points = {_array(vertices, 3)}",
            f"                normal3f[] normals = {_array(normals, 3)} (",
            '                    interpolation = "vertex"',
            "                )",
            f"                rel material:binding = </XrealityAsset/Looks/{material_name}>",
            '                uniform token subdivisionScheme = "none"',
        ])

        uv = getattr(getattr(mesh, "visual", None), "uv", None)
        if uv is not None and len(uv) == len(vertices):
            uv = np.asarray(uv, dtype=float).copy()
            uv[:, 1] = 1.0 - uv[:, 1]
            variant_lines.extend(
                [
                    f"                texCoord2f[] primvars:st = {_array(uv, 2)} (",
                    '                    interpolation = "vertex"',
                    "                )",
                ]
            )

        variant_lines.extend(["            }", "        }"])

    variant_lines.append('    }')

    lines.extend(["    }", ""])
    lines.extend(variant_lines)
    lines.append("}")

    Path(usda_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "meshes": len(lods),
        "vertices": vertex_total,
        "faces": face_total,
        "materials": len(lods),
        "textures": texture_count,
        "lod_variants": [f"LOD{i}" for i in range(len(lods))],
    }


def convert_glb_to_usd_production(glb_path, output_dir, parts=None, lods=None):
    """Full production export: USDA + textures + USDZ packaging with Parts or LODs."""
    source = Path(glb_path).resolve()
    if not source.is_file() or source.suffix.lower() != ".glb":
        raise RuntimeError("Selecciona un archivo GLB válido.")
    
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    usdzip = _tool(_USDZIP_CANDIDATES, "usdzip")
    output = output_dir / f"{source.stem}-production.usdz"
    output.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="xreality-openusd-prod-", dir=output_dir) as work_raw:
        work = Path(work_raw)
        root = work / "XrealityAsset.usda"
        texture_dir = work / "textures"
        
        metrics = {}
        parts_count = 0
        lod_variants = []
        features = ["MaterialBindingAPI", "UsdPreviewSurface"]

        if lods:
            metrics = write_usda_with_lods(source, lods, root, texture_dir)
            lod_variants = metrics.get("lod_variants", [])
            features.append("VariantSets")
        elif parts:
            metrics = write_usda_with_parts(source, parts, root, texture_dir)
            parts_count = metrics.get("parts_count", 0)
            features.append("PartHierarchy")
        else:
            metrics = write_usda(source, root, texture_dir)

        package = subprocess.run(
            [usdzip, str(output), "--arkitAsset", str(root)],
            cwd=work,
            capture_output=True,
            text=True,
        )
        
        if package.returncode != 0 or not output.is_file():
            output.unlink(missing_ok=True)
            raise RuntimeError(f"No se pudo crear el paquete OpenUSD de producción: {package.stderr}")

    return {
        "ok": True,
        "format": "usdz",
        "usdz_path": str(output),
        "parts_count": parts_count,
        "lod_variants": lod_variants,
        "materialx_compatible": True,
        "realitykit_features": features,
        **metrics,
    }
