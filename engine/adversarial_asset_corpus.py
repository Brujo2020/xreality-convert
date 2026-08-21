"""Deterministic, local adversarial GLB corpus for fail-closed validation.

This is deliberately a *validator* corpus, not an asset generator or a
fuzzing service.  Every byte sequence is constructed locally and has a stable
case id and digest.  A corpus run is successful only when the benign control
asset passes and every required malicious asset is rejected by the existing
container and runtime-certification gates.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, Callable, Iterable

from buffalo_runtime import artifact_descriptor
from runtime_certification import RuntimeCertificationError, certify_glb_for_target
from secure_artifacts import UnsafeAssetError, validate_glb_container


CORPUS_SCHEMA_VERSION = 1
GLB_MAGIC = 0x46546C67
GLB_JSON = 0x4E4F534A
GLB_BIN = 0x004E4942


class AdversarialCorpusError(RuntimeError):
    """Raised if the validation boundary accepts a required hostile asset."""


@dataclass(frozen=True)
class CorpusCase:
    """A small, deterministic local GLB fixture and its expected disposition."""

    case_id: str
    malicious: bool
    required: bool
    expected_reason: str | None
    payload: bytes


ContainerValidator = Callable[[str | Path], dict[str, Any]]
CertificateValidator = Callable[[str | Path, str], dict[str, Any]]


def _pad4(value: bytes, fill: bytes = b"\x00") -> bytes:
    return value + fill * ((4 - len(value) % 4) % 4)


def _pack_glb(document: dict[str, Any], binary: bytes = b"") -> bytes:
    """Build a minimal GLB without any runtime or renderer dependency."""
    encoded = _pad4(json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8"), b" ")
    chunks = struct.pack("<II", len(encoded), GLB_JSON) + encoded
    if binary:
        encoded_binary = _pad4(binary)
        chunks += struct.pack("<II", len(encoded_binary), GLB_BIN) + encoded_binary
    return struct.pack("<III", GLB_MAGIC, 2, 12 + len(chunks)) + chunks


def _triangle_document(*, scenes: bool = True, bad_view: bool = False, bad_node: bool = False) -> tuple[dict[str, Any], bytes]:
    binary = b"\x00" * 36
    document: dict[str, Any] = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 64 if bad_view else len(binary)}],
        "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "nodes": [{"mesh": 7 if bad_node else 0}],
    }
    if scenes:
        document.update({"scenes": [{"nodes": [0]}], "scene": 0})
    return document, binary


def corpus_cases() -> tuple[CorpusCase, ...]:
    """Return stable, ordered fixtures; no input or network is consulted."""
    valid_document, binary = _triangle_document()
    external_document, _ = _triangle_document()
    external_document["images"] = [{"uri": "https://example.invalid/texture.png"}]
    scene_less_document, scene_less_binary = _triangle_document(scenes=False)
    bad_view_document, bad_view_binary = _triangle_document(bad_view=True)
    bad_node_document, bad_node_binary = _triangle_document(bad_node=True)
    malformed_json = struct.pack("<III", GLB_MAGIC, 2, 24) + struct.pack("<II", 4, GLB_JSON) + b"{bad"
    header_mismatch = struct.pack("<III", GLB_MAGIC, 2, 21) + struct.pack("<II", 0, GLB_JSON)
    trailing_byte = _pack_glb(valid_document, binary) + b"\x00"
    return (
        CorpusCase("control-minimal-triangle", False, True, None, _pack_glb(valid_document, binary)),
        CorpusCase("malicious-external-texture-uri", True, True, "external_texture_uri", _pack_glb(external_document, binary)),
        CorpusCase("malicious-invalid-header-length", True, True, "invalid_glb_header", header_mismatch),
        CorpusCase("malicious-invalid-json", True, True, "invalid_glb_json", malformed_json),
        CorpusCase("malicious-trailing-byte", True, True, "invalid_glb_header", trailing_byte),
        CorpusCase("malicious-missing-default-scene", True, True, "missing_scene", _pack_glb(scene_less_document, scene_less_binary)),
        CorpusCase("malicious-buffer-view-out-of-bounds", True, True, "buffer_view_out_of_bounds", _pack_glb(bad_view_document, bad_view_binary)),
        CorpusCase("malicious-invalid-node-reference", True, True, "invalid_node_mesh", _pack_glb(bad_node_document, bad_node_binary)),
    )


def materialize_corpus(root: str | Path, cases: Iterable[CorpusCase] | None = None) -> list[dict[str, Any]]:
    """Write corpus inputs atomically enough for local test use and seal digests."""
    destination = Path(root)
    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for case in cases or corpus_cases():
        path = destination / f"{case.case_id}.glb"
        path.write_bytes(case.payload)
        entry = {
            "case_id": case.case_id,
            "malicious": case.malicious,
            "required": case.required,
            "expected_reason": case.expected_reason,
            "artifact": artifact_descriptor(path),
        }
        entries.append(entry)
    return entries


def _classify_case(
    case: CorpusCase,
    path: Path,
    target: str,
    *,
    container_validator: ContainerValidator,
    certificate_validator: CertificateValidator,
) -> dict[str, Any]:
    """Classify one fixture through both existing local validation boundaries."""
    entry: dict[str, Any] = {
        "case_id": case.case_id,
        "malicious": case.malicious,
        "required": case.required,
        "expected_reason": case.expected_reason,
        "artifact": artifact_descriptor(path),
    }
    try:
        container = container_validator(path)
    except (UnsafeAssetError, RuntimeCertificationError, ValueError, OSError) as exc:
        entry.update({"classification": "reject", "lane": "container", "reason": str(exc)})
        return entry
    entry["container"] = container
    try:
        certificate = certificate_validator(path, target)
    except (UnsafeAssetError, RuntimeCertificationError, ValueError, OSError) as exc:
        entry.update({"classification": "reject", "lane": "runtime_certification", "reason": str(exc)})
        return entry
    # Runtime certificates intentionally retain their source path for delivery
    # traceability.  The corpus report instead uses a portable relative name so
    # its digest is reproducible across two local output directories.
    portable_certificate = dict(certificate)
    if isinstance(portable_certificate.get("artifact"), dict):
        portable_artifact = dict(portable_certificate["artifact"])
        portable_artifact["path"] = path.name
        portable_certificate["artifact"] = portable_artifact
    entry.update({"classification": "pass", "lane": "runtime_certification", "certificate": portable_certificate})
    return entry


def _case_conforms(case: CorpusCase, result: dict[str, Any]) -> tuple[bool, str | None]:
    if case.malicious:
        if result["classification"] != "reject":
            return False, "malicious_asset_accepted"
        if case.expected_reason and case.expected_reason not in str(result.get("reason", "")):
            return False, "unexpected_rejection_reason"
        return True, None
    if result["classification"] != "pass":
        return False, "benign_control_rejected"
    if result.get("certificate", {}).get("status") != "pass":
        return False, "benign_control_uncertified"
    return True, None


def run_adversarial_asset_corpus(
    root: str | Path,
    *,
    target: str = "web",
    cases: Iterable[CorpusCase] | None = None,
    container_validator: ContainerValidator = validate_glb_container,
    certificate_validator: CertificateValidator = certify_glb_for_target,
    raise_on_failure: bool = True,
) -> dict[str, Any]:
    """Execute the local corpus and fail closed on any required mismatch.

    Injected validators are only a unit-test seam; production callers use the
    existing fail-closed container and certification implementations.
    """
    selected = tuple(cases or corpus_cases())
    if not selected or len({case.case_id for case in selected}) != len(selected):
        raise AdversarialCorpusError("invalid_corpus_definition")
    destination = Path(root)
    materialize_corpus(destination, selected)
    results = []
    failures = []
    for case in selected:
        result = _classify_case(
            case, destination / f"{case.case_id}.glb", target,
            container_validator=container_validator,
            certificate_validator=certificate_validator,
        )
        conforms, failure = _case_conforms(case, result)
        result["conforms"] = conforms
        if case.required and not conforms:
            failures.append({"case_id": case.case_id, "reason": failure})
        results.append(result)
    report = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "target": target,
        "execution": "local_deterministic",
        "cases": results,
        "required_cases": [case.case_id for case in selected if case.required],
        "passed": not failures,
        "failures": failures,
        "corpus_sha256": hashlib.sha256(
            json.dumps(results, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest(),
    }
    if failures and raise_on_failure:
        raise AdversarialCorpusError("adversarial_corpus_failed:" + ",".join(failure["case_id"] for failure in failures))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local, deterministic adversarial GLB validator corpus")
    parser.add_argument("--root", required=True, help="directory for regenerated local fixtures")
    parser.add_argument("--target", choices=("web", "xr", "mobile"), default="web")
    parser.add_argument("--report", help="optional JSON report destination")
    args = parser.parse_args()
    try:
        report = run_adversarial_asset_corpus(args.root, target=args.target)
    except AdversarialCorpusError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, sort_keys=True))
        return 1
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
