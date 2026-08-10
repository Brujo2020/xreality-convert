"""Fail-closed admission contract for multi-view Shape reconstruction."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


CANONICAL_VIEWS = ("front", "right", "back", "left", "top", "bottom")
EVIDENCE_CLASSES = {"measured", "synthetic"}


class MultiViewContractError(ValueError):
    pass


def admit_multiview_shape(views: Sequence[Mapping[str, Any]], *, profile: str) -> dict[str, Any]:
    """Validate camera coverage without calling synthetic views real evidence."""
    if not isinstance(views, Sequence) or isinstance(views, (str, bytes)):
        raise MultiViewContractError("multiview_list_required")
    normalized = []
    seen = set()
    for view in views:
        if not isinstance(view, Mapping):
            raise MultiViewContractError("multiview_record_invalid")
        view_id = view.get("view_id")
        evidence = view.get("evidence_class")
        if view_id not in CANONICAL_VIEWS or view_id in seen:
            raise MultiViewContractError("multiview_camera_invalid_or_duplicate")
        if evidence not in EVIDENCE_CLASSES:
            raise MultiViewContractError("multiview_evidence_invalid")
        if not isinstance(view.get("sha256"), str) or len(view["sha256"]) != 64:
            raise MultiViewContractError("multiview_hash_required")
        seen.add(view_id)
        normalized.append({"view_id": view_id, "evidence_class": evidence, "sha256": view["sha256"]})
    real = {item["view_id"] for item in normalized if item["evidence_class"] == "measured"}
    if "front" not in real:
        raise MultiViewContractError("multiview_real_front_required")
    coverage = tuple(item for item in CANONICAL_VIEWS if item in seen)
    missing = tuple(item for item in CANONICAL_VIEWS if item not in seen)
    master = profile == "maxquality"
    if master and set(CANONICAL_VIEWS) - real:
        raise MultiViewContractError("master_requires_six_real_views")
    return {
        "passed": len(coverage) == len(CANONICAL_VIEWS),
        "coverage": coverage,
        "missing": missing,
        "real_views": tuple(item for item in CANONICAL_VIEWS if item in real),
        "synthetic_views": tuple(item["view_id"] for item in normalized if item["evidence_class"] == "synthetic"),
        "promotion": "human_review_required" if len(coverage) == 6 else "blocked",
        "synthetic_is_evidence": False,
    }
