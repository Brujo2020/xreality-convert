#!/usr/bin/env python3
"""Read-only architecture audit for the local Xreality asset compiler.

This deliberately audits installed source contracts, not a rendered asset and
not a model claim.  It gives operators a reproducible preflight signal before
they run expensive Metal work: which fail-closed controls are present and
which evidence lanes still require an external/physical measurement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REQUIRED_ENGINE_FILES = (
    "asset_director.py",
    "buffalo_runtime.py",
    "secure_artifacts.py",
    "stage_supervisor.py",
    "shape_worker.py",
    "review_gate_evidence.py",
    "master_promotion_service.py",
    "offline_campaign.py",
    "offline_campaign_repository.py",
    "supply_chain_registry.py",
    "pinned_stage_worker.py",
    "runtime_probe_evidence.py",
    "pbr_texture_quality_gate.py",
    "geometry_quality_gate.py",
    "offline_corpus_preflight.py",
    "canonical_render_evidence.py",
    "gltf_validator_gate.py",
)


def audit(repo_root: Path) -> dict:
    root = repo_root.resolve()
    engine = root / "engine"
    required = {
        name: {"present": (engine / name).is_file()}
        for name in REQUIRED_ENGINE_FILES
    }
    if str(engine) not in sys.path:
        sys.path.insert(0, str(engine))
    plans: dict[str, dict] = {}
    error = None
    try:
        from asset_director import ASSET_CONTRACTS, plan_asset

        for category in sorted(ASSET_CONTRACTS):
            plan = plan_asset(category=category, profile="xreal")
            plans[category] = {
                "material": plan["material"],
                "quality_tier": plan["quality_tier"],
                "required_parts": len(plan["semantic_contract"].get("required_parts", [])),
            }
    except Exception as exc:  # Report an audit failure without hiding it.
        error = f"asset_director_unavailable:{exc}"
    present = all(entry["present"] for entry in required.values()) and error is None
    return {
        "schema_version": 1,
        "kind": "xreality_local_architecture_audit",
        "repo_root": str(root),
        "status": "pass" if present else "fail",
        "controls": required,
        "asset_director": {"plans": plans, "error": error},
        "not_measured": [
            "real_metal_inference",
            "canonical_blender_render",
            "device_runtime_execution",
            "named_human_review",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = audit(args.repo_root)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
