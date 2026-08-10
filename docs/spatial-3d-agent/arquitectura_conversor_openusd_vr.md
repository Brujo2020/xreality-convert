# Arquitectura Industrial: Conversor 3D IA a OpenUSD VR-Ready & Piezas Segmentadas (Agosto 2026)

## 📐 1. Filosofía de Diseño del Sistema

Para lograr activos **VR-Ready (Meta Quest 3, Apple Vision Pro, OpenXR)** partiendo de mallas generadas por IA, el sistema debe resolver cuatro cuellos de botella críticos:
1. **Presupuesto de Draw Calls en VR:** Máximo 50–100 Draw Calls por frame para mantener 90/120 FPS sin latencia.
2. **Geometría Desarticulada (Segmentación de Partes):** Las mallas IA suelen ser una sola "escultura colapsada". El conversor debe separar partes (ruedas, puertas, armas, extremidades, accesorios) en nodos independientes (`UsdGeom.Xform`) para permitir rigging, animaciones y físicas relativas.
3. **Supercompresión VRAM (Basis Universal / KTX2):** Texturas PBR comprimidas que se transcodifican directamente en GPU (ASTC/BC7) reduciendo el consumo de memoria de textura en un 75%.
4. **Formato Estándar Industrial (Pixar OpenUSD / USDZ):** Jerarquía de escena profesional basada en Schemas de USD con `VariantSets` para niveles de detalle (LOD0, LOD1, LOD2).

---

## 🏗️ 2. Diagrama del Pipeline de Conversión (End-to-End)

```
┌────────────────────────────────────────────────────────┐
│  Malla de Entrada IA (GLB / FBX / Meshy / TRELLIS)    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ FASE 1: Segmentación Topológica y Descomposición 3D    │
│ - Análisis de Componentes Conexas (Trimesh / Bounding) │
│ - V-HACD (Volumetric Hierarchical Convex Hull)        │
│ - Mapeo de Nodos Jerárquicos en UsdGeom.Xform         │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ FASE 2: Retopología Low-Poly VR & Generación de LODs   │
│ - MeshAnything v2 / gltfpack (Decimado QSLIM)          │
│ - LOD0 (Hero: <= 15k tris)                             │
│ - LOD1 (Mid VR: <= 4k tris)                            │
│ - LOD2 (Far/Impostor: <= 1k tris)                      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ FASE 3: Texture Atlas Packing & Compresión KTX2        │
│ - De-lighting de Albedo (Eliminación de Sombras)       │
│ - Packing PBR: ORM (Occlusion + Roughness + Metallic) │
│ - Transcodificación KTX2 / Basis Universal             │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ FASE 4: Ensamblado de Stage OpenUSD y empaquetado USDZ │
│ - Authoring Python `pxr` (UsdStage, UsdGeom, UsdShade)  │
│ - Definición de VariantSets de LOD y Materiales        │
│ - Empaquetado `usdzip` final (.usdz)                   │
└────────────────────────────────────────────────────────┘
```

---

## 🧩 3. Estrategia de Segmentación de Partes y Piezas Separadas

Para convertir una malla IA "mono-bloque" en un ensamblaje modular:

### A. Algoritmo de Segmentación Geométrica
1. **Separación por Componentes Conexas:** El conversor analiza las matrices de adyacencia de caras. Si el objeto contiene piezas flotantes no soldadas (ej. la empuñadura y la hoja de una espada, las ruedas de un vehículo), se dividen instantáneamente en sub-mallas.
2. **Segmentación por Curvatura y Color UV:** Identificación de bordes duros (*sharp creases*) y discontinuidades de mapas normales para partir piezas complejas.
3. **V-HACD para Físicas y Rigging:** Cada sub-pieza pasa por V-HACD para generar su envolvente convexa (*Convex Hull*), esencial para colisiones físicas en motores como Unreal, Unity u Omniverse.

### B. Estructura de Escena en OpenUSD
En lugar de empaquetar geometría plana, el conversor genera una estructura basada en el estándar Pixar OpenUSD:

```usd
#usda 1.0
(
    defaultPrim = "VehiculoFuturista"
    metersPerUnit = 1.0
    upAxis = "Y"
)

def Xform "VehiculoFuturista"
{
    def Scope "Materials"
    {
        def Material "PBR_Chasis"
        {
            # Definiendo UsdPreviewSurface con mapas KTX2/Basis
        }
    }

    def Xform "Pieza_Chasis" (
        kind = "component"
    )
    {
        def Mesh "Mesh_LOD0"
        {
            # Geometría Low-Poly Chasis
        }
    }

    def Xform "Pieza_Rueda_Delantera_Izq"
    {
        # Permite rotación o animación independiente de la rueda
        matrix4d xformOp:transform = ( (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0.5, 0.2, 1.2, 1) )
        uniform token[] xformOpOrder = ["xformOp:transform"]

        def Mesh "Mesh_LOD0"
        {
            # Geometría Rueda
        }
    }
}
```

---

## ⚡ 4. Especificaciones VR-Ready (OpenXR / Vision Pro / Meta Quest 3)

| Parámetro de Rendimiento | Límite Máximo en VR | Optimización del Conversor |
| :--- | :--- | :--- |
| **Polygon Count Total** | < 100,000 Triángulos por Escena | Decimado QSLIM / MeshAnything v2 con LODs automáticos |
| **Draw Calls** | < 50 Draw Calls por Marco | **Texture Packing (Atlasing):** Fusiona mapas PBR de múltiples piezas en 1 sola textura |
| **Formato de Texturas VRAM** | KTX2 / Basis Universal | Transcodificación UASTC / ETC1S a formatos nativos de GPU (ASTC en Vision Pro / Quest) |
| **Geometría Compresiva** | Draco 14-bit Position | Múltiples niveles de quantización sin pérdida visual percibida a 90Hz |
| **Origin / Pivot Point** | `origin_at: "bottom"` | Punto pivote fijado en 0,0,0 en la base para instanciación limpia por código |

---

## 🛠️ 5. Ejecución del Conversor desde Terminal (CLI)

Para procesar cualquier modelo generado por IA o descargado en `.glb` / `.fbx`:

```bash
# Instalar dependencias necesarias
pip install pxr-usd trimesh numpy Pillow pyvhacd

# Ejecutar el conversor Python sobre un activo 3D
python3 conversor_openusd_vr_ready.py --input mis_modelos/robot_ia.glb --output_dir dist_usdz/
```

El conversor procesará automáticamente la segmentación por piezas, la reducción de polígonos, la jerarquía USD y empaquetará el archivo final `.usdz` listo para AR/VR.
