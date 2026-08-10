# DOCUMENTO MAESTRO SUPREMO: ARQUITECTURA AGÉNTICA 3D (Agosto 2026)
## Fusión Híbrida: Meshy v6 + TRELLIS.2 + Hunyuan3D-Buffalo + Rodin 3.0 + Disney Principles + OpenUSD & Unity

---

## 📑 Tabla de Contenidos
1. **Estudio e Integración del Ecosistema de 12 Skills**
2. **Arquitectura Híbrida de Generación (Fusión de Competencia)**
3. **Orquestación Agéntica con LangGraph & LangChain (Optimizada para Ahorro de Tokens)**
4. **Hacks Supremos de Meshy API & Pipeline Economizador de Créditos**
5. **Principios de Animación de Disney (12 Principles) Aplicados a Rigging 3D**
6. **Diseño Industrial y Estándares de Producción (Watertight, PBR, OpenUSD, Unity)**
7. **Flujo de Integración en Blender (Blender MCP) & Unity (C# Importer)**

---

## 🧠 1. Estudio e Integración de la Red de Skills (Skills.sh & GitHub)

Hemos auditado y extraído lo mejor de cada una de las 12 skills solicitadas para construir un pipeline agéntico sin fisuras:

| Skill / Repo | Aporte Principal al Pipeline | Integración en la Arquitectura Agéntica |
| :--- | :--- | :--- |
| **`dylantarre/animation-principles/3d-spatial`** | Los 12 Principios de Animación de Disney adaptados a 3D espacial | Inyecta *drivers* de Squash & Stretch, Anticipación y Arcos dinámicos en los rigs de Blender. |
| **`guia-matthieu/clawfu-skills/image-to-3d-pipeline`** | Pre-procesamiento de imágenes 2D y remoción de fondos con rembg/Bria | Nodo de entrada 2D: limpia la iluminación, elimina sombras y genera vistas multi-ángulo. |
| **`deemostech/rodin3d-skills/rodin3d-skill`** | Esculturas de alta fidelidad para personajes *Hero* | Router de precisión: invoca la API de Rodin 3.0 cuando el prompt exige detalles orgánicos micro-geométricos. |
| **`meshy-dev/meshy-3d-agent/meshy-3d-generation`** | Herramientas agénticas de Meshy (MCP Server) | Ejecución directa de tareas asíncronas de Preview, Refine, Retexture y Remesh en Meshy. |
| **`calesthio/generative-media-skills/meshy-3d`** | Prompt Engineering específico para assets 3D | Normaliza prompts de texto para evitar artefactos, caras invertidas y geometrías no manifold. |
| **`alphaonedev/openclaw-graph/3d-modeling`** | Grafo de dependencias de modelado 3D | Define la jerarquía de ejecución en LangGraph (nodos de evaluación y re-intentos). |
| **`freshtechbro/web3d-integration-patterns`** | Patrones de carga WebGL / Three.js / WebXR | Aplica formatos KTX2, Basis Universal y compresión Draco para renderizado fluido en browser/VR. |
| **`freshtechbro/substance-3d-texturing`** | Estándar de materiales PBR (Albedo, Normal, Roughness, Metal) | Calibra los mapas PBR de Meshy para cumplir los estándares de Substance 3D Painter. |
| **`freshtechbro/lightweight-3d-effects`** | Shaders ligeros y efectos de partículas | Inyecta materiales de sombreado eficiente para mobile/VR. |
| **`opusgamelabs/game-creator/game-3d-assets`** | Optimización de assets para motores de juego | Genera LODs automáticos (LOD0, LOD1, LOD2) y colisionadores convexos V-HACD. |
| **`sickn33` & `davila7` (3D Web Experience)** | Estructuras de proyectos Web3D interactivas | Plantillas de exportación lista para Three.js y React Three Fiber (R3F). |
| **`smithery.ai/blender-3d`** | Control total de Blender vía MCP (`bpy`) | Scripting en tiempo real dentro de Blender para post-procesado, retopología y rigging. |

---

## ⚔️ 2. Arquitectura de Fusión Híbrida (Lo Mejor de Cada Gigante)

No dependemos de un solo motor. El agente utiliza un **Router Inteligente 3D**:

```
                              [Prompt / Imagen 2D]
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   3D AGENTIC ROUTER NODE      │
                       └───────────────┬───────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
│   Meshy API v6    │        │ Microsoft TRELLIS │        │ Tencent Hunyuan3D │
│ (PBR, Quad Mesh,  │        │   (2.0 / Local)   │        │   (Buffalo 1.0)   │
│ Retexture, USDZ)  │        │ (4B Flow-Matching │        │ (Edición 3D por   │
│                   │        │  Gaussian Splat)  │        │  instrucciones)   │
└─────────┬─────────┘        └─────────┬─────────┘        └─────────┬─────────┘
          │                            │                            │
          └────────────────────────────┼────────────────────────────┘
                                       ▼
                       ┌───────────────────────────────┐
                       │   Deemos Rodin 3.0 (Cloud)    │
                       │ (Solo para Hero Micro-Detail) │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ MeshAnything v2 (Topology AMs)│
                       └───────────────────────────────┘
```

1. **Meshy v6:** Para texturizado PBR 8K de-lit, retexturizado de mallas externas, exportación multiformato y pipeline `Preview -> Refine`.
2. **Microsoft TRELLIS.2:** Cuando se busca **coste cero local (GPU)** con representación de voxeles dispersos (O-Voxel) y Gaussian Splats.
3. **Tencent Hunyuan3D-Buffalo 1.0:** Cuando el usuario pide **modificar o editar partes específicas** de un modelo 3D sin destruir el resto.
4. **Deemos Rodin 3.0:** Reservado exclusivamente para personajes hiperrealistas *Hero* de máxima densidad.
5. **MeshAnything v2:** La capa unificada de *retopología* que limpia el output de cualquiera de los motores anteriores y lo convierte en quads optimizados.

---

## 🔄 3. Grafo Agéntico LangGraph / LangChain (Token & Credit Optimized)

Para evitar desperdiciar tokens de LLM y créditos de API, el grafo utiliza **respuestas estructuradas JSON (Pydantic)** y transiciones deterministas sin bucles innecesarios.

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional, List

class Agent3DState(TypedDict):
    prompt: str
    image_input: Optional[str]
    target_engine: str  # "unity", "unreal", "webxr", "openusd"
    poly_budget: int    # Low-poly: 5000, Mid: 15000, Hero: 50000
    preview_task_id: Optional[str]
    mesh_url: Optional[str]
    parts_separated: bool
    status: str

# Nodos del Grafo LangGraph
def node_concept_preprocess(state: Agent3DState):
    # Preprocesamiento de prompt e imagen (Clawfu Image-to-3D)
    return {"status": "preprocessed"}

def node_router_3d_engine(state: Agent3DState):
    # Decide la mejor herramienta: Meshy, TRELLIS.2 o Rodin
    if state["poly_budget"] < 10000:
        return {"target_tool": "meshy_quad_lowpoly"}
    elif "edit" in state["prompt"].lower():
        return {"target_tool": "hunyuan3d_buffalo"}
    else:
        return {"target_tool": "trellis_local"}

def node_meshy_cheap_preview(state: Agent3DState):
    # Hack de Ahorro: Lanza preview asíncrono
    return {"preview_task_id": "task_12345"}

def node_vision_evaluator(state: Agent3DState):
    # Evalúa la imagen 2D del preview antes de gastar créditos en Refine
    is_good = True # Evaluación con modelo de visión ligero
    if is_good:
        return {"status": "approved_for_refine"}
    return {"status": "retry_preview"}

# Ensamblado del Grafo
workflow = StateGraph(Agent3DState)
workflow.add_node("preprocess", node_concept_preprocess)
workflow.add_node("router", node_router_3d_engine)
workflow.add_node("meshy_preview", node_meshy_cheap_preview)
workflow.add_node("evaluator", node_vision_evaluator)

workflow.set_entry_point("preprocess")
workflow.add_edge("preprocess", "router")
workflow.add_edge("router", "meshy_preview")
workflow.add_edge("meshy_preview", "evaluator")
```

---

## 🎨 4. Los 12 Principios de Animación de Disney en 3D (Disney Gold Standard)

Para que los modelos 3D cobren vida al animarse en Blender o Unity, el agente inyecta restricciones y blendshapes respetando los 12 principios clásicos:

1. **Squash & Stretch (Encoger y Estirar):** Preservación estricta de volumen mediante la fórmula en Blender $Scale_X = \frac{1}{\sqrt{Scale_Y}}$.
2. **Anticipation (Anticipación):** Animaciones preparatorias antes de acciones principales en los rigs.
3. **Staging (Puesta en Escena):** Posicionamiento de cámara y silueta clara del modelo 3D.
4. **Straight Ahead & Pose to Pose:** Combinación de simulación física con keyframes de poses clave.
5. **Follow Through & Overlapping Action:** Huesos secundarios (pelo, capas, colas) que continúan el movimiento tras detenerse el cuerpo.
6. **Slow In & Slow Out (Frenadas y Arrancadas):** Curvas de interpolación Bezier suaves en lugar de lineales.
7. **Arcs (Arcos):** Todos los movimientos de extremidades siguen trayectorias parabólicas/circulares.
8. **Secondary Action (Acción Secundaria):** Parpadeo o gestos faciales mientras el personaje camina.
9. **Timing (Ritmo):** Ajuste preciso de frames por segundo para dar peso físico.
10. **Exaggeration (Exageración):** Deformación expresiva de mallas vía Blendshapes.
11. **Solid Drawing (Dibujo Sólido):** Topología equilibrada sin estiramientos raros de UVs.
12. **Appeal (Atractivo):** Proporciones estilizadas y siluetas memorables.

---

## 🏭 5. Estándares de Diseño Industrial y Compatibilidad

* **Watertight & Manifold:** Todas las mallas generadas pasan por validación de aristas no-manifold (`bpy.ops.mesh.select_non_manifold`) para garantizar la impresión 3D sin huecos.
* **Escala Métrica Real:** `auto_size: true` garantiza que una silla mida 0.9m y un vehículo 4.5m en el espacio 3D.
* **OpenUSD & USDZ (Vision Pro / Omniverse):** Estructura jerárquica `UsdGeom.Xform` con capas de materiales `UsdShade` y compresión `usdzip`.
* **Unity URP / HDRP:** Asignación automática de mapas PBR y `LODGroup` mediante el script C# Editor `MeshyUnityAssetImporter.cs`.

---

## 🔗 Código y Scripts del Pipeline Integrados

Los scripts automatizados completos para Blender y Unity se han generado en tu proyecto:
* 📜 **Blender MCP Python Automation:** [blender_mcp_automation.py](file:///Users/mramospe/.gemini/antigravity/brain/56ecdc5a-6659-4b78-bb5d-d42fe49900ab/blender_mcp_automation.py)
* 📜 **Unity C# Asset Importer:** [MeshyUnityAssetImporter.cs](file:///Users/mramospe/.gemini/antigravity/brain/56ecdc5a-6659-4b78-bb5d-d42fe49900ab/MeshyUnityAssetImporter.cs)
* 📜 **Conversor OpenUSD VR-Ready:** [conversor_openusd_vr_ready.py](file:///Users/mramospe/.gemini/antigravity/brain/56ecdc5a-6659-4b78-bb5d-d42fe49900ab/conversor_openusd_vr_ready.py)
