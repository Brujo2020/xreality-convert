"""3D Local Master Orchestrator and CLI Controller.

Implements the North Star pipeline:
3d-local create "prompt or image" --parts --pbr --rig --lod --target visionos
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Local imports
from asset_graph import AssetGraph, PartialRegenerationEngine
from capability_router import CapabilityRouter, CapabilityProfile
from models.trellis2_adapter import Trellis2Adapter
from models.pixal3d_adapter import Pixal3dAdapter
from models.partpacker_adapter import PartPackerAdapter
from models.triposg_adapter import TripoSGAdapter
from models.riganything_adapter import RigAnythingAdapter
from models.material_generator import MaterialGenerator
from blender_mcp import BlenderMCPBridge
from visionos_bridge import VisionOSBridge
from benchmark_3d_local import BenchmarkSuite3DLocal


class Orchestrator3DLocal:
    """Master Orchestrator for 3D Local."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (Path(__file__).parent / "jobs" / "local3d_assets")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        input_source: str,
        quality: str = CapabilityProfile.QUALITY,
        target: str = "webxr",
        parts: bool = False,
        pbr: bool = True,
        rig: bool = False,
        lod: bool = True,
        device: str = "mlx",
    ) -> Dict[str, Any]:
        """North Star Execution Pipeline:

        Prompt/Image -> Plan -> Geometry -> Semantic Parts -> Mesh Repair -> Topology -> UV -> PBR -> Rig -> LOD -> Collision -> GLB/USD/USDZ.
        """
        start_time = time.time()

        # Step 1: Resolve Pipeline Graph via Capability Router
        pipeline_spec = CapabilityRouter.resolve_pipeline(
            quality=quality,
            target=target,
            request_parts=parts,
            request_pbr=pbr,
            request_rig=rig,
            request_lod=lod,
        )

        is_image = Path(input_source).is_file() and Path(input_source).suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]
        prompt = "" if is_image else input_source
        image_path = Path(input_source) if is_image else None

        # Step 2: Initialize 3D Asset Graph
        graph = AssetGraph(
            prompt=prompt or (image_path.name if image_path else "3D Asset"),
            source_image=str(image_path) if image_path else None,
            model_name=pipeline_spec["backbone_model"],
            backend=device,
        )

        master_glb = self.output_dir / f"{graph.asset_id}_master.glb"
        master_usdz = self.output_dir / f"{graph.asset_id}_master.usdz"

        # Step 3: Geometry Generation
        backbone_name = pipeline_spec["backbone_model"]
        if backbone_name == "triposg":
            adapter = TripoSGAdapter(device="mps")
            geom_res = adapter.generate(image_path or master_glb, master_glb, target_faces=pipeline_spec["target_faces"])
        elif backbone_name == "trellis2":
            adapter = Trellis2Adapter(device=device)
            geom_res = adapter.generate_geometry(image_path or master_glb, steps=pipeline_spec["steps"], octree_resolution=pipeline_spec["octree_resolution"])
        else:  # Pixal3D Flagship
            adapter = Pixal3dAdapter(device=device)
            geom_res = adapter.generate(image_path or master_glb, master_glb, prompt=prompt, steps=pipeline_spec["steps"], octree_resolution=pipeline_spec["octree_resolution"], target_faces=pipeline_spec["target_faces"], pbr=pipeline_spec["pbr_materials"])

        graph.geometry["triangles"] = pipeline_spec["target_faces"]
        graph.geometry["master_glb_path"] = str(master_glb)

        # Step 4: Semantic Part Partitioning (NVIDIA PartPacker)
        parts_res = None
        if pipeline_spec["parts_separation"]:
            partpacker = PartPackerAdapter(device="cpu")
            parts_res = partpacker.decompose(master_glb, graph, category="furniture")

        # Step 5: Multi-Modal PBR Material Generation
        pbr_res = None
        if pipeline_spec["pbr_materials"]:
            mat_gen = MaterialGenerator(backend="pixal")
            pbr_res = mat_gen.generate(master_glb, graph, prompt=prompt, resolution=2048)

        # Step 6: Rigging & Skinning (RigAnything)
        rig_res = None
        if pipeline_spec["rigging"]:
            rigger = RigAnythingAdapter(device="cpu")
            rig_res = rigger.rig(master_glb, graph, category="generic")

        # Step 7: LOD Generation
        if pipeline_spec["lod_generation"]:
            graph.set_lod("lod0", str(master_glb), pipeline_spec["target_faces"])
            graph.set_lod("lod1", str(self.output_dir / f"{graph.asset_id}_lod1.glb"), int(pipeline_spec["target_faces"] * 0.5))
            graph.set_lod("lod2", str(self.output_dir / f"{graph.asset_id}_lod2.glb"), int(pipeline_spec["target_faces"] * 0.2))
            graph.set_lod("lod3", str(self.output_dir / f"{graph.asset_id}_lod3.glb"), int(pipeline_spec["target_faces"] * 0.05))

        # Step 8: visionOS / RealityKit Packaging
        usdz_res = None
        if target == "visionos" or "usdz" in pipeline_spec["export_formats"]:
            usdz_res = VisionOSBridge.validate_and_package(master_glb, master_usdz, graph)

        graph.exports["glb"] = str(master_glb)

        # Save Asset Graph JSON
        graph_json_path = self.output_dir / f"{graph.asset_id}_graph.json"
        graph.save_json(graph_json_path)

        duration = time.time() - start_time

        return {
            "status": "success",
            "asset_id": graph.asset_id,
            "pipeline_profile": pipeline_spec["profile"],
            "asset_graph_path": str(graph_json_path),
            "master_glb_path": str(master_glb),
            "master_usdz_path": str(master_usdz) if usdz_res else None,
            "parts_count": len(graph.parts),
            "joint_count": graph.rig.get("joint_count", 0),
            "lod_levels": [k for k, v in graph.lod.items() if v is not None],
            "visionos_ready": graph.targets["visionos_ready"],
            "duration_sec": round(duration, 3),
        }


def main():
    parser = argparse.ArgumentParser(prog="3d-local", description="3D Local — Local Orquestador & Runtime 3D sobre Apple Silicon")
    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponibles")

    # 3d-local create
    create_parser = subparsers.add_parser("create", help="North Star: Genera un activo 3D completo y production-ready")
    create_parser.add_argument("input", help="Prompt o ruta a imagen de referencia")
    create_parser.add_argument("--quality", choices=["fast", "balanced", "quality", "max"], default="quality", help="Nivel de calidad")
    create_parser.add_argument("--target", choices=["webxr", "visionos", "blender"], default="webxr", help="Plataforma de destino")
    create_parser.add_argument("--parts", action="store_true", help="Separación en partes semánticas (PartPacker)")
    create_parser.add_argument("--pbr", action="store_true", default=True, help="Generación de materiales PBR")
    create_parser.add_argument("--rig", action="store_true", help="Predicción de esqueleto y skinning (RigAnything)")
    create_parser.add_argument("--lod", action="store_true", default=True, help="Generación de LODs")
    create_parser.add_argument("--device", choices=["mlx", "mps", "cpu"], default="mlx", help="Backend de hardware")

    # 3d-local generate
    gen_parser = subparsers.add_parser("generate", help="Genera geometría 3D")
    gen_parser.add_argument("input", help="Ruta a imagen")
    gen_parser.add_argument("--model", choices=["pixal3d", "trellis2", "triposg"], default="pixal3d")
    gen_parser.add_argument("--device", choices=["mlx", "mps", "cpu"], default="mlx")

    # 3d-local parts
    parts_parser = subparsers.add_parser("parts", help="Decompone una malla en partes semánticas")
    parts_parser.add_argument("glb_path", help="Ruta al GLB")
    parts_parser.add_argument("--category", default="generic")

    # 3d-local rig
    rig_parser = subparsers.add_parser("rig", help="Añade rig y skinning a una malla")
    rig_parser.add_argument("glb_path", help="Ruta al GLB")
    rig_parser.add_argument("--category", default="generic")

    # 3d-local edit
    edit_parser = subparsers.add_parser("edit", help="Edición parcial de activo mediante lenguaje natural")
    edit_parser.add_argument("graph_json", help="Ruta al JSON de AssetGraph")
    edit_parser.add_argument("--instruction", required=True, help="Instrucción de modificación")

    # 3d-local bench
    bench_parser = subparsers.add_parser("bench", help="Ejecuta la suite 3D-Local-Bench")
    bench_parser.add_argument("--samples", type=int, default=5, help="Número de muestras")

    args = parser.parse_args()

    orchestrator = Orchestrator3DLocal()

    if args.subcommand == "create":
        res = orchestrator.create(
            input_source=args.input,
            quality=args.quality,
            target=args.target,
            parts=args.parts,
            pbr=args.pbr,
            rig=args.rig,
            lod=args.lod,
            device=args.device,
        )
        print(json.dumps(res, indent=2))

    elif args.subcommand == "generate":
        dummy_graph = AssetGraph(prompt="CLI Generate", source_image=args.input)
        res = orchestrator.create(input_source=args.input, quality="quality", device=args.device)
        print(json.dumps(res, indent=2))

    elif args.subcommand == "parts":
        graph = AssetGraph(prompt="CLI Parts")
        adapter = PartPackerAdapter()
        res = adapter.decompose(Path(args.glb_path), graph, category=args.category)
        print(json.dumps(res, indent=2))

    elif args.subcommand == "rig":
        graph = AssetGraph(prompt="CLI Rig")
        adapter = RigAnythingAdapter()
        res = adapter.rig(Path(args.glb_path), graph, category=args.category)
        print(json.dumps(res, indent=2))

    elif args.subcommand == "edit":
        graph = AssetGraph.load_json(args.graph_json)
        bridge = BlenderMCPBridge()
        res = bridge.process_asset_graph(graph, args.instruction)
        print(json.dumps(res, indent=2))

    elif args.subcommand == "bench":
        suite = BenchmarkSuite3DLocal()
        res = suite.run_benchmark(sample_count=args.samples)
        print(json.dumps(res, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
