"""Bind independently produced Blender canonical renders to a sealed job.

This module intentionally *does not* start Blender, create a placeholder
image, or infer a visual result.  It accepts a pre-existing renderer report
only when every claimed render and its per-render metadata are regular,
job-local files tied to the exact GLB and compiled semantic graph.  The
resulting evidence record is created once, made read-only, and can be checked
again before a human reviews a MASTER candidate.

The fixed render matrix makes a beauty render insufficient evidence:
unlit/base-colour, three neutral views, grazing light, wireframe, and a
semantic-part view are always required.  An alpha/transmission checker is
required precisely when the GLB declares alpha blending/masking or material
transmission.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from buffalo_runtime import ContractError, atomic_write_json, canonical_json, make_read_only, safe_job_path, sha256_file
from runtime_certification import RuntimeCertificationError, _read_glb
from secure_artifacts import UnsafeAssetError, validate_glb_container


CANONICAL_RENDER_EVIDENCE_SCHEMA_VERSION = 1
_REPORT_KIND = "xreality.blender_canonical_render_report"
_META_KIND = "xreality.blender_canonical_render_meta"
_RECORD_KIND = "xreality.canonical_render_evidence"
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_BASE_MODES = frozenset({
    "unlit",
    "neutral-front",
    "neutral-quarter-left",
    "neutral-quarter-right",
    "grazing",
    "wireframe",
    "semantic-part",
})
_ALPHA_MODE = "alpha-transmission-checker"


class CanonicalRenderEvidenceError(ValueError):
    """A claimed canonical Blender render is incomplete or untrustworthy."""


def _hash(value: Any, reason: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value.lower()) is None:
        raise CanonicalRenderEvidenceError(reason)
    return value.lower()


def _canonical_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value)).hexdigest()


def _root(job_dir: str | Path) -> Path:
    root = Path(job_dir).resolve()
    if not root.is_dir() or root.is_symlink():
        raise CanonicalRenderEvidenceError("managed_job_missing")
    return root


def _relative_file(root: Path, relative: Any, *, missing: str, unsafe: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise CanonicalRenderEvidenceError(unsafe)
    try:
        path = safe_job_path(root, relative)
    except ContractError as exc:
        raise CanonicalRenderEvidenceError(unsafe) from exc
    if path.is_symlink():
        raise CanonicalRenderEvidenceError(unsafe)
    if not path.is_file():
        raise CanonicalRenderEvidenceError(missing)
    resolved = path.resolve()
    if root not in resolved.parents:
        raise CanonicalRenderEvidenceError(unsafe)
    return resolved


def _read_json(path: Path, reason: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalRenderEvidenceError(reason) from exc
    if not isinstance(value, Mapping):
        raise CanonicalRenderEvidenceError(reason)
    return value


def _expect_mapping(value: Any, reason: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CanonicalRenderEvidenceError(reason)
    return value


def _graph_descriptor(root: Path, graph_path: str) -> tuple[Path, dict[str, Any]]:
    path = _relative_file(root, graph_path, missing="semantic_graph_missing", unsafe="unsafe_semantic_graph_path")
    graph = _read_json(path, "invalid_semantic_graph")
    if graph.get("schema_version") != 1 or not isinstance(graph.get("nodes"), list):
        raise CanonicalRenderEvidenceError("invalid_semantic_graph")
    graph_id = _hash(graph.get("graph_id"), "semantic_graph_id_invalid")
    unsigned = {key: value for key, value in graph.items() if key != "graph_id"}
    if _canonical_hash(unsigned) != graph_id:
        raise CanonicalRenderEvidenceError("semantic_graph_integrity_mismatch")
    if not any(isinstance(node, Mapping) and node.get("kind") == "part" for node in graph["nodes"]):
        raise CanonicalRenderEvidenceError("semantic_graph_parts_required")
    return path, {
        "path": path.relative_to(root).as_posix(),
        "sha256": "sha256:" + sha256_file(path),
        "graph_id": graph_id,
    }


def _requires_alpha_transmission_checker(glb: Path) -> bool:
    try:
        document, _ = _read_glb(glb)
    except (OSError, RuntimeCertificationError) as exc:
        raise CanonicalRenderEvidenceError("invalid_glb_document") from exc
    materials = document.get("materials", [])
    if not isinstance(materials, list):
        raise CanonicalRenderEvidenceError("invalid_glb_materials")
    for material in materials:
        if not isinstance(material, Mapping):
            raise CanonicalRenderEvidenceError("invalid_glb_materials")
        if material.get("alphaMode", "OPAQUE") in {"MASK", "BLEND"}:
            return True
        extensions = material.get("extensions", {})
        if not isinstance(extensions, Mapping):
            raise CanonicalRenderEvidenceError("invalid_glb_material_extensions")
        if "KHR_materials_transmission" in extensions:
            return True
    return False


def _runner(report: Mapping[str, Any]) -> dict[str, str]:
    measurement = _expect_mapping(report.get("measurement"), "canonical_measurement_missing")
    if (measurement.get("kind") != "external_blender_canonical_render"
            or measurement.get("executed") is not True or measurement.get("exit_code") != 0):
        raise CanonicalRenderEvidenceError("canonical_render_not_measured")
    runner = _expect_mapping(report.get("runner"), "canonical_runner_missing")
    producer = runner.get("producer")
    execution_id = runner.get("execution_id")
    if not isinstance(producer, str) or not producer.strip() or not isinstance(execution_id, str) or not execution_id.strip():
        raise CanonicalRenderEvidenceError("canonical_runner_missing")
    return {"producer": producer.strip(), "execution_id": execution_id.strip()}


def _validate_report_header(
    report: Mapping[str, Any], *, artifact: dict[str, Any], graph: dict[str, Any], expected_report_path: str,
) -> dict[str, str]:
    if report.get("schema_version") != CANONICAL_RENDER_EVIDENCE_SCHEMA_VERSION or report.get("kind") != _REPORT_KIND:
        raise CanonicalRenderEvidenceError("unsupported_canonical_render_report")
    if report.get("status") != "pass":
        raise CanonicalRenderEvidenceError("canonical_render_not_passed")
    runner = _runner(report)
    reported_asset = _expect_mapping(report.get("artifact"), "canonical_artifact_missing")
    if reported_asset.get("path") != artifact["path"] or _hash(reported_asset.get("sha256"), "canonical_artifact_hash_invalid") != artifact["sha256"]:
        raise CanonicalRenderEvidenceError("canonical_artifact_mismatch")
    reported_graph = _expect_mapping(report.get("semantic_graph"), "canonical_semantic_graph_missing")
    if (
        reported_graph.get("path") != graph["path"]
        or _hash(reported_graph.get("sha256"), "canonical_semantic_graph_hash_invalid") != graph["sha256"]
        or _hash(reported_graph.get("graph_id"), "canonical_semantic_graph_id_invalid") != graph["graph_id"]
    ):
        raise CanonicalRenderEvidenceError("canonical_semantic_graph_mismatch")
    # The source report cannot include itself as a render, which prevents a
    # self-referential JSON claim from standing in for a measured frame.
    if expected_report_path == artifact["path"] or expected_report_path == graph["path"]:
        raise CanonicalRenderEvidenceError("canonical_report_path_conflict")
    return runner


def _validate_render_item(
    *, root: Path, item: Any, mode: str, artifact: dict[str, Any], graph: dict[str, Any], runner: Mapping[str, str], report_path: str,
) -> dict[str, Any]:
    entry = _expect_mapping(item, "invalid_canonical_render_entry")
    if entry.get("mode") != mode:
        raise CanonicalRenderEvidenceError("canonical_render_mode_mismatch")
    render_path_value = entry.get("path")
    metadata_path_value = entry.get("metadata_path")
    render = _relative_file(root, render_path_value, missing="canonical_render_missing", unsafe="unsafe_canonical_render_path")
    metadata = _relative_file(root, metadata_path_value, missing="canonical_render_metadata_missing", unsafe="unsafe_canonical_render_metadata_path")
    if render.relative_to(root).as_posix() in {report_path, artifact["path"], graph["path"]}:
        raise CanonicalRenderEvidenceError("canonical_render_path_conflict")
    if metadata.relative_to(root).as_posix() in {report_path, artifact["path"], graph["path"]}:
        raise CanonicalRenderEvidenceError("canonical_metadata_path_conflict")
    render_hash = "sha256:" + sha256_file(render)
    metadata_hash = "sha256:" + sha256_file(metadata)
    if _hash(entry.get("sha256"), "canonical_render_hash_invalid") != render_hash:
        raise CanonicalRenderEvidenceError("canonical_render_hash_mismatch")
    if _hash(entry.get("metadata_sha256"), "canonical_render_metadata_hash_invalid") != metadata_hash:
        raise CanonicalRenderEvidenceError("canonical_render_metadata_hash_mismatch")
    meta = _read_json(metadata, "invalid_canonical_render_metadata")
    if meta.get("schema_version") != CANONICAL_RENDER_EVIDENCE_SCHEMA_VERSION or meta.get("kind") != _META_KIND or meta.get("mode") != mode:
        raise CanonicalRenderEvidenceError("canonical_metadata_contract_mismatch")
    if _expect_mapping(meta.get("runner"), "canonical_metadata_runner_missing") != runner:
        raise CanonicalRenderEvidenceError("canonical_metadata_runner_mismatch")
    meta_asset = _expect_mapping(meta.get("artifact"), "canonical_metadata_artifact_missing")
    meta_graph = _expect_mapping(meta.get("semantic_graph"), "canonical_metadata_semantic_graph_missing")
    meta_render = _expect_mapping(meta.get("render"), "canonical_metadata_render_missing")
    if (meta_asset.get("sha256") != artifact["sha256"]
            or meta_graph.get("sha256") != graph["sha256"]
            or meta_graph.get("graph_id") != graph["graph_id"]
            or meta_render.get("path") != render.relative_to(root).as_posix()
            or meta_render.get("sha256") != render_hash):
        raise CanonicalRenderEvidenceError("canonical_metadata_binding_mismatch")
    return {
        "mode": mode,
        "path": render.relative_to(root).as_posix(),
        "sha256": render_hash,
        "bytes": render.stat().st_size,
        "metadata_path": metadata.relative_to(root).as_posix(),
        "metadata_sha256": metadata_hash,
    }


def _validate_report(
    *, root: Path, report_path: Path, artifact: dict[str, Any], graph: dict[str, Any], alpha_required: bool,
) -> tuple[Mapping[str, Any], dict[str, str], list[dict[str, Any]]]:
    report = _read_json(report_path, "invalid_canonical_render_report")
    relative_report = report_path.relative_to(root).as_posix()
    runner = _validate_report_header(report, artifact=artifact, graph=graph, expected_report_path=relative_report)
    renders = report.get("renders")
    if not isinstance(renders, list):
        raise CanonicalRenderEvidenceError("canonical_render_matrix_missing")
    required = set(_BASE_MODES)
    if alpha_required:
        required.add(_ALPHA_MODE)
    observed_modes: list[str] = []
    bound: list[dict[str, Any]] = []
    for item in renders:
        if not isinstance(item, Mapping) or not isinstance(item.get("mode"), str):
            raise CanonicalRenderEvidenceError("invalid_canonical_render_entry")
        mode = item["mode"]
        observed_modes.append(mode)
        if mode not in required:
            raise CanonicalRenderEvidenceError("unexpected_canonical_render_mode")
        bound.append(_validate_render_item(
            root=root, item=item, mode=mode, artifact=artifact, graph=graph, runner=runner, report_path=relative_report,
        ))
    if set(observed_modes) != required or len(observed_modes) != len(set(observed_modes)):
        raise CanonicalRenderEvidenceError("canonical_render_matrix_incomplete")
    paths = [entry["path"] for entry in bound] + [entry["metadata_path"] for entry in bound]
    if len(paths) != len(set(paths)):
        raise CanonicalRenderEvidenceError("canonical_render_evidence_paths_not_unique")
    return report, runner, sorted(bound, key=lambda entry: entry["mode"])


def _seal_external_sources(root: Path, report_path: Path, renders: list[Mapping[str, Any]]) -> None:
    """Freeze the accepted report, sidecars, and frames after verification.

    This is deliberately performed only after the whole matrix validates.  A
    partial or rejected external render remains writable for its worker, while
    an accepted attestation cannot be accidentally overwritten by a later DCC
    run in the same job directory.
    """
    paths = [report_path]
    for render in renders:
        paths.append(_relative_file(root, render["path"], missing="canonical_render_missing", unsafe="unsafe_canonical_render_path"))
        paths.append(_relative_file(root, render["metadata_path"], missing="canonical_render_metadata_missing", unsafe="unsafe_canonical_render_metadata_path"))
    for path in paths:
        make_read_only(path)


def bind_canonical_render_evidence(
    *, job_dir: str | Path, glb_path: str, semantic_graph_path: str, render_report_path: str,
) -> dict[str, Any]:
    """Seal real Blender canonical-render evidence, or reject without fallback.

    Callers must run Blender separately.  This binder never treats an existing
    ``blender-runtime-report.json`` as equivalent evidence: it requires the
    complete independent render matrix and a per-frame metadata sidecar.
    """
    root = _root(job_dir)
    glb = _relative_file(root, glb_path, missing="canonical_artifact_missing", unsafe="unsafe_canonical_artifact_path")
    try:
        container = validate_glb_container(glb)
    except UnsafeAssetError as exc:
        raise CanonicalRenderEvidenceError("unsafe_canonical_artifact") from exc
    artifact = {"path": glb.relative_to(root).as_posix(), "sha256": "sha256:" + sha256_file(glb), "bytes": glb.stat().st_size}
    _, graph = _graph_descriptor(root, semantic_graph_path)
    report_path = _relative_file(root, render_report_path, missing="canonical_render_report_missing", unsafe="unsafe_canonical_render_report_path")
    alpha_required = _requires_alpha_transmission_checker(glb)
    report, runner, renders = _validate_report(
        root=root, report_path=report_path, artifact=artifact, graph=graph, alpha_required=alpha_required,
    )
    _seal_external_sources(root, report_path, renders)
    payload = {
        "schema_version": CANONICAL_RENDER_EVIDENCE_SCHEMA_VERSION,
        "kind": _RECORD_KIND,
        "status": "measured_pass",
        "artifact": artifact,
        "semantic_graph": graph,
        "render_report": {
            "path": report_path.relative_to(root).as_posix(),
            "sha256": "sha256:" + sha256_file(report_path),
            "contract_sha256": _canonical_hash(report),
        },
        "runner": runner,
        "renders": renders,
        "requirements": {"alpha_transmission_checker_required": alpha_required},
        "promotion": "human_review_required",
        "evidence_scope": {
            "renderer_execution": "measured_local",
            "canonical_render_matrix": "measured_local",
            "artistic_master_quality": "human_review_required",
        },
    }
    record_id = _canonical_hash(payload)
    record = {**payload, "record_id": record_id, "seal": {"algorithm": "sha256", "value": record_id}}
    destination = safe_job_path(root, f"canonical-render-evidence/{record_id.removeprefix('sha256:')}.json")
    if destination.exists() or destination.is_symlink():
        raise CanonicalRenderEvidenceError("canonical_render_evidence_already_exists")
    atomic_write_json(destination, record)
    make_read_only(destination)
    return {**record, "path": str(destination)}


def verify_canonical_render_evidence(*, job_dir: str | Path, record_path: str) -> dict[str, Any]:
    """Revalidate a sealed evidence record against every current source byte."""
    root = _root(job_dir)
    path = _relative_file(root, record_path, missing="canonical_render_evidence_record_missing", unsafe="unsafe_canonical_render_evidence_record_path")
    if path.stat().st_mode & 0o222:
        raise CanonicalRenderEvidenceError("canonical_render_evidence_record_not_sealed")
    record = _read_json(path, "invalid_canonical_render_evidence_record")
    if record.get("schema_version") != CANONICAL_RENDER_EVIDENCE_SCHEMA_VERSION or record.get("kind") != _RECORD_KIND:
        raise CanonicalRenderEvidenceError("invalid_canonical_render_evidence_record")
    payload = {key: value for key, value in record.items() if key not in {"record_id", "seal", "path"}}
    expected = _canonical_hash(payload)
    seal = record.get("seal")
    if not isinstance(seal, Mapping) or seal.get("algorithm") != "sha256" or seal.get("value") != expected or record.get("record_id") != expected:
        raise CanonicalRenderEvidenceError("canonical_render_evidence_seal_invalid")
    artifact = record.get("artifact")
    graph = record.get("semantic_graph")
    report = record.get("render_report")
    if not isinstance(artifact, Mapping) or not isinstance(graph, Mapping) or not isinstance(report, Mapping):
        raise CanonicalRenderEvidenceError("invalid_canonical_render_evidence_record")
    glb = _relative_file(root, artifact.get("path"), missing="canonical_artifact_missing", unsafe="unsafe_canonical_artifact_path")
    if "sha256:" + sha256_file(glb) != artifact.get("sha256"):
        raise CanonicalRenderEvidenceError("canonical_artifact_mismatch")
    _, current_graph = _graph_descriptor(root, graph.get("path"))
    if dict(graph) != current_graph:
        raise CanonicalRenderEvidenceError("canonical_semantic_graph_mismatch")
    report_path = _relative_file(root, report.get("path"), missing="canonical_render_report_missing", unsafe="unsafe_canonical_render_report_path")
    if "sha256:" + sha256_file(report_path) != report.get("sha256"):
        raise CanonicalRenderEvidenceError("canonical_render_report_hash_mismatch")
    alpha_required = _requires_alpha_transmission_checker(glb)
    _, runner, renders = _validate_report(root=root, report_path=report_path, artifact=dict(artifact), graph=current_graph, alpha_required=alpha_required)
    if record.get("runner") != runner or record.get("renders") != renders:
        raise CanonicalRenderEvidenceError("canonical_render_evidence_binding_mismatch")
    if record.get("requirements") != {"alpha_transmission_checker_required": alpha_required}:
        raise CanonicalRenderEvidenceError("canonical_render_requirement_mismatch")
    return dict(record)
