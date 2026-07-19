# Pipeline local de activos XR: diseño integral y validación adversarial

Fecha: 2026-07-19
Estado: fundaciones aprobadas; extendido por Local Asset Compiler
Ámbito: Texto a Imagen, Texto a 3D, Imagen a 3D, PBR, optimización y exportación

## 0. Jerarquía del programa

Este documento conserva fundaciones de seguridad, lifecycle, assets y gates. El programa aprobado `2026-07-19-local-asset-compiler-program-design.md` prevalece en estrategia 2026, modularidad y secuencia. Especializaciones:

- `2026-07-19-profile-policy-design.md`
- `2026-07-19-benchmark-arena-model-registry-design.md`
- `2026-07-19-reference-director-provider-router-design.md`
- `2026-07-19-render-critic-asset-auditor-design.md`

Una especialización no puede relajar P0/P1, ownership, exclusión GPU, persistencia transaccional o límites de esta base.

## 1. Objetivo

Construir un flujo local exigente dentro de un Mac Apple Silicon con 24 GB, sin confundir novedad con compatibilidad ni preview con activo terminado. Cada etapa produce un artefacto cacheable, verificable y reutilizable. Un fallo detiene o degrada solo esa etapa; nunca obliga a regenerar todo sin necesidad.

```text
Prompt
  -> Referencias 2D candidatas
  -> Gate de reconstruibilidad
  -> Preparación de referencia
  -> Geometría 3D
  -> Gate geométrico
  -> PBR/UV/texturas
  -> Gate material
  -> Optimización XR
  -> Gate GLB/STL final
  -> Historial/Exportación
```

## 2. Veredicto actual

La aplicación no está lista para ampliar proveedores/modelos sin saneamiento previo:

- **P0:** compilador Texto a 3D basado en `node:vm` permite escape mediante funciones host; la solución objetivo elimina ejecución de JavaScript generado.
- **P1:** renderer controla rutas de lectura/escritura; Hunyuan loopback no autentica identidad.
- **P1:** controllers/job IDs globales mezclan cancelación y operaciones.
- **P1:** respuestas/base64/imágenes carecen de límites durante streaming/decodificación.
- **P1:** Texturas 1K/2K son no-op; GLB observados carecen de UV/material/imagen.
- **P1:** calidad Hunyuan se calcula antes de simplificar/exportar, no sobre artefacto final.
- **Bloqueo operacional:** Ollama está detenido y no hay modelos Ollama instalados; Texto a Imagen y fallback no pueden validarse en vivo.
- **Inconsistencia:** `engine/.installed` contiene versión 3 y Electron exige versión 4.

## 3. Estrategia: estable, laboratorio y promoción

### Ruta estable objetivo

- Texto a Imagen: Ollama con modelo instalado, licenciado y validado.
- Texto a 3D: oMLX/Ollama generan una CSG IR declarativa validada; código JavaScript del modelo nunca se evalúa.
- Imagen a 3D shape: fork `dgrauet/Hunyuan3D-2.1-mlx@58e61ee`; antes de estable se fija también digest/revisión exacta de pesos en registry.
- PBR: `Hunyuan3DPaintPipelineMLX` del mismo fork, integrado como Stage 2 real.

### Laboratorio

- TRELLIS.2 oficial es referencia moderna de 4B/PBR, pero upstream requiere Linux/NVIDIA >=24 GB.
- El port MLX local `xocialize/trellis2-mlx` no se promueve por estar descargado. Debe superar contract, memoria, calidad, licencia y exportación en runner separado.
- Stable Fast 3D/SPAR3D solo entran si existe port Apple Silicon mantenible y licencia compatible; no son drop-in.

### Regla de promoción

Una alternativa pasa de laboratorio a estable solo si:

1. Completa corpus holdout sin crash/OOM.
2. Cumple gates duros de seguridad y artefacto.
3. Domina frontera Pareto o mejora significativamente métrica prioritaria.
4. Licencia y procedencia están documentadas.
5. Existe rollback probado a ruta estable.

Cada promoción crea un registro inmutable con repo, revisión o digest de manifiesto, versión engine, licencia, configuración y fecha/reporte de benchmark. `latest` solo se admite en laboratorio; estable siempre queda pinneado.

## 4. Fundaciones transversales

### 4.1 WorkflowCoordinator

Registry main-owned por `operationId`:

- `start(request) -> operationId`; el ID lo genera main y lo reserva atómicamente, nunca renderer.
- owner `webContents.id` y workflow.
- estados `queued/acquiring/running/cancelling/releasing/committing/succeeded/failed/cancelled`.
- señal raíz por operación y controller hijo por intento/deadline; abortar un intento no inutiliza la señal del fallback.
- lease GPU central; máximo una operación pesada activa, cola FIFO de una pendiente y tercera solicitud rechazada explícitamente.
- release solo tras ack de terminación o kill confirmado; cancelación elimina queued o domina terminal mediante CAS.
- admission usa memoria pinned/no-evictable + target + reserva transitoria medida; unload/pause debe confirmarse antes de Shape, Paint o fallback.
- progreso/resultados incluyen `operationId`; renderer descarta eventos stale.
- cancel/result verifican owner; reload/close cancela todas las operaciones de ese owner.
- cancelación durante inferencia MLX es `requested/best-effort` hasta que backend confirme terminación.
- CAS exclusivo `releasing -> committing` precede linearización. Si cancel gana antes, se descarta temp; si `committing` gana, cancel responde `too_late_to_cancel`. `succeeded` solo después de fsync+rename del manifest; nunca se publica `cancelled` para un manifest comprometido.

Texto a Imagen y Texto a 3D dejan de compartir `activeController`. Hunyuan deja de usar `hunyuanActiveJobId`/`hunyuanCancelled` globales.

### 4.2 AssetRepository

- Renderer maneja IDs opacos, nunca paths.
- Main resuelve roots permitidos; `open(O_NOFOLLOW)` -> `fstat` de tipo/owner/tamaño y opera por descriptor. Temporales usan `O_EXCL|0600`; tests cubren symlink swap.
- Artefactos grandes permanecen en disco; preview usa protocolo seguro, no base64 duplicado.
- Manifest main-owned es la única fuente de verdad. Linearización: escribir temp -> fsync -> rename artefacto -> escribir/fsync/rename manifest comprometido. Historial es índice derivado/reconstruible y resultado IPC ocurre después del manifest.
- Startup reconcilia temporales/huérfanos.
- Cuota, TTL/LRU y acción explícita de conservar/exportar.
- Historial no persiste claves, cuerpos HTTP, prompts/código intermedio ni imágenes base64.

### 4.3 Servicios locales autenticados

- Hunyuan recibe token efímero por arranque con entorno mínimo y challenge identidad/version/capabilities.
- Engine devuelve asset ID, no `glb_path` arbitrario.
- oMLX restringido a origin loopback aprobado; redirects prohibidos y clave ligada al origin.
- Cada hijo recibe un `env` nuevo por allowlist, ejecutable absoluto y directorios explícitos; nunca `{...process.env}`, `HOME`, proxies ni variables `*_KEY|*_TOKEN|*_SECRET`. El token efímero Hunyuan es la única credencial de ese hijo. Tests centinela inspeccionan el entorno observado.

### 4.4 Límites

- HTTP local usa `Accept-Encoding: identity`, rechaza `Content-Length` superior y corta stream en N+1.
- Error body: 64 KiB; discovery JSON: 4 MiB/10.000 items/profundidad 32; completion/CSG IR: 2 MiB/profundidad 64/4.096 nodos.
- Imagen input: 20 MiB encoded, 80 MiB decoded, máximo 4096x4096 y 16 MP; validar mime real antes de decodificar.
- STL: 64 MiB; GLB: 512 MiB; nunca cruzan HTTP/IPC renderer como base64.
- Toda expansión/decodificación valida también tamaño posterior; N+1 aplica al contenido ya descomprimido si un backend no soporta `identity`.

### 4.5 CSG IR segura

El modelo produce JSON declarativo versionado con primitivas, parámetros numéricos acotados, transforms y booleanos allowlisted. Un parser con límite de profundidad/nodos valida schema, finitud, rangos y coste antes de invocar funciones JSCAD confiables. Se prohíben expresiones, identificadores dinámicos, módulos, callbacks y JavaScript. El PoC `constructor` debe ser imposible por contrato, no solo bloqueado por proceso. La compatibilidad legacy basada en código queda deshabilitada; cualquier migración futura requerirá gate de aislamiento independiente.

Parser y compilador confiable corren en utility process desechable para proteger el main de geometría patológica. Solo reciben IR validada y directorio/FD de salida. Presupuesto inicial: 4.096 nodos, profundidad booleana 32, 256 segmentos/primitiva, coste booleano ponderado 50.000 y 1M triángulos estimados; proceso con CPU 30 s, wall 45 s, RSS 2 GiB y output 64 MiB. Exceder cualquiera aborta. Timeout fuerza kill y espera confirmación antes de liberar lease. Este proceso aísla DoS; la seguridad RCE proviene de no ejecutar JavaScript generado.

## 5. Estado por capacidad

```text
text_image: ready | degraded | blocked
text_3d: ready | degraded | blocked
image_3d_shape: ready | degraded | blocked
image_3d_pbr: ready | degraded | blocked
export: ready | degraded | blocked
```

Header agregado nunca dice “Listo” por un solo servicio. Workflow seleccionado muestra readiness propio, dependencia faltante y fallback real. `/health` 200 no equivale a `ready:true`.

## 6. Texto a Imagen orientado a 3D

### 6.1 Propósito

Generar referencia reconstruible, no solo estética. Prompt optimizer produce objeto único, vista 3/4, cuerpo completo, fondo simple, iluminación neutra, oclusión mínima y materiales legibles.

### 6.2 Candidatos, previa autorización de descarga

- `x/flux2-klein:4b`: default provisional por memoria/latencia/licencia Apache-2.0.
- `x/z-image-turbo:fp8`: candidato de fidelidad; mayor consumo.
- `x/flux2-klein:9b`: laboratorio condicionado por licencia no comercial.
- `z-image-turbo:bf16` queda excluido en 24 GB.

No se descarga ninguno sin aprobación explícita.

### 6.3 Gate de referencia

- una entidad principal y máscara conectada.
- sujeto completo, sin recorte crítico.
- cobertura 55-85% del frame.
- contraste con fondo y bordes nítidos.
- sin texto/watermark/objetos superpuestos no solicitados.
- perspectiva coherente y cavidades/partes finas visibles.
- score bajo no bloquea exportar imagen, pero bloquea autoencadenado 3D sin confirmación.

### 6.4 Benchmark

20 prompts por categorías, 4 seeds y 1024². Métrica principal: tasa de éxito/quality downstream usando mismo Hunyuan y parámetros. Alignment/CLIP son secundarios; evaluación pairwise ciega. No FID sobre corpus pequeño.

## 7. Texto a 3D

El diseño detallado vive en `2026-07-18-omlx-text-to-3d-design.md` con estas restricciones padre:

- eliminar evaluación JSCAD generada y adoptar CSG IR antes de oMLX.
- CSG IR declarativa; cero evaluación de JavaScript generado.
- `start(request)->operationId`, progress/cancel/result con ownership y terminal CAS.
- allowlist por capability/benchmark, no substring.
- modelo oMLX provisional: Gemma Coder; gpt-oss como provenance; qwen3-8b como control eficiente. Ninguno es ganador sin benchmark.
- modelos <4096 output quedan limitados; qwen3-4b (256) excluido.
- fallback no arranca otro workload GPU hasta confirmar que primario terminó.

## 8. Imagen a 3D: shape

### 8.1 Preparación

- Validar input antes de PIL: bytes, mime, megapíxeles y orientación.
- Conservar original inmutable y producir prepared version cacheada.
- Reportar si rembg falló; no continuar silenciosamente con semántica distinta.
- Seed viaja UI -> Electron -> engine -> ShapePipeline y queda en reporte.

### 8.2 Generación

- Cola GPU single-flight.
- Stage Shape produce GLB/mesh intermedio sin textura.
- Liberar pipeline Shape y ejecutar GC/clear verificable antes de Paint.
- Separar métricas: load, preprocess, infer, clean, decimate, export.

### 8.3 Gate geométrico final

Validar después de simplificación y recargar archivo exportado:

- faces/vertices raw, clean y final separados.
- parse GLB exitoso y buffers íntegros.
- AABB finito, volumen/superficie no degenerados.
- componentes, watertight/manifold, winding y self-intersections.
- thin-structure recall y agujeros funcionales cuando corpus los define.
- silhouette IoU/depth/normals en vistas fijas para benchmark.
- presupuesto XR aplicado al artefacto final.

## 9. PBR y texturas reales

### 9.1 Stage 2

Si `texture=true`:

1. Verificar gate shape.
2. Liberar ShapePipeline.
3. Instanciar `Hunyuan3DPaintPipelineMLX` con reference prepared.
4. Remesh/UV solo cuando sea necesario, preservando asset intermedio.
5. Generar albedo y metallic-roughness; super-resolution según perfil.
6. Exportar OBJ temporal y GLB final desde material en memoria para no perder PBR.
7. Liberar Paint y limpiar temporales según política.

`textureSize` debe cruzar todos los contratos y mapear a atlas real. Perfiles iniciales: Sin textura, 1K y 2K. 4K queda laboratorio por memoria/tiempo.

### 9.2 Gate `generated_textured_pbr`

`textureApplied=true` solo si GLB recargado contiene:

- UV válidas y cobertura suficiente.
- material PBR.
- baseColorTexture presente.
- metallicRoughnessTexture presente y channel packing documentado.
- imágenes embebidas/resolución conforme al perfil.
- texels finitos, sin atlas vacío.
- seam energy y bleeding bajo umbral del corpus.
- render neutral válido bajo tres HDRI para benchmark.

Si Paint falla, conservar shape-only y preguntar si exportar degradado. Nunca etiquetarlo texturizado.

Conformidad glTF general se informa aparte como `gltf_material_conformant`, que puede aceptar materiales factor-only válidos. Nunca deriva `textureApplied=true`.

## 10. Optimización y exportación

- Optimización parte de artefacto validado y produce uno nuevo; no muta fuente.
- Revalidar geometría y materiales después de decimation/conversion.
- GLB: buffers, texturas, materiales, escala y unidades.
- STL: watertight, orientación, dimensiones mm y espesor mínimo; materiales se declaran descartados.
- Export blocked solo por gate crítico; warnings muestran causa y acción.
- Historial guarda lineage entre original, prepared, shape, PBR y optimized.

## 11. Benchmarks sin score engañoso

### Texto a 3D

24 prompts, 3 seeds, holdout, `schemaValid@1`, rechazo por rango/coste, `compile@1` y `recovery@3` separados, asserts geométricos, CI 95% y Pareto calidad/latencia/memoria. Primaria: `compile@1`; promoción de calidad exige +5 puntos porcentuales y límite inferior CI pareado >0, con validez geométrica no peor de 2 puntos, p95 latencia ≤+25% y memoria ≤+15% dentro de admisión. Promoción de eficiencia exige calidad dentro de -2 puntos y mejora ≥20% con CI en latencia o memoria.

### Texto a Imagen

20 prompts, 4 seeds; reference quality + éxito downstream 3D con mismo conjunto de seeds Hunyuan; pairwise ciego. Métrica primaria: éxito downstream; promoción exige +5 puntos porcentuales y CI bootstrap pareado 95% excluyendo 0.

### Imagen a 3D/PBR

12-20 objetos con GT/cámaras versionados y alineación canónica. Shape: Chamfer/F-score, normals, silhouette/depth, topology; primaria F-score, promoción ≥3% relativa con CI pareado 95% excluyendo 0 y sin regresión de gates. Detail: multi-scale normals/depth, curvature, thin structures. PBR con GT material: exposición/tonemapping fijos, UV y seam energy; albedo usa sRGB decode → RGB lineal → XYZ/Lab D65 → CIEDE2000, y LPIPS/SSIM documentan su dominio; roughness MAE, metallic F1 y renders neutrales. Sin GT material, promoción requiere win-rate humano ≥60% y límite inferior CI 95% >50%, mínimo tres evaluadores ciegos por muestra y adjudicación de empate; no se inventan MAE/F1.

Bootstrap es pareado por prompt/objeto con seeds anidados; corpus, métrica primaria y margen se congelan antes del run.

No combinar shape-only y PBR en score. Reportar gates, métricas crudas y fronteras Pareto. “Cold” solo después de unload/restart autorizado; de otro modo `first observed`.

## 12. Plan por gates

### Gate -2: baseline read-only

- Capturar build, tests y artefactos actuales antes de mutar producción.
- Añadir caracterización y PoC rojos en entorno controlado; no ejecutar payloads contra datos reales.
- Registrar versiones, árbol dirty y bloqueos externos.

### Gate -1: contención

- Tests para eliminación de evaluación JS, rutas IPC, symlink, Hunyuan impostor, bombs y doble cancel.
- CSG IR validada, asset IDs, token engine, límites y entorno por allowlist.

No avanzar si existe P0/P1 sin mitigación.

### Gate 0: lifecycle

- WorkflowCoordinator, operation IDs, progress y ownership.
- Result/AssetRepository transaccional y retention.
- Capability matrix honesta.

### Gate 1: baseline funcional

- Caracterizar los tres pipelines actuales.
- Corregir version marker 3/4.
- Retirar labels PBR falsos hasta Stage 2 real.

### Gate 2: Texto a 3D multi-proveedor

- oMLX auth/discovery/completion/fallback después de aislamiento.
- Smoke con modelo pequeño y benchmark Coder.

### Gate 3: Texto a Imagen

- Usuario aprueba descarga/licencia.
- Instalar un modelo default y ejecutar benchmark de referencia.

### Gate 4: Hunyuan Shape

- Seed, single-flight, cancel best-effort, quality post-export.

### Gate 5: Hunyuan Paint MLX

- PBR real, textureSize y validación estructural/render.

### Gate 6: Laboratorio TRELLIS.2

- Runner separado, sin afectar ruta estable.
- Contract/memory/output benchmark; promoción explícita o rechazo documentado.

### Gate 7: cadena completa

- Prompt -> imagen -> shape -> PBR -> optimize -> export.
- Fallos inyectados por etapa; reanudación desde caché; no rerun innecesario.
- Browser, consola, archivos, historial y privacidad.

## 13. Criterios finales

- Cero ejecución de código generado en cualquier proceso; solo CSG IR validada y compilador confiable.
- Cero paths arbitrarios o secretos legibles desde renderer.
- Cero servicio local aceptado solo por ocupar puerto.
- Cero operación GPU concurrente no coordinada en 24 GB.
- Cancelación correlacionada; resultados tardíos ignorados.
- Cada workflow tiene readiness propio.
- Textura declarada solo si GLB prueba UV/material/mapas.
- Calidad calculada sobre archivo final recargado.
- Cada etapa cacheable/reanudable y con lineage.
- Benchmarks reproducibles, sin score principal único ni auto-promoción.
- Ruta estable comprobada y laboratorio aislado.
- Tests, build, smoke real y navegador con evidencia fresca.

## 14. Riesgos residuales

- CSG IR reduce superficie al no ejecutar JavaScript; parser/compiler aún requieren fuzzing de schema, coste y geometría patológica.
- Cancelar request no garantiza detener kernel MLX; UI debe decir `cancelación solicitada` hasta confirmación.
- Calidad backside desde una sola imagen sigue siendo inferencia, no verdad; referencias multivista serían entrega futura.
- PBR MLX puede exceder margen con oMLX cargado; coordinador debe liberar/pausar modelos o bloquear Stage 2 con diagnóstico, nunca causar swap/OOM silencioso.
- TRELLIS.2 MLX comunitario puede divergir del upstream CUDA; solo benchmark local decide.
