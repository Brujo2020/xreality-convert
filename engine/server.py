"""Local HTTP bridge between Xreality Convert and Hunyuan3D MLX.

The model loads lazily so launching the desktop app remains fast. The first
conversion downloads the MLX weights if they are not already present.
"""

import asyncio
import base64
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Hunyuan3D-2.1-mlx"
if SOURCE.exists():
    sys.path.insert(0, str(SOURCE))

JOBS_DIR = ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = JOBS_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

jobs = {}
shape_pipeline = None
load_error = None
background_session = None

app = FastAPI(title="Xreality Convert 3D Engine")


class GenerateRequest(BaseModel):
    image_base64: str = Field(min_length=32)
    steps: int = Field(default=30, ge=10, le=60)
    octree_resolution: int = Field(default=192, ge=96, le=256)
    texture: bool = False
    target_faces: int = Field(default=50000, ge=1000, le=500000)
    scale_meters: float = Field(default=1.0, gt=0, le=1000)
    profile: str = "xreal"
    category: str = "custom"
    guidance: float = Field(default=6.0, ge=1.0, le=12.0)
    background_mode: str = "auto"
    subject_padding: float = Field(default=0.16, ge=0.02, le=0.4)


class StlRequest(BaseModel):
    glb_path: str
    target_mm: float = Field(default=60, gt=0, le=10000)


class AnalyzeRequest(BaseModel):
    image_base64: str = Field(min_length=32)
    category: str = "custom"
    background_mode: str = "auto"


def patch_mlx_runtime():
    """Fix sparse marching-cubes NaNs that create thousands of degenerate faces."""
    model_file = SOURCE / "hy3dshape" / "hy3dshape" / "models" / "autoencoders" / "model_mlx.py"
    if not model_file.exists():
        return
    source = model_file.read_text()
    broken = "grid_logits[grid_logits == -10000.0] = float('nan')"
    fixed = (
        "grid_logits[grid_logits == -10000.0] = -100.0\n"
        "        grid_logits = np.nan_to_num(grid_logits, nan=-100.0, posinf=100.0, neginf=-100.0)"
    )
    if broken in source:
        model_file.write_text(source.replace(broken, fixed))


def get_pipeline():
    global shape_pipeline, load_error
    if shape_pipeline is not None:
        return shape_pipeline
    try:
        patch_mlx_runtime()
        from hy3dshape.hy3dshape.pipeline_mlx import ShapePipeline

        model_id = os.environ.get("HUNYUAN3D_MLX_WEIGHTS_DIR") or "dgrauet/hunyuan3d-2.1-mlx"
        shape_pipeline = ShapePipeline.from_pretrained(model_id)
        load_error = None
        return shape_pipeline
    except Exception as exc:
        load_error = str(exc)
        raise


def extract_mesh(result):
    if isinstance(result, (list, tuple)):
        return result[0]
    return result


def decode_image_base64(image_base64: str) -> bytes:
    return base64.b64decode(image_base64, validate=True)


def image_to_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def foreground_mask(image: Image.Image):
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    has_alpha = alpha.getextrema()[0] < 255
    if has_alpha:
        mask = alpha.point(lambda value: 255 if value > 16 else 0)
        return rgba, mask, True

    gray = rgba.convert("L")
    border_samples = []
    border_samples.extend(list(gray.crop((0, 0, gray.width, min(16, gray.height))).getdata()))
    border_samples.extend(list(gray.crop((0, max(0, gray.height - 16), gray.width, gray.height)).getdata()))
    border_samples.extend(list(gray.crop((0, 0, min(16, gray.width), gray.height)).getdata()))
    border_samples.extend(list(gray.crop((max(0, gray.width - 16), 0, gray.width, gray.height)).getdata()))
    border_value = sum(border_samples) / max(len(border_samples), 1)
    mask = gray.point(lambda value: 255 if abs(value - border_value) > 18 else 0)
    return rgba, mask, False


def count_components(mask: Image.Image) -> int:
    resample = Image.Resampling.BILINEAR if hasattr(Image, "Resampling") else Image.BILINEAR
    small = mask.convert("1").resize((64, 64), resample)
    data = small.load()
    width, height = small.size
    visited = set()
    components = 0

    for y in range(height):
        for x in range(width):
            if not data[x, y] or (x, y) in visited:
                continue
            components += 1
            stack = [(x, y)]
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                visited.add((cx, cy))
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    for ny in range(max(0, cy - 1), min(height, cy + 2)):
                        if data[nx, ny] and (nx, ny) not in visited:
                            stack.append((nx, ny))
    return components


def prepare_reference_image(image: Image.Image, category: str, background_mode: str, subject_padding: float = 0.16):
    global background_session
    remove_background = background_mode == "remove" or (
        background_mode == "auto" and category != "architecture"
    )

    prepared = image.convert("RGBA")
    if remove_background:
        try:
            from rembg import new_session, remove

            if background_session is None:
                background_session = new_session("u2net")
            prepared = remove(prepared, session=background_session).convert("RGBA")
        except Exception:
            prepared = prepared.convert("RGBA")

    alpha = prepared.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        subject = prepared.crop(bbox)
        padding = max(24, int(max(subject.size) * subject_padding))
        side = max(subject.size) + padding * 2
        canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
        canvas.alpha_composite(subject, ((side - subject.width) // 2, (side - subject.height) // 2))
        prepared = canvas

    return prepared


def prepare_reference(image_path: Path, request: GenerateRequest) -> Path:
    prepared = prepare_reference_image(
        Image.open(image_path),
        request.category,
        request.background_mode,
        request.subject_padding,
    )
    output = JOBS_DIR / f"{image_path.stem}-prepared.png"
    prepared.save(output)
    return output


def analyze_image(image: Image.Image, category: str, background_mode: str):
    rgba, mask, has_alpha = foreground_mask(image)
    width, height = rgba.size
    aspect_ratio = round(width / max(height, 1), 3)
    bbox = mask.getbbox()
    touches_edges = False
    if bbox:
        touches_edges = bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= width or bbox[3] >= height

    alpha_fraction = 0.0
    if has_alpha:
        alpha = rgba.getchannel("A")
        alpha_values = list(alpha.getdata())
        alpha_fraction = round(
            sum(1 for value in alpha_values if value < 16) / max(len(alpha_values), 1),
            4,
        )

    subject_components = count_components(mask)
    gray = rgba.convert("L")
    crop_center = gray.crop(
        (
            max(0, width // 4),
            max(0, height // 4),
            min(width, width - width // 4),
            min(height, height - height // 4),
        )
    )
    crop_border = gray.crop((0, 0, min(width, 48), min(height, 48)))
    center_values = list(crop_center.getdata()) or [128]
    border_values = list(crop_border.getdata()) or [128]
    contrast = abs((sum(center_values) / len(center_values)) - (sum(border_values) / len(border_values)))

    status = "Óptima"
    actions = []
    if width < 768 or height < 768:
        status = "Procesable con ajustes"
        actions.append("Usa una imagen de al menos 768 px en el lado corto.")
    if aspect_ratio > 1.45 or aspect_ratio < 0.7:
        status = "Procesable con ajustes"
        actions.append("Acerca el encuadre a un formato más cercano al cuadrado.")
    if subject_components > 2:
        status = "Procesable con ajustes"
        actions.append("Reduce elementos secundarios para que el sujeto principal quede único.")
    if touches_edges:
        status = "Procesable con ajustes"
        actions.append("Deja margen alrededor del sujeto y evita recortes en bordes.")
    if not has_alpha and contrast < 18:
        status = "No recomendada"
        actions.append("Aumenta el contraste entre sujeto y fondo o usa un PNG con transparencia.")

    if category == "architecture":
        suggested_background = "keep"
    elif has_alpha:
        suggested_background = "auto"
    else:
        suggested_background = "remove"

    if category == "custom" and subject_components > 2:
        suggested_category = "custom"
    elif category == "custom" and aspect_ratio > 1.3:
        suggested_category = "product"
    elif category == "custom" and aspect_ratio < 0.85:
        suggested_category = "person"
    else:
        suggested_category = category

    if background_mode == "auto":
        actions.append(
            "El fondo automático decidirá entre quitarlo o conservarlo según la categoría."
        )
    elif background_mode == "remove":
        actions.append("Se forzará la eliminación del fondo antes de reconstruir.")
    else:
        actions.append("Se conservará el fondo completo para la reconstrucción.")

    if category == "architecture":
        actions.append("Para arquitectura, conviene mantener la escena completa.")

    prepared = prepare_reference_image(rgba, category, background_mode, 0.16)
    return {
        "status": status,
        "resolution": {"width": width, "height": height},
        "aspect_ratio": aspect_ratio,
        "orientation": (
            "landscape"
            if width > height * 1.15
            else "portrait"
            if height > width * 1.15
            else "square"
        ),
        "has_alpha": has_alpha,
        "transparent_fraction": alpha_fraction,
        "subject_components": subject_components,
        "touches_edges": touches_edges,
        "contrast": round(contrast, 2),
        "suggested_category": suggested_category,
        "suggested_background_mode": suggested_background,
        "actions": actions,
        "preview_base64": image_to_base64(prepared),
    }


def mesh_component_stats(mesh):
    try:
        components = mesh.split(only_watertight=False)
    except Exception:
        components = [mesh]
    if not components:
        components = [mesh]
    areas = [float(getattr(component, "area", 0.0) or 0.0) for component in components]
    total_area = sum(areas) or 1.0
    largest_area = max(areas) if areas else 0.0
    largest_faces = max((len(getattr(component, "faces", [])) for component in components), default=0)
    return {
        "component_count": len(components),
        "largest_component_ratio": round((largest_area / total_area) if total_area else 1.0, 4),
        "largest_component_faces": int(largest_faces),
    }


def compute_quality(mesh, category: str, request: GenerateRequest, faces_before: int, raw_faces: int):
    faces = len(getattr(mesh, "faces", []))
    vertices = len(getattr(mesh, "vertices", []))
    try:
        watertight = bool(mesh.is_watertight)
    except Exception:
        watertight = False
    try:
        winding = bool(mesh.is_winding_consistent)
    except Exception:
        winding = False

    component_stats = mesh_component_stats(mesh)
    score = 100
    reasons = []

    minimum_faces = 3000 if category in {"animal", "person"} else 800
    if faces < minimum_faces:
        score -= 40
        reasons.append("La geometría útil es demasiado pequeña.")
    if vertices < 500:
        score -= 25
        reasons.append("Faltan vértices útiles para una forma estable.")
    if not watertight:
        score -= 20
        reasons.append("La malla no es watertight.")
    if not winding:
        score -= 10
        reasons.append("Las normales no están completamente consistentes.")
    if component_stats["component_count"] > 4 and category != "architecture":
        score -= 10
        reasons.append("Hay demasiados componentes desconectados.")
    if component_stats["largest_component_ratio"] < 0.6 and category != "architecture":
        score -= 15
        reasons.append("El componente principal es demasiado pequeño frente al resto.")
    if faces_before > request.target_faces * 1.35:
        score -= 15
        reasons.append("Excede ampliamente el presupuesto de caras.")
    if raw_faces - faces > max(200, int(faces * 0.2)):
        score -= 10
        reasons.append("La limpieza eliminó demasiada geometría irregular.")

    score = max(0, min(100, score))
    if score >= 80 and watertight:
        level = "listo"
    elif score >= 55:
        level = "atencion"
    else:
        level = "critico"

    if faces < minimum_faces:
        level = "critico"

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "faces": faces,
        "vertices": vertices,
        "watertight": watertight,
        "winding_consistent": winding,
        **component_stats,
    }


def clean_mesh(mesh, category: str):
    import trimesh

    faces_initial = len(mesh.faces)
    if hasattr(mesh, "remove_infinite_values"):
        mesh.remove_infinite_values()
    if hasattr(mesh, "remove_degenerate_faces"):
        try:
            mesh.remove_degenerate_faces()
        except Exception:
            mesh.update_faces(mesh.nondegenerate_faces())
    else:
        mesh.update_faces(mesh.nondegenerate_faces())
    if hasattr(mesh, "remove_duplicate_faces"):
        try:
            mesh.remove_duplicate_faces()
        except Exception:
            mesh.update_faces(mesh.unique_faces())
    else:
        mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    try:
        mesh.fix_normals()
    except Exception:
        pass
    try:
        trimesh.repair.fill_holes(mesh)
    except Exception:
        pass

    components = mesh.split(only_watertight=False)
    if components:
        if category in {"animal", "person", "product", "industrial", "custom"}:
            mesh = max(components, key=lambda item: len(item.faces))
        else:
            largest_area = max(component.area for component in components) or 1
            kept = [component for component in components if component.area >= largest_area * 0.015]
            mesh = trimesh.util.concatenate(kept or [max(components, key=lambda item: item.area)])

    try:
        mesh.process(validate=True)
    except Exception:
        mesh.remove_unreferenced_vertices()

    try:
        mesh.fix_normals()
    except Exception:
        pass

    return mesh, faces_initial


def save_report(job_id: str, payload: dict) -> str:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"{job_id}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return str(path)


def mark_cancelled(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return None
    job.update(
        {
            "status": "cancelled",
            "stage": "Cancelado por el usuario",
            "cancel_requested": True,
        }
    )
    return job


def cleanup_job(job_id: str):
    for suffix in (".png", "-prepared.png"):
        path = JOBS_DIR / f"{job_id}{suffix}"
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass


def run_job(job_id: str, request: GenerateRequest):
    global shape_pipeline
    job = jobs[job_id]
    started = time.monotonic()

    def cancelled():
        return bool(job.get("cancel_requested"))

    try:
        if cancelled():
            return
        job.update({"status": "running", "progress": 5, "stage": "Preparando referencia"})

        image_path = JOBS_DIR / f"{job_id}.png"
        image_path.write_bytes(decode_image_base64(request.image_base64))
        if cancelled():
            return

        job.update({"progress": 8, "stage": "Aislando y encuadrando el sujeto"})
        prepared_path = prepare_reference(image_path, request)
        if cancelled():
            return

        job.update({"progress": 15, "stage": "Cargando Hunyuan3D"})
        pipeline = get_pipeline()
        if cancelled():
            return

        mesh = extract_mesh(
            pipeline(
                str(prepared_path),
                num_inference_steps=request.steps,
                guidance_scale=request.guidance,
                octree_resolution=request.octree_resolution,
            )
        )
        shape_pipeline = None
        if cancelled():
            return

        job.update({"progress": 82, "stage": "Optimizando geometría"})
        mesh, raw_faces = clean_mesh(mesh, request.category)
        faces_before = len(getattr(mesh, "faces", []))

        minimum_faces = 3000 if request.category in {"animal", "person"} else 800
        if faces_before < minimum_faces or len(getattr(mesh, "vertices", [])) < 500:
            raise RuntimeError(
                f"Resultado rechazado por control de calidad: {faces_before} caras y "
                f"{len(getattr(mesh, 'vertices', []))} vértices útiles. "
                "Usa una imagen de cuerpo/objeto completo, sin elementos delante y con fondo simple."
            )

        quality = compute_quality(mesh, request.category, request, faces_before, raw_faces)
        if quality["level"] == "critico":
            raise RuntimeError(
                "Resultado rechazado por control de calidad: "
                + "; ".join(quality["reasons"] or ["la malla no alcanzó el nivel mínimo."])
            )

        if faces_before > request.target_faces:
            try:
                mesh = mesh.simplify_quadric_decimation(face_count=request.target_faces)
            except TypeError:
                mesh = mesh.simplify_quadric_decimation(request.target_faces)

        longest = max(getattr(mesh, "extents", [1])) or 1
        mesh.apply_scale(request.scale_meters / longest)

        output = JOBS_DIR / f"{job_id}.glb"
        job.update({"progress": 94, "stage": "Empaquetando GLB"})
        mesh.export(str(output))

        faces = len(getattr(mesh, "faces", []))
        elapsed = round(time.monotonic() - started, 1)
        report = {
            "job_id": job_id,
            "kind": "image3d",
            "created_at": time.time(),
            "elapsed": elapsed,
            "input": {
                "steps": request.steps,
                "octree_resolution": request.octree_resolution,
                "texture": request.texture,
                "target_faces": request.target_faces,
                "scale_meters": request.scale_meters,
                "profile": request.profile,
                "category": request.category,
                "guidance": request.guidance,
                "background_mode": request.background_mode,
                "subject_padding": request.subject_padding,
            },
            "metrics": {
                "faces_before": faces_before,
                "raw_faces": raw_faces,
                "faces": faces,
                "vertices": len(getattr(mesh, "vertices", [])),
                **quality,
            },
        }
        report_path = save_report(job_id, report)
        job.update(
            {
                "status": "done",
                "progress": 100,
                "stage": "Completado",
                "glb_path": str(output),
                "faces": faces,
                "faces_before": faces_before,
                "raw_faces": raw_faces,
                "elapsed": elapsed,
                "texture_requested": request.texture,
                "profile": request.profile,
                "category": request.category,
                "background_mode": request.background_mode,
                "report_path": report_path,
                "quality_score": quality["score"],
                "quality_level": quality["level"],
                "quality_text": " ".join(quality["reasons"]) if quality["reasons"] else "Validado correctamente.",
            }
        )
    except Exception as exc:
        shape_pipeline = None
        job.update({"status": "error", "error": str(exc), "elapsed": round(time.monotonic() - started, 1)})
    finally:
        cleanup_job(job_id)


@app.get("/health")
def health():
    return {"ready": SOURCE.exists(), "model_loaded": shape_pipeline is not None, "error": load_error}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if not SOURCE.exists():
        raise HTTPException(503, "Motor no instalado. Ejecuta la instalación desde Xreality Convert.")
    try:
        image = Image.open(io.BytesIO(decode_image_base64(request.image_base64)))
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer la imagen: {exc}") from exc
    return analyze_image(image, request.category, request.background_mode)


@app.post("/generate")
async def generate(request: GenerateRequest):
    if not SOURCE.exists():
        raise HTTPException(503, "Motor no instalado. Ejecuta la instalación desde Xreality Convert.")
    job_id = uuid.uuid4().hex
    jobs[job_id] = {"status": "queued", "cancel_requested": False, "progress": 0, "stage": "En cola"}
    asyncio.create_task(asyncio.to_thread(run_job, job_id, request))
    return {"job_id": job_id}


@app.post("/cancel/{job_id}")
def cancel(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado.")
    mark_cancelled(job_id)
    return {"ok": True, "status": job.get("status")}


@app.get("/status/{job_id}")
def status(job_id: str):
    return jobs.get(job_id, {"status": "unknown"})


@app.post("/to-stl")
def to_stl(request: StlRequest):
    try:
        import trimesh

        mesh = trimesh.load(request.glb_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
        if hasattr(mesh, "remove_infinite_values"):
            mesh.remove_infinite_values()
        if hasattr(mesh, "remove_degenerate_faces"):
            mesh.remove_degenerate_faces()
        if hasattr(mesh, "remove_duplicate_faces"):
            mesh.remove_duplicate_faces()
        mesh.remove_unreferenced_vertices()
        try:
            mesh.fix_normals()
        except Exception:
            pass
        try:
            trimesh.repair.fill_holes(mesh)
        except Exception:
            pass
        longest = max(mesh.extents) or 1
        mesh.apply_scale(request.target_mm / longest)
        watertight = bool(getattr(mesh, "is_watertight", False))
        winding = bool(getattr(mesh, "is_winding_consistent", False))
        if not watertight or not winding:
            raise RuntimeError("La STL resultante no es watertight o tiene normales inconsistentes.")
        output = JOBS_DIR / f"{uuid.uuid4().hex}.stl"
        mesh.export(str(output))
        return {
            "ok": True,
            "stl_path": str(output),
            "dims_mm": [round(float(d), 2) for d in mesh.extents],
            "watertight": watertight,
            "winding_consistent": winding,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
