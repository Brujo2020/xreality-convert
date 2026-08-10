# 💎 ESTUDIO DE JOYERÍA FINA: DIAGRAMA NEURAL DE NVIDIA AXOLOTL3D Y LATO.2
## *Desglose de Redes Neuronales, Flujo de Tensores y Síntesis para Xreality Convert & NTT Data (2026)*

---

## 🎨 1. Análisis del Diagrama Neural de NVIDIA Axolotl3D

Basándonos en la arquitectura oficial revelada por el **NVIDIA Spatial Intelligence Lab (SIL)** para **Axolotl3D** (ECCV 2026):

```
                                  [NVIDIA AXOLOTL3D NEURAL FLOW]

Input View(s) ──────► [ ❄️ DINOv2 ] ───(+)───► [ FFN ] ───(+)───┐
                                       │                  │     │
Camera Plücker ──────► [ Linear ] ─────┘                  │     ▼
                                                          ├─► [ Condition Tokens ]
Condition Points ───► [ ❄️ VecSetX ] ────────► [ FFN ] ───(+)───┤         │
                                                          │     │         │ KV
Visible Area Mask ──► [ Patchify & Flatten ] ─────────────┘     ▼         ▼
                                                       [ Attention Mask ] ───┐
                                                                             │
Noisy Latent ────────────────────────────────────────► [ Hunyuan3D DiT ] ◄───┘
                                                        ├── Self Attention
                                                        └── Cross Attention
                                                                 │
                                                                 ▼
                                                        [ ❄️ VAE Decoder ]
                                                                 │
                                                                 ▼
                                                      [ Watertight 3D Mesh ]
```

### A. Componentes y Flujos de Tensores (Tensor Flows)
1. **Ruta de Visión (Visual Path):**
   * **Input View(s):** Imágenes multi-vista $I \in \mathbb{R}^{B \times H \times W \times 3}$.
   * **DINOv2 Encoder (Frozen):** Extrae características semánticas densas $F_{dino} \in \mathbb{R}^{B \times N_{patches} \times D}$.
   * **Camera Plücker Embeddings:** Codifica los rayos de la cámara (origen y dirección) en el espacio tridimensional:
     $$P(r) = (o \times d, d) \in \mathbb{R}^6$$
     Pasados por una capa `Linear`, se suman linealmente a las características de DINOv2.

2. **Ruta de Geometría y Oclusión (Geometric & Amodal Path):**
   * **Condition Points:** Nube de puntos 3D parciales $X_{pts} \in \mathbb{R}^{B \times N \times 3}$.
   * **VecSetX Encoder (Frozen):** Red de conjuntos de vectores que procesa puntos 3D sin orden específico.
   * **Visible Area Mask(s):** Máscara binaria que delimita qué partes son visibles y cuáles están ocluidas. Se transforma mediante `Patchify & Flatten` para formar la **Attention Mask** (Image Mask + Points Mask).

3. **Núcleo Generativo DiT y Decodificación:**
   * **Hunyuan3D DiT (Diffusion Transformer):** Recibe el *Noisy Latent* y procesa en paralelo:
     * **Self Attention:** Modela relaciones espaciales entre tokens de la malla 3D.
     * **Cross Attention:** Proyecta la información de `Condition Tokens` (Key/Value) utilizando la `Attention Mask` para guiar la reconstrucción de zonas ocluidas.
   * **VAE Decoder (Frozen):** Decodifica los latentes limpios en mallas 3D herméticas (*watertight meshes*).

---

## 🧬 2. LATO.2: Generación Factorizada (V-Flow & T-Flow)

Complementando la inferencia amodal de Axolotl3D, **LATO.2** resuelve la retopología y el control estricto de polígonos:

```
┌────────────────────────────────────────────────────────┐
│  STAGE 1: V-Flow (Vertex Flow Matching)                │
│  - Vértices 3D con precisión sub-voxel                 │
│  - Presupuesto exacto prescrito: 200 a 5.000 vértices  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  STAGE 2: T-Flow (Topology Flow Matching)              │
│  - Predice la conectividad cuadrangular (Quads/Tris)   │
│  - Malla limpia lista para VR Standalone (Quest 3)     │
└────────────────────────────────────────────────────────┘
```

---

## 🏆 3. La Estrategia Híbrida "10 de 10" para Campeonar en 2026

```
                    ┌──────────────────────────────────────────────┐
                    │      XREALITY CONVERT 3D AGENTIC SYSTEM      │
                    └──────────────────────┬───────────────────────┘
                                           │
             ┌─────────────────────────────┴─────────────────────────────┐
             ▼                                                           ▼
┌─────────────────────────────────────────┐  ┌─────────────────────────────────────────┐
│ MODO LOCAL OFFLINE (Campeón 8GB VRAM)   │  │ MODO CLOUD HYBRID (Meshy API v6)        │
│ ─────────────────────────────────────── │  │ ─────────────────────────────────────── │
│ 1. NVIDIA Axolotl3D: Inferencia amodal  │  │ 1. Cheap Preview Filter (5 créditos)    │
│    de partes ocultas y oclusión.        │  │    Borrador ultrarrápido en la nube.    │
│ 2. LATO.2: V-Flow (posicionamiento de   │  │ 2. Refine PBR 8K (20 créditos)          │
│    vértices) + T-Flow (topología quad). │  │    Texturizado De-lit profesional.      │
│ 3. MLX Hunyuan3D: Difusión local.       │  │ 3. Quad Remesh & Exportación OpenUSD.   │
└─────────────────────────────────────────┘  └─────────────────────────────────────────┘
```

---

## 📌 Estado de Descarga de Checkpoints LATO.2 Local

Los pesos del modelo LATO.2 están descargándose en segundo plano en `tmp/LATO.2/ckpt/` desde Hugging Face (`0x4c48/LATO.2`) para ejecutar las pruebas locales tan pronto finalice la descarga.
