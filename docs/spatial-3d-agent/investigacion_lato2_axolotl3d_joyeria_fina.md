# 💎 ESTUDIO DE JOYERÍA FINA: ARQUITECTURAS LATO.2 Y NVIDIA AXOLOTL3D
## *Extracción Teórica, Desglose de Redes Neuronales y Síntesis para la Plataforma Xreality Convert & NTT Data (2026)*

---

## 📌 Resumen Ejecutivo de la Investigación

En este informe de alta precisión se desglosan las dos investigaciones más revolucionarias del panorama 3D en 2026:
1. **LATO.2 (LoHhhha / Long et al., arXiv:2607.10623):** Generación de mallas 3D factorizada mediante flujos desacoplados de Vértices (**V-Flow**) y Topología (**T-Flow**).
2. **NVIDIA Axolotl3D (NVIDIA Spatial Intelligence Lab / Hu & Shugrina, ECCV 2026):** Framework 3D unificado multimodal con inferencia amodal de partes ocultas (oclusión), control de geometría por nubes de puntos parciales y edición por instrucciones.

---

## 🧬 1. LATO.2: Generación Factorizada de Mallas (V-Flow & T-Flow)

### A. El Problema Histórico
Los modelos 3D convencionales (como LRM, CRM o Tripo 1.0) intentaban modelar las posiciones de los vértices y la conectividad de las aristas/caras en un único espacio latente acoplado. Esto provocaba **vértices flotantes (*drifting vertices*)**, **agujeros en las superficies** y una densidad de polígonos caótica e incontrolable.

### B. La Solución Factorizada de LATO.2
LATO.2 desacopla el proceso de generación en dos etapas continuas y coordinadas:

```
┌────────────────────────────────────────────────────────┐
│  Scaffold Voxelizado Grueso (Estructura de Partes)     │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  STAGE 1: V-Flow (Vertex Flow Matching)                │
│  - Genera posiciones de vértices con precisión sub-voxel│
│  - Permite prescribir el recuento exacto: 200 - 5.000  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  STAGE 2: T-Flow (Topology Flow Matching)              │
│  - Predice la conectividad (caras/aristas) sobre los   │
│    vértices generados en el Stage 1                    │
│  - Re-calcula la topología automáticamente tras editar│
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  Malla Low-Poly Limpia con Topología Adaptativa        │
└────────────────────────────────────────────────────────┘
```

### C. Características Clave de LATO.2 para Nuestro Pipeline Low-Poly (70%)
1. **Presupuesto Exacto de Vértices:** Se puede solicitar explícitamente un recuento de 500, 2.000 o 5.000 vértices para Meta Quest 3 o WebXR.
2. **Generación por Partes (Part-wise Generation):** Al particionar el scaffold, cada sub-pieza se sintetiza utilizando toda la capacidad del latente, logrando una resolución geométrica superior en ensamblajes industriales.
3. **Consumo Eficiente de VRAM:** Funciona con solo **8 GB de VRAM**, haciéndolo ideal para ejecución local en Apple Silicon / GPUs de consumo.

---

## 🐊 2. NVIDIA Axolotl3D: Framework Multimodal Unificado

### A. La Matriz de Tareas Unificadas
Como muestra la investigación del **NVIDIA Spatial Intelligence Lab (SIL)** presentada en **ECCV 2026**, Axolotl3D supera a todos los modelos competidores al unificar las 4 grandes tareas 3D en un solo modelo de difusión:

| Método | Multi-View | Occlusion (Amodal) | Geometry-Control | Editing |
| :--- | :---: | :---: | :---: | :---: |
| Amodal3R | ❌ | ✅ | ❌ | ❌ |
| SAM3D | ❌ | ✅ | ❌ | ❌ |
| Hunyuan3D-Omni | ❌ | ❌ | ✅ | ❌ |
| ShapeR | ✅ | ✅ | ✅ | ❌ |
| GENA3D | ✅ | ✅ | ✅ | ❌ |
| VecSet-Edit | ❌ | ❌ | ❌ | ✅ |
| 👑 **NVIDIA Axolotl3D** | ✅ | ✅ | ✅ | ✅ |

### B. Mecanismos Arquitectónicos de Axolotl3D
1. **Inferencia Amodal (Manejo de Oclusiones):** Utiliza máscaras de visibilidad (*visibility masks*) para predecir e inferir las superficies y partes traseras ocultas detrás de un objeto en una foto 2D.
2. **Anclas Geométricas por Nubes de Puntos Parciales (Geometry-Control):** Si se escanea un objeto parcialmente, Axolotl3D usa la nube de puntos como "ancla estructural" fijando las dimensiones reales.
3. **Edición Guiada por Instrucciones:** Permite sustituir o transformar piezas específicas sobre escenas o Gaussian Splats 3D manteniendo el alineamiento de cámara y parámetros del modelo.

---

## 🏛️ 3. Síntesis e Integración en la Arquitectura Xreality Convert & NTT Data

La fusión de **LATO.2** y **NVIDIA Axolotl3D** complementa de forma natural nuestro ecosistema **Dual-Engine (Meshy Cloud API + Local MLX)**:

```
[Entrada: Imagen 2D / Prompt / Escaneo Parcial]
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│  MODO A: 70% Standalone VR (Low-Poly Limpio)           │
│  - Geometría V-Flow + T-Flow inspirada en LATO.2       │
│  - Retopología Quad + Compresión KTX2 / Draco          │
│  - Motor Cloud: Meshy API v6 (5cr Cheap Preview)       │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  MODO B: 30% Digital Twins & PC-VR (NVIDIA Omniverse)  │
│  - Reconstrucción Amodal por Oclusión (Axolotl3D Spec) │
│  - Edición de Partes y Envolventes V-HACD              │
│  - Motor Local / High Poly: TRELLIS.2 / Rodin 3.0      │
│  - Exportación: OpenUSD (.usda / .usdz)                │
└────────────────────────────────────────────────────────┘
```

---

## 📊 4. Conclusión Técnica

* **LATO.2** aporta la solución teórica definitiva para la **retopología y control de vértices Low-Poly en local**.
* **NVIDIA Axolotl3D** aporta el estándar de **reconstrucción amodal (completar partes ocultas) y edición localizada**.
* Ambos avances están completamente alineados con el pipeline **Dual-Engine** implementado en el software `Xreality Convert` (`ollama-image-studio`).
