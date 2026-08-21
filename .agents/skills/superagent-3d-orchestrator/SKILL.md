---
name: superagent-3d-orchestrator
description: "Orquestador supremo de superagentes 3D para xreality-convert / ollama-image-studio (2026). Integra agentes offline/online, los 5 hacks de Meshy API, LATO.2 V-Flow/T-Flow, NVIDIA Axolotl3D, 3DGenStudio MeshTools, 70% VR Low-Poly + 30% OpenUSD Omniverse."
---

# 👑 SUPERAGENT 3D ORCHESTRATOR (SKILL REVELACIÓN 2026)

## 📌 Visión de los 4 Superagentes Orquestadores

```
                             ┌──────────────────────────────────────┐
                             │       MASTER ORCHESTRATOR AGENT      │
                             │ (Router Multimodal & Decision Engine)│
                             └──────────────────┬───────────────────┘
                                                │
          ┌──────────────────────┬──────────────┴───────┬──────────────────────┐
          ▼                      ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  LOCAL GENIUS    │   │   CLOUD TITAN    │   │  VR OMNIVERSE    │   │   QUALITY GATE   │
│     AGENT        │   │      AGENT       │   │      AGENT       │   │      AGENT       │
│  (Offline MLX /  │   │ (Meshy API v6 +  │   │  (70% Low-Poly   │   │ (Watertight /    │
│  LATO.2 8GB VRAM)│   │  5 Hacks Ahorro) │   │  + 30% OpenUSD)  │   │ Disney #1 Vol)   │
└──────────────────┘   └──────────────────┘   └──────────────────┘   └──────────────────┘
```

---

## ⚡ Los 5 Hacks Máximos de Economía y Rendimiento (100% Incluidos)

1. **Hack #1: Cheap Preview Filter (Filtro de Previsualización Económica)**
   - Genera 4 borradores candidate a 5 créditos en `mode: "preview"`.
   - Selecciona el mejor borrador mediante puntuación visual AI.
   - Aplica `mode: "refine"` (20 créditos) usando `preview_task_id`.
   - **Resultado:** Ahorro del 60-75% de créditos (40cr vs 100cr por activo).

2. **Hack #2: Zero-Cost Multi-Format Conversion via Local Trimesh / OpenUSD**
   - Solicita **únicamente `.glb`** a la nube.
   - Pide a los scripts locales Python (`pxr` / `trimesh`) que conviertan a `.usdz`, `.stl`, `.obj`, `.fbx` y `.ply`.
   - **Resultado:** 0 créditos gastados en descargas de formatos adicionales.

3. **Hack #3: PBR De-Lighting Nativo (`remove_lighting: true`)**
   - Fuerza `remove_lighting: true` en el payload REST para eliminar sombras direccionales horneadas.
   - **Resultado:** Mapas Albedo/Roughness/Normal puros listos para iluminación dinámica en WebXR y Meta Quest 3.

4. **Hack #4: Quad Retopology Pre-budgeting (`topology: "quad"`, `target_polycount`)**
   - Prescribe la topología cuadrangular e introduce el presupuesto exacto:
     - `5.000` tris para VR Low-Poly (Meta Quest 3)
     - `12.000` tris para Juegos Estándar
     - `30.000` tris para Hero Assets / Digital Twins
   - **Resultado:** Mallas limpias listas para rigging sin pasar horas en Blender.

5. **Hack #5: Non-Blocking Async Polling & Local Disk Cache (`meshy-cache/`)**
   - Guarda los IDs de tarea en `~/Library/Application Support/XrealityConvert/meshy-cache/`.
   - **Resultado:** Sondeo resiliente. Si se interrumpe la red, se reconecta al ID existente sin gastar créditos nuevos.

---

## 🏛️ Matriz de Producción XR: 70% VR Low-Poly + 30% OpenUSD PC-VR

* **70% Standalone VR (Meta Quest 3 / WebXR):**
  - Mallas LATO.2 (V-Flow/T-Flow) de 500 a 5.000 vértices.
  - Texturas GLTF optimizadas con compresión KTX2 / Draco.
  - Alineamiento de pivote: `origin_at: "bottom"`.
* **30% Hiperrealismo PC-VR (HTC VIVE Focus / NVIDIA Omniverse):**
  - Inferencia amodal de oclusiones con **NVIDIA Axolotl3D**.
  - Descomposición física convexa V-HACD.
  - Exportación jerárquica OpenUSD (`UsdGeom.Xform` + VariantSets de LOD).

---

## 🎭 Inyección de Principios de Animación de Disney

Aplica el **Principio #1 de Disney (Squash & Stretch)** conservando el volumen tridimensional:

$$Scale_X = \frac{1}{\sqrt{Scale_Y}}, \quad Scale_Z = \frac{1}{\sqrt{Scale_Y}}$$

Esto previene deformaciones irreales durante animaciones interactivas en motores 3D.
