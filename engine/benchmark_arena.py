"""Fail-closed local arena for Image-to-3D and PBR model ports."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

from pbr_glb import _read_glb, validate_pbr_glb


HEX40 = re.compile(r"^[0-9a-f]{40}$")
CAPABILITIES = {"image_to_mesh", "mesh_image_to_pbr", "pbr_glb", "uv", "materials", "textures"}
PROVIDER_STATES = {"candidate", "research", "unavailable", "orchestrator"}
VISUAL_THRESHOLDS = {
    "minimum_silhouette_iou": 0.80,
    "minimum_spatial_color_correlation": 0.80,
    "minimum_quarter_palette_similarity": 0.80,
    "minimum_quarter_color_retention": 0.80,
}


def _json(path):
    return json.loads(Path(path).read_text())


def _safe_relative(value):
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe_relative_path:{value}")
    return path


def sha256_file(path, block_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_spec(spec):
    if spec.get("schema_version") != 1:
        raise ValueError("unsupported_schema_version")
    providers = spec.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("providers_required")
    seen = set()
    for provider in providers:
        provider_id = provider.get("id")
        if not provider_id or provider_id in seen:
            raise ValueError(f"duplicate_or_missing_provider:{provider_id}")
        seen.add(provider_id)
        if provider.get("state") not in PROVIDER_STATES:
            raise ValueError(f"invalid_provider_state:{provider_id}")
        unknown = set(provider.get("capabilities", {})) - CAPABILITIES
        if unknown:
            raise ValueError(f"unknown_capabilities:{provider_id}:{','.join(sorted(unknown))}")
        model = provider.get("model")
        if model:
            if not model.get("repo") or not HEX40.fullmatch(model.get("revision", "")):
                raise ValueError(f"unpinned_model:{provider_id}")
            for artifact in model.get("artifacts", []):
                _safe_relative(artifact.get("path", ""))
                if int(artifact.get("size", 0)) <= 0:
                    raise ValueError(f"invalid_artifact_size:{provider_id}")
                digest = artifact.get("sha256")
                if digest is not None and not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ValueError(f"invalid_artifact_hash:{provider_id}")
        code = provider.get("code")
        if code and not HEX40.fullmatch(code.get("revision", "")):
            raise ValueError(f"unpinned_code:{provider_id}")
    return spec


def _hf_snapshot(cache_root, repo_id, revision):
    owner, name = repo_id.split("/", 1)
    return Path(cache_root) / f"models--{owner}--{name}" / "snapshots" / revision


def _git_state(path):
    root = Path(path)
    if not (root / ".git").exists():
        return {"present": False}
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip())
    return {"present": True, "revision": head, "dirty": dirty}


def preflight_provider(provider, cache_root, repo_root, deep=False):
    result = {
        "id": provider["id"],
        "state": provider["state"],
        "role": provider.get("role", "competitor"),
        "capabilities": provider.get("capabilities", {}),
        "eligible": provider["state"] == "candidate" and provider.get("role", "competitor") == "competitor",
        "reasons": [],
    }
    model = provider.get("model")
    artifacts = []
    if model:
        snapshot = _hf_snapshot(cache_root, model["repo"], model["revision"])
        result["snapshot"] = str(snapshot)
        for expected in model.get("artifacts", []):
            path = snapshot / _safe_relative(expected["path"])
            item = {"path": expected["path"], "lanes": expected.get("lanes", [])}
            if not path.is_file():
                item["status"] = "missing"
            elif path.stat().st_size != expected["size"]:
                item.update(status="size_mismatch", actual_size=path.stat().st_size)
            elif deep and expected.get("sha256") and sha256_file(path) != expected["sha256"]:
                item["status"] = "hash_mismatch"
            else:
                item["status"] = "ready"
            artifacts.append(item)
        result["artifacts"] = artifacts
        if any(item["status"] != "ready" for item in artifacts):
            result["reasons"].append("model_artifacts_incomplete")
    code = provider.get("code")
    if code:
        local_path = Path(repo_root) / code["local_path"] if code.get("local_path") else None
        state = _git_state(local_path) if local_path else {"present": False}
        state["expected_revision"] = code["revision"]
        result["code"] = state
        if not state.get("present"):
            result["reasons"].append("code_missing")
        elif state.get("revision") != code["revision"]:
            result["reasons"].append("code_revision_mismatch")
        if state.get("dirty"):
            result["reasons"].append("code_dirty")
    if provider["state"] != "candidate":
        result["reasons"].append(f"declared_{provider['state']}")
    if result["role"] != "competitor":
        result["reasons"].append("not_a_3d_competitor")
    result["promotion_ready"] = result["eligible"] and not result["reasons"]
    return result


def preflight(spec, cache_root, repo_root, deep=False):
    validate_spec(spec)
    return {
        "schema_version": 1,
        "providers": [preflight_provider(p, cache_root, repo_root, deep) for p in spec["providers"]],
    }


def seal_corpus(corpus, repo_root):
    root = Path(repo_root).resolve()
    sealed = {"schema_version": 1, "cases": []}
    seen = set()
    for case in corpus.get("cases", []):
        case_id = case.get("id")
        if not case_id or case_id in seen:
            raise ValueError(f"duplicate_or_missing_case:{case_id}")
        seen.add(case_id)
        output = {"id": case_id, "lanes": sorted(set(case.get("lanes", []))), "assets": {}}
        for key, relative in sorted(case.get("assets", {}).items()):
            safe = _safe_relative(relative)
            path = (root / safe).resolve()
            if root not in path.parents or not path.is_file():
                raise ValueError(f"missing_or_escaped_asset:{relative}")
            output["assets"][key] = {
                "path": safe.as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        sealed["cases"].append(output)
    sealed["cases"].sort(key=lambda item: item["id"])
    canonical = json.dumps(sealed, sort_keys=True, separators=(",", ":")).encode()
    sealed["corpus_sha256"] = hashlib.sha256(canonical).hexdigest()
    return sealed


def _embedded_image_reports(document, binary):
    reports = []
    views = document.get("bufferViews") or []
    for item in document.get("images") or []:
        view_index = item.get("bufferView")
        report = {"mime_type": item.get("mimeType"), "embedded": False}
        if isinstance(view_index, int) and 0 <= view_index < len(views):
            view = views[view_index]
            start = int(view.get("byteOffset", 0))
            end = start + int(view.get("byteLength", 0))
            try:
                with Image.open(io.BytesIO(binary[start:end])) as image:
                    report.update(embedded=True, width=image.width, height=image.height, mode=image.mode)
            except (OSError, ValueError):
                pass
        reports.append(report)
    return reports


def _mesh_report(path):
    loaded = trimesh.load(path, force="scene", process=False)
    meshes = list(loaded.geometry.values()) if isinstance(loaded, trimesh.Scene) else [loaded]
    meshes = [mesh for mesh in meshes if isinstance(mesh, trimesh.Trimesh)]
    vertices = sum(len(mesh.vertices) for mesh in meshes)
    faces = sum(len(mesh.faces) for mesh in meshes)
    finite_vertices = sum(int(np.isfinite(mesh.vertices).all(axis=1).sum()) for mesh in meshes)
    degenerate = sum(int((mesh.area_faces <= 1e-12).sum()) for mesh in meshes if len(mesh.faces))
    components = 0
    for mesh in meshes:
        if not len(mesh.faces):
            continue
        labels = trimesh.graph.connected_component_labels(
            mesh.face_adjacency,
            node_count=len(mesh.faces),
        )
        components += len(np.unique(labels))
    uv_vertices = 0
    uv_finite = 0
    uv_in_range = 0
    uv_degenerate = 0
    uv_faces = 0
    for mesh in meshes:
        uv = getattr(mesh.visual, "uv", None)
        if uv is None or len(uv) != len(mesh.vertices):
            continue
        uv = np.asarray(uv)
        uv_vertices += len(uv)
        uv_finite += int(np.isfinite(uv).all(axis=1).sum())
        uv_in_range += int(((uv >= -1e-6) & (uv <= 1 + 1e-6)).all(axis=1).sum())
        if len(mesh.faces):
            triangles = uv[mesh.faces]
            edge_a = triangles[:, 1] - triangles[:, 0]
            edge_b = triangles[:, 2] - triangles[:, 0]
            twice_area = np.abs(edge_a[:, 0] * edge_b[:, 1] - edge_a[:, 1] * edge_b[:, 0])
            uv_degenerate += int((twice_area <= 1e-10).sum())
            uv_faces += len(mesh.faces)
    return {
        "meshes": len(meshes),
        "vertices": vertices,
        "faces": faces,
        "finite_vertex_ratio": finite_vertices / max(1, vertices),
        "degenerate_face_ratio": degenerate / max(1, faces),
        "components": components,
        "watertight_meshes": sum(bool(mesh.is_watertight) for mesh in meshes),
        "uv_vertices": uv_vertices,
        "uv_finite_ratio": uv_finite / max(1, uv_vertices),
        "uv_in_unit_square_ratio": uv_in_range / max(1, uv_vertices),
        "uv_degenerate_face_ratio": uv_degenerate / max(1, uv_faces),
    }


def review_visual_evidence(evidence, human_decision="not_measured"):
    if human_decision not in {"not_measured", "pass", "reject"}:
        raise ValueError(f"invalid_human_decision:{human_decision}")
    gate = evidence.get("gate") or {}
    front = ((gate.get("front") or {}).get("metrics") or {})
    quarters = ((gate.get("quarters") or {}).get("metrics") or {})
    left = quarters.get("quarter-left") or {}
    right = quarters.get("quarter-right") or {}
    metrics = {
        "silhouette_iou": front.get("silhouetteIoU"),
        "spatial_color_correlation": front.get("spatialColorCorrelation"),
        "quarter_left_palette_similarity": left.get("paletteSimilarity"),
        "quarter_left_color_retention": left.get("colorRetention"),
        "quarter_right_palette_similarity": right.get("paletteSimilarity"),
        "quarter_right_color_retention": right.get("colorRetention"),
    }
    checks = {
        "upstream_gate": gate.get("passed") is True,
        "silhouette": isinstance(metrics["silhouette_iou"], (int, float))
        and metrics["silhouette_iou"] >= VISUAL_THRESHOLDS["minimum_silhouette_iou"],
        "spatial_color": isinstance(metrics["spatial_color_correlation"], (int, float))
        and metrics["spatial_color_correlation"] >= VISUAL_THRESHOLDS["minimum_spatial_color_correlation"],
        "quarter_left_palette": isinstance(metrics["quarter_left_palette_similarity"], (int, float))
        and metrics["quarter_left_palette_similarity"] >= VISUAL_THRESHOLDS["minimum_quarter_palette_similarity"],
        "quarter_left_color": isinstance(metrics["quarter_left_color_retention"], (int, float))
        and metrics["quarter_left_color_retention"] >= VISUAL_THRESHOLDS["minimum_quarter_color_retention"],
        "quarter_right_palette": isinstance(metrics["quarter_right_palette_similarity"], (int, float))
        and metrics["quarter_right_palette_similarity"] >= VISUAL_THRESHOLDS["minimum_quarter_palette_similarity"],
        "quarter_right_color": isinstance(metrics["quarter_right_color_retention"], (int, float))
        and metrics["quarter_right_color_retention"] >= VISUAL_THRESHOLDS["minimum_quarter_color_retention"],
    }
    automatic_passed = all(checks.values())
    passed = automatic_passed and human_decision == "pass"
    if human_decision == "reject" or not automatic_passed:
        visual_quality = "reject"
    elif passed:
        visual_quality = "pass"
    else:
        visual_quality = "not_measured"
    reasons = [name for name, value in checks.items() if not value]
    if human_decision != "pass":
        reasons.append(f"human_{human_decision}")
    return {
        "automatic_passed": automatic_passed,
        "human_decision": human_decision,
        "passed": passed,
        "visual_quality": visual_quality,
        "metrics": metrics,
        "checks": checks,
        "thresholds": VISUAL_THRESHOLDS,
        "reasons": reasons,
    }


def audit_glb(path, require_pbr=False, min_texture_size=512, visual_evidence=None, human_decision="not_measured"):
    target = Path(path)
    try:
        document, binary = _read_glb(target)
        geometry = _mesh_report(target)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "path": str(target),
            "require_pbr": require_pbr,
            "passed": False,
            "reasons": [str(exc) or "invalid_glb"],
            "structural_score": 0,
            "pbr_score": 0 if require_pbr else None,
            "visual_quality": "not_measured",
            "promotion_passed": False,
        }
    pbr = validate_pbr_glb(target)
    images = _embedded_image_reports(document, binary)
    geometry_passed = (
        geometry["faces"] > 0
        and geometry["vertices"] > 0
        and geometry["finite_vertex_ratio"] == 1.0
        and geometry["degenerate_face_ratio"] <= 0.001
    )
    uv_passed = (
        geometry["uv_vertices"] > 0
        and geometry["uv_finite_ratio"] == 1.0
        and geometry["uv_in_unit_square_ratio"] >= 0.99
        and geometry["uv_degenerate_face_ratio"] <= 0.01
    )
    texture_passed = bool(images) and all(
        item.get("embedded")
        and min(item.get("width", 0), item.get("height", 0)) >= min_texture_size
        for item in images
    )
    score = 10 if geometry_passed else 0
    score += 30 * (
        0.25 * (geometry["faces"] > 0)
        + 0.25 * (geometry["finite_vertex_ratio"] == 1.0)
        + 0.25 * (geometry["degenerate_face_ratio"] <= 0.001)
        + 0.25 * (geometry["components"] > 0)
    )
    pbr_score = None
    if require_pbr:
        pbr_score = 10 * pbr["passed"] + 10 * uv_passed
        pbr_score += 8 * pbr.get("embedded_base_color", False)
        pbr_score += 8 * pbr.get("embedded_metallic_roughness", False)
        pbr_score += 4 * texture_passed
        score += pbr_score
    structural_passed = geometry_passed and (not require_pbr or (pbr["passed"] and uv_passed and texture_passed))
    visual = review_visual_evidence(visual_evidence, human_decision) if visual_evidence else None
    return {
        "path": str(target),
        "bytes": target.stat().st_size,
        "require_pbr": require_pbr,
        "passed": structural_passed,
        "geometry": geometry,
        "pbr": pbr,
        "images": images,
        "gates": {"geometry": geometry_passed, "uv": uv_passed, "textures": texture_passed},
        "structural_score": round(score, 2),
        "pbr_score": round(pbr_score, 2) if pbr_score is not None else None,
        "visual_quality": visual["visual_quality"] if visual else "not_measured",
        "visual_review": visual,
        "promotion_passed": structural_passed and bool(visual and visual["passed"]),
    }


def rank_reports(reports):
    ranked = []
    for report in reports:
        if report.get("role", "competitor") != "competitor":
            continue
        ranked.append({
            "provider": report["provider"],
            "passed": bool(report.get("promotion_passed")),
            "structural_passed": bool(report.get("passed")),
            "score": float(report.get("structural_score", 0)),
            "visual_quality": report.get("visual_quality", "not_measured"),
        })
    ranked.sort(key=lambda item: (item["passed"], item["score"]), reverse=True)
    return {"ranking": ranked, "winner": ranked[0]["provider"] if ranked and ranked[0]["passed"] else None}


def _print(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--spec", required=True)
    pre.add_argument("--cache-root", default=os.environ.get("HF_HUB_CACHE", str(Path.home() / ".cache/huggingface/hub")))
    pre.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    pre.add_argument("--deep", action="store_true")
    seal = sub.add_parser("seal")
    seal.add_argument("--corpus", required=True)
    seal.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    audit = sub.add_parser("audit")
    audit.add_argument("glb")
    audit.add_argument("--require-pbr", action="store_true")
    audit.add_argument("--min-texture-size", type=int, default=512)
    audit.add_argument("--visual-evidence")
    audit.add_argument("--human-decision", choices=("not_measured", "pass", "reject"), default="not_measured")
    rank = sub.add_parser("rank")
    rank.add_argument("reports", nargs="+")
    args = parser.parse_args()
    if args.command == "preflight":
        _print(preflight(_json(args.spec), args.cache_root, args.repo_root, args.deep))
    elif args.command == "seal":
        _print(seal_corpus(_json(args.corpus), args.repo_root))
    elif args.command == "audit":
        evidence = _json(args.visual_evidence) if args.visual_evidence else None
        _print(audit_glb(args.glb, args.require_pbr, args.min_texture_size, evidence, args.human_decision))
    else:
        _print(rank_reports([_json(path) for path in args.reports]))


if __name__ == "__main__":
    main()
