import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import trimesh

from paint_service import PaintService
from pbr_glb import validate_pbr_glb


logger = logging.getLogger(__name__)


@dataclass
class RegionalPaintResult:
    output_glb: str
    parts_painted: int
    total_parts: int
    per_part_reports: List[Dict]
    merged_successfully: bool
    total_materials: int
    texture_resolution: str
    paint_duration_seconds: float


class RegionalPaintService:
    def __init__(self, paint_service_factory=None, progress_callback=None):
        if paint_service_factory is None:
            self.paint_service_factory = lambda: PaintService(progress_callback=progress_callback)
        else:
            self.paint_service_factory = paint_service_factory
        self.progress_callback = progress_callback

    def _report_progress(self, percent: int, message: str):
        if callable(self.progress_callback):
            try:
                self.progress_callback(percent, message)
            except Exception as exc:
                logger.warning(f"Progress callback raised an exception: {exc}")

    def generate_part_material_hints(
        self,
        parts: List[Any],
        category: str,
        image_path: Optional[Path] = None,
    ) -> Dict[str, str]:
        """Auto-detect material hints per part based on category + position."""
        hints = {}
        category = category.lower()
        
        for part in parts:
            part_name = getattr(part, "name", getattr(part, "part_id", "unknown")).lower()
            hint = "auto"
            
            if category == "animal":
                if any(x in part_name for x in ["body", "head", "leg", "tail"]):
                    hint = "fur"
                else:
                    hint = "auto"
            elif category == "vehicle":
                if "body" in part_name:
                    hint = "painted_metal"
                elif "wheel" in part_name or "tire" in part_name:
                    hint = "rubber"
                elif "window" in part_name or "glass" in part_name:
                    hint = "glass"
            elif category == "person":
                if "body" in part_name or "cloth" in part_name:
                    hint = "fabric"
                elif "head" in part_name or "face" in part_name or "skin" in part_name:
                    hint = "skin"
                elif "hair" in part_name:
                    hint = "hair"
            elif category == "product":
                hint = "plastic"
            elif category == "industrial":
                hint = "metal"
            
            hints[getattr(part, "part_id", part_name)] = hint
            
        return hints

    def paint_by_parts(
        self,
        mesh_path: Path,
        image_path: Path,
        parts: List[Any],
        output_dir: Path,
        texture_size: str = "2K",
        material_hints: Optional[Dict[str, str]] = None,
    ) -> RegionalPaintResult:
        """Paint each part independently, then merge into final GLB."""
        start_time = time.time()
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        final_glb_path = output_dir / "final_merged.glb"
        
        if material_hints is None:
            material_hints = {}
            
        self._report_progress(5, f"Starting regional paint for {len(parts)} parts")
        
        painted_parts = []
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            for i, part in enumerate(parts):
                part_id = getattr(part, "part_id", f"part_{i}")
                
                # Export part mesh
                part_obj_path = temp_dir_path / f"{part_id}.obj"
                
                if hasattr(part, "mesh") and hasattr(part.mesh, "export"):
                    part.mesh.export(str(part_obj_path))
                else:
                    logger.error(f"Part {part_id} does not have a valid exportable mesh.")
                    continue
                    
                hint = material_hints.get(part_id, "auto")
                part_glb_path = temp_dir_path / f"{part_id}_painted.glb"
                
                self._report_progress(
                    10 + int(80 * (i / len(parts))), 
                    f"Painting part {i+1}/{len(parts)}: {part_id} (hint: {hint})"
                )
                
                paint_service = self.paint_service_factory()
                
                try:
                    report = paint_service.run(
                        mesh_path=part_obj_path,
                        image_path=image_path,
                        output_glb_path=part_glb_path,
                        texture_size=texture_size,
                        material_profile=hint,
                        category="custom",
                        enforce_validation=False
                    )
                    
                    if part_glb_path.exists():
                        painted_parts.append({
                            "part_id": part_id,
                            "glb_path": part_glb_path,
                            "paint_report": report
                        })
                    else:
                        logger.error(f"Paint service did not produce GLB for part {part_id}")
                except Exception as e:
                    logger.error(f"Failed to paint part {part_id}: {e}")
            
            self._report_progress(90, "Merging painted parts")
            
            merged_successfully = False
            total_materials = 0
            
            try:
                merged_path = self.merge_painted_parts(painted_parts, final_glb_path)
                if merged_path and merged_path.exists():
                    merged_successfully = True
                    # Run validation
                    val_report = validate_pbr_glb(merged_path)
                    total_materials = val_report.get("materials", len(painted_parts))
            except Exception as e:
                logger.error(f"Failed to merge painted parts: {e}")
                
        duration = time.time() - start_time
        
        self._report_progress(100, "Regional paint complete")
        
        return RegionalPaintResult(
            output_glb=str(final_glb_path) if merged_successfully else "",
            parts_painted=len(painted_parts),
            total_parts=len(parts),
            per_part_reports=[p["paint_report"] for p in painted_parts],
            merged_successfully=merged_successfully,
            total_materials=total_materials,
            texture_resolution=texture_size,
            paint_duration_seconds=duration
        )

    def merge_painted_parts(
        self,
        painted_parts: List[Dict],
        output_glb: Path,
    ) -> Path:
        """Merge independently painted parts into single GLB with multi-material."""
        if not painted_parts:
            raise ValueError("No painted parts to merge")
            
        scene = trimesh.Scene()
        
        for part_data in painted_parts:
            part_id = part_data["part_id"]
            glb_path = part_data["glb_path"]
            
            try:
                part_mesh = trimesh.load(glb_path, force="mesh")
                
                if isinstance(part_mesh, trimesh.Scene):
                    for name, geom in part_mesh.geometry.items():
                        new_name = f"{part_id}_{name}"
                        scene.add_geometry(geom, node_name=new_name, geom_name=new_name)
                else:
                    scene.add_geometry(part_mesh, node_name=part_id, geom_name=part_id)
            except Exception as e:
                logger.error(f"Error loading part {part_id} for merge: {e}")
                
        output_glb = Path(output_glb)
        output_glb.parent.mkdir(parents=True, exist_ok=True)
        
        # Export as GLB
        scene.export(str(output_glb))
        
        return output_glb
