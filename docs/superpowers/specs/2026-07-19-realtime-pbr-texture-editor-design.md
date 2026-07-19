# Texturizado PBR derivado y editor material en tiempo real

Fecha: 2026-07-19
Estado: aprobado por el usuario
Ámbito: Imagen a 3D, Paint MLX, visor, historial y exportación GLB

## 1. Objetivo

Añadir una etapa local e independiente que aplique a una malla existente una textura PBR basada en la imagen de referencia. La malla original permanece inmutable. El usuario puede alternar original/PBR, personalizar la apariencia en tiempo real y exportar un GLB que conserve el estado visible.

Este diseño especializa la etapa PBR de:

- `2026-07-19-end-to-end-asset-pipeline-design.md`;
- `2026-07-19-reference-director-provider-router-design.md`.

No relaja sus reglas de exclusión GPU, ownership, lineage ni validación del artefacto final.

## 2. Evidencia y decisión de modelo

La ruta estable será `Hunyuan3DPaintPipelineMLX` del fork local `dgrauet/Hunyuan3D-2.1-mlx@58e61ee`:

- el código ya está instalado dentro del motor;
- los pesos MLX de Shape y Paint ya ocupan aproximadamente 13 GB en la caché local;
- el pipeline genera albedo y metallic-roughness, crea UV cuando faltan y exporta GLB;
- su Stage 2 documenta aproximadamente 6 GB de memoria adicional y ejecución local Apple Silicon;
- el equipo dispone de 24 GB de memoria unificada.

Referencias primarias:

- <https://github.com/dgrauet/Hunyuan3D-2.1-mlx>
- <https://huggingface.co/dgrauet/hunyuan3d-2.1-mlx>
- <https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1>

Alternativas rechazadas para esta entrega:

- Pixal3D ofrece una ruta 2026 de alta fidelidad y PBR, pero su implementación publicada depende de TRELLIS.2, CUDA y NATTEN. No es un proveedor ejecutable en este Mac.
- TRELLIS.2 oficial genera PBR y acepta mesh conditioning, pero upstream declara Linux, CUDA y NVIDIA con al menos 24 GB VRAM.
- `xocialize/trellis2-mlx` permanece en laboratorio: exige otro runtime, unos 17.6 GB de pesos y obligaciones adicionales de DINOv3. No sustituye una ruta Paint ya instalada sin benchmark local.

Referencias primarias:

- <https://github.com/TencentARC/Pixal3D>
- <https://github.com/microsoft/TRELLIS.2>
- <https://huggingface.co/xocialize/trellis2-mlx>

## 3. Alcance

Incluye:

- trabajo Paint separado de Shape;
- presets Rápido, Balanceado y Calidad;
- overlay colapsable dentro del visor;
- comparación original/PBR instantánea;
- brillo, contraste, saturación, tinte, intensidad de tinte, roughness y metallic;
- presets visuales Natural, Mate, Brillante y Metálico;
- exportación del original o de una variante PBR materializada;
- persistencia de lineage, preset y ajustes;
- cancelación, progreso, gate PBR y errores accionables.

No incluye:

- edición manual de UV;
- pintura por pincel sobre el modelo;
- normal map generado por un modelo adicional;
- texturas 4K;
- regeneración automática de geometría;
- nuevos proveedores 3D.

## 4. Principio de artefactos

```text
SourceImage
  -> ShapeArtifact (original, immutable)
       -> PaintArtifact (PBR, immutable)
            -> MaterialState (editable, persisted)
                 -> DeliveryArtifact (materialized GLB)
```

Reglas:

1. Shape nunca se sobrescribe.
2. Paint produce un archivo nuevo y registra `parentArtifactId`.
3. Los sliders no escriben el GLB Paint.
4. Cada exportación crea Delivery con su propio digest y snapshot de ajustes.
5. Apagar el switch selecciona Shape; no elimina Paint ni sus ajustes.

## 5. Contratos

```text
TextureProfile = fast | balanced | quality

MaterialSettings {
  brightness: 0.50..1.50       // default 1.00
  contrast: 0.50..1.50         // default 1.00
  saturation: 0.00..2.00       // default 1.00
  tint: #RRGGBB                // default #FFFFFF
  tintStrength: 0.00..1.00     // default 0.00
  roughness: 0.00..1.00        // default derivado del material, fallback 0.60
  metallic: 0.00..1.00         // default derivado del material, fallback 0.00
}

TextureVariant {
  artifactId
  parentArtifactId
  referenceArtifactId
  profile
  status
  progress
  stage
  glbDigest
  gateReportId
  settings
  createdAt
}
```

Renderer solo transmite IDs y valores validados. Main resuelve rutas y ownership; no se aceptan rutas arbitrarias desde la UI.

## 6. Perfiles Paint

| Perfil | Vistas | Resolución de inferencia | Pasos | Atlas | Superresolución | Propósito |
|---|---:|---:|---:|---:|---|---|
| Rápido | 4 | 256 | 10 | 1024 | no | iteración y prueba de material |
| Balanceado | 6 | 512 | 15 | 1024 | no | opción predeterminada |
| Calidad | 6 | 512 | 15 | 2048 | RealESRGAN MLX | entrega final |

El selector expresa trabajo real. `texture_size`, `render_size`, número de vistas, pasos y superresolución deben llegar a `Hunyuan3DPaintConfigMLX`; una etiqueta que no cambie esas propiedades falla el contrato.

Calidad no cae silenciosamente a Balanceado. Un fallo de memoria conserva Shape y ofrece reintento explícito con un perfil inferior.

## 7. Flujo backend

1. Main valida owner, Shape final, imagen preparada y perfil.
2. WorkflowCoordinator adquiere lease GPU single-flight.
3. ShapePipeline se descarga de memoria y se verifica liberación antes de cargar Paint.
4. El trabajo entra en estados:
   - `queued`;
   - `preparing_uv`;
   - `loading_model`;
   - `generating_views`;
   - `baking_pbr`;
   - `validating`;
   - `ready | failed | cancelled`.
5. Paint usa Shape + imagen preparada y escribe temporales bajo el directorio del trabajo.
6. El GLB PBR se recarga y pasa el gate material.
7. Solo después del gate se crea el `TextureVariant` visible.
8. Se libera Paint, temporales no necesarios y lease GPU.

La cancelación domina cualquier resultado tardío. Shape y un Paint previamente válido permanecen disponibles.

## 8. Gate `generated_textured_pbr`

Paint queda `ready` únicamente si el GLB recargado contiene:

- `TEXCOORD_0` finito y con cardinalidad válida;
- cobertura UV suficiente y coordenadas dentro del dominio admitido;
- material PBR;
- `baseColorTexture` con imagen no vacía;
- `metallicRoughnessTexture` con packing glTF documentado;
- resolución de atlas igual al perfil solicitado;
- buffers, bufferViews e índices dentro de rango;
- dimensiones, AABB y geometría finitas;
- render neutral sin material negro ni textura ausente.

`textureApplied=true` se deriva de este gate. Nunca se deriva del request ni de que la función Paint haya retornado.

## 9. Overlay del visor

Ubicación aprobada: overlay superior derecho dentro del visor.

Estado expandido:

- encabezado `Material Lab`;
- switch `Textura aplicada`;
- selector Rápido/Balanceado/Calidad;
- acción `Generar` o `Regenerar textura PBR`;
- presets Natural, Mate, Brillante y Metálico;
- sliders de apariencia;
- `Ver original` para comparación momentánea;
- `Exportar GLB visible`;
- control para colapsar.

Estado colapsado:

- esfera de material;
- estado `Sin PBR | Generando | PBR listo`;
- preset activo;
- switch;
- expansión.

El overlay no es draggable. Su posición es estable, teclado y lector de pantalla reciben labels completos y `prefers-reduced-motion` elimina transiciones no esenciales.

## 10. Preview en tiempo real

El visor conserva dos escenas alineadas: Shape y Paint. El switch alterna `visible` sin volver a parsear GLB ni ejecutar IA.

Paint conserva una copia de sus materiales originales. Los ajustes se aplican como override reversible:

- roughness y metallic actualizan factores PBR;
- brillo, contraste, saturación y tinte se aplican en shader;
- `Ver original` mantiene presionado Shape visible y restaura Paint al soltar;
- `Restablecer` vuelve a los valores inferidos del Paint, no a constantes inventadas.

Transformación de color común a preview y exportación, definida en sRGB:

1. multiplicar brillo;
2. aplicar contraste alrededor de 0.5;
3. mezclar luminancia Rec.709 según saturación;
4. mezclar con `tint` según `tintStrength`;
5. clamp a `[0,1]`.

El shader convierte lineal a sRGB antes de estas operaciones y vuelve a lineal después. La materialización CPU opera directamente sobre texels sRGB usando la misma fórmula.

Objetivo interactivo: cambio visible en el siguiente frame y sin reconstruir escena. No se promete una cifra de milisegundos independiente de carga GPU.

## 11. Presets de apariencia

Los presets solo cambian `MaterialSettings`; nunca regeneran Paint:

| Preset | Brillo | Contraste | Saturación | Roughness | Metallic |
|---|---:|---:|---:|---:|---:|
| Natural | 1.00 | 1.00 | 1.00 | valor Paint | valor Paint |
| Mate | 1.00 | 0.98 | 0.95 | 0.90 | 0.00 |
| Brillante | 1.03 | 1.05 | 1.02 | 0.18 | valor Paint |
| Metálico | 0.95 | 1.08 | 0.90 | 0.28 | 0.90 |

Modificar cualquier slider después de un preset cambia el estado a `Personalizado`.

## 12. Exportación

Switch apagado:

- se copia Shape sin mutación;
- se conserva su contenido y se registra un nuevo Delivery digest.

Switch encendido:

1. Main resuelve el Paint validado por ID.
2. Se extrae `baseColorTexture` embebida.
3. Se aplica la fórmula sRGB de la sección 10.
4. Se vuelve a embebir albedo sin cambiar UV.
5. Se escriben `roughnessFactor` y `metallicFactor`.
6. Se exporta un GLB nuevo.
7. Se recarga, valida y renderiza antes de ofrecerlo.

La exportación no debe pasar por OBJ/trimesh si ese round-trip pierde PBR. La edición se realiza directamente sobre glTF/GLB con `pygltflib` y Pillow, preservando imágenes, bufferViews y material restante.

## 13. Persistencia e historial

Historial ligero guarda IDs, digests, perfil, gate report, `MaterialSettings`, estado del switch y timestamps. No guarda blobs base64.

Al reabrir:

- si Shape existe y Paint no, se muestra original;
- si Paint existe y pasa digest/gate, se restauran switch y ajustes;
- si Paint falta o cambió, se marca `PBR no disponible` sin borrar Shape;
- un Delivery no reemplaza su padre.

## 14. Errores

| Fallo | Comportamiento |
|---|---|
| Sin UV y xatlas ausente | Paint bloqueado; acción para instalar/verificar motor |
| OOM | trabajo failed; Shape intacto; sugerir perfil inferior |
| Cancelación | terminal cancelled; temporales limpiados; Shape intacto |
| GLB PBR inválido | conservar diagnóstico interno; no ofrecer como PBR |
| Textura vacía/negra | gate failed; mostrar causa y reintento |
| Exportación inválida | no reemplazar destino; conservar Paint y ajustes |
| Archivo padre ausente | deshabilitar acción y explicar cómo regenerar |

No existe fallback silencioso a gris ni éxito parcial etiquetado como PBR.

## 15. Pruebas

### Unitarias

- mapeo exacto de los tres perfiles a config Paint;
- validación y clamp de `MaterialSettings`;
- fórmula sRGB con vectores dorados;
- presets de apariencia;
- gate glTF: válido, sin UV, sin albedo, sin MR, atlas incorrecto;
- original digest idéntico tras Paint y exportación.

### Integración

- endpoint/IPC start-progress-cancel-result con pipeline falso;
- ownership por `webContents.id` y rechazo de IDs ajenos;
- materialización GLB con textura embebida;
- reload del GLB y verificación de factores/mapas;
- historial y recuperación de variante.

### UI y navegador

- generar/regenerar desde overlay;
- expandir/colapsar;
- switch original/PBR sin recargar IA;
- presets y sliders reflejados en visor;
- `Ver original` temporal;
- teclado, labels y reduced motion;
- exportar respeta switch.

### Smoke real

Con la imagen del perro usada en la sesión:

1. producir Shape base;
2. ejecutar Rápido y verificar PBR estructural;
3. ejecutar Balanceado si memoria/tiempo lo permiten;
4. comparar original, Paint y Delivery bajo cámara/luz fijas;
5. reabrir Delivery en el visor;
6. registrar duración, pico de memoria, tamaños y gate report.

## 16. Criterios de aceptación

1. El usuario puede conservar y exportar Shape sin generar Paint.
2. Paint es un trabajo separado, cancelable y con progreso real.
3. El switch alterna original/PBR sin inferencia adicional.
4. Los siete ajustes cambian el preview y sobreviven al historial.
5. Exportar con switch apagado entrega Shape; encendido entrega PBR materializado.
6. Reabrir Delivery reproduce ajustes de color y factores PBR.
7. Shape conserva exactamente su digest durante todo el flujo.
8. Un GLB sin UV, albedo o MR nunca aparece como `PBR listo`.
9. Rápido/Balanceado/Calidad modifican realmente config y coste.
10. La prueba real produce evidencia o se reporta como bloqueada con causa; no se sustituye por mocks.

## 17. Riesgos residuales

- Paint MLX sigue siendo un fork comunitario y requiere pin de digest de pesos además del commit de código.
- La licencia Hunyuan 3D 2.1 impone territorio y restricciones de uso/distribución; el empaquetado debe mostrar avisos aplicables.
- El remesh de Paint puede alterar ligeramente geometría. Shape permanece disponible y el gate compara AABB/silueta para detectar regresión excesiva.
- Calidad 2K puede presionar memoria unificada de 24 GB; requiere medición real antes de quedar habilitada por defecto.
