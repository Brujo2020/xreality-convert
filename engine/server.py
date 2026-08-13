"""Local, fail-closed Image-to-3D bridge for Hunyuan3D MLX.

Shape and six-view Paint run sequentially because they share unified memory.
Independent CPU preparation and validation work is parallelized around those
Metal stages. No placeholder image or synthetic texture is promoted as output.
"""

import asyncio
import base64
import gc
import hashlib
import io
import json
import os
import secrets
import shutil
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image

from paint_service import PaintService
from agentic_paint_service import AgenticPaintService
from asset_director import (
    component_policy,
    material_profile_for_paint,
    optimize_delivery_settings,
    plan_asset,
)
from buffalo_strategy import (
    STRATEGY_VERSION,
    build_apple_execution_graph,
    build_strategy_report,
    capture_assembly_fingerprint,
    embed_strategy_metadata,
    validate_assembly_preservation,
)
from buffalo_runtime import (
    ContractError,
    JobLedger,
    atomic_write_json,
    build_evidence_manifest,
    build_job_contract,
    decode_base64_image,
    make_read_only,
    recover_interrupted_ledgers,
    validate_image_bytes,
)
from pbr_glb import apply_material_features, validate_material_contract
from openusd_export import convert_glb_to_usdz
from reference_projection import validate_native_paint_glb
from secure_artifacts import validate_glb_container
from stage_supervisor import StageLimits, StageSupervisor, StageWorkerError
from agentic_paint_service import memory_snapshot
from edit_executor import EditExecutionError, execute_replace_material
from runtime_certification import RuntimeCertificationError, certify_glb_for_target
from semantic_graph import SemanticGraphError, compile_semantic_graph
from derivative_lineage import DerivativeLineageError, build_derivative_manifest
from blender_validation_service import BlenderCanonicalValidationService, BlenderValidationError
from blender_repair_service import BlenderRepairError, BlenderRepairService
from lod_derivation import LODDerivationError, derive_glb_lod
from regional_pbr_gate import audit_regional_pbr
from pbr_texture_quality_gate import audit_pbr_texture_quality
from geometry_quality_gate import GeometryQualityError, audit_geometry_quality
from gltf_validator_gate import GlTFValidatorGate, GlTFValidatorGateError
from cloud_consent import CloudConsentError, create_consent, engage_kill_switch
from master_promotion_service import MasterPromotionError, seal_master_promotion
from multiview_contract import MultiViewContractError, admit_multiview_shape
from multiview_shape_backend import inspect_multiview_shape_backend

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "Hunyuan3D-2.1-mlx"
if SOURCE.exists():
    sys.path.insert(0, str(SOURCE))

JOBS_DIR = ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = JOBS_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCENE_CATEGORIES = {"architecture", "warehouse", "building", "electrical", "solar"}

jobs = {}
job_ledgers = {}
shape_pipeline = None
load_error = None
background_session = None
m5_optimizer = None
pipeline_lock = threading.RLock()
generation_lock = threading.Lock()
preload_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="xreality-shape-load")
ENGINE_TOKEN = os.environ.get("XREALITY_ENGINE_TOKEN", "")
ENGINE_VERSION = "21"
# The generation path keeps an input, prepared reference, geometry checkpoint,
# GLB and (when enabled) six Paint views.  These conservative reservations
# protect the user volume before any Metal allocation is admitted; they are not
# a claim about model-weight download size.
MIN_FREE_DISK_BYTES_GEOMETRY = 2 * 1024 ** 3
MIN_FREE_DISK_BYTES_TEXTURE = 6 * 1024 ** 3
# There is deliberately no provider default.  Merely installing the engine
# cannot make a networked route eligible; an operator must both configure an
# allow-list and create an asset-bound consent below.
CLOUD_ALLOWED_PROVIDERS = tuple(
    item.strip() for item in os.environ.get("XREALITY_CLOUD_PROVIDER_ALLOWLIST", "").split(",")
    if item.strip()
)
# These are intentionally unset by default.  A deployment administrator must
# seal and configure both files before the local review endpoint can act.
MASTER_REVIEW_POLICY_PATH = os.environ.get("XREALITY_MASTER_REVIEW_POLICY_PATH", "")
MASTER_REVIEWER_REGISTRY_PATH = os.environ.get("XREALITY_MASTER_REVIEWER_REGISTRY_PATH", "")

app = FastAPI(title="Xreality Convert 3D Engine")


@app.on_event("startup")
async def recover_control_plane_after_restart():
    """Expose interrupted durable jobs without silently replaying inference."""
    for item in recover_interrupted_ledgers(JOBS_DIR):
        job_id = item["job_id"]
        try:
            job_ledgers[job_id] = JobLedger.load(JOBS_DIR, job_id)
        except ContractError:
            continue
        if item.get("recovered"):
            jobs[job_id] = {
                "status": "interrupted",
                "stage": "Recuperado tras reinicio; reintento explícito requerido",
                "recovery": item,
            }


class GenerateRequest(BaseModel):
    image_base64: str = Field(min_length=32)
    multi_view_images: dict[str, str] = Field(default_factory=dict, max_length=5)
    use_multiview_shape: bool = False
    steps: int = Field(default=30, ge=10, le=60)
    octree_resolution: int = Field(default=192, ge=96, le=256)
    texture: bool = True  # Enabled by default for premium
    texture_resolution: int = Field(default=2048, ge=1024, le=2048)
    paint_backend: Literal["fast", "agentic"] = "fast"
    target_faces: int = Field(default=50000, ge=1000, le=500000)
    scale_meters: float = Field(default=1.0, gt=0, le=1000)
    profile: Literal[
        "lowpoly", "mobile", "quest", "vrready", "smart", "xreal", "pcvr", "maxquality"
    ] = "xreal"
    category: Literal[
        "animal",
        "person",
        "product",
        "industrial",
        "construction",
        "warehouse",
        "architecture",
        "vehicle",
        "cargo_vehicle",
        "truck",
        "crane",
        "electrical",
        "vegetation",
        "building",
        "tool",
        "forklift",
        "excavator",
        "motorcycle",
        "bus",
        "drone",
        "boat",
        "furniture",
        "solar",
        "custom",
    ] = "custom"
    material_hint: Literal[
        "auto",
        "skin",
        "hair",
        "fur",
        "foliage",
        "metal",
        "painted_metal",
        "rust",
        "carpet",
        "fabric",
        "plastic",
        "rubber",
        "ceramic",
        "porcelain",
        "glass",
        "concrete",
        "wood",
        "matte_paint",
    ] = "auto"
    guidance: float = Field(default=6.0, ge=1.0, le=12.0)
    background_mode: Literal["auto", "remove", "keep"] = "auto"
    subject_padding: float = Field(default=0.16, ge=0.02, le=0.4)


class StlRequest(BaseModel):
    glb_path: str
    target_mm: float = Field(default=60, gt=0, le=10000)


class OpenUsdRequest(BaseModel):
    glb_path: str
    format: Literal["usdz"] = "usdz"


class RuntimeCertificationRequest(BaseModel):
    glb_path: str
    target: Literal["web", "xr", "mobile"]


class ReplaceMaterialEditRequest(BaseModel):
    source_glb_path: str
    delta: dict


class DerivativeManifestRequest(BaseModel):
    master_glb_path: str
    output_path: str
    target: Literal["lod", "web", "xr", "mobile", "usdz"]
    topology_changed: bool
    target_certificate: dict
    rebake_evidence: dict | None = None


class BlenderValidationRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    glb_path: str
    projection_report_path: str
    output_dir: str


class ValidationArtifactStageRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    glb_path: str
    projection_report_path: str


class BlenderRepairRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    source_glb_path: str
    output_glb_path: str
    operation_contract: dict


class LODDerivationRequest(BaseModel):
    master_glb_path: str
    output_name: str = Field(min_length=5, max_length=128)
    target_faces: int = Field(ge=1, le=500000)


class RegionalPBRAuditRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    glb_path: str
    regional_map_contract: dict


class GeometryQualityRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    glb_path: str
    policy: dict = Field(default_factory=dict)


class GlTFValidatorRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    glb_path: str


class CloudConsentRequest(BaseModel):
    """Record explicit authority for a future isolated provider adapter.

    This endpoint never uploads data, resolves credentials, or starts a
    provider worker.  It exists so consent is explicit and hash-bound before a
    separately implemented adapter can reserve any budget.
    """

    job_id: str = Field(min_length=8, max_length=64)
    asset_path: str
    provider: str = Field(min_length=1, max_length=96)
    operation: str = Field(min_length=1, max_length=96)
    max_cost_micros: int = Field(default=0, ge=0, le=10**15)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    expires_at: float


class CloudKillSwitchRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    reason: str = Field(min_length=1, max_length=96)


class MasterPromotionRequest(BaseModel):
    job_id: str = Field(min_length=8, max_length=64)
    asset_path: str
    reviewer_id: str = Field(min_length=1, max_length=160)
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=512)


class AnalyzeRequest(BaseModel):
    image_base64: str = Field(min_length=32)
    category: str = "custom"
    background_mode: str = "auto"


class MultiViewAdmissionRequest(BaseModel):
    views: list[dict] = Field(min_length=1, max_length=6)
    profile: Literal["lowpoly", "mobile", "quest", "vrready", "smart", "xreal", "pcvr", "maxquality"] = "xreal"


@app.middleware("http")
async def require_engine_token(request, call_next):
    if ENGINE_TOKEN and request.url.path != "/health":
        supplied = request.headers.get("x-xreality-engine-token", "")
        if not secrets.compare_digest(supplied, ENGINE_TOKEN):
            return JSONResponse(status_code=401, content={"detail": "Motor local no autorizado."})
    return await call_next(request)


def apply_m5_optimizations():
    """Apply bounded MLX cache controls for the detected Apple chip."""
    global m5_optimizer

    try:
        from m5_optimizer import apply_m5_optimizations as apply_opts
        m5_optimizer = apply_opts()
        os.environ["XREALITY_VALIDATION_WORKERS"] = str(m5_optimizer.validation_workers)
    except ImportError:
        print("MLX runtime helper unavailable; using MLX defaults")
    except Exception as e:
        print(f"MLX runtime configuration failed: {e}")


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
    """Load the native MLX Shape pipeline once, safely across worker threads."""
    global shape_pipeline, load_error, m5_optimizer

    with pipeline_lock:
        if shape_pipeline is not None:
            return shape_pipeline
        if m5_optimizer is None:
            apply_m5_optimizations()

        try:
            patch_mlx_runtime()
            from hy3dshape.hy3dshape.pipeline_mlx import ShapePipeline

            model_id = os.environ.get("HUNYUAN3D_MLX_WEIGHTS_DIR") or "dgrauet/hunyuan3d-2.1-mlx"
            # This is the native MLX contract. PyTorch-only kwargs such as
            # torch_dtype are deliberately not accepted by ShapePipeline.
            shape_pipeline = ShapePipeline.from_pretrained(model_id)
            load_error = None
            print("Hunyuan3D Shape MLX loaded")
            return shape_pipeline
        except Exception as exc:
            load_error = str(exc)
            raise


def release_shape_pipeline(pipeline):
    """Release Shape before Paint so both model families never overlap in RAM."""
    global shape_pipeline

    with pipeline_lock:
        if shape_pipeline is pipeline:
            shape_pipeline = None
    del pipeline
    gc.collect()
    if m5_optimizer is not None:
        m5_optimizer.clear_cache()


def settle_shape_memory():
    """Collect after the caller has dropped its final Shape reference."""
    gc.collect()
    if m5_optimizer is not None:
        m5_optimizer.clear_cache()


def release_preloaded_pipeline(future):
    try:
        release_shape_pipeline(future.result())
    except Exception:
        pass


def extract_mesh(result):
    if isinstance(result, (list, tuple)):
        return result[0]
    return result


def isolated_shape_worker_enabled():
    """Opt-in only until physical-Metal parity has been measured."""
    return os.environ.get("XREALITY_SHAPE_WORKER") == "1"


def run_isolated_shape_worker(job_id, prepared_path, request):
    """Generate a sealed Shape checkpoint in a disposable local process."""
    raw_glb = JOBS_DIR / f"{job_id}-shape-worker.glb"
    report_path = JOBS_DIR / f"{job_id}-shape-worker-report.json"
    command = [
        sys.executable, str(ROOT / "shape_worker.py"),
        "--input", str(Path(prepared_path).resolve()),
        "--output", str(raw_glb.resolve()),
        "--report", str(report_path.resolve()),
        "--steps", str(request.steps),
        "--guidance", str(request.guidance),
        "--octree-resolution", str(request.octree_resolution),
    ]
    swap_limit = float(os.environ.get("XREALITY_MAX_SHAPE_SWAP_GROWTH_MB", "2048"))
    try:
        watchdog = StageSupervisor(memory_snapshot).run(
            command,
            cwd=ROOT.parent,
            limits=StageLimits(
                timeout_seconds=1800,
                minimum_free_percent=8,
                maximum_swap_growth_mb=swap_limit,
                network_allowed=False,
            ),
        )
    except StageWorkerError as exc:
        raise RuntimeError(f"Shape MLX abortado por watchdog: {exc.reason_code}") from exc
    if not raw_glb.is_file() or not report_path.is_file():
        raise RuntimeError("Shape MLX worker terminó sin sus artefactos requeridos")
    validate_glb_container(raw_glb)
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("Reporte inválido del Shape worker") from exc
    if (
        not report.get("passed")
        or report.get("provider") != "hunyuan3d-2.1-mlx"
        or Path(report.get("output_glb", "")).resolve() != raw_glb.resolve()
    ):
        raise RuntimeError("Contrato inválido del Shape worker")
    try:
        import trimesh
        mesh = trimesh.load(str(raw_glb), force="mesh")
    except Exception as exc:
        raise RuntimeError("Shape worker produjo una malla no cargable") from exc
    return mesh, {"worker": report, "watchdog": watchdog, "raw_glb": str(raw_glb)}


def seal_multiview_inputs(job_id, request, front_path):
    """Persist six camera inputs immutably before the multi-view worker starts."""
    views_dir = JOBS_DIR / f"{job_id}-multiview"
    views_dir.mkdir(parents=True, exist_ok=True)
    supplied = {"front": request.image_base64, **request.multi_view_images}
    records = []
    for view_id in ("front", "right", "back", "left", "top", "bottom"):
        encoded = supplied.get(view_id)
        if not encoded:
            raise RuntimeError(f"Vista multi-vista faltante: {view_id}")
        if view_id == "front":
            target = front_path
        else:
            target = views_dir / f"{view_id}.png"
            payload = decode_image_base64(encoded)
            validate_image_bytes(payload)
            target.write_bytes(payload)
            make_read_only(target)
        records.append({
            "view_id": view_id,
            "evidence_class": "measured",
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "file_path": str(target.resolve()),
        })
    admission = admit_multiview_shape(records, profile=request.profile)
    if not admission["passed"]:
        raise RuntimeError("Cobertura multi-vista incompleta")
    manifest = views_dir / "manifest.json"
    atomic_write_json(manifest, {"profile": request.profile, "views": records, "admission": admission})
    make_read_only(manifest)
    return manifest, admission


def run_multiview_shape_worker(job_id, manifest_path, request):
    """Execute official Hunyuan3D-2mv only after six inputs were sealed."""
    runtime = ROOT / "venv" / "bin" / "python"
    source = ROOT / "Hunyuan3D-2-official"
    weights = Path(os.environ.get("XREALITY_MULTIVIEW_WEIGHTS_DIR", ROOT / "models" / "Hunyuan3D-2mv"))
    if not runtime.is_file() or not source.is_dir() or not weights.is_dir():
        raise RuntimeError("Runtime multi-vista incompleto")
    raw_glb = JOBS_DIR / f"{job_id}-shape-multiview.glb"
    report_path = JOBS_DIR / f"{job_id}-shape-multiview-report.json"
    command = [str(runtime), str(ROOT / "multiview_shape_worker.py"), "--manifest", str(manifest_path),
               "--output", str(raw_glb), "--report", str(report_path), "--steps", str(request.steps),
               "--guidance", str(request.guidance), "--octree-resolution", str(request.octree_resolution),
               "--weights", str(weights), "--source", str(source), "--device", "mps"]
    try:
        watchdog = StageSupervisor(memory_snapshot).run(command, cwd=ROOT.parent, limits=StageLimits(
            timeout_seconds=1800, minimum_free_percent=8,
            maximum_swap_growth_mb=float(os.environ.get("XREALITY_MAX_SHAPE_SWAP_GROWTH_MB", "4096")),
            network_allowed=False,
        ))
    except StageWorkerError as exc:
        raise RuntimeError(f"Shape multi-vista abortado por watchdog: {exc.reason_code}") from exc
    validate_glb_container(raw_glb)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if not report.get("passed") or report.get("provider") != "hunyuan3d-2mv-pytorch":
        raise RuntimeError("Contrato inválido del worker multi-vista")
    import trimesh
    return trimesh.load(str(raw_glb), force="mesh"), {"worker": report, "watchdog": watchdog, "raw_glb": str(raw_glb)}


def decode_image_base64(image_base64: str) -> bytes:
    return decode_base64_image(image_base64)


def transition_ledger(job_id: str, target: str, reason_code: str, metadata=None):
    """Persist control-plane state without turning reporting failures into ML failures."""
    ledger = job_ledgers.get(job_id)
    if ledger is None:
        return None
    try:
        return ledger.transition(target, reason_code, metadata)
    except ContractError:
        return None


def ledger_summary(job_id: str):
    ledger = job_ledgers.get(job_id)
    if ledger is None:
        return None
    snapshot = None
    if ledger.snapshot_path.is_file():
        try:
            snapshot = json.loads(ledger.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            snapshot = {"state": "unreadable"}
    return {
        "state": snapshot or {"state": ledger.state},
        "job_dir": str(ledger.job_dir),
        "contract_path": str(ledger.contract_path),
        "evidence_path": str(ledger.job_dir / "evidence-manifest.json"),
        "journal_path": str(ledger.journal_path),
    }


def managed_glb_path(value: str) -> Path:
    source = Path(value).resolve()
    if not source.is_file() or source.suffix.lower() != ".glb":
        raise RuntimeError("Sólo se aceptan archivos GLB válidos.")
    validate_glb_container(source)
    return source


def managed_job_path(value: str) -> Path:
    source = Path(value).resolve()
    root = JOBS_DIR.resolve()
    if not source.is_file() or not source.is_relative_to(root):
        raise RuntimeError("Sólo se aceptan artefactos administrados por Xreality.")
    return source


def sealed_job_ledger(job_id: str) -> JobLedger:
    ledger = job_ledgers.get(job_id)
    if ledger is not None:
        return ledger
    candidate = (JOBS_DIR / job_id).resolve()
    if not candidate.is_dir() or not candidate.is_relative_to(JOBS_DIR.resolve()):
        raise RuntimeError("El job sellado no existe.")
    ledger = JobLedger.load(JOBS_DIR, job_id)
    if not ledger.contract_path.is_file():
        raise RuntimeError("El job no tiene un contrato sellado.")
    job_ledgers[job_id] = ledger
    return ledger


def ensure_generation_disk_space(request: GenerateRequest) -> dict:
    """Fail admission before inference when managed-job storage is exhausted."""
    required = MIN_FREE_DISK_BYTES_TEXTURE if request.texture else MIN_FREE_DISK_BYTES_GEOMETRY
    try:
        free = shutil.disk_usage(JOBS_DIR).free
    except OSError as exc:
        raise RuntimeError("No se pudo comprobar el espacio libre del motor local.") from exc
    if free < required:
        raise RuntimeError(
            "Espacio insuficiente para iniciar la conversión: "
            f"se requieren al menos {required // 1024 ** 3} GB libres y hay "
            f"{free // 1024 ** 3} GB disponibles."
        )
    return {"free_bytes": free, "required_bytes": required}


def build_explicit_retry_request(source_job_id: str) -> GenerateRequest:
    """Rebuild a request only from sealed local evidence after a restart."""
    source_ledger = JobLedger.load(JOBS_DIR, source_job_id)
    if not source_ledger.snapshot_path.is_file():
        raise ContractError("retry_source_unsealed")
    snapshot = json.loads(source_ledger.snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("reason_code") != "control_process_restarted":
        raise ContractError("retry_requires_restart_recovery")
    request_path = source_ledger.job_dir / "request.json"
    image_path = JOBS_DIR / f"{source_job_id}.png"
    if not request_path.is_file() or not image_path.is_file():
        raise ContractError("retry_evidence_incomplete")
    request_payload = json.loads(request_path.read_text(encoding="utf-8"))
    image_payload = image_path.read_bytes()
    validate_image_bytes(image_payload)
    request_payload["image_base64"] = base64.b64encode(image_payload).decode("ascii")
    return GenerateRequest.model_validate(request_payload)


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
    border_samples.extend(list(gray.crop((0, 0, gray.width, min(16, gray.height))).get_flattened_data()))
    border_samples.extend(list(gray.crop((0, max(0, gray.height - 16), gray.width, gray.height)).get_flattened_data()))
    border_samples.extend(list(gray.crop((0, 0, min(16, gray.width), gray.height)).get_flattened_data()))
    border_samples.extend(list(gray.crop((max(0, gray.width - 16), 0, gray.width, gray.height)).get_flattened_data()))
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
        background_mode == "auto" and category not in SCENE_CATEGORIES
    )

    prepared = image.convert("RGBA")
    if remove_background:
        try:
            from rembg import new_session, remove

            if background_session is None:
                background_session = new_session(
                    os.environ.get("XREALITY_REMBG_MODEL", "birefnet-general-lite")
                )
            prepared = remove(prepared, session=background_session).convert("RGBA")
        except Exception:
            prepared = prepared.convert("RGBA")

    alpha = prepared.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        subject = prepared.crop(bbox)
        # Match Hunyuan3D ImageProcessorV2: padding is the total border ratio,
        # not an extra ratio added independently on all four sides.
        side = max(1, round(max(subject.size) / (1 - subject_padding)))
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


def analyze_image(image: Image.Image, category: str, background_mode: str, include_preview=True):
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
    center_values = list(crop_center.get_flattened_data()) or [128]
    border_values = list(crop_border.get_flattened_data()) or [128]
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

    if category in SCENE_CATEGORIES:
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

    if category in SCENE_CATEGORIES:
        actions.append("Para arquitectura, conviene mantener la escena completa.")

    report = {
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
    }
    if include_preview:
        prepared = prepare_reference_image(rgba, category, background_mode, 0.16)
        report["preview_base64"] = image_to_base64(prepared)
    return report


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


def compute_quality(
    mesh,
    category: str,
    request: GenerateRequest,
    faces_before: int,
    raw_faces: int,
    asset_plan=None,
):
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

    contract = (asset_plan or {}).get("geometry_contract") or {}
    minimum_faces = int(
        contract.get("minimum_faces", 3000 if category in {"animal", "person"} else 800)
    )
    minimum_vertices = int(contract.get("minimum_vertices", 500))
    maximum_components = int(
        contract.get("maximum_components", 64 if category == "architecture" else 4)
    )
    minimum_component_ratio = float(
        contract.get(
            "minimum_largest_component_ratio",
            0.0 if category == "architecture" else 0.6,
        )
    )
    require_watertight = bool(contract.get("require_watertight", False))
    prefer_watertight = bool(contract.get("prefer_watertight", require_watertight))
    if faces < minimum_faces:
        score -= 40
        reasons.append("La geometría útil es demasiado pequeña.")
    if vertices < minimum_vertices:
        score -= 25
        reasons.append("Faltan vértices útiles para una forma estable.")
    if not watertight and require_watertight:
        score -= 20
        reasons.append("El nivel maestro exige una malla watertight.")
    elif not watertight and prefer_watertight:
        score -= 10
        reasons.append(
            "Cierre parcial: GLB/XR permitido con atención; STL permanece bloqueado."
        )
    if not winding:
        score -= 10
        reasons.append("Las normales no están completamente consistentes.")
    if component_stats["component_count"] > maximum_components:
        score -= 10
        reasons.append("Hay demasiados componentes desconectados.")
    if component_stats["largest_component_ratio"] < minimum_component_ratio:
        score -= 15
        reasons.append("El componente principal es demasiado pequeño frente al resto.")
    if faces_before > request.target_faces * 1.35:
        score -= 15
        reasons.append("Excede ampliamente el presupuesto de caras.")
    if raw_faces - faces > max(200, int(faces * 0.2)):
        score -= 10
        reasons.append("La limpieza eliminó demasiada geometría irregular.")

    score = max(0, min(100, score))
    if score >= 80 and (watertight or not require_watertight):
        level = "atencion" if prefer_watertight and not watertight else "listo"
    elif score >= 55:
        level = "atencion"
    else:
        level = "critico"

    if faces < minimum_faces or vertices < minimum_vertices or (require_watertight and not watertight):
        level = "critico"

    renderable_for_glb = (
        faces >= minimum_faces
        and vertices >= minimum_vertices
        and winding
        and component_stats["largest_component_ratio"] >= minimum_component_ratio
    )

    return {
        "score": score,
        "level": level,
        "reasons": reasons,
        "faces": faces,
        "vertices": vertices,
        "watertight": watertight,
        "winding_consistent": winding,
        "renderable_for_glb": renderable_for_glb,
        "contract": {
            "minimum_faces": minimum_faces,
            "minimum_vertices": minimum_vertices,
            "maximum_components": maximum_components,
            "minimum_largest_component_ratio": minimum_component_ratio,
            "require_watertight": require_watertight,
            "prefer_watertight": prefer_watertight,
            "watertight_policy": contract.get("watertight_policy", "legacy"),
        },
        **component_stats,
    }


def admit_renderable_glb_fallback(quality):
    """Downgrade failed master/solid promotion without discarding a safe GLB.

    The strict contract remains recorded as rejected.  This only changes the
    delivery lane to attention when the mesh has enough geometry, consistent
    winding and a category-credible principal component. STL remains guarded
    by its independent watertight check.
    """
    if quality.get("level") != "critico" or not quality.get("renderable_for_glb"):
        return False
    quality["contract_level"] = "critico"
    quality["level"] = "atencion"
    quality["score"] = min(int(quality.get("score", 0)), 79)
    quality["delivery_downgraded"] = True
    quality["master_promotion_passed"] = False
    quality.setdefault("reasons", []).append(
        "Gate maestro no aprobado; se entrega GLB/XR recuperable, no STL."
    )
    return True


def clean_mesh(mesh, category: str, profile="xreal"):
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
        policy = component_policy(category, profile)
        if not policy["preserve_assembly"]:
            mesh = max(components, key=lambda item: len(item.faces))
        else:
            largest_area = max(component.area for component in components) or 1
            kept = [
                component
                for component in components
                if component.area >= largest_area * policy["minimum_component_area_ratio"]
            ]
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


def seal_artifact(path):
    artifact = Path(path)
    if not artifact.is_file():
        return None
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(artifact),
        "bytes": artifact.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def recover_from_geometry_checkpoint(job_id, job, error, started, asset_plan=None):
    """Turn any post-geometry failure into an explicit non-premium delivery."""
    checkpoint = JOBS_DIR / f"{job_id}-shape.glb"
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        return False
    output = JOBS_DIR / f"{job_id}.glb"
    shutil.copy2(checkpoint, output)
    elapsed = round(time.monotonic() - started, 1)
    reason = f"Recuperación desde geometría validada: {error}"
    report = {
        "job_id": job_id,
        "kind": "image3d",
        "created_at": time.time(),
        "elapsed": elapsed,
        "texture": {
            "requested": True,
            "applied": False,
            "report": {
                "passed": False,
                "backend": "geometry-checkpoint",
                "degraded": True,
                "fallback_chain": [{"backend": "post_geometry", "passed": False, "error": str(error)}],
            },
            "shape_glb_path": str(checkpoint),
        },
        "art_director": asset_plan or {},
        "delivery": {
            "level": "atencion",
            "material_premium_ready": False,
            "reasons": [reason],
        },
    }
    report_path = save_report(job_id, report)
    job.update({
        "status": "done",
        "progress": 100,
        "stage": "Geometría recuperada",
        "glb_path": str(output),
        "shape_glb_path": str(checkpoint),
        "elapsed": elapsed,
        "texture_requested": True,
        "texture_applied": False,
        "texture_report": report["texture"]["report"],
        "art_director": asset_plan or {},
        "report_path": report_path,
        "quality_score": 0,
        "quality_level": "atencion",
        "quality_text": reason,
    })
    return True


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
    # Keep the original input as immutable evidence. Prepared derivatives may be
    # recreated from it and are safe to discard after the job exits.
    for suffix in ("-prepared.png",):
        path = JOBS_DIR / f"{job_id}{suffix}"
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass


def texture_profile_for_resolution(texture_resolution):
    return "2K" if int(texture_resolution) >= 2048 else "1K"


def apply_texture_to_mesh(
    mesh,
    reference_path,
    texture_resolution,
    output_path,
    category="custom",
    paint_backend="fast",
    material_hint="auto",
    profile="xreal",
    asset_plan=None,
):
    """Run Paint with explicit recovery while preserving the accepted Shape."""
    output = Path(output_path)
    shape_output = output.with_name(f"{output.stem}-shape.glb")
    paint_output = output.with_name(f"{output.stem}-paint.glb")
    mesh.export(str(shape_output))
    asset_plan = asset_plan or plan_asset(
        category=category,
        material_hint=material_hint,
        profile=profile,
        requested_paint_backend=paint_backend,
        texture_enabled=True,
    )
    requested_backend = asset_plan["paint_backend"]
    attempts = []

    def run_fast_paint(recovery=False):
        paint_profile = texture_profile_for_resolution(texture_resolution)
        material_profile = material_profile_for_paint(asset_plan["material"])
        fast_report = PaintService().run(
            mesh_path=shape_output,
            image_path=reference_path,
            output_glb_path=paint_output,
            texture_size=paint_profile,
            material_profile=material_profile,
            category=category,
        )
        fidelity = validate_native_paint_glb(
            paint_output,
            reference_path,
            JOBS_DIR / "evidence" / f"{output.stem}-native-paint",
            # A fragmented projection is worse than an untextured delivery.
            # Preview/mobile may surface it as attention, but premium/master
            # routes must fall back to the accepted geometry rather than
            # publishing corrupted albedo as a usable material.
            fail_closed=asset_plan["quality_tier"] in {"premium", "master"},
        )
        paint_output.replace(output)
        visual_attention = not fidelity.get("gate", {}).get("passed", False)
        return {
            **fast_report,
            "backend": "hunyuan-fast-recovery" if recovery else "hunyuan-fast",
            "visual_fidelity": fidelity,
            "degraded": visual_attention,
            "visual_attention": fidelity.get("gate", {}).get("reasons", []) if visual_attention else [],
        }

    try:
        if requested_backend == "agentic":
            report = AgenticPaintService().run(
                mesh_path=shape_output,
                image_path=reference_path,
                output_glb_path=output,
                steps=4,
                texture_size=2048 if int(texture_resolution) >= 2048 else 1024,
                seed=42,
            )
        elif requested_backend == "fast":
            report = run_fast_paint()
        else:
            raise ValueError(f"Backend de textura desconocido: {requested_backend}")
    except Exception as primary_error:
        attempts.append(
            {"backend": requested_backend, "passed": False, "error": str(primary_error)}
        )
        if requested_backend == "agentic":
            try:
                report = run_fast_paint(recovery=True)
            except Exception as recovery_error:
                attempts.append(
                    {"backend": "fast", "passed": False, "error": str(recovery_error)}
                )
                shutil.copy2(shape_output, output)
                return {
                    "passed": False,
                    "backend": "geometry-checkpoint",
                    "backend_requested": requested_backend,
                    "degraded": True,
                    "fallback_chain": attempts,
                    "material": asset_plan["material"],
                    "material_features": {"applied": False, "extensions": []},
                    "material_contract": {
                        "passed": False,
                        "premium_ready": False,
                        "reasons": ["texture_backends_unavailable"],
                        "missing_recommended_maps": [],
                        "material_regions_ready": False,
                    },
                    "art_director": asset_plan,
                }, shape_output
        else:
            shutil.copy2(shape_output, output)
            return {
                "passed": False,
                "backend": "geometry-checkpoint",
                "backend_requested": requested_backend,
                "degraded": True,
                "fallback_chain": attempts,
                "material": asset_plan["material"],
                "material_features": {"applied": False, "extensions": []},
                "material_contract": {
                    "passed": False,
                    "premium_ready": False,
                    "reasons": ["texture_backend_unavailable"],
                    "missing_recommended_maps": [],
                    "material_regions_ready": False,
                },
                "art_director": asset_plan,
            }, shape_output

    try:
        feature_report = apply_material_features(
            output, asset_plan["material_contract"]
        )
        contract_report = validate_material_contract(
            output,
            asset_plan["material_contract"],
            enforce_recommended=asset_plan["enforce_recommended_maps"],
        )
    except Exception as material_error:
        attempts.append({
            "backend": report.get("backend", requested_backend),
            "passed": False,
            "error": f"material_validation_error: {material_error}",
        })
        shutil.copy2(shape_output, output)
        return {
            "passed": False,
            "backend": "geometry-checkpoint",
            "backend_requested": requested_backend,
            "degraded": True,
            "fallback_chain": attempts,
            "material": asset_plan["material"],
            "material_features": {"applied": False, "extensions": []},
            "material_contract": {
                "passed": False,
                "premium_ready": False,
                "reasons": ["material_validation_error"],
                "missing_recommended_maps": [],
                "material_regions_ready": False,
            },
            "art_director": asset_plan,
        }, shape_output
    if not contract_report["passed"]:
        attempts.append({
            "backend": report.get("backend", requested_backend),
            "passed": False,
            "error": "Material rechazado por contrato artístico: "
            + ", ".join(contract_report["reasons"]),
        })
        shutil.copy2(shape_output, output)
        return {
            "passed": False,
            "backend": "geometry-checkpoint",
            "backend_requested": requested_backend,
            "degraded": True,
            "fallback_chain": attempts,
            "material": asset_plan["material"],
            "material_features": feature_report,
            "material_contract": contract_report,
            "art_director": asset_plan,
        }, shape_output
    return {
        **report,
        "backend_requested": requested_backend,
        "degraded": bool(attempts) or bool(report.get("degraded")),
        "fallback_chain": attempts,
        "material": asset_plan["material"],
        "material_features": feature_report,
        "material_contract": contract_report,
        "art_director": asset_plan,
    }, shape_output


def run_job(job_id: str, request: GenerateRequest):
    job = jobs[job_id]
    started = time.monotonic()
    pipeline = None
    pipeline_future = None
    milestones = {}
    last_quality = None
    rejected_artifact = None

    def mark_milestone(name):
        milestones[name] = round(time.monotonic() - started, 3)
    with pipeline_lock:
        if m5_optimizer is None:
            apply_m5_optimizations()
    memory_gb = (
        float(m5_optimizer.total_memory) / (1024 ** 3)
        if m5_optimizer is not None
        else None
    )
    execution_plan = optimize_delivery_settings(
        profile=request.profile,
        steps=request.steps,
        octree_resolution=request.octree_resolution,
        target_faces=request.target_faces,
        texture_resolution=request.texture_resolution,
        paint_backend=request.paint_backend,
        unified_memory_gb=memory_gb,
    )
    runtime_snapshot = m5_optimizer.snapshot() if m5_optimizer is not None else {}
    apple_execution = build_apple_execution_graph(runtime_snapshot)
    execution_plan["buffalo_mlx"] = apple_execution
    request.steps = execution_plan["steps"]
    request.octree_resolution = execution_plan["octree_resolution"]
    request.target_faces = execution_plan["target_faces"]
    request.texture_resolution = execution_plan["texture_resolution"]
    request.paint_backend = execution_plan["paint_backend"]
    asset_plan = plan_asset(
        category=request.category,
        material_hint=request.material_hint,
        profile=request.profile,
        requested_paint_backend=request.paint_backend,
        texture_enabled=request.texture,
    )
    try:
        semantic_graph = compile_semantic_graph(asset_plan["semantic_contract"])
    except SemanticGraphError as exc:
        raise RuntimeError(f"Contrato semántico inválido: {exc}") from exc
    asset_plan["semantic_graph"] = semantic_graph
    ledger = job_ledgers.get(job_id)
    def cancelled():
        return bool(job.get("cancel_requested"))

    generation_lock.acquire()
    try:
        if asset_plan["blocked"]:
            raise RuntimeError(
                "Trabajo rechazado por el director técnico: "
                + ", ".join(asset_plan["blockers"])
            )
        if cancelled():
            return
        job.update({
            "status": "running",
            "progress": 5,
            "stage": "Buffalo-MLX: sellando contrato semántico",
            "category": request.category,
            "profile": request.profile,
            "execution_plan": execution_plan,
        })

        image_path = JOBS_DIR / f"{job_id}.png"
        input_payload = decode_image_base64(request.image_base64)
        image_info = validate_image_bytes(input_payload)
        image_path.write_bytes(input_payload)
        evidence_manifest = build_evidence_manifest(image_path, image_info)
        make_read_only(image_path)
        multiview_manifest = None
        multiview_admission = None
        if request.use_multiview_shape:
            multiview_manifest, multiview_admission = seal_multiview_inputs(job_id, request, image_path)
        execution_policy = {
            "deadline_seconds": 1800,
            "material_contract": asset_plan["material_contract"],
            "execution_plan": execution_plan,
            "apple_execution": apple_execution,
            "network_allowed": False,
            "retry_of": job.get("retry_of"),
            "semantic_graph_id": semantic_graph["graph_id"],
        }
        if ledger is not None:
            contract = build_job_contract(
                job_id=job_id,
                request=request.model_dump(exclude={"image_base64"}),
                evidence_manifest=evidence_manifest,
                semantic_contract=semantic_graph,
                execution_policy=execution_policy,
            )
            ledger.seal(contract, evidence_manifest, request.model_dump(exclude={"image_base64"}))
            semantic_graph_path = ledger.job_dir / "semantic-graph.json"
            atomic_write_json(semantic_graph_path, semantic_graph)
            make_read_only(semantic_graph_path)
            ledger.transition("PREFLIGHTED", "input_admitted", {"image": image_info})
        with Image.open(image_path) as source_image:
            input_analysis = analyze_image(
                source_image,
                request.category,
                request.background_mode,
                include_preview=False,
            )
        mark_milestone("input_preflight_complete")
        if input_analysis["status"] == "No recomendada":
            raise RuntimeError(
                "Referencia rechazada antes de iniciar MLX: "
                + " ".join(input_analysis.get("actions") or ["Mejora el contraste y el encuadre."])
            )
        # The experimental worker gives Metal allocations a process boundary.
        # The resident path remains the default until it wins physical-Mac
        # parity and latency trials on the same corpus.
        use_multiview_worker = request.use_multiview_shape
        use_shape_worker = isolated_shape_worker_enabled() and not use_multiview_worker
        if not use_shape_worker and not use_multiview_worker:
            # Weight loading is independent from CPU image isolation. Overlapping
            # both shortens a cold first run without running Shape and Paint together.
            pipeline_future = preload_executor.submit(get_pipeline)
        if cancelled():
            return

        job.update({"progress": 8, "stage": "Sellando cámaras multi-vista" if use_multiview_worker else "Aislando y encuadrando el sujeto"})
        prepared_path = image_path if use_multiview_worker else prepare_reference(image_path, request)
        mark_milestone("reference_preparation_complete")
        if cancelled():
            return

        job.update({"progress": 15, "stage": "Cargando Hunyuan3D"})
        if not use_shape_worker and not use_multiview_worker:
            pipeline = pipeline_future.result()
            pipeline_future = None
        mark_milestone("shape_weights_ready")
        if cancelled():
            return

        job.update({"progress": 24, "stage": "Motor Hunyuan3D listo"})

        def shape_progress(completed, total):
            progress = 30 + round(40 * completed / max(1, total))
            job.update(
                {
                    "progress": progress,
                    "stage": f"Reconstruyendo volumen · {completed}/{total}",
                }
            )

        job.update({"progress": 30, "stage": "Reconstruyendo volumen"})
        transition_ledger(job_id, "RUNNING_STAGE", "shape_started", {
            "provider": "hunyuan3d-2mv-pytorch" if use_multiview_worker else "hunyuan3d-2.1-mlx",
            "steps": request.steps,
            "resolution": request.octree_resolution,
            "multiview_admission": multiview_admission,
        })
        if use_multiview_worker:
            mesh, shape_worker_report = run_multiview_shape_worker(job_id, multiview_manifest, request)
        elif use_shape_worker:
            mesh, shape_worker_report = run_isolated_shape_worker(job_id, prepared_path, request)
        else:
            mesh = extract_mesh(
                pipeline(
                    str(prepared_path),
                    num_inference_steps=request.steps,
                    guidance_scale=request.guidance,
                    octree_resolution=request.octree_resolution,
                    progress_callback=shape_progress,
                )
            )
        mark_milestone("shape_inference_complete")
        job.update({"progress": 76, "stage": "Volumen reconstruido"})
        if pipeline is not None:
            release_shape_pipeline(pipeline)
            pipeline = None
            settle_shape_memory()
        if ledger is not None:
            ledger.record_stage("shape", "passed", {
                "milestone": milestones.get("shape_inference_complete"),
                "isolation": shape_worker_report if (use_shape_worker or use_multiview_worker) else {"mode": "resident"},
            })
        transition_ledger(job_id, "STAGE_PASSED", "shape_passed")
        if cancelled():
            return

        job.update({"progress": 82, "stage": "Optimizando geometría"})
        transition_ledger(job_id, "RUNNING_STAGE", "geometry_started")
        mesh, raw_faces = clean_mesh(mesh, request.category, request.profile)
        faces_before = len(getattr(mesh, "faces", []))
        assembly_before = capture_assembly_fingerprint(mesh)

        geometry_contract = asset_plan["geometry_contract"]
        minimum_faces = geometry_contract["minimum_faces"]
        minimum_vertices = geometry_contract["minimum_vertices"]
        if faces_before < minimum_faces or len(getattr(mesh, "vertices", [])) < minimum_vertices:
            raise RuntimeError(
                f"Resultado rechazado por control de calidad: {faces_before} caras y "
                f"{len(getattr(mesh, 'vertices', []))} vértices útiles. "
                "Usa una imagen de cuerpo/objeto completo, sin elementos delante y con fondo simple."
            )

        pre_decimation_quality = compute_quality(
            mesh, request.category, request, faces_before, raw_faces, asset_plan
        )
        last_quality = pre_decimation_quality
        if (
            pre_decimation_quality["level"] == "critico"
            and not admit_renderable_glb_fallback(pre_decimation_quality)
        ):
            rejected_artifact = JOBS_DIR / f"{job_id}-rejected-shape.glb"
            mesh.export(str(rejected_artifact))
            raise RuntimeError(
                "Resultado rechazado por control de calidad: "
                + "; ".join(
                    pre_decimation_quality["reasons"]
                    or ["la malla no alcanzó el nivel mínimo."]
                )
            )

        master_output = None
        master_mesh = None
        preservation_gate = validate_assembly_preservation(
            assembly_before,
            assembly_before,
            asset_plan["semantic_contract"],
        )
        if faces_before > request.target_faces:
            # Simplification is transactional: the accepted geometry remains in
            # memory until the derived candidate passes the assembly gate.
            accepted_master = mesh.copy()
            try:
                candidate = mesh.simplify_quadric_decimation(face_count=request.target_faces)
            except TypeError:
                candidate = mesh.simplify_quadric_decimation(request.target_faces)
            candidate_fingerprint = capture_assembly_fingerprint(candidate)
            candidate_gate = validate_assembly_preservation(
                assembly_before,
                candidate_fingerprint,
                asset_plan["semantic_contract"],
            )
            if candidate_gate["passed"]:
                mesh = candidate
                preservation_gate = candidate_gate
                if execution_plan["preserve_master"]:
                    master_mesh = accepted_master
            else:
                # Never deliver a budget-compliant mesh that lost meaningful
                # components. Keep the accepted master and report the rejected
                # derivation instead of silently damaging the asset.
                mesh = accepted_master
                master_mesh = accepted_master.copy()
                preservation_gate = validate_assembly_preservation(
                    assembly_before,
                    capture_assembly_fingerprint(mesh),
                    asset_plan["semantic_contract"],
                )
                preservation_gate["candidate_rejected"] = candidate_gate
                preservation_gate["fallback_to_accepted_master"] = True
                preservation_gate["delivery_budget_met"] = False

        job.update({"progress": 86, "stage": "Validando geometría final"})
        delivery_faces = len(getattr(mesh, "faces", []))
        quality = compute_quality(
            mesh,
            request.category,
            request,
            delivery_faces,
            delivery_faces,
            asset_plan,
        )
        last_quality = quality
        mark_milestone("geometry_and_preservation_gates_complete")
        if quality["level"] == "critico" and not admit_renderable_glb_fallback(quality):
            rejected_artifact = JOBS_DIR / f"{job_id}-rejected-shape.glb"
            mesh.export(str(rejected_artifact))
            raise RuntimeError(
                "Resultado rechazado tras optimizar la geometría: "
                + "; ".join(quality["reasons"] or ["la malla final no es entregable."])
            )

        longest = max(getattr(mesh, "extents", [1])) or 1
        mesh.apply_scale(request.scale_meters / longest)
        if master_mesh is not None:
            master_longest = max(getattr(master_mesh, "extents", [1])) or 1
            master_mesh.apply_scale(request.scale_meters / master_longest)
            master_output = JOBS_DIR / f"{job_id}-master.glb"
            master_mesh.export(str(master_output))

        # Commit the accepted geometry before entering any texture/material
        # stage. This file is the global recovery boundary for the job.
        geometry_checkpoint = JOBS_DIR / f"{job_id}-shape.glb"
        mesh.export(str(geometry_checkpoint))
        if ledger is not None:
            ledger.record_stage("geometry", "passed", {
                "artifact": seal_artifact(geometry_checkpoint),
                "quality": quality.get("level"),
                "preservation": preservation_gate.get("decision"),
            })
        transition_ledger(job_id, "STAGE_PASSED", "geometry_passed")

        output = JOBS_DIR / f"{job_id}.glb"
        texture_report = None
        shape_output = None
        if request.texture:
            paint_label = (
                "AgenticVibes: calidad + reference lock"
                if asset_plan["paint_backend"] == "agentic"
                else "Hunyuan Paint: 6 vistas + horneado PBR"
            )
            job.update({"progress": 90, "stage": paint_label})
            transition_ledger(job_id, "RUNNING_STAGE", "paint_started", {
                "backend": asset_plan["paint_backend"],
                "texture_resolution": request.texture_resolution,
            })
            texture_report, shape_output = apply_texture_to_mesh(
                mesh,
                prepared_path,
                request.texture_resolution,
                output,
                request.category,
                asset_plan["paint_backend"],
                request.material_hint,
                request.profile,
                asset_plan,
            )
        else:
            job.update({"progress": 94, "stage": "Empaquetando GLB"})
            mesh.export(str(output))

        if ledger is not None:
            ledger.record_stage("paint_pbr", "passed" if request.texture else "admitted", {
                "artifact": seal_artifact(output),
                "backend": (texture_report or {}).get("backend", "geometry_only"),
            })
        if request.texture:
            transition_ledger(job_id, "STAGE_PASSED", "paint_finished")

        metadata_report = {"embedded": False}
        try:
            metadata_report = embed_strategy_metadata(
                output,
                asset_plan["semantic_contract"],
                preservation_gate,
            )
        except Exception as metadata_error:
            metadata_report = {
                "embedded": False,
                "error": str(metadata_error),
            }
        mark_milestone("paint_pbr_and_glb_complete")

        # Promotion binds to a job-local immutable candidate, never to the
        # convenient flat delivery output that a later tool could replace.
        review_candidate = None
        if ledger is not None:
            candidate_dir = ledger.job_dir / "delivery-candidate"
            candidate_dir.mkdir(exist_ok=True)
            candidate_path = candidate_dir / "asset.glb"
            if candidate_path.exists():
                raise RuntimeError("El candidato de revisión ya existe para este job.")
            shutil.copy2(output, candidate_path)
            make_read_only(candidate_path)
            review_candidate = seal_artifact(candidate_path)
            ledger.record_stage("delivery_candidate", "passed", {
                "artifact": review_candidate,
                "source_artifact": seal_artifact(output),
                "promotion": "human_review_required",
            })

        sealed_artifacts = {
            "input": seal_artifact(image_path),
            "prepared_reference": seal_artifact(prepared_path),
            "geometry_checkpoint": seal_artifact(geometry_checkpoint),
            "master": seal_artifact(master_output) if master_output else None,
            "delivery_glb": seal_artifact(output),
        }
        if review_candidate is not None:
            sealed_artifacts["review_candidate"] = review_candidate

        faces = len(getattr(mesh, "faces", []))
        elapsed = round(time.monotonic() - started, 1)
        material_contract_report = (texture_report or {}).get("material_contract") or {}
        buffalo_report = build_strategy_report(
            asset_plan["semantic_contract"],
            apple_execution,
            preservation_gate,
            material_report=material_contract_report,
            input_analysis=input_analysis,
            sealed_artifacts=sealed_artifacts,
            milestones=milestones,
        )
        buffalo_report["glb_metadata"] = metadata_report
        buffalo_manifest_path = save_report(f"{job_id}-buffalo", buffalo_report)
        buffalo_report["manifest_path"] = buffalo_manifest_path
        material_premium_ready = (
            not request.texture or material_contract_report.get("premium_ready") is True
        )
        delivery_level = quality["level"]
        delivery_reasons = list(quality["reasons"])
        if texture_report and texture_report.get("degraded"):
            if delivery_level == "listo":
                delivery_level = "atencion"
            executed_backend = texture_report.get("backend", "geometry-checkpoint")
            delivery_reasons.append(
                f"Recuperación automática de textura: entrega {executed_backend}."
            )
        if preservation_gate.get("fallback_to_accepted_master"):
            if delivery_level == "listo":
                delivery_level = "atencion"
            delivery_reasons.append(
                "Buffalo-MLX descartó la simplificación porque perdía estructura; "
                "se conservó la malla maestra aceptada."
            )
        if (
            delivery_level == "listo"
            and asset_plan["quality_tier"] in {"premium", "master"}
            and not material_premium_ready
        ):
            delivery_level = "atencion"
            missing = material_contract_report.get("missing_recommended_maps") or []
            if missing:
                delivery_reasons.append(
                    "Faltan mapas premium: " + ", ".join(missing) + "."
                )
            if not material_contract_report.get("material_regions_ready", True):
                delivery_reasons.append(
                    "El activo necesita regiones de material separadas para nivel premium."
                )
        if asset_plan["quality_tier"] == "master" and not buffalo_report["master_promotion_passed"]:
            if delivery_level == "listo":
                delivery_level = "atencion"
            delivery_reasons.append(
                "Nivel maestro pendiente: el inventario semántico requiere evidencia humana o multivista."
            )
        report = {
            "job_id": job_id,
            "kind": "image3d",
            "created_at": time.time(),
            "elapsed": elapsed,
            "input": {
                "steps": request.steps,
                "octree_resolution": request.octree_resolution,
                "texture": request.texture,
                "texture_resolution": request.texture_resolution,
                "paint_backend": request.paint_backend,
                "paint_backend_selected": asset_plan["paint_backend"],
                "target_faces": request.target_faces,
                "scale_meters": request.scale_meters,
                "profile": request.profile,
                "category": request.category,
                "material_hint": request.material_hint,
                "guidance": request.guidance,
                "background_mode": request.background_mode,
                "subject_padding": request.subject_padding,
                "execution_plan": execution_plan,
            },
            "metrics": {
                "faces_before": faces_before,
                "raw_faces": raw_faces,
                "faces": faces,
                "vertices": len(getattr(mesh, "vertices", [])),
                "pre_decimation_quality": pre_decimation_quality,
                **quality,
            },
            "texture": {
                "requested": request.texture,
                "applied": bool(texture_report and texture_report.get("passed")),
                "report": texture_report,
                "shape_glb_path": str(shape_output) if shape_output else None,
                "master_glb_path": str(master_output) if master_output else None,
            },
            "art_director": asset_plan,
            "buffalo_strategy": buffalo_report,
            "delivery": {
                "level": delivery_level,
                "material_premium_ready": material_premium_ready,
                "reasons": delivery_reasons,
            },
        }
        report_path = save_report(job_id, report)
        transition_ledger(job_id, "DELIVERY_CANDIDATE", "delivery_gated", {
            "delivery_level": delivery_level,
            "report": Path(report_path).name,
        })
        # Automated success is never MASTER. Keep the durable waiting state so
        # the only permitted promotion path is a named human decision.
        transition_ledger(job_id, "HUMAN_REVIEW_REQUIRED", "human_review_required")
        job.update(
            {
                "status": "done",
                "progress": 100,
                "stage": "Completado; requiere revisión humana para MASTER",
                "glb_path": str(output),
                "faces": faces,
                "faces_before": faces_before,
                "raw_faces": raw_faces,
                "elapsed": elapsed,
                "texture_requested": request.texture,
                "texture_applied": bool(texture_report and texture_report.get("passed")),
                "texture_report": texture_report,
                "shape_glb_path": str(shape_output) if shape_output else None,
                "profile": request.profile,
                "category": request.category,
                "material": asset_plan["material"],
                "art_director": asset_plan,
                "buffalo_strategy": buffalo_report,
                "background_mode": request.background_mode,
                "report_path": report_path,
                "quality_score": quality["score"],
                "quality_level": delivery_level,
                "quality_text": " ".join(delivery_reasons) if delivery_reasons else "Validado correctamente.",
                "runtime": m5_optimizer.snapshot() if m5_optimizer is not None else {},
                "execution_plan": execution_plan,
                "master_glb_path": str(master_output) if master_output else None,
            }
        )
    except Exception as exc:
        transition_ledger(job_id, "STAGE_REJECTED", "stage_exception", {"error": str(exc)})
        if not recover_from_geometry_checkpoint(job_id, job, exc, started, asset_plan):
            elapsed = round(time.monotonic() - started, 1)
            failure_report = {
                "job_id": job_id,
                "kind": "image3d_failure",
                "created_at": time.time(),
                "elapsed": elapsed,
                "error": str(exc),
                "input": {
                    "category": request.category,
                    "profile": request.profile,
                    "steps": request.steps,
                    "octree_resolution": request.octree_resolution,
                    "target_faces": request.target_faces,
                    "texture": request.texture,
                },
                "geometry": last_quality,
                "rejected_artifact": seal_artifact(rejected_artifact) if rejected_artifact else None,
                "art_director": asset_plan,
                "milestones_seconds": milestones,
                "runtime": m5_optimizer.snapshot() if m5_optimizer is not None else {},
            }
            report_path = save_report(f"{job_id}-failure", failure_report)
            job.update({
                "status": "error",
                "error": str(exc),
                "elapsed": elapsed,
                "report_path": report_path,
                "quality_level": "critico",
                "quality_text": str(exc),
                "geometry_quality": last_quality,
                "rejected_artifact": str(rejected_artifact) if rejected_artifact else None,
            })
            transition_ledger(job_id, "ERROR", "job_failed", {"error": str(exc)})
    finally:
        if pipeline is not None:
            release_shape_pipeline(pipeline)
            pipeline = None
            settle_shape_memory()
        elif pipeline_future is not None:
            pipeline_future.add_done_callback(release_preloaded_pipeline)
        cleanup_job(job_id)
        generation_lock.release()


@app.get("/health")
def health():
    # Shape is intentionally lazy-loaded, so an unloaded pipeline is healthy.
    # A prior load failure is not: callers can then surface a recovery action
    # instead of treating the engine as silently ready.
    if not SOURCE.exists():
        health_status = "unavailable"
        degraded_reasons = ["shape_runtime_missing"]
    elif load_error:
        health_status = "degraded"
        degraded_reasons = ["shape_pipeline_load_failed"]
    else:
        health_status = "ready"
        degraded_reasons = []
    return {
        "ready": health_status == "ready",
        "status": health_status,
        "degraded_reasons": degraded_reasons,
        "engine_version": ENGINE_VERSION,
        "model_loaded": shape_pipeline is not None,
        "error": load_error,
        "runtime": m5_optimizer.snapshot() if m5_optimizer is not None else {},
        "strategy": {
            "version": STRATEGY_VERSION,
            "name": "Buffalo Strategic MLX",
            "official_buffalo_backend": False,
        },
        "openusd": {
            "formats": ["usdz"],
            "usdzip": Path("/usr/bin/usdzip").is_file() or shutil.which("usdzip") is not None,
            "usdchecker": Path("/usr/bin/usdchecker").is_file() or shutil.which("usdchecker") is not None,
            "gate": "usdchecker --arkit --strict",
        },
    }


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    if not SOURCE.exists():
        raise HTTPException(503, "Motor no instalado. Ejecuta la instalación desde Xreality Convert.")
    try:
        image = Image.open(io.BytesIO(decode_image_base64(request.image_base64)))
    except Exception as exc:
        raise HTTPException(400, f"No se pudo leer la imagen: {exc}") from exc
    return analyze_image(image, request.category, request.background_mode)


@app.post("/multiview/admit")
def admit_multiview(request: MultiViewAdmissionRequest):
    """Validate six camera records before a future multi-view Shape stage."""
    try:
        return {"ok": True, "admission": admit_multiview_shape(request.views, profile=request.profile)}
    except MultiViewContractError as exc:
        return {"ok": False, "error": str(exc), "promotion": "blocked"}


@app.get("/multiview/status")
def multiview_status():
    """Advertise only a backend that can actually consume labelled cameras."""
    return inspect_multiview_shape_backend(SOURCE)


@app.post("/generate")
async def generate(request: GenerateRequest):
    if not SOURCE.exists():
        raise HTTPException(503, "Motor no instalado. Ejecuta la instalación desde Xreality Convert.")
    try:
        ensure_generation_disk_space(request)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    job_id = uuid.uuid4().hex
    job_ledgers[job_id] = JobLedger(JOBS_DIR, job_id)
    jobs[job_id] = {"status": "queued", "cancel_requested": False, "progress": 0, "stage": "En cola"}
    asyncio.create_task(asyncio.to_thread(run_job, job_id, request))
    return {"job_id": job_id, "control_plane": ledger_summary(job_id)}


@app.post("/retry/{source_job_id}")
async def retry_interrupted_job(source_job_id: str):
    """Create a new lineage-linked attempt; source history remains immutable."""
    try:
        request = build_explicit_retry_request(source_job_id)
    except (ContractError, OSError, ValueError) as exc:
        raise HTTPException(409, f"Reintento no disponible: {exc}") from exc
    try:
        ensure_generation_disk_space(request)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    job_id = uuid.uuid4().hex
    job_ledgers[job_id] = JobLedger(JOBS_DIR, job_id)
    jobs[job_id] = {
        "status": "queued", "cancel_requested": False, "progress": 0,
        "stage": "Reintento en cola", "retry_of": source_job_id,
    }
    asyncio.create_task(asyncio.to_thread(run_job, job_id, request))
    return {"job_id": job_id, "retry_of": source_job_id, "control_plane": ledger_summary(job_id)}


@app.post("/cancel/{job_id}")
def cancel(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado.")
    mark_cancelled(job_id)
    transition_ledger(job_id, "CANCELLED", "user_cancelled")
    return {"ok": True, "status": job.get("status")}


@app.get("/status/{job_id}")
def status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        return {"status": "unknown"}
    return {**job, "control_plane": ledger_summary(job_id)}


@app.post("/to-stl")
def to_stl(request: StlRequest):
    try:
        import trimesh

        source = managed_glb_path(request.glb_path)
        mesh = trimesh.load(source, force="mesh")
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


@app.post("/to-openusd")
def to_openusd(request: OpenUsdRequest):
    """Export a generated GLB as a validated Apple RealityKit USDZ package."""
    try:
        source = managed_glb_path(request.glb_path)
        return convert_glb_to_usdz(source, JOBS_DIR / "openusd")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/certify-runtime")
def certify_runtime(request: RuntimeCertificationRequest):
    """Certify local GLB structure/budgets, never an unmeasured viewer run."""
    try:
        certificate = certify_glb_for_target(managed_glb_path(request.glb_path), request.target)
        return {"ok": True, "certificate": certificate}
    except (RuntimeCertificationError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/edit/replace-material")
def edit_replace_material(request: ReplaceMaterialEditRequest):
    """Apply the first bounded Buffalo delta without mutating the master."""
    try:
        source = managed_glb_path(request.source_glb_path)
        output = JOBS_DIR / f"{source.stem}-material-edit-{uuid.uuid4().hex}.glb"
        result = execute_replace_material(source, output, request.delta)
        return {"ok": True, "edit": result}
    except (EditExecutionError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/derivatives/manifest")
def seal_derivative(request: DerivativeManifestRequest):
    """Seal lineage only after a target-specific certificate is supplied."""
    try:
        manifest = build_derivative_manifest(
            master_path=managed_glb_path(request.master_glb_path),
            output_path=managed_job_path(request.output_path),
            target=request.target,
            topology_changed=request.topology_changed,
            target_certificate=request.target_certificate,
            rebake_evidence=request.rebake_evidence,
        )
        destination = JOBS_DIR / "derivatives" / f"{uuid.uuid4().hex}.json"
        atomic_write_json(destination, manifest)
        return {"ok": True, "manifest_path": str(destination), "manifest": manifest}
    except (DerivativeLineageError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/validate-blender")
def validate_blender_canonically(request: BlenderValidationRequest):
    """Create offline canonical render evidence; never self-promote a master."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        result = BlenderCanonicalValidationService().run(
            job_dir=ledger.job_dir,
            glb_path=request.glb_path,
            projection_report_path=request.projection_report_path,
            output_dir=request.output_dir,
        )
        ledger.record_stage("blender_canonical", "passed", {
            "report_path": result["render_report_path"],
            "promotion": "human_review_required",
        })
        job_ledgers[request.job_id] = ledger
        return {"ok": True, "validation": result}
    except (BlenderValidationError, ContractError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "promotion": "blocked"}


@app.post("/stage-validation-artifacts")
def stage_validation_artifacts(request: ValidationArtifactStageRequest):
    """Seal managed GLB/projection inputs before an independent DCC worker reads them."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        glb = managed_glb_path(request.glb_path)
        projection = managed_job_path(request.projection_report_path)
        if projection.suffix.lower() != ".json":
            raise RuntimeError("El reporte de proyección debe ser JSON.")
        destination = ledger.job_dir / "validation-inputs"
        if destination.exists():
            raise RuntimeError("Los inputs de validación ya fueron sellados para este job.")
        destination.mkdir(parents=True)
        sealed_glb = destination / "asset.glb"
        sealed_projection = destination / "projection-report.json"
        shutil.copy2(glb, sealed_glb)
        shutil.copy2(projection, sealed_projection)
        validate_glb_container(sealed_glb)
        json.loads(sealed_projection.read_text(encoding="utf-8"))
        make_read_only(sealed_glb)
        make_read_only(sealed_projection)
        ledger.record_stage("validation_inputs", "passed", {
            "glb": seal_artifact(sealed_glb),
            "projection_report": seal_artifact(sealed_projection),
        })
        return {
            "ok": True,
            "job_id": request.job_id,
            "glb_path": str(sealed_glb),
            "projection_report_path": str(sealed_projection),
        }
    except (ContractError, RuntimeError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/repair-blender")
def repair_with_blender(request: BlenderRepairRequest):
    """Run exactly one bounded repair/retopo/UV operation in isolated Blender."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        result = BlenderRepairService().run(
            job_dir=ledger.job_dir,
            source_glb_path=request.source_glb_path,
            output_glb_path=request.output_glb_path,
            operation_contract=request.operation_contract,
        )
        ledger.record_stage("blender_repair", "passed", {
            "operation": result["operation"],
            "output": result["output"],
            "report_path": result["report_path"],
            "promotion": "human_review_required",
        })
        return {"ok": True, "repair": result}
    except (BlenderRepairError, ContractError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "promotion": "blocked"}


@app.post("/derive-lod")
def derive_lod(request: LODDerivationRequest):
    """Create an actual local geometry LOD; PBR rebake remains mandatory."""
    try:
        master = managed_glb_path(request.master_glb_path)
        name = Path(request.output_name)
        if name.name != request.output_name or name.suffix.lower() != ".glb":
            raise RuntimeError("El nombre de salida LOD debe ser un archivo GLB simple.")
        output = JOBS_DIR / "derivatives" / name
        output.parent.mkdir(parents=True, exist_ok=True)
        report = derive_glb_lod(master, output, target_faces=request.target_faces)
        return {"ok": True, "lod": report, "rebake_required": True}
    except (LODDerivationError, RuntimeError) as exc:
        return {"ok": False, "error": str(exc), "rebake_required": True}


@app.post("/audit-regional-pbr")
def audit_pbr_regions(request: RegionalPBRAuditRequest):
    """Seal a regional PBR audit; unknown visual lanes remain not measured."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        graph_path = ledger.job_dir / "semantic-graph.json"
        if not graph_path.is_file():
            raise RuntimeError("El grafo semántico sellado no existe.")
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        report = audit_regional_pbr(managed_glb_path(request.glb_path), graph, request.regional_map_contract)
        report_path = ledger.job_dir / "regional-pbr-report.json"
        if report_path.exists():
            raise RuntimeError("La auditoría PBR regional ya fue sellada para este job.")
        atomic_write_json(report_path, report)
        make_read_only(report_path)
        ledger.record_stage("regional_pbr", "passed" if report.get("passed") else "rejected", {
            "report_path": str(report_path), "failures": report.get("failures", []),
        })
        return {"ok": bool(report.get("passed")), "report_path": str(report_path), "audit": report}
    except (ContractError, RuntimeError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/audit-pbr-textures")
def audit_pbr_texture_maps(request: RegionalPBRAuditRequest):
    """Measure embedded PBR-map integrity without claiming visual realism."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        graph_path = ledger.job_dir / "semantic-graph.json"
        if not graph_path.is_file():
            raise RuntimeError("El grafo semántico sellado no existe.")
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        report = audit_pbr_texture_quality(
            managed_glb_path(request.glb_path), graph, request.regional_map_contract,
        )
        report_path = ledger.job_dir / "pbr-texture-quality-report.json"
        if report_path.exists():
            raise RuntimeError("La auditoría de mapas PBR ya fue sellada para este job.")
        atomic_write_json(report_path, report)
        make_read_only(report_path)
        ledger.record_stage("pbr_texture_quality", "passed" if report.get("passed") else "rejected", {
            "report_path": str(report_path),
            "failures": report.get("failures", []),
            "not_measured": report.get("evidence_scope", {}),
        })
        return {"ok": bool(report.get("passed")), "report_path": str(report_path), "audit": report}
    except (ContractError, RuntimeError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/audit-geometry")
def audit_geometry(request: GeometryQualityRequest):
    """Seal local structural geometry evidence; unmeasured lanes remain so."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        report = audit_geometry_quality(managed_glb_path(request.glb_path), policy=request.policy)
        report_path = ledger.job_dir / "geometry-quality-report.json"
        if report_path.exists():
            raise RuntimeError("La auditoría geométrica ya fue sellada para este job.")
        atomic_write_json(report_path, report)
        make_read_only(report_path)
        ledger.record_stage("geometry_quality", "passed" if report.get("passed") else "rejected", {
            "report_path": str(report_path), "failures": report.get("failures", []),
            "not_measured": report.get("not_measured", {}),
        })
        return {"ok": bool(report.get("passed")), "report_path": str(report_path), "audit": report}
    except (GeometryQualityError, ContractError, RuntimeError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/validate-gltf")
def validate_gltf(request: GlTFValidatorRequest):
    """Run Khronos CLI only when installed; absent tooling stays unmeasured."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        result = GlTFValidatorGate().run(
            job_dir=ledger.job_dir,
            glb_path=managed_glb_path(request.glb_path),
        )
        if result.get("status") == "not_measured":
            return {"ok": False, "validator": result}
        ledger.record_stage("gltf_validator", "passed" if result.get("passed") else "rejected", result)
        return {"ok": bool(result.get("passed")), "validator": result}
    except (GlTFValidatorGateError, ContractError, RuntimeError, OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


@app.post("/cloud/consent")
def create_cloud_consent(request: CloudConsentRequest):
    """Seal opt-in cloud authority without performing network I/O.

    SDD H-08: the default provider allow-list is empty, so an unconfigured
    installation rejects this request.  The asset must belong to the exact
    sealed job -- another job's managed output cannot be reused as consent
    input.
    """
    try:
        ledger = sealed_job_ledger(request.job_id)
        asset = managed_job_path(request.asset_path)
        if not asset.is_relative_to(ledger.job_dir):
            raise RuntimeError("El asset cloud debe pertenecer al job sellado.")
        artifact = seal_artifact(asset)
        consent = create_consent(
            job_dir=ledger.job_dir,
            asset_sha256=artifact["sha256"],
            provider=request.provider,
            operation=request.operation,
            max_cost_micros=request.max_cost_micros,
            currency=request.currency,
            expires_at=request.expires_at,
            allowed_providers=CLOUD_ALLOWED_PROVIDERS,
        )
        return {
            "ok": True,
            "network_started": False,
            "provider_adapter": "not_installed",
            "asset": artifact,
            "consent": consent,
        }
    except (CloudConsentError, ContractError, RuntimeError, OSError) as exc:
        return {"ok": False, "network_started": False, "error": str(exc)}


@app.post("/cloud/kill-switch")
def disable_cloud_for_job(request: CloudKillSwitchRequest):
    """Irreversibly deny future cloud reservations for one sealed job."""
    try:
        ledger = sealed_job_ledger(request.job_id)
        record = engage_kill_switch(job_dir=ledger.job_dir, reason=request.reason)
        return {"ok": True, "network_started": False, "kill_switch": record}
    except (CloudConsentError, ContractError, RuntimeError, OSError) as exc:
        return {"ok": False, "network_started": False, "error": str(exc)}


@app.post("/review/master")
def decide_master_promotion(request: MasterPromotionRequest):
    """Apply the sole explicit, named-human path from candidate to MASTER."""
    try:
        if not MASTER_REVIEW_POLICY_PATH or not MASTER_REVIEWER_REGISTRY_PATH:
            raise RuntimeError("La política y el registro de revisores MASTER no están configurados.")
        ledger = sealed_job_ledger(request.job_id)
        if ledger.state != "HUMAN_REVIEW_REQUIRED":
            raise RuntimeError("El job no está esperando una decisión humana MASTER.")
        asset = managed_glb_path(request.asset_path)
        if not asset.is_relative_to(ledger.job_dir):
            raise RuntimeError("El asset revisado debe ser el candidato sellado del job.")
        record = seal_master_promotion(
            job_dir=ledger.job_dir,
            asset_path=asset,
            reviewer_id=request.reviewer_id,
            decision=request.decision,
            policy_path=MASTER_REVIEW_POLICY_PATH,
            reviewer_registry_path=MASTER_REVIEWER_REGISTRY_PATH,
            note=request.note,
        )
        target = "MASTER" if record["promotion"] == "MASTER" else "NON_MASTER"
        ledger.transition(target, "named_human_review", {
            "promotion_record": record["record_id"],
            "reviewer_id": request.reviewer_id,
            "decision": request.decision,
        })
        return {"ok": True, "promotion": target, "record": record}
    except (MasterPromotionError, ContractError, RuntimeError, OSError) as exc:
        return {"ok": False, "promotion": "blocked", "error": str(exc)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
