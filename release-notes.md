# Xreality Convert v1.7.0 — 3D Local Maximum Architecture Release

## 🚀 Novedades y Orquestador 3D Local

1. **Orquestador CLI 3D Local (`./bin/3d-local`)**: Interfaz de línea de comandos para la ejecución de pipelines 3D completos (`Prompt/Image → VLM Plan → Geometría MLX → PartPacker → Repair → UV → PBR → Rigging → LODs → USDZ visionOS`).
2. **Grafo de Activos 3D (`AssetGraph`)**: Manifiesto inmutable de linaje y metadatos con soporte para regeneración y modificación parcial de piezas sin re-computar el objeto completo.
3. **Capability Router Adaptativo (Fast, Balanced, Quality, Max)**: Enrutador de capacidades que selecciona automáticamente los mejores modelos (Pixal3D, TRELLIS.2 MLX, PartPacker, TripoSG, RigAnything, VideoMatGen) según la plataforma objetivo.
4. **Empaquetador visionOS & RealityKit (`VisionOSBridge`)**: Exportación y validación estricta de activos USDZ con anchuras espaciales y mallas de colisión para Apple Vision Pro y Quick Look.
5. **Separación de Piezas Semánticas (NVIDIA PartPacker)**: Descomposición de mallas monolíticas en sub-componentes independientes (`seat`, `backrest`, `legs`) para interacción y físicas en XR.
6. **Auto-Rigging y Skinning (RigAnything)**: Predicción de articulaciones y cálculo de matrices de skinning para activos animados.
7. **Suite de Benchmarks (`3D-Local-Bench`)**: Medición automatizada con la métrica principal `QUALITY / GB / SECOND`.
8. **Visor 3D WebGL con Iluminación Studio & Badges HUD**: Visualización PBR perfeccionada con luz de relleno y badges de telemetría y calidad flotantes en tiempo real.
9. **Sondeo Adaptativo Meshy API v6**: Detección acelerada a 750ms para entrega de activos en la nube de baja latencia.

Validación: 13/13 pruebas del runtime Electron, 8/8 pruebas del orquestador 3D Local y 100% de los componentes verificados.

---

# Xreality Convert v1.6.0 — Final Release

## 🚀 20 Puntos de Mejora Integrados

1. **Suite E2E Integrada (`npm run test:all`)**: Verificación automática de IPC Electron, sanitización Base64 GLB y contratos de la API Meshy v6.
2. **Meshy Cloud API v6 Dual Engine**: Integración transparente con Meshy API v6 (Preview, Refine, Remesh, Auto-Rigging, Auto-UV).
3. **Escudo de Créditos (5cr Smart Preview)**: Protección contra gastos accidentales validando geometría en Smart Topology T2 a 5 créditos.
4. **Purga Automática de VRAM & Memoria en Apple Silicon**: Gestión inteligente de memoria PyTorch/MLX para evitar fugas en sesiones largas.
5. **Algoritmo de Reparación Manifold y Watertight**: Corrección automática de micro-agujeros, caras degeneradas y normales invertidas para STL 3D printing.
6. **Dynamic Island HUD en la Barra de Estado**: Indicador de estado flotante al estilo Apple con telemetría viva de MLX/Meshy y contador de progreso.
7. **Grid Multi-Vista de 6 Ángulos**: Carga e inspección de vistas ortográficas (Frente, Atrás, Izquierda, Derecha, Arriba, Abajo) con validación de admisión.
8. **Grafo de Nodos Interactivo del Pipeline 3D**: Visualización interactiva en tiempo real del flujo de procesamiento (Preprocesamiento → Rembg → MLX/Meshy → Decimación → PBR → OpenUSD).
9. **Auditoría de Diseño Steve Jobs & Jony Ive**: Evaluación automatizada de 10 puntos de estética spatial computing (presupuesto de polígonos, curvatura, armonía PBR y fidelidad de escala AR).
10. **Generador de Textura PBR por Inteligencia Artificial**: Re-texturizado online en tiempo real mediante prompts creativos ("titanio cepillado", "fibra de carbono cyberpunk", "roble envejecido").
11. **Escultor y Corrector Geométrico Remesh Quad**: Conversión directa a topología Quad Low Poly, suavizado de superficies y preservación de bordes duros.
12. **Biblioteca de Materiales PBR y Selector de Presets**: Presets curados de mapas de textura 4K/2K (Cristal, Oro, Carbono, Cuero, Plástico Mate, Hormigón).
13. **Cajón de Telemetría Viva con Monitoreo Térmico y VRAM**: Panel en vivo de uso de Apple Neural Engine, consumo de GPU y estimador de tiempo restante.
14. **Estudio Guiado Horizontal (Flow Studio)**: Asistente visual paso a paso para usuarios novatos con transición fluida al Modo Experto.
15. **Efectos Micro-Animados Sparkle Burst FX**: Animación de partículas al completar la generación y transiciones glassmorphic suaves.
16. **Límite de Errores React con Recuperación WebGL**: Captura de excepciones de contexto WebGL o fallos de renderizado sin congelar la ventana de Electron.
17. **Exportación Mejorada OpenUSD / USDZ para Apple Vision Pro**: Archivos `.usdz` 100% compatibles con UsdPreviewSurface para Quick Look en visionOS y iOS.
18. **Optimización de Bundle Vite con Split de Chunks Manual**: Separación en chunks independientes para Three.js, Phosphor Icons y JSCAD en `dist/`.
19. **Buscador y Filtro en el Historial con Exportación de Informes JSON**: Búsqueda por prompt, categoría o score de calidad, y descarga de informes técnicos JSON.
20. **Blindaje IPC y Sanitización de Rutas**: Validación de entradas IPC, prevención de travesía de rutas y manejo seguro de eventos.

Validación: 13/13 pruebas del runtime Electron, auditoría E2E de cableado y verificación de módulos 100% aprobadas.

---

# Xreality Convert v1.4.1


## Gate geométrico por destino

- GLB/XR ya no se rechaza por una regla global de `watertight`.
- Productos y orgánicos abiertos continúan como `atención` en perfiles XR; el
  cierre sigue siendo obligatorio para nivel maestro y para exportar STL.
- Si una malla renderizable falla sólo la promoción maestra/sólida, el trabajo
  no se pierde: se entrega degradado y rotulado como GLB/XR no maestro, no STL.
- Ensamblajes como vehículos, grúas, camiones e instalaciones no reciben una
  penalización por estar compuestos por superficies o piezas separadas.
- Todo rechazo geométrico conserva un GLB diagnóstico y un reporte con perfil,
  categoría, contrato, métricas, hitos y estado de memoria.
- Motor local 18 para forzar la actualización segura de este contrato.

Validación: 98 pruebas del motor y 11 del runtime Electron aprobadas.

---

# Xreality Convert v1.4.0

## Buffalo Strategic MLX

- Contrato semántico de piezas y regiones materiales por categoría.
- Gate transaccional que rechaza simplificaciones que pierden componentes.
- Preservación de la malla maestra cuando Low Poly o VR dañan estructura.
- Plan Apple Silicon explícito: Shape y Paint Metal secuenciales, CPU acotada.
- Reporte por carriles con estados `pass`, `reject` y `not_measured`.
- Identidad honesta: arquitectura inspirada en Buffalo; no usa pesos Buffalo
  oficiales ni afirma capacidades todavía no publicadas.
- Conversor GLB → OpenUSD/USDZ con jerarquía, UV, normales y materiales PBR.
- Validación fail-closed mediante `usdchecker --arkit --strict` antes de guardar.
- Botón `Exportar USDZ` para Quick Look y flujos RealityKit en Apple.
- El visor abre el GLB directamente desde disco: evita duplicar archivos grandes
  como Base64 y elimina un crash reproducible del renderer Electron/ANGLE.
- Render PBR ligero para Apple Silicon, sin PMREM ni sombras que compitan por
  memoria gráfica durante la revisión del resultado.
- Arranque del motor protegido también durante la ventana posterior al `spawn`:
  la UI no puede lanzar un segundo Uvicorn mientras el primero importa MLX.

La suite incluye 95 pruebas del motor y 11 pruebas del runtime Electron.

---

# Xreality Convert v1.2.2

## Español

Esta versión deja la distribución de macOS lista para instalarse con identidad visual coherente y firma/notarización validadas.

### Cambios
- Nombre de la app ajustado a `Xreality Convert`
- Icono, favicon y assets de macOS alineados con la nueva identidad
- DMG firmado y notarizado para una instalación más segura en Mac
- Instalador de Hunyuan3D corregido para exigir Python 3.11 o 3.12
- README actualizado y manual bilingüe nuevo con capturas actuales

## English

This release polishes the macOS distribution so it installs with a consistent brand identity and validated signing/notarization.

### Changes
- App name updated to `Xreality Convert`
- macOS icon, favicon, and assets aligned with the new identity
- DMG signed and notarized for safer Mac installation
- Hunyuan3D installer fixed to require Python 3.11 or 3.12
- Updated README and a new bilingual manual with current screenshots
