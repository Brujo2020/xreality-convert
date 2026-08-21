"""3D Asset Graph specification and partial regeneration engine for 3D Local.

The Asset Graph is the immutable control-plane model for every 3D asset in 3D Local.
It records the complete lineage, semantic part hierarchy, PBR materials, skeletal
rigs, level-of-detail (LOD) variations, and export targets.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Union


class AssetGraphNode:
    """Represents a semantic node within an asset (e.g., seat, backrest, leg_1)."""

    def __init__(
        self,
        node_id: str,
        name: str,
        category: str = "generic",
        mesh_path: Optional[str] = None,
        triangles: int = 0,
        bbox: Optional[Dict[str, List[float]]] = None,
        transform_matrix: Optional[List[float]] = None,
        material_id: Optional[str] = None,
        children: Optional[List[str]] = None,
    ):
        self.node_id = node_id
        self.name = name
        self.category = category
        self.mesh_path = mesh_path
        self.triangles = triangles
        self.bbox = bbox or {"min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5]}
        self.transform_matrix = transform_matrix or [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0
        ]
        self.material_id = material_id
        self.children = children or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "category": self.category,
            "mesh_path": self.mesh_path,
            "triangles": self.triangles,
            "bbox": self.bbox,
            "transform_matrix": self.transform_matrix,
            "material_id": self.material_id,
            "children": self.children,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AssetGraphNode":
        return cls(
            node_id=data.get("node_id", str(uuid.uuid4())[:8]),
            name=data.get("name", "part"),
            category=data.get("category", "generic"),
            mesh_path=data.get("mesh_path"),
            triangles=data.get("triangles", 0),
            bbox=data.get("bbox"),
            transform_matrix=data.get("transform_matrix"),
            material_id=data.get("material_id"),
            children=data.get("children", []),
        )


class AssetGraph:
    """Immutable asset container tracking 3D generation, parts, PBR, rig, LODs, and exports."""

    def __init__(
        self,
        asset_id: Optional[str] = None,
        prompt: str = "",
        source_image: Optional[str] = None,
        model_name: str = "pixal3d",
        backend: str = "mlx",
        seed: int = 42,
    ):
        self.asset_id = asset_id or f"asset_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self.created_at = time.time()
        self.updated_at = self.created_at

        # Lineage & Source
        self.source = {
            "prompt": prompt,
            "image_path": source_image,
            "multiview": [],
        }

        # Generation Config & Execution
        self.generation = {
            "model": model_name,
            "backend": backend,
            "seed": seed,
            "steps": 30,
            "guidance": 6.0,
            "device": "apple_silicon_mlx",
            "execution_duration_sec": 0.0,
            "peak_memory_mb": 0.0,
        }

        # Main Geometry Summary
        self.geometry = {
            "representation": "mesh",
            "triangles": 0,
            "vertices": 0,
            "watertight": True,
            "manifold": True,
            "bounds_mm": [100.0, 100.0, 100.0],
            "master_glb_path": None,
        }

        # PartPacker Semantic Node Hierarchy
        self.parts: Dict[str, AssetGraphNode] = {}
        self.root_nodes: List[str] = []

        # PBR Materials Map
        self.materials: Dict[str, Dict[str, Any]] = {
            "default_pbr": {
                "type": "pbr_metallic_roughness",
                "base_color_factor": [1.0, 1.0, 1.0, 1.0],
                "metallic_factor": 0.1,
                "roughness_factor": 0.5,
                "maps": {
                    "basecolor": None,
                    "normal": None,
                    "roughness": None,
                    "metallic": None,
                    "ao": None,
                    "emissive": None,
                },
            }
        }

        # Skeleton & Skinning Rig
        self.rig = {
            "has_rig": False,
            "joint_count": 0,
            "rig_model": "riganything",
            "skeleton_path": None,
            "joints": [],
        }

        # Level of Detail (LOD) Meshes
        self.lod = {
            "lod0": None,  # High poly (master)
            "lod1": None,  # Mid poly (game ready ~50%)
            "lod2": None,  # Low poly (XR / mobile ~20%)
            "lod3": None,  # Ultra low poly (far distance ~5%)
        }

        # Exports
        self.exports: Dict[str, Optional[str]] = {
            "glb": None,
            "usd": None,
            "usdz": None,
            "blend": None,
        }

        # Compliance & Targets
        self.targets = {
            "visionos_ready": False,
            "realitykit_validated": False,
            "webxr_ready": False,
            "blender_mcp_compatible": True,
        }

    def add_node(self, node: AssetGraphNode, parent_id: Optional[str] = None) -> None:
        """Add a semantic part node into the hierarchy."""
        self.parts[node.node_id] = node
        if parent_id and parent_id in self.parts:
            if node.node_id not in self.parts[parent_id].children:
                self.parts[parent_id].children.append(node.node_id)
        else:
            if node.node_id not in self.root_nodes:
                self.root_nodes.append(node.node_id)
        self.updated_at = time.time()

    def get_node(self, node_id: str) -> Optional[AssetGraphNode]:
        return self.parts.get(node_id)

    def update_material(self, material_id: str, material_data: Dict[str, Any]) -> None:
        """Update or register a PBR material profile."""
        self.materials[material_id] = material_data
        self.updated_at = time.time()

    def set_lod(self, lod_level: str, glb_path: str, faces: int) -> None:
        """Assign a Level of Detail mesh path and polycount."""
        if lod_level in self.lod:
            self.lod[lod_level] = {
                "path": glb_path,
                "faces": faces,
                "created_at": time.time(),
            }
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "generation": self.generation,
            "geometry": self.geometry,
            "parts": {
                "root_nodes": self.root_nodes,
                "nodes": {nid: node.to_dict() for nid, node in self.parts.items()},
            },
            "materials": self.materials,
            "rig": self.rig,
            "lod": self.lod,
            "exports": self.exports,
            "targets": self.targets,
        }

    def save_json(self, output_path: Union[str, Path]) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load_json(cls, input_path: Union[str, Path]) -> "AssetGraph":
        path = Path(input_path)
        data = json.loads(path.read_text(encoding="utf-8"))

        graph = cls(
            asset_id=data.get("asset_id"),
            prompt=data.get("source", {}).get("prompt", ""),
            source_image=data.get("source", {}).get("image_path"),
            model_name=data.get("generation", {}).get("model", "pixal3d"),
            backend=data.get("generation", {}).get("backend", "mlx"),
            seed=data.get("generation", {}).get("seed", 42),
        )

        graph.created_at = data.get("created_at", time.time())
        graph.updated_at = data.get("updated_at", time.time())
        graph.source = data.get("source", graph.source)
        graph.generation = data.get("generation", graph.generation)
        graph.geometry = data.get("geometry", graph.geometry)
        graph.materials = data.get("materials", graph.materials)
        graph.rig = data.get("rig", graph.rig)
        graph.lod = data.get("lod", graph.lod)
        graph.exports = data.get("exports", graph.exports)
        graph.targets = data.get("targets", graph.targets)

        parts_data = data.get("parts", {})
        graph.root_nodes = parts_data.get("root_nodes", [])
        nodes_dict = parts_data.get("nodes", {})
        for nid, ndata in nodes_dict.items():
            graph.parts[nid] = AssetGraphNode.from_dict(ndata)

        return graph


class PartialRegenerationEngine:
    """Engine allowing selective re-generation or modification of specific asset nodes."""

    @staticmethod
    def modify_node(
        graph: AssetGraph,
        node_id: str,
        action: str,
        params: Dict[str, Any]
    ) -> AssetGraph:
        """Modify a single semantic node (e.g. resize leg, change material, remove arm)

        without re-computing unaffected parts.
        """
        node = graph.get_node(node_id)
        if not node:
            raise ValueError(f"Node '{node_id}' not found in AssetGraph {graph.asset_id}")

        if action == "scale":
            factors = params.get("scale_factors", [1.0, 1.0, 1.0])
            mat = list(node.transform_matrix)
            mat[0] *= factors[0]
            mat[5] *= factors[1]
            mat[10] *= factors[2]
            node.transform_matrix = mat

        elif action == "change_material":
            new_mat_id = params.get("material_id", "custom_pbr")
            if new_mat_id in graph.materials:
                node.material_id = new_mat_id

        elif action == "remove":
            if node_id in graph.parts:
                del graph.parts[node_id]
            if node_id in graph.root_nodes:
                graph.root_nodes.remove(node_id)

        graph.updated_at = time.time()
        return graph
