import os
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
import trimesh
from scipy.cluster.vq import kmeans2
from pathlib import Path
import scipy.sparse as sp

@dataclass
class SemanticPart:
    part_id: str
    label: str  # e.g. 'body', 'head', 'arm', 'base', 'top', 'leg'
    mesh: trimesh.Trimesh
    face_indices: np.ndarray  # indices into original mesh
    centroid: np.ndarray
    bbox_min: np.ndarray
    bbox_max: np.ndarray
    volume_fraction: float  # fraction of total volume
    surface_area: float

class PartDecomposer:
    def __init__(self, min_part_fraction=0.02, max_parts=16, 
                 normal_clustering_threshold=0.5, category='custom'):
        self.min_part_fraction = min_part_fraction
        self.max_parts = max_parts
        self.normal_clustering_threshold = normal_clustering_threshold
        self.category = category
        
    def decompose(self, mesh: trimesh.Trimesh) -> List[SemanticPart]:
        """Full pipeline: segment → label → refine → return parts."""
        if mesh is None or mesh.is_empty:
            return []
            
        if len(mesh.faces) == 0:
            return []

        if len(mesh.faces) < 4:
            # Too small, return as single part
            part = self._create_part(mesh, np.arange(len(mesh.faces)), "0", "body")
            return [part] if part else []

        # 1. Normal-based clustering
        n_clusters = min(8, self.max_parts)
        labels = self.segment_by_normals(mesh, n_clusters=n_clusters)
        
        # 2. Refine boundaries
        labels = self.refine_boundaries(mesh, labels, iterations=3)
        
        # 3. Connected component analysis
        adj = mesh.face_adjacency
        if len(adj) > 0:
            same_label = labels[adj[:, 0]] == labels[adj[:, 1]]
            filtered_adj = adj[same_label]
            
            n_faces = len(mesh.faces)
            row = filtered_adj[:, 0]
            col = filtered_adj[:, 1]
            data = np.ones(len(row), dtype=bool)
            
            graph = sp.coo_matrix((data, (row, col)), shape=(n_faces, n_faces))
            n_components, comp_labels = sp.csgraph.connected_components(graph, directed=False)
        else:
            n_components = 1
            comp_labels = np.zeros(len(mesh.faces), dtype=int)
            
        parts = []
        for i in range(n_components):
            face_indices = np.where(comp_labels == i)[0]
            if len(face_indices) == 0:
                continue
                
            part = self._create_part(mesh, face_indices, str(i), "part")
            if part:
                parts.append(part)
                
        # 4. Filter by volume fraction
        filtered_parts = [p for p in parts if p.volume_fraction >= self.min_part_fraction]
        
        # Ensure we have at least one part if filtering removes all
        if not filtered_parts and parts:
            filtered_parts = [max(parts, key=lambda p: p.volume_fraction)]
                
        # 5. Semantic labeling heuristic
        labeled_parts = self.assign_semantic_labels(filtered_parts, self.category)
        return labeled_parts

    @staticmethod
    def _safe_volume(mesh: trimesh.Trimesh) -> float:
        """Compute mesh volume with fallback for degenerate geometry."""
        if mesh.is_empty or len(mesh.vertices) < 4:
            # Not enough points for a 3D volume, estimate from bounding box
            extents = mesh.bounding_box.extents if not mesh.is_empty else np.zeros(3)
            return float(np.prod(extents)) if np.all(extents > 0) else 1e-12
        if mesh.is_volume:
            return float(mesh.volume)
        try:
            return float(mesh.convex_hull.volume)
        except Exception:
            # Fallback: bounding box volume estimate
            extents = mesh.bounding_box.extents
            return float(np.prod(extents)) if np.all(extents > 0) else 1e-12

    def _create_part(self, original_mesh: trimesh.Trimesh, face_indices: np.ndarray, part_id: str, label: str) -> Optional[SemanticPart]:
        submesh = original_mesh.submesh([face_indices], append=True)
        if submesh.is_empty:
            return None
            
        orig_vol = self._safe_volume(original_mesh)
        if orig_vol <= 0:
            orig_vol = 1e-9

        sub_vol = self._safe_volume(submesh)
        if sub_vol < 0:
            sub_vol = 0
        
        vol_frac = sub_vol / orig_vol
        
        return SemanticPart(
            part_id=part_id,
            label=label,
            mesh=submesh,
            face_indices=face_indices,
            centroid=submesh.centroid,
            bbox_min=submesh.bounds[0],
            bbox_max=submesh.bounds[1],
            volume_fraction=vol_frac,
            surface_area=submesh.area
        )
        
    def segment_by_normals(self, mesh: trimesh.Trimesh, n_clusters=8) -> np.ndarray:
        """K-means clustering on face normals. Returns face-to-cluster labels."""
        normals = mesh.face_normals
        if len(normals) < n_clusters:
            return np.zeros(len(normals), dtype=np.int32)
            
        centroids, labels = kmeans2(normals, n_clusters, minit='points')
        return labels
        
    def segment_connected_components(self, mesh: trimesh.Trimesh) -> List[trimesh.Trimesh]:
        """Split mesh into connected components."""
        return mesh.split(only_watertight=False)
        
    def refine_boundaries(self, mesh: trimesh.Trimesh, labels: np.ndarray, iterations=3) -> np.ndarray:
        """Smooth part boundaries using face adjacency."""
        refined_labels = labels.copy()
        adj = mesh.face_adjacency
        if len(adj) == 0:
            return refined_labels
            
        for _ in range(iterations):
            new_labels = refined_labels.copy()
            for i in range(len(mesh.faces)):
                neighbors = adj[adj[:, 0] == i, 1]
                neighbors = np.append(neighbors, adj[adj[:, 1] == i, 0])
                if len(neighbors) > 0:
                    neighbor_labels = refined_labels[neighbors]
                    counts = np.bincount(neighbor_labels)
                    new_labels[i] = np.argmax(counts)
            refined_labels = new_labels
        return refined_labels
        
    def assign_semantic_labels(self, parts: List[SemanticPart], category: str) -> List[SemanticPart]:
        """Assign meaningful labels based on position and shape heuristics."""
        if not parts:
            return []
            
        parts_sorted_by_y = sorted(parts, key=lambda p: p.centroid[1])
        parts_sorted_by_vol = sorted(parts, key=lambda p: p.volume_fraction, reverse=True)
        largest_part = parts_sorted_by_vol[0]
        
        if category == 'animal':
            for p in parts:
                if p == largest_part:
                    p.label = 'body'
                elif p.centroid[1] > largest_part.centroid[1]:
                    p.label = 'head'
                else:
                    p.label = 'leg'
        elif category == 'vehicle':
            for p in parts:
                if p == largest_part:
                    p.label = 'body'
                elif p.centroid[1] < largest_part.centroid[1] and p.volume_fraction < 0.15:
                    p.label = 'wheel'
                else:
                    p.label = 'part'
        elif category == 'product':
            n = len(parts_sorted_by_y)
            for i, p in enumerate(parts_sorted_by_y):
                if i < n / 3:
                    p.label = 'base'
                elif i > 2 * n / 3:
                    p.label = 'top'
                else:
                    p.label = 'body'
        else:
            for i, p in enumerate(parts):
                p.label = f'part_{i}'
                
        return parts

    def export_parts_glb(self, parts: List[SemanticPart], output_dir: Path) -> Dict[str, str]:
        """Export each part as separate GLB file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported = {}
        for p in parts:
            filename = f"{p.label}_{p.part_id}.glb"
            filepath = output_dir / filename
            p.mesh.export(str(filepath))
            exported[p.part_id] = str(filepath)
            
        return exported

def decompose_mesh(mesh: trimesh.Trimesh, category='custom', min_part_fraction=0.02) -> List[SemanticPart]:
    """Convenience function."""
    decomposer = PartDecomposer(min_part_fraction=min_part_fraction, category=category)
    return decomposer.decompose(mesh)
