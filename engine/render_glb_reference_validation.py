"""Render an actual GLB with its embedded base color, without HDRI lighting."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--glb", required=True)
    parser.add_argument("--projection-report", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            block.remove(item)


def _bounds(objects):
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    minimum = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    maximum = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    return minimum, maximum


def _base_color_only(objects):
    for obj in objects:
        for slot in obj.material_slots:
            material = slot.material
            if material is None:
                continue
            material.use_nodes = True
            nodes = material.node_tree.nodes
            image_node = next((node for node in nodes if node.type == "TEX_IMAGE" and node.image), None)
            if image_node is None:
                raise RuntimeError(f"embedded_base_color_missing:{material.name}")
            image = image_node.image
            nodes.clear()
            texture = nodes.new("ShaderNodeTexImage")
            texture.image = image
            emission = nodes.new("ShaderNodeEmission")
            output = nodes.new("ShaderNodeOutputMaterial")
            material.node_tree.links.new(texture.outputs["Color"], emission.inputs["Color"])
            material.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])


def _camera(scene, target, direction, ortho_scale):
    data = bpy.data.cameras.new("ReferenceValidationCamera")
    data.type = "ORTHO"
    data.ortho_scale = ortho_scale
    camera = bpy.data.objects.new("ReferenceValidationCamera", data)
    scene.collection.objects.link(camera)
    camera.location = target + direction * (ortho_scale * 3.0)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    return camera


def main():
    args = _arguments()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads(Path(args.projection_report).read_text(encoding="utf-8"))
    calibration = report["calibration"]
    _clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(Path(args.glb).resolve()))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not objects:
        raise RuntimeError("glb_mesh_missing")
    _base_color_only(objects)
    minimum, maximum = _bounds(objects)
    target = (minimum + maximum) * 0.5
    ortho_scale = max(maximum.z - minimum.z, maximum.x - minimum.x, maximum.y - minimum.y) * 1.12
    source_direction = calibration["cameraDirection"]
    base_direction = Vector((source_direction[0], -source_direction[2], source_direction[1])).normalized()

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    camera = _camera(scene, target, base_direction, ortho_scale)
    rendered = []
    for label, angle in (("front", 0), ("quarter-left", -30), ("quarter-right", 30)):
        radians = math.radians(angle)
        direction = Vector(
            (
                base_direction.x * math.cos(radians) - base_direction.y * math.sin(radians),
                base_direction.x * math.sin(radians) + base_direction.y * math.cos(radians),
                base_direction.z,
            )
        ).normalized()
        camera.location = target + direction * (ortho_scale * 3.0)
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        output = output_dir / f"blender-{label}.png"
        scene.render.filepath = str(output)
        bpy.ops.render.render(write_still=True)
        rendered.append(str(output))
    glb_path = Path(args.glb).resolve()
    projection_report = Path(args.projection_report).resolve()
    evidence = {
        "schemaVersion": 1,
        "renderer": bpy.app.version_string,
        "lighting": "embedded_base_color_only",
        "hdriInvoked": False,
        "glb": str(glb_path),
        "glbSha256": _sha256(glb_path),
        "projectionReport": str(projection_report),
        "projectionReportSha256": _sha256(projection_report),
        "renders": [
            {"path": path, "sha256": _sha256(path)} for path in rendered
        ],
    }
    report_path = output_dir / "blender-runtime-report.json"
    report_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({**evidence, "report": str(report_path)}))


if __name__ == "__main__":
    main()
