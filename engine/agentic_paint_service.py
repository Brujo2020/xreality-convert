"""Isolated AgenticVibes quality-paint service for Apple Silicon."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from huggingface_hub import snapshot_download
from huggingface_hub.constants import HUGGINGFACE_HUB_CACHE

from pbr_glb import validate_pbr_glb


AGENTIC_MODEL = "AgenticVibes/hunyuan3d-2.1-mlx"
AGENTIC_REVISION = "06ff58f0778649cbfc18f393925373782c6a705b"
TENCENT_MODEL = "tencent/Hunyuan3D-2.1"
TENCENT_REVISION = "0b94677654c57bb9a6b6845cd7b704ccf551d327"
DINO_MODEL = "facebook/dinov2-giant"
DINO_REVISION = "611a9d42f2335e0f921f1e313ad3c1b7178d206d"


def _command_number(command, pattern):
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=5, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(pattern, completed.stdout + completed.stderr)
    return float(match.group(1)) if match else None


def memory_snapshot():
    total_bytes = _command_number(["sysctl", "-n", "hw.memsize"], r"(\d+)")
    free_percent = _command_number(
        ["memory_pressure", "-Q"], r"free percentage:\s*([0-9.]+)%"
    )
    swap_used_mb = _command_number(
        ["sysctl", "vm.swapusage"], r"used\s*=\s*([0-9.]+)M"
    )
    swap_free_mb = _command_number(
        ["sysctl", "vm.swapusage"], r"free\s*=\s*([0-9.]+)M"
    )
    return {
        "physical_gb": round(total_bytes / 2**30, 2) if total_bytes is not None else None,
        "free_percent": free_percent,
        "swap_used_mb": swap_used_mb,
        "swap_free_mb": swap_free_mb,
    }


def admit_agentic(snapshot=None):
    snapshot = snapshot or memory_snapshot()
    reasons = []
    if snapshot["physical_gb"] is not None and snapshot["physical_gb"] < 23.5:
        reasons.append("physical_memory_below_24gb")
    if snapshot["free_percent"] is not None and snapshot["free_percent"] < 35:
        reasons.append("memory_pressure_too_high")
    # macOS allocates swap files dynamically, so vm.swapusage "free" is not a
    # fixed capacity limit and can be below 2 GiB on an otherwise healthy Mac.
    # Admission is based on real memory pressure; the running watchdog below
    # limits swap *growth* caused by this job.
    return {"passed": not reasons, "reasons": reasons, "snapshot": snapshot}


def _cached_revision_path(repo_id, revision):
    repo_cache = f"models--{repo_id.replace('/', '--')}"
    return Path(HUGGINGFACE_HUB_CACHE) / repo_cache / "snapshots" / revision


def _has_required_files(path, required_files):
    path = Path(path)
    return path.is_dir() and all((path / relative).is_file() for relative in required_files)


def _snapshot(repo_id, revision, *, allow_patterns=None, required_files=()):
    kwargs = {
        "repo_id": repo_id,
        "revision": revision,
        "allow_patterns": allow_patterns,
    }
    try:
        local = Path(snapshot_download(**kwargs, local_files_only=True))
        if not required_files or _has_required_files(local, required_files):
            return local
    except Exception:
        # huggingface_hub may reject a usable snapshot when an administrative
        # file such as .gitattributes is absent. The runtime only admits a
        # direct cache path after every inference-critical file is present.
        local = _cached_revision_path(repo_id, revision)
        if required_files and _has_required_files(local, required_files):
            return local

    # Inference never repairs a cache over the network. Model installation is
    # a separate, explicitly consented operation; allowing a hot path to fetch
    # weights would violate the job's local-first privacy and cost contract.
    raise RuntimeError(
        f"Snapshot local incompleto para {repo_id}@{revision}; "
        "instala y verifica los pesos antes de ejecutar el job."
    )


class AgenticPaintService:
    def __init__(self, engine_dir=None):
        self.engine_dir = Path(engine_dir or Path(__file__).resolve().parent)
        self.app_root = self.engine_dir.parent
        installed_runner = self.engine_dir / "agentic_paint_runner.py"
        development_runner = (
            self.app_root / "benchmarks" / "model-arena" / "run_agenticvibes_paint.py"
        )
        self.runner = (
            installed_runner if installed_runner.exists() else development_runner
        )

    def _models(self):
        mlx_weights = _snapshot(
            AGENTIC_MODEL,
            AGENTIC_REVISION,
            required_files=("unet.npz", "vae.npz"),
        )
        tencent = _snapshot(
            TENCENT_MODEL,
            TENCENT_REVISION,
            allow_patterns=["hunyuan3d-paintpbr-v2-1/**"],
        )
        dino = _snapshot(DINO_MODEL, DINO_REVISION)
        return {
            "mlx": mlx_weights,
            "paint": tencent / "hunyuan3d-paintpbr-v2-1",
            "dino": dino,
        }

    def run(
        self,
        *,
        mesh_path,
        image_path,
        output_glb_path,
        steps=4,
        texture_size=1024,
        seed=42,
    ):
        admission = admit_agentic()
        if not admission["passed"]:
            raise RuntimeError(
                "AgenticVibes no admitido para proteger la memoria unificada: "
                + ", ".join(admission["reasons"])
            )
        models = self._models()
        output_glb_path = Path(output_glb_path).resolve()
        work_dir = output_glb_path.with_name(f"{output_glb_path.stem}-agentic")
        command = [
            sys.executable,
            str(self.runner),
            "--mesh",
            str(Path(mesh_path).resolve()),
            "--image",
            str(Path(image_path).resolve()),
            "--output-dir",
            str(work_dir),
            "--paint-model",
            str(models["paint"]),
            "--dino-model",
            str(models["dino"]),
            "--mlx-weights",
            str(models["mlx"]),
            "--steps",
            str(steps),
            "--texture-size",
            str(texture_size),
            "--reference-lock",
        ]
        environment = os.environ.copy()
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        swap_growth_limit_mb = float(
            os.environ.get("XREALITY_MAX_AGENTIC_SWAP_GROWTH_MB", "2048")
        )
        process = subprocess.Popen(
            command,
            cwd=self.app_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started = time.monotonic()
        baseline_swap = admission["snapshot"].get("swap_used_mb")
        min_free_percent = admission["snapshot"].get("free_percent")
        stdout = ""
        stderr = ""
        while True:
            try:
                stdout, stderr = process.communicate(timeout=2)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() - started > 1800:
                    process.terminate()
                    stdout, stderr = process.communicate(timeout=15)
                    raise RuntimeError("AgenticVibes excedió el límite de 30 minutos")
                current = memory_snapshot()
                free_percent = current.get("free_percent")
                if free_percent is not None:
                    min_free_percent = (
                        free_percent
                        if min_free_percent is None
                        else min(min_free_percent, free_percent)
                    )
                swap_used = current.get("swap_used_mb")
                unsafe_pressure = free_percent is not None and free_percent < 8
                unsafe_swap = (
                    baseline_swap is not None
                    and swap_used is not None
                    and swap_used - baseline_swap > swap_growth_limit_mb
                )
                if unsafe_pressure or unsafe_swap:
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                    reason = "memory_pressure_below_8_percent" if unsafe_pressure else "swap_growth_limit_exceeded"
                    raise RuntimeError(
                        f"AgenticVibes abortado por watchdog: {reason}"
                    )
        if process.returncode:
            diagnostic = (stdout + "\n" + stderr)[-5000:]
            raise RuntimeError(f"AgenticVibes Paint falló:\n{diagnostic}")
        report_path = work_dir / "run-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        reference_lock = report.get("referenceLock") or {}
        gate = reference_lock.get("gate") or {}
        if not gate.get("passed"):
            reasons = ", ".join(gate.get("reasons") or ["reference_lock_failed"])
            raise RuntimeError(f"AgenticVibes rechazado por fidelidad: {reasons}")
        locked_glb = Path(reference_lock["outputGlb"])
        structural = validate_pbr_glb(locked_glb)
        if not structural.get("passed"):
            reasons = ", ".join(structural.get("reasons") or ["pbr_gate_failed"])
            raise RuntimeError(f"AgenticVibes rechazado por PBR: {reasons}")
        output_glb_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(locked_glb, output_glb_path)
        return {
            "passed": True,
            "backend": "agenticvibes-mlx-quality",
            "visual_fidelity": reference_lock,
            "structural_gate": structural,
            "arena": report,
            "report_path": str(report_path),
            "memory_admission": admission,
            "memory_watchdog": {
                "minimum_free_percent": min_free_percent,
                "maximum_swap_growth_mb": swap_growth_limit_mb,
            },
        }
