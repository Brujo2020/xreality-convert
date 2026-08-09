"""Small, deterministic control-plane primitives for Buffalo MLX jobs.

This module intentionally has no MLX, Blender, network, or provider dependency.
It owns durable state and content-addressed evidence so the inference backends
cannot promote their own output or silently rewrite job history.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, UnidentifiedImageError


SCHEMA_VERSION = 3
MAX_INPUT_BYTES = 24 * 1024 * 1024
MAX_IMAGE_PIXELS = 36_000_000
EVIDENCE_CLASSES = {"measured", "user_asserted", "inferred", "synthetic", "not_measured"}
TERMINAL_STATES = {"REJECTED", "BLOCKED", "CANCELLED", "ERROR", "NON_MASTER", "MASTER"}
ALLOWED_TRANSITIONS = {
    "DRAFT": {"SEALED", "REJECTED", "CANCELLED"},
    "SEALED": {"PREFLIGHTED", "REJECTED", "CANCELLED"},
    "PREFLIGHTED": {"RUNNING_STAGE", "BLOCKED", "CANCELLED", "REJECTED"},
    "RUNNING_STAGE": {"STAGE_PASSED", "STAGE_REJECTED", "ERROR", "CANCELLED"},
    "STAGE_PASSED": {"RUNNING_STAGE", "DELIVERY_CANDIDATE", "CANCELLED"},
    "STAGE_REJECTED": {"RECOVERY_DECISION", "REJECTED", "CANCELLED"},
    "RECOVERY_DECISION": {"RUNNING_STAGE", "NON_MASTER", "REJECTED", "CANCELLED"},
    "DELIVERY_CANDIDATE": {"HUMAN_REVIEW_REQUIRED", "NON_MASTER", "REJECTED"},
    "HUMAN_REVIEW_REQUIRED": {"MASTER", "NON_MASTER", "REJECTED"},
}


class ContractError(ValueError):
    """Raised when a durable control-plane contract is unsafe or inconsistent."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_descriptor(path: str | Path) -> dict[str, Any]:
    artifact = Path(path)
    if not artifact.is_file():
        raise ContractError(f"artifact_missing:{artifact}")
    return {
        "path": artifact.name,
        "bytes": artifact.stat().st_size,
        "sha256": f"sha256:{sha256_file(artifact)}",
    }


def safe_job_path(job_root: str | Path, relative: str | Path) -> Path:
    root = Path(job_root).resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ContractError(f"unsafe_job_path:{relative}")
    return candidate


def decode_base64_image(value: str) -> bytes:
    if not isinstance(value, str):
        raise ContractError("image_base64_required")
    # Base64 has at most 4/3 expansion. Check before decoding to avoid a large
    # allocation from an untrusted HTTP body.
    if len(value) > ((MAX_INPUT_BYTES + 2) // 3) * 4:
        raise ContractError("image_payload_too_large")
    try:
        payload = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ContractError("invalid_image_base64") from exc
    if not payload or len(payload) > MAX_INPUT_BYTES:
        raise ContractError("image_payload_too_large")
    validate_image_bytes(payload)
    return payload


def validate_image_bytes(payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) > MAX_INPUT_BYTES:
        raise ContractError("image_payload_too_large")
    prior_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(__import__("io").BytesIO(payload)) as image:
            image.verify()
        with Image.open(__import__("io").BytesIO(payload)) as image:
            width, height = image.size
            if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                raise ContractError("image_dimensions_unsafe")
            return {"format": image.format, "width": width, "height": height, "bytes": len(payload)}
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ContractError("invalid_or_unsafe_image") from exc
    finally:
        Image.MAX_IMAGE_PIXELS = prior_limit


def atomic_write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.replace(destination)


def make_read_only(path: str | Path) -> None:
    """Seal an accepted local artifact against accidental worker mutation."""
    artifact = Path(path)
    if not artifact.is_file():
        raise ContractError(f"artifact_missing:{artifact}")
    artifact.chmod(0o400)


def build_evidence_manifest(input_path: str | Path, image_info: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = artifact_descriptor(input_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "observations": [{
            "observation_id": "input-0001",
            "source_asset_hash": descriptor["sha256"],
            "kind": "reference_image",
            "camera": {"status": "not_measured"},
            "visibility": {"status": "measured", "coverage": "front_only"},
            "region": "full_frame",
            "value": dict(image_info),
            "confidence": 1.0,
            "evidence_class": "measured",
            "producer": "user_input",
            "license": "user_supplied",
            "privacy_class": "local_default",
            "created_at": time.time(),
        }],
        "input": descriptor,
    }


def build_job_contract(
    *,
    job_id: str,
    request: Mapping[str, Any],
    evidence_manifest: Mapping[str, Any],
    semantic_contract: Mapping[str, Any],
    execution_policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not job_id:
        raise ContractError("job_id_required")
    evidence_hash = f"sha256:{sha256_bytes(canonical_json(evidence_manifest))}"
    semantic_hash = f"sha256:{sha256_bytes(canonical_json(semantic_contract))}"
    policy_hash = f"sha256:{sha256_bytes(canonical_json(execution_policy))}"
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id,
        "created_at": time.time(),
        "intent": {
            "quality": request.get("profile", "xreal"),
            "targets": ["glb"],
            "face_budget": int(request.get("target_faces", 0)),
            "texture_budget": int(request.get("texture_resolution", 0)),
            "deadline_seconds": int(execution_policy.get("deadline_seconds", 1800)),
        },
        "evidence_manifest_hash": evidence_hash,
        "semantic_contract_hash": semantic_hash,
        "material_contract_hash": f"sha256:{sha256_bytes(canonical_json(execution_policy.get('material_contract', {})))}",
        "execution_policy_hash": policy_hash,
        "network": {"allowed": False, "consent_id": None},
        "economy": {"currency": "USD", "maximum": 0, "auto_refill": False},
    }


class JobLedger:
    """Append-only state journal with a compact latest-state snapshot."""

    def __init__(self, root: str | Path, job_id: str):
        if not job_id or any(char not in "0123456789abcdef-" for char in job_id):
            raise ContractError("unsafe_job_id")
        self.root = Path(root).resolve()
        self.job_id = job_id
        self.job_dir = safe_job_path(self.root, job_id)
        self.job_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.job_dir / "journal.jsonl"
        self.snapshot_path = self.job_dir / "state.json"
        self.contract_path = self.job_dir / "job-contract.json"
        self._state = "DRAFT"
        self._version = 0

    @property
    def state(self) -> str:
        return self._state

    @classmethod
    def load(cls, root: str | Path, job_id: str) -> "JobLedger":
        ledger = cls(root, job_id)
        if not ledger.snapshot_path.is_file():
            return ledger
        try:
            snapshot = json.loads(ledger.snapshot_path.read_text(encoding="utf-8"))
            state = snapshot["state"]
            version = int(snapshot["state_version"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ContractError("invalid_job_snapshot") from exc
        if (state not in ALLOWED_TRANSITIONS and state not in TERMINAL_STATES) or version < 0:
            raise ContractError("invalid_job_snapshot")
        ledger._state = state
        ledger._version = version
        return ledger

    def seal(self, contract: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
        if self._state != "DRAFT":
            raise ContractError("job_already_sealed")
        atomic_write_json(self.contract_path, dict(contract))
        atomic_write_json(self.job_dir / "evidence-manifest.json", dict(evidence))
        self.transition("SEALED", "contract_sealed")

    def transition(self, target: str, reason_code: str, metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
        allowed = ALLOWED_TRANSITIONS.get(self._state, set())
        if target not in allowed:
            raise ContractError(f"invalid_transition:{self._state}:{target}")
        self._version += 1
        event = {
            "schema_version": SCHEMA_VERSION,
            "job_id": self.job_id,
            "event_id": self._version,
            "at": time.time(),
            "from": self._state,
            "to": target,
            "reason_code": reason_code,
            "metadata": dict(metadata or {}),
        }
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._state = target
        atomic_write_json(self.snapshot_path, {
            "schema_version": SCHEMA_VERSION,
            "job_id": self.job_id,
            "state": self._state,
            "state_version": self._version,
            "updated_at": event["at"],
            "reason_code": reason_code,
        })
        return event

    def record_stage(self, name: str, status: str, metadata: Mapping[str, Any] | None = None) -> Path:
        if not name or status not in {"admitted", "running", "passed", "rejected", "cancelled"}:
            raise ContractError("invalid_stage_result")
        result = {
            "schema_version": SCHEMA_VERSION,
            "job_id": self.job_id,
            "stage": name,
            "status": status,
            "at": time.time(),
            "metadata": dict(metadata or {}),
        }
        path = safe_job_path(self.job_dir, f"stages/{name}.json")
        atomic_write_json(path, result)
        return path

    def checkpoint_matches(self, stage: str, input_hashes: Mapping[str, str]) -> bool:
        path = safe_job_path(self.job_dir, f"stages/{stage}.json")
        if not path.is_file():
            return False
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if result.get("status") != "passed":
            return False
        expected = (result.get("metadata") or {}).get("input_hashes")
        return isinstance(expected, dict) and dict(expected) == dict(input_hashes)
