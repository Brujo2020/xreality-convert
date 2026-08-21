"""Capability Router for 3D Local.

Intelligently routes user prompts, images, quality constraints, and target platforms
(visionOS, WebXR, Blender) to the optimal pipeline execution graph and model stack.
"""

from typing import Dict, Any, Optional
from pathlib import Path


class CapabilityProfile:
    FAST = "fast"          # TripoSG rapid geometry
    BALANCED = "balanced"  # TRELLIS.2 Low-res / Hunyuan MLX
    QUALITY = "quality"    # Pixal3D MLX + PBR 2K + PartPacker
    MAX = "max"            # Pixal3D MLX + PartPacker + RigAnything + LOD + USDZ (North Star)


class CapabilityRouter:
    """Routes generation requests to optimal execution graph based on target and quality level."""

    @staticmethod
    def resolve_pipeline(
        quality: str = CapabilityProfile.QUALITY,
        target: str = "webxr",
        request_parts: bool = False,
        request_pbr: bool = True,
        request_rig: bool = False,
        request_lod: bool = True,
    ) -> Dict[str, Any]:
        """Resolve model selection and step execution graph for a target profile."""
        quality = quality.lower()
        if quality not in (CapabilityProfile.FAST, CapabilityProfile.BALANCED, CapabilityProfile.QUALITY, CapabilityProfile.MAX):
            quality = CapabilityProfile.QUALITY

        # Auto-upgrade quality to MAX if full pipeline flags requested
        if (request_parts and request_rig and target == "visionos") or quality == CapabilityProfile.MAX:
            quality = CapabilityProfile.MAX

        if quality == CapabilityProfile.FAST:
            return {
                "profile": CapabilityProfile.FAST,
                "backbone_model": "triposg",
                "device": "mps",
                "steps": 15,
                "octree_resolution": 128,
                "target_faces": 15000,
                "parts_separation": False,
                "pbr_materials": False,
                "rigging": False,
                "lod_generation": False,
                "export_formats": ["glb"],
                "target_platform": target,
            }

        elif quality == CapabilityProfile.BALANCED:
            return {
                "profile": CapabilityProfile.BALANCED,
                "backbone_model": "trellis2",
                "device": "mlx",
                "steps": 25,
                "octree_resolution": 160,
                "target_faces": 35000,
                "parts_separation": request_parts,
                "pbr_materials": request_pbr,
                "rigging": False,
                "lod_generation": request_lod,
                "export_formats": ["glb", "usdz"],
                "target_platform": target,
            }

        elif quality == CapabilityProfile.QUALITY:
            return {
                "profile": CapabilityProfile.QUALITY,
                "backbone_model": "pixal3d",
                "device": "mlx",
                "steps": 35,
                "octree_resolution": 192,
                "target_faces": 50000,
                "parts_separation": request_parts,
                "pbr_materials": True,
                "rigging": request_rig,
                "lod_generation": True,
                "export_formats": ["glb", "usd", "usdz"],
                "target_platform": target,
            }

        else:  # CapabilityProfile.MAX (North Star)
            return {
                "profile": CapabilityProfile.MAX,
                "backbone_model": "pixal3d",
                "partpacker_model": "partpacker",
                "material_generator": "videomatgen",
                "rigging_model": "riganything",
                "device": "mlx",
                "steps": 45,
                "octree_resolution": 256,
                "target_faces": 85000,
                "parts_separation": True,
                "pbr_materials": True,
                "rigging": True,
                "lod_generation": True,
                "collision_mesh": True,
                "export_formats": ["glb", "usd", "usdz", "blend"],
                "target_platform": "visionos" if target == "visionos" else target,
            }
