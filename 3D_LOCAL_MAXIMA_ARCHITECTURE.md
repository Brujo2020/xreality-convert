# 3D Local — Estrategia Máxima de Research, MLX y Pipeline 3D

## Visión de Producto & North Star Architecture

**3D Local** es un runtime y orquestador local de activos 3D de alta fidelidad optimizado exclusivamente para **Apple Silicon (MLX + Metal + MPS)**. En lugar de limitarse a generar un archivo `.glb` monolítico básico, **3D Local** produce **activos estructurados para producción** con separación semántica de piezas, materiales PBR, rigging, skinning, jerarquías de LOD y exportación validada para **visionOS / RealityKit**, **WebXR** y **Blender**.

---

## 1. Comando North Star CLI (`bin/3d-local`)

Ejecución unificada de extremo a extremo:

```bash
./bin/3d-local create "retro futuristic robot" \
  --quality max \
  --parts \
  --pbr \
  --rig \
  --lod \
  --target visionos
```

### Flujo de Ejecución del Pipeline:
```
Prompt / Referencia 2D
         ↓
VLM Understanding & Planning Layer
         ↓
3D Geometry Generation (Pixal3D / TRELLIS.2 MLX)
         ↓
NVIDIA PartPacker (Separación de Partes Semánticas)
         ↓
Mesh Repair & Retopología
         ↓
Smart UV Unwrapping
         ↓
Multi-Modal PBR Material Synthesis
         ↓
RigAnything (Joint Hierarchy & Skinning Weights)
         ↓
LOD Generation (LOD0 .. LOD3)
         ↓
Collision Mesh & Spatial Bounds
         ↓
3D Asset Graph (Manifest JSON)
         ↓
Exportación USDZ / GLB / USD / Blender MCP
```

---

## 2. Arquitectura Modular & Capas del Sistema

```
                 PROMPT / IMAGE / MULTIVIEW
                            │
                            ▼
              ┌────────────────────────┐
              │ 3D LOCAL ORCHESTRATOR  │
              │ MLX + Metal + MPS + CPU│
              └────────────┬───────────┘
                           │
                Capability Router (Fast/Balanced/Quality/Max)
                           │
                ┌──────────┴───────────┐
                │                      │
                ▼                      ▼
         CREATE (Pipeline)       EDIT (Partial Regeneration)
                │                      │
                ▼                      ▼
        Pixal3D / TRELLIS.2      AssetGraph Node Selection
                │
                ▼
          HIGH QUALITY MESH
                │
                ├───────────────┐
                │               │
                ▼               ▼
       NVIDIA PartPacker     Mesh Repair
                │               │
                ▼               │
        SEMANTIC PARTS          │
                └───────┬───────┘
                        ▼
                  PBR MATERIALS (Multi-Modal)
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Pixal3D      TRELLIS.2    VideoMatGen
                        │
                        ▼
                     RIGGING (RigAnything)
                        │
                        ▼
                OPTIMIZATION / LOD (LOD0..3)
                        │
                        ▼
                 3D ASSET GRAPH (Metadata & Lineage)
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
          GLB           USD          USDZ
           │             │            │
           ▼             ▼            ▼
        WebXR         Blender      visionOS / RealityKit
```

---

## 3. Matriz de Modelos e Infraestructura

| Prioridad | Modelo | Función Principal | Estrategia de Inferencia |
| :--- | :--- | :--- | :--- |
| **P0** | **TRELLIS.2 MLX** | Backbone 3D principal | Port Transformer & VAE a MLX, Voxel Kernels en Metal |
| **P0** | **Pixal3D MLX** | Flagship Image → 3D + PBR | Modelo insignia sobre TRELLIS.2 MLX |
| **P1** | **NVIDIA PartPacker** | Separación semántica de componentes | Sub-mallas independientes (`seat`, `backrest`, `legs`) |
| **P1** | **TripoSG** | Geometría ultra-rápida | Perfil `FAST` en MPS |
| **P1** | **RigAnything** | Skeleton + Skinning Weights | Articulaciones y pesos de animación |
| **P1** | **Hunyuan3D-2.1** | Reconstrucción Shape & Paint | Backend alternativo de respaldo |
| **Watch** | **Hunyuan3D-Buffalo** | Cerebro semántico de edición | Inspección y edición basada en instrucciones |
| **Watch** | **NVIDIA Meshtron** | Malla autoregresiva | Research experimental |
| **Watch** | **NVIDIA VideoMatGen** | Materiales PBR multimodales | Generación conjunta BaseColor + Normal + Roughness + Metallic |

---

## 4. Específicación del 3D Asset Graph (`AssetGraph`)

Cada activo procesado por **3D Local** genera un manifesto `AssetGraph` inmutable:

```json
{
  "asset_id": "asset_1786584547_d5e49c",
  "created_at": 1786584547.0,
  "source": {
    "prompt": "retro futuristic robot",
    "image_path": null
  },
  "generation": {
    "model": "pixal3d",
    "backend": "mlx",
    "seed": 42,
    "steps": 45,
    "device": "apple_silicon_mlx"
  },
  "geometry": {
    "triangles": 85000,
    "watertight": true,
    "master_glb_path": "jobs/local3d_assets/asset_master.glb"
  },
  "parts": {
    "root_nodes": ["root_assembly"],
    "nodes": {
      "part_1_chassis": { "name": "chassis", "triangles": 21000 },
      "part_2_head": { "name": "head", "triangles": 14000 }
    }
  },
  "materials": {
    "pbr_master_material": {
      "type": "pbr_metallic_roughness",
      "resolution": 2048
    }
  },
  "rig": {
    "has_rig": true,
    "joint_count": 8,
    "rig_model": "riganything"
  },
  "lod": {
    "lod0": { "faces": 85000 },
    "lod1": { "faces": 42500 },
    "lod2": { "faces": 17000 },
    "lod3": { "faces": 4250 }
  },
  "targets": {
    "visionos_ready": true,
    "realitykit_validated": true
  }
}
```

---

## 5. Benchmark: `3D-Local-Bench`

El marco de pruebas mide la métrica fundamental de eficiencia:

$$\text{Métrica} = \frac{\text{QUALITY\_SCORE}}{\text{GB\_RAM} \times \text{SEGUNDOS}}$$

Comando para ejecutar el benchmark:
```bash
./bin/3d-local bench --samples 10
```

---

## 6. Módulos Implementados en la Arquitectura

1. `bin/3d-local`: Ejecutable CLI principal.
2. `engine/cli_orchestrator.py`: Orquestador máster y procesador de comandos.
3. `engine/asset_graph.py`: Estructura del grafo de activos y motor de edición parcial.
4. `engine/capability_router.py`: Enrutador de capacidades (Fast, Balanced, Quality, Max).
5. `engine/models/trellis2_adapter.py`: Adaptador del backbone TRELLIS.2 MLX.
6. `engine/models/pixal3d_adapter.py`: Adaptador insignia Pixal3D.
7. `engine/models/partpacker_adapter.py`: Adaptador NVIDIA PartPacker.
8. `engine/models/triposg_adapter.py`: Adaptador TripoSG.
9. `engine/models/riganything_adapter.py`: Adaptador de rigging y skinning RigAnything.
10. `engine/models/material_generator.py`: Generador de materiales PBR multimodales.
11. `engine/blender_mcp.py`: Puente de operaciones scriptadas para Blender.
12. `engine/visionos_bridge.py`: Empaquetador y validador USDZ para visionOS / RealityKit.
13. `engine/benchmark_3d_local.py`: Suite de benchmarks `3D-Local-Bench`.
14. `engine/test_3d_local_orchestrator.py`: Suite completa de pruebas unitarias e integración.
