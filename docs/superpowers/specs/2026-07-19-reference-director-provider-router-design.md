# Reference Director y Provider Router para Imagen a 3D

Fecha: 2026-07-19
Estado: diseño aprobado; listo para plan de implementación
Ámbito: referencia única, multivista capturada o generada, geometría, materiales PBR, routing estable/laboratorio y validación de activos
Plataforma objetivo: Apple Silicon con 24 GB de memoria unificada

## 0. Relación con el diseño integral

Este documento especializa Imagen a 3D y el tramo de referencias del pipeline descrito en `2026-07-19-end-to-end-asset-pipeline-design.md`. El diseño integral prevalece en seguridad IPC, propiedad de operaciones, cancelación, exclusión GPU, límites de entrada, persistencia transaccional, repositorio de assets y lifecycle de procesos. Este documento prevalece en:

- semántica de `InputSet` y procedencia de vistas;
- contrato de `ReferenceDirector`;
- contratos `GeometryProvider` y `MaterialProvider`;
- routing por capacidad, readiness, memoria, licencia y tier;
- artefactos canónicos entre geometría, material, optimización y exportación;
- gates específicos para consistencia entre vistas, geometría y PBR;
- promoción de proveedores Imagen a 3D desde laboratorio a estable.

No autoriza descargas, cambios de modelo, ejecución de pesos comunitarios ni promoción automática. Cada instalación o descarga requiere aprobación explícita y revisión de licencia.

## 1. Objetivo verificable

Construir una ruta Imagen a 3D que acepte una imagen o un conjunto multivista, preserve la diferencia entre observación y contenido generado, seleccione un proveedor compatible sin exceder 24 GB, y entregue un GLB cuya geometría y materiales hayan sido validados sobre el archivo final.

El resultado cumple el diseño cuando:

1. una referencia única genera un artefacto geométrico canónico mediante un provider `stable`; Hunyuan3D MLX permanece `lab` hasta promoción;
2. un conjunto de vistas capturadas conserva cámara, rol y confianza sin tratarlas como imágenes intercambiables;
3. las vistas generadas quedan marcadas como inferencias y nunca reemplazan evidencia capturada;
4. geometría y materiales se ejecutan como etapas separadas, con liberación confirmada de memoria entre ellas;
5. cada intento registra proveedor, revisión de código/pesos, parámetros, seed, memoria pico, tiempos y lineage;
6. un fallo de Paint conserva el shape válido y produce una degradación explícita, no un falso éxito PBR;
7. TRELLIS.2 Swift y Hunyuan3D-Swift permanecen aislados en laboratorio hasta superar gates medibles;
8. Pixal3D y Home3D se usan solo como referencias de investigación, nunca como proveedores ejecutables;
9. el GLB final se recarga y valida después de cualquier remesh, bake, decimación, compresión o conversión.

## 2. Principios vinculantes

1. **Evidencia antes que síntesis:** una vista capturada tiene autoridad sobre una vista generada para la región que observa.
2. **Capacidad antes que nombre:** el router usa capabilities demostradas y restricciones actuales, no coincidencias de strings ni reputación.
3. **Geometría antes que Paint:** ningún proveedor material recibe un mesh que no haya superado el gate geométrico requerido.
4. **Artefactos antes que paths:** renderer y proveedores intercambian IDs opacos y manifests; nunca rutas arbitrarias.
5. **Una etapa pesada a la vez:** Shape, Paint y generadores de vistas no coexisten en memoria salvo benchmark explícito que pruebe admisión.
6. **Tier no equivale a preferencia:** `stable` es elegible automáticamente; `lab` exige opt-in; `research-only` es documentación sin ejecución.
7. **Readiness es por workflow:** tener pesos descargados, un puerto abierto o un health 200 no implica capacidad utilizable.
8. **Fallback conserva semántica:** cambiar de proveedor no puede perder cámaras, seed, perfil, material esperado ni procedencia.
9. **Degradación honesta:** shape-only, PBR parcial, memoria insuficiente y vista inferida se muestran como estados distintos.
10. **Promoción humana y reversible:** un benchmark puede recomendar, pero nunca cambia el default por sí solo.

## 3. Alcance y exclusiones

### Incluye

- `ReferenceDirector` para validar, normalizar y clasificar referencias.
- `InputSet` single, multiview capturado y multiview generado.
- routing separado para geometría y materiales.
- registro de proveedores con tier, capabilities, readiness y licencia.
- Hunyuan3D 2.1 MLX como ruta `lab/capability_unverified` y stable objetivo tras promoción.
- TRELLIS.2 Swift/MLX y Hunyuan3D-Swift como rutas de laboratorio.
- artefactos canónicos, lineage, caching y reanudación por etapa.
- budgets conservadores para 24 GB.
- gates automáticos, revisión humana ciega y benchmarks adversariales.
- errores normalizados y política exacta de fallback.

### Excluye

- entrenar o fine-tunear modelos.
- inventar poses de cámara para imágenes que no las poseen.
- convertir Pixal3D o Home3D en proveedores sin implementación y auditoría posteriores.
- descargar, borrar o actualizar pesos.
- ejecutar TRELLIS.2 upstream CUDA en Apple Silicon.
- presentar Gaussian Splat, NeRF o preview volumétrico como mesh PBR terminado.
- reconstrucción métrica garantizada desde una sola imagen.
- publicar modelos Hunyuan en territorios o escenarios no autorizados por su licencia.
- ocultar un cambio de proveedor, tier o pérdida de calidad.

## 4. Vocabulario y estados

- **Vista capturada:** imagen obtenida del objeto o escena real. Puede tener cámara conocida o desconocida.
- **Vista generada:** imagen sintetizada desde otra vista o prompt. Es soporte probabilístico, no nueva evidencia.
- **Vista canónica:** representación normalizada y cacheada, derivada de una vista fuente sin alterar su procedencia.
- **Shape:** geometría sin obligación de UV o materiales.
- **PBR:** material cuyo GLB final contiene al menos UV, `baseColorTexture` y `metallicRoughnessTexture` válidas; normal/occlusion/emissive se reportan por separado.
- **Stable-conditioned:** ruta elegible automáticamente solo cuando las precondiciones locales medidas se cumplen.
- **Lab:** ruta manual y aislada; sus resultados no reemplazan silenciosamente el baseline.
- **Research-only:** fuente para diseño o evaluación; no aparece como opción ejecutable.

Estados terminales de una etapa:

```text
succeeded
degraded_shape_only
degraded_partial_material
failed
cancelled
```

`degraded_shape_only` requiere un shape comprometido y validado. `degraded_partial_material` conserva un material diagnóstico, pero no lo etiqueta como PBR ni lo ofrece como export final estable.

## 5. Contrato InputSet

`InputSet` es inmutable después de iniciar una operación. Main lo crea desde asset IDs y metadatos validados; renderer no construye paths ni hashes confiables.

```text
InputSet {
  schemaVersion: 1
  id: InputSetId
  mode: single | captured_multiview | generated_multiview | mixed_multiview
  subjectId: string
  views: InputView[1..12]
  coordinateFrame: unknown | right_handed_y_up | right_handed_z_up
  declaredUnits: unknown | mm | cm | m
  createdAt: ISO-8601
  provenancePolicy: strict
}

InputView {
  viewId: string
  sourceAssetId: AssetId
  canonicalAssetId: AssetId | null
  origin: captured | generated
  role: front | front_left | left | back_left | back |
        back_right | right | front_right | top | bottom | detail | unknown
  camera: CameraObservation | null
  maskAssetId: AssetId | null
  confidence: number [0,1]
  sourceViewId: string | null
  generatorRunId: string | null
  contentDigest: sha256
  width: integer [64,4096]
  height: integer [64,4096]
  mime: image/png | image/jpeg | image/webp
  warnings: ReferenceWarning[]
}

CameraObservation {
  model: perspective | orthographic
  intrinsics: fx, fy, cx, cy | null
  worldFromCamera: 4x4 finite matrix | null
  poseSource: calibrated | exif | estimated | user_declared
  reprojectionErrorPx: finite number | null
}
```

Invariantes:

- `single` contiene exactamente una vista.
- `captured_multiview` contiene dos o más vistas y todas tienen `origin=captured`.
- `generated_multiview` contiene una vista capturada fuente y una o más vistas generadas; el nombre describe el soporte añadido, no múltiples observaciones reales.
- `mixed_multiview` contiene al menos dos vistas capturadas y una generada.
- una vista generada exige `sourceViewId` y `generatorRunId`.
- `confidence` máxima inicial: capturada calibrada `1.0`; capturada sin pose `0.85`; pose estimada `0.65`; generada `0.35`.
- una pose estimada nunca se serializa como calibrada.
- duplicados por digest o similitud perceptual mayor al umbral del corpus se eliminan conservando la vista de mayor autoridad.
- una imagen generada no puede adoptar `origin=captured` mediante edición de UI o migración de historial.
- roles incompatibles o duplicados no se corrigen silenciosamente; producen warning y reducen elegibilidad de proveedores con roles fijos.

## 6. Reference Director

### 6.1 Responsabilidad

`ReferenceDirector` transforma assets de entrada en un `PreparedInputSet` reproducible. No genera mesh, no elige proveedor de geometría y no convierte vistas generadas en evidencia.

```text
prepare(inputSetId, profile, signal) -> PreparedInputSet
assess(preparedInputSetId) -> ReferenceAssessment
buildRoutingFacts(preparedInputSetId) -> ReferenceRoutingFacts
```

`PreparedInputSet` contiene:

- referencia al `InputSet` original;
- imagen canónica por vista, sin mutar original;
- orientación EXIF aplicada;
- máscara y bounding box, con método y versión;
- transformación crop/resize reversible;
- cámara normalizada si existe;
- métricas de cobertura, recorte, blur, exposición, conectividad y duplicación;
- warnings por vista y conjunto;
- digest del algoritmo/configuración de preparación.

### 6.2 Flujo

```text
Asset IDs
  -> validación de bytes/mime/dimensiones
  -> orientación y normalización de color
  -> segmentación o máscara aportada
  -> crop con margen versionado
  -> detección de duplicados y roles
  -> validación de cámaras
  -> assessment por vista y conjunto
  -> PreparedInputSet comprometido
  -> facts inmutables para Provider Router
```

### 6.3 Reglas de dirección

- El original permanece inmutable y siempre es recuperable por lineage.
- Background removal fallido deja warning y conserva versión sin rembg; no cambia semántica silenciosamente.
- El crop debe preservar al menos 98% de la máscara y un margen mínimo de 4% por lado cuando exista espacio.
- Cobertura aceptable del sujeto para autoencadenado: 45-90% del frame; fuera de rango requiere warning.
- Blur, clipping de highlights y fondo complejo son señales, no bloqueos aislados.
- Máscara vacía, bytes corruptos, más de 16 MP, dimensiones no finitas o cámara con matriz singular bloquean preparación.
- Si dos vistas capturadas se contradicen, el director reporta inconsistencia; no genera una tercera vista para ocultarla.
- Vistas de detalle no participan en geometría global salvo que el proveedor declare soporte explícito.
- Un proveedor de roles fijos solo es elegible cuando los roles requeridos están presentes y no son ambiguos.

### 6.4 Gate de reconstruibilidad

El assessment produce métricas individuales, no un score opaco. Bloqueos duros:

- cero sujeto principal detectable;
- recorte crítico que elimina más de 5% de la máscara en una frontera relevante;
- menos de 64 px en cualquier dimensión;
- conjunto sin vista capturada;
- pose no finita o inconsistente con el frame declarado;
- contenido prohibido por licencia o política de uso del proveedor seleccionado.

Warnings accionables:

- cobertura fuera de 45-90%;
- oclusión estimada mayor a 35%;
- blur por debajo del umbral calibrado del corpus;
- iluminación quemada o material especular ambiguo;
- vistas con overlap insuficiente;
- roles desconocidos;
- soporte sintético con confianza reducida.

El autoencadenado requiere cero bloqueos y al menos una vista capturada con cobertura válida. Los warnings quedan visibles en reporte y manifest.

## 7. Contratos de proveedores

### 7.1 Contrato común

Todos los proveedores implementan lifecycle y observabilidad comunes:

```text
describe() -> ProviderDescriptor
probe({ deadline, signal }) -> ProviderProbe
estimate(requestFacts) -> ResourceEstimate
load({ revision, signal }) -> LoadedProvider
unload({ signal }) -> UnloadReceipt
```

`UnloadReceipt` debe confirmar que el proceso/pipeline terminó y reportar memoria observable posterior. Un timeout de unload bloquea fallback pesado con `primary_may_still_be_running`.

### 7.2 GeometryProvider

```text
generateGeometry({
  operationId,
  preparedInputSetId,
  profile,
  seed,
  providerRevision,
  signal
}) -> GeometryRunResult
```

Precondiciones:

- `PreparedInputSet` comprometido y gate de referencia aprobado;
- capabilities compatibles con modo, número de vistas, roles/cámaras y perfil;
- reserva de memoria concedida;
- licencia elegible para territorio y uso declarados;
- tier permitido por configuración de la operación.

Salida obligatoria:

- `RawGeometryArtifact` comprometido;
- seed efectivo y parámetros normalizados;
- tiempos load/preprocess/infer/postprocess/export;
- memoria `before`, `peakObserved` y `afterUnload`;
- provider ID, revisión de código, revisión/digest de pesos y dependencias críticas;
- warnings, fallback lineage y métricas preliminares.

El resultado no puede contener un path arbitrario ni declararse exitoso antes de que el archivo sea recargable.

### 7.3 MaterialProvider

```text
generateMaterial({
  operationId,
  validatedGeometryArtifactId,
  preparedInputSetId,
  textureProfile,
  seed,
  providerRevision,
  signal
}) -> MaterialRunResult
```

Precondiciones:

- gate geométrico requerido en PASS;
- Shape descargado y lease pesado liberado/reasignado;
- mesh dentro del rango de faces/vertices soportado;
- memoria estimada dentro del presupuesto;
- capacidad declarada para UV, atlas y mapas requeridos.

Salida obligatoria:

- `RawMaterialArtifact` y `TexturedGeometryArtifact` separados;
- UV generation/reuse method y transformaciones geométricas;
- resolución real de cada atlas;
- channel packing documentado;
- lista explícita de mapas presentes y ausentes;
- tiempos y memoria por etapa;
- provider/revision/weights/seed/lineage.

`textureApplied=true` se deriva del gate final, no de la intención del request ni de que el proveedor haya retornado sin excepción.

## 8. Provider Registry, capabilities y readiness

### 8.1 Descriptor

```text
ProviderDescriptor {
  id: string
  displayName: string
  stage: geometry | material | combined
  manifestId: string
  decisionId: string
  implementation: mlx_python | mlx_swift | pytorch_mps | cuda | documentation
  capabilities: CapabilitySet
  resourceProfile: ResourceProfile
  rollbackProviderId: string | null
}

CapabilitySet {
  inputModes: single[] | captured_multiview[] | generated_support[]
  requiredViewRoles: string[]
  consumesCameras: none | optional | required
  outputGeometry: mesh | gaussian_splat | voxel
  uv: none | generated | preserved
  materialMaps: base_color[] | metallic_roughness[] | normal[] |
                opacity[] | occlusion[] | emissive[]
  maxTextureSize: integer | null
  deterministicSeed: true | false | partial
  cancelMode: cooperative | process_kill | best_effort
}
```

### 8.2 Readiness

```text
ProviderReadiness {
  state: ready | degraded | blocked | unknown
  reasons: ReadinessReason[]
  checkedAt: ISO-8601
  expiresAt: ISO-8601
  codeRevisionMatched: boolean
  weightsDigestMatched: boolean
  runtimeMatched: boolean
  capabilityProbePassed: boolean
  memoryAdmissionPassed: boolean
  licenseAdmissionPassed: boolean
  lastKnownGoodReportId: string | null
}
```

`ready` exige todas las coincidencias y probes anteriores. `degraded` permite ejecución solo cuando la causa no invalida la salida —por ejemplo, cold timing no disponible— y la UI la explica. Pesos descargados con digest desconocido, SDK incompatible, licencia no admitida o memoria insuficiente producen `blocked`.

Readiness se calcula por combinación proveedor/revisión/perfil/input mode. Un proveedor puede estar `ready` para Shape 256 y `blocked` para Paint 2K.

Clasificación, revisión, licencia y benchmark provienen exclusivamente de `RegistryDecision` y `ModelManifest`, referenciados por `decisionId` y `manifestId`. El descriptor no los replica. Solo decisiones `stable|lab` crean providers ejecutables; `reject` y referencias de investigación quedan fuera del router. Readiness contextual no crea nuevos tiers.

### 8.3 Matriz inicial

| Proveedor | Etapa | Tier inicial | Capacidad admitida | Estado 24 GB |
|---|---|---|---|---|
| fork local Hunyuan3D 2.1 MLX pinneado | geometry | lab | single image, mesh | `capability_unverified`; elegible tras probe, digest y benchmark local |
| `Hunyuan3DPaintPipelineMLX` del fork pinneado | material | lab | UV/PBR según output demostrado | `capability_unverified`; 1K solo tras memoria/gate; 2K condicionado; 4K bloqueado |
| TRELLIS.2 Swift/MLX de xocialize | combined | lab | single image, mesh y PBR declarado | opt-in; 17.6 GB de pesos deja margen no demostrado |
| Hunyuan3D-Swift Shape | geometry | lab | single image, mesh | benchmark publicado sugiere ~5.6-7.3 GB; requiere reproducción local |
| Hunyuan3D-Swift Paint | material | reject | RGB/PBR | benchmarks publicados ~38-39 GB; no admitir |
| Hunyuan3D 2mv upstream | geometry | reject | referencia roles front/left/back | no port MLX validado; no provider ejecutable |
| Pixal3D | research-only | reject | referencia de fidelidad pixel-aligned | sin provider ni runtime MLX validado |
| Home3D 1.0 | architecture | reject | referencia modular de mesh/PBR/partes | no aparece en selector ni routing |

La tabla es baseline de política, no reemplaza probes. Un cambio de revisión invalida readiness y exige nuevo informe.

## 9. Provider Router

### 9.1 Entradas y salida

```text
planStageCandidates(RoutePlanRequest) -> StageCandidatePolicy[]
routeStage(StageRouteRequest) -> StageRouteDecision

RoutePlanRequest {
  operationId
  policyConstraintsDigest
  capabilitiesSnapshotId
  requiredStages[]
  requestedTier: stable_only | allow_lab
  requestedProviderByStage: map<stage, providerId | auto>
  qualityProfile
  textureProfile
  deliveryProfile
  licenseContext: LicenseContext
}

LicenseContext {
  territory
  intendedUse
  deliveryProfile
  distributionMode: local_only | redistribute | hosted
  monthlyActiveUsersBand
  aupPolicyDigest
  contextDigest
}

LicenseAdmissionReceipt {
  receiptId
  licenseContextDigest
  manifestId/decisionId/licenseDigest
  decision: allow | deny | unknown
  obligationsDigest
  issuedAt/validUntil
}

StageCandidatePolicy {
  stage
  allowedCandidates[]: { providerId, manifestId, decisionId }
  fallbackOrder[]
  hardConstraintsDigest
  policyDigest
}

StageRouteRequest {
  operationId
  effectivePlanHash
  stageCandidatePolicyDigest
  licenseContextDigest
  inputSafetyAssessmentDigest
  preparedInputSetId
  stage
  qualityProfile: speed | balanced | quality
  executionMode: preview | final
  textureProfile: none | pbr_1k | pbr_2k
  targetProfile: xr_mobile | xr_desktop | web_xr | fabrication_preview
  territory
  intendedUse: personal | research | commercial
  memorySnapshot
}

StageRouteDecision {
  selectedProviderId
  selectedRevision
  frozenCapabilities
  stageAdmissionReceiptId
  reasons[]
  warnings[]
  fallbackPlan: FallbackCandidate[]
  benchmarkReportId
  licenseAdmissionReceiptId
}
```

`planStageCandidates` corre una vez durante `start` y su output entra en `EffectivePlan`. `routeStage` corre exactamente una vez al iniciar cada etapa: geometry al comienzo; material solo tras Geometry Gate y unload. Selecciona dentro de la policy congelada y emite `StageAdmissionReceipt {operationId, stageAttemptId, provider/revision, measuredMemorySnapshot, effectiveCeiling, transientReserve, expiresAt}`. Ese receipt, no el plan, autoriza la carga. Un refresh posterior no cambia una etapa activa.

`routeStage` rechaza drift entre `licenseContextDigest`, candidate policy y admission receipt; nunca reevalúa con contexto mutable.

### 9.2 Algoritmo de elegibilidad

El router filtra en este orden:

1. etapa y tipo de output;
2. tier autorizado;
3. modo de input, roles y cámaras;
4. perfil de calidad/textura;
5. revisión/digest disponible;
6. runtime y probe de capability;
7. territorio, uso y obligaciones de licencia;
8. estimación de memoria más reserva;
9. benchmark vigente y ausencia de gates críticos fallidos;
10. rollback/fallback viable.

Entre candidatos restantes no usa un score único. Construye frontera Pareto sobre éxito de gates, calidad principal, p95 de latencia y memoria pico. La ruta promovida/pinneada gana mientras permanezca en la frontera y no viole restricciones. Un empate se resuelve por menor tier, menor memoria pico, menor p95 y finalmente ID estable para determinismo. License admission genera un `LicenseAdmissionReceipt` inmutable y su ID viaja en `StageRouteDecision`; el auditor deriva después un `LicenseDecisionReceipt` ligado al hash del asset.

### 9.3 Routing inicial

- `single + stable_only + geometry`: exige `RegistryDecision=stable`, binding vigente y readiness `ready`; Hunyuan3D 2.1 MLX no entra mientras permanezca `lab`.
- `single + allow_lab + provider manual`: TRELLIS.2 Swift o Hunyuan3D-Swift si el usuario acepta tier/licencia y admission pasa.
- `captured_multiview`: ningún proveedor single recibe el conjunto fingiendo soporte multivista. Se elige un provider multivista validado o se solicita seleccionar una vista primaria, preservando el resto para gates.
- `generated_multiview`: el provider debe declarar soporte a vistas sintéticas o se usa solo la vista capturada fuente; las generadas permanecen disponibles para evaluación.
- `material pbr_1k`: Paint MLX `lab` solo con `allow_lab` manual, tras unload Shape y admission fresco; luego de promoción puede ser `stable`.
- `material pbr_2k`: requiere benchmark local específico; si falla admission, se ofrece 1K o shape-only.
- `pbr_4k`: no forma parte del schema estable en 24 GB.
- Pixal3D/Home3D nunca son candidatos runtime.

### 9.4 Fallback

Fallback automático solo se permite ante:

- `provider_unavailable`;
- `model_unavailable`;
- `runtime_mismatch` detectado antes de inferencia;
- `timeout_before_content` con terminación confirmada;
- `oom_preflight` antes de cargar;
- `provider_overloaded`;
- `empty_result` sin artefacto parcial comprometido.

No se permite fallback automático ante:

- cancelación;
- licencia bloqueada;
- referencia inválida;
- OOM ocurrido durante un kernel sin terminación confirmada;
- mesh generado pero inválido;
- PBR inválido después de recibir contenido;
- fallo al comprometer artefacto;
- selección manual de proveedor lab, salvo aceptación explícita previa.

Un fallback debe consumir el mismo `PreparedInputSet`, seed cuando el provider lo soporte, perfil y constraints. El informe conserva causa primaria y diferencias de capability. Geometría válida no se regenera porque Paint falle.

## 10. Artefactos canónicos y lineage

### 10.1 Clases de artefacto

```text
OriginalReferenceArtifact
PreparedReferenceArtifact
GeneratedSupportViewArtifact
RawGeometryArtifact
ValidatedGeometryArtifact
RawMaterialArtifact
TexturedGeometryArtifact
OptimizedGeometryArtifact
DeliveryArtifact
ValidationReportArtifact
BenchmarkReportArtifact
```

Cada manifest incluye:

```text
artifactId, schemaVersion, artifactType, state, contentDigest,
byteSize, mediaType, createdAt, operationId, parentArtifactIds[],
inputSetId, providerId, providerRevision, weightsDigest,
parametersDigest, effectiveSeed, coordinateFrame, units,
geometryStats, materialStats, validationReportIds[], warnings[]
```

### 10.2 Reglas de canonicalización

- El formato de intercambio render/export es GLB 2.0; OBJ puede existir solo como temporal interno de un proveedor material.
- Geometría canónica usa sistema right-handed Y-up y unidades metros; conversiones registran matriz y factor exactos.
- Raw nunca se sobrescribe. Clean, remesh, UV, Paint, decimation y compression generan nuevos IDs.
- Un cambio topológico después del gate geométrico exige nuevo gate geométrico.
- Un cambio de UV o material exige nuevo gate PBR.
- Optimización final revalida geometría, materiales, buffers y extensiones GLB.
- Cache key incluye digest de inputs preparados, provider/revision/weights, parámetros, seed, perfil y versión del normalizador.
- Artefacto cacheado solo se reutiliza si todos los digests coinciden y sus reportes siguen compatibles con la versión de gates.
- Un resultado lab queda marcado `lab=true` en toda su descendencia; optimizarlo no lo convierte en stable.

### 10.3 Commit transaccional

Cada etapa escribe temporal privado, valida tamaño y parseo, hace fsync, renombra artefacto, escribe/fsync/renombra manifest y solo entonces publica resultado. Si cancelación gana antes de `committing`, elimina temporal. Si commit gana, cancel devuelve `too_late_to_cancel`. Historial es índice derivado y reconstruible.

## 11. Flujo de datos completo

```text
InputSet
  -> ReferenceDirector.prepare
  -> Reference Gate
  -> ProviderRouter.planStageCandidates (una vez; policy congelada)
  -> ProviderRouter.routeStage(stage=geometry)
  -> StageAdmissionReceipt -> GPU lease
  -> GeometryProvider.generateGeometry
  -> raw GLB commit
  -> Geometry Gate sobre GLB recargado
  -> validated shape commit
  -> provider unload + memoria confirmada
  -> ProviderRouter.routeStage(stage=material)
  -> fresh StageAdmissionReceipt -> GPU lease
  -> MaterialProvider.generateMaterial
  -> textured GLB commit
  -> PBR Gate sobre GLB recargado y renders neutrales
  -> optimize as derived artifact
  -> final Geometry + PBR + GLB Gates
  -> DeliveryArtifact + report + history index
```

Reanudación:

- fallo Reference: no existe Shape;
- fallo Shape antes de commit: puede reintentar provider según política;
- fallo Geometry Gate: conserva raw diagnóstico, bloquea Paint;
- fallo Paint: conserva validated Shape y ofrece export shape-only;
- fallo PBR Gate: conserva textured artifact diagnóstico, no lo ofrece como PBR estable;
- fallo Optimize: conserva PBR validado y permite exportarlo sin optimización;
- fallo Delivery Gate: conserva padre validado y reporta conversión/exportación defectuosa.

## 12. Política de memoria para 24 GB

### 12.1 Presupuesto

La admisión usa memoria no evictable observada, estimación del provider, overhead de preparación/mesh/texturas y reserva transitoria. Presupuesto inicial conservador:

- memoria total nominal: 24 GiB;
- reserva sistema/UI/Electron: 5 GiB;
- margen anti-swap y variabilidad: 3 GiB;
- presupuesto pesado admisible inicial: 16 GiB;
- fórmula canónica: `pinnedNonEvictableBytes + stageMeasuredOrEstimatedPeakBytes + transientReserveBytes <= effectiveCeiling_live`; default `effectiveCeiling_live=16 GiB`, peak excluye transient y cualquier swap bloquea;
- solo una etapa pesada activa;
- cola FIFO máxima de una operación pesada pendiente;
- tercera operación pesada se rechaza con diagnóstico.

Estos valores solo pueden relajarse con benchmark local que mida presión, swap, latencia y estabilidad; no por tamaño nominal de pesos.

### 12.2 Secuencia obligatoria

1. pausar/descargar modelos oMLX no necesarios y confirmar receipt;
2. cargar GeometryProvider;
3. generar y comprometer raw shape;
4. descargar pipeline Shape;
5. ejecutar GC/clear específico del runtime;
6. esperar memoria observable estabilizada con deadline;
7. recalcular admission para Paint;
8. cargar Paint solo si pasa;
9. descargar Paint antes de optimización pesada o siguiente operación.

No se contabiliza memoria liberada hasta confirmación observable. Si no baja al umbral, se devuelve `memory_not_reclaimed`; no se inicia fallback ni Paint.

### 12.3 Perfiles

- `preview`: Shape con límites de faces y sin Paint; objetivo p95 menor y artefacto derivado.
- `balanced`: Shape stable + PBR 1K cuando admission pasa.
- `quality`: Shape stable + PBR 2K únicamente con informe local vigente.
- TRELLIS.2 Swift: lab manual; pesos anunciados de 17.6 GB no prueban que activaciones, conditioner, decode y bake quepan.
- Hunyuan3D-Swift Shape: lab; reproducir benchmarks publicados antes de confiar en ~5.6-7.3 GB.
- Hunyuan3D-Swift Paint: bloqueado por benchmarks publicados ~38-39 GB.

## 13. Gates de calidad y seguridad del artefacto

### 13.1 Gate de referencia

PASS exige bytes/mime/dimensiones válidos, al menos una vista capturada, máscara/crop no críticos y metadatos finitos. Reporta por separado cobertura, recorte, blur, iluminación, roles, cámaras, duplicados y proporción de soporte generado.

### 13.2 Gate geométrico

Se ejecuta sobre el GLB exportado y recargado. Bloqueos:

- parser GLB falla, buffers fuera de rango o referencias rotas;
- NaN/Infinity en positions, normals, indices o transforms;
- cero triángulos o AABB degenerado;
- más de 1% de triángulos degenerados después de clean;
- índices fuera de rango;
- escala o unidades ausentes/incompatibles con target;
- presupuesto XR excedido sin derivado optimizable.

Métricas obligatorias:

- vertices/faces raw, clean y final;
- componentes conectados;
- watertight, manifold, winding y self-intersections;
- área, volumen cuando sea cerrada, AABB y thin structures;
- silhouette IoU por vista capturada y generada, reportadas separadamente;
- depth y normal consistency cuando hay GT/cámaras;
- distancia Chamfer/F-score cuando existe GT alineado.

Las vistas generadas pesan como máximo 0.35 y no pueden compensar una regresión en vistas capturadas.

### 13.3 Gate `generated_textured_pbr`

Se ejecuta sobre el GLB texturizado recargado. PASS PBR exige:

- UV finitas dentro del dominio permitido y cobertura de atlas mayor o igual a 70%;
- al menos un material PBR referenciado por primitivas;
- `baseColorTexture` presente, decodificable y no uniforme/vacía;
- `metallicRoughnessTexture` presente, decodificable y channel packing documentado;
- atlas con resolución real igual al perfil, tolerando solo padding técnico documentado;
- texels finitos y alpha coherente;
- seam energy y bleeding bajo umbrales congelados por corpus;
- tres renders neutrales reproducibles sin material negro, missing texture ni transform roto.

`gltf_material_conformant` es un gate independiente para imports/materiales factor-only; no habilita `textureApplied=true`.

Normal, occlusion, emissive y opacity son capabilities adicionales; su ausencia no puede mostrarse como presente. Si Paint remeshea, también debe pasar gate geométrico.

### 13.4 Gate final GLB/XR

- GLB parseable en validador independiente y viewer de la app;
- buffers, bufferViews, accessors, images y materiales alcanzables;
- transform root, unidades y AABB correctos;
- target `web_xr`: presupuesto congelado de faces, draw calls, atlas y bytes;
- target `xr_mobile`: presupuesto más estricto versionado por perfil;
- no extensiones obligatorias no soportadas por el viewer objetivo;
- lineage completo hasta referencias originales;
- PBR solo se etiqueta si el gate PBR final permanece PASS después de optimizar.

## 14. Taxonomía de errores

```text
reference_invalid
reference_inconsistent
camera_invalid
capability_mismatch
provider_unavailable
provider_overloaded
provider_not_ready
runtime_mismatch
weights_mismatch
license_blocked
memory_admission_denied
memory_not_reclaimed
oom_preflight
oom_during_inference
timeout_before_content
timeout_after_partial
primary_may_still_be_running
cancel_requested
cancelled
geometry_generation_failed
geometry_invalid
material_generation_failed
pbr_invalid
artifact_commit_failed
cache_incompatible
export_invalid
```

Todo error incluye `code`, `stage`, `operationId`, `providerId`, `retryable`, `fallbackAllowed`, `userMessage`, `technicalSummary` redactado y `reportId`. Nunca incluye key, body HTTP completo, base64, path real ni stack con entorno.

Política:

- errores de input, licencia, capability y gates no son retryable automáticamente;
- infraestructura antes de contenido puede usar un fallback congelado;
- OOM durante inferencia obliga a terminar/descargar y confirmar memoria antes de cualquier acción;
- timeout tras output parcial no cambia de proveedor automáticamente;
- fallo Paint propone shape-only sin regenerar Shape;
- fallo de commit no publica resultado ni historial;
- cancelación permanece `cancel_requested` hasta ack o kill confirmado.

## 15. Seguridad, privacidad y procedencia

- Renderer solo recibe IDs, estado, previews acotadas y reportes redactados.
- Proveedores reciben assets mediante directorios/FDs confinados y entorno allowlisted.
- Ningún proceso hijo hereda `HOME`, proxies o variables `*_KEY`, `*_TOKEN`, `*_SECRET` salvo token efímero explícito del servicio.
- Inputs, máscaras, vistas generadas y meshes no salen de loopback en esta arquitectura.
- Manifest registra repo, commit/revisión, digest de pesos, licencia, fecha de aceptación y tier.
- Vistas generadas registran modelo, revisión, seed y vista fuente.
- Reports no mezclan métricas de capturadas y generadas.
- Cache e historial no contienen base64, keys ni cuerpos completos de proveedor.
- Un provider comunitario nuevo se ejecuta en runner separado con mínimo privilegio hasta promoción.

## 16. Benchmark y promoción

### 16.1 Corpus

Corpus Imagen a 3D versionado de 20 objetos como mínimo:

- 8 objetos cotidianos rígidos;
- 4 objetos con partes finas;
- 4 objetos con cavidades o concavidades;
- 2 objetos simétricos;
- 2 objetos con materiales metálico/roughness diferenciables.

Cada objeto incluye, cuando exista, 8 vistas capturadas calibradas, máscaras, mesh GT normalizado, escala y material GT. Evaluación single usa una vista congelada; captured multiview usa conjuntos de 3 y 6 vistas congelados; generated support usa la misma vista fuente y seeds fijadas. Seeds del provider: 3 por caso.

### 16.2 Métricas

Geometría:

- tasa de gate geométrico PASS;
- F-score como métrica principal con GT;
- Chamfer, normal consistency y silhouette IoU;
- thin-structure recall, componentes y topology;
- p50/p95 de tiempo y memoria pico.

PBR:

- tasa de gate PBR PASS;
- albedo con GT: sRGB decode → RGB lineal → XYZ/Lab D65 → CIEDE2000; LPIPS/SSIM se reportan en su dominio declarado;
- roughness MAE y metallic F1 con GT;
- seam energy, cobertura UV y bleeding;
- consistencia de renders bajo tres HDRI neutrales;
- sin GT, comparación pairwise ciega con tres evaluadores por muestra.

Procedimiento:

- corpus, primary metric, seeds, perfiles y márgenes se congelan antes del run;
- bootstrap pareado por objeto con seeds anidados, CI 95%;
- single, captured multiview y generated support se reportan separados;
- Shape y PBR no se agregan en un score;
- cold requiere unload/restart verificado; si no, usar `first observed`;
- fallos/OOM cuentan como fallos, no se excluyen del denominador;
- cada informe conserva outputs y manifests para auditoría.

### 16.3 Promoción `lab` a `stable`

Un provider lab solo puede proponerse para promoción si:

1. completa 100% del corpus sin crash, hang, swap sostenido ni OOM;
2. gates críticos de seguridad, geometry, PBR cuando aplique y GLB final tienen 100% PASS;
3. tasa funcional no es inferior al baseline por más de 2 puntos porcentuales;
4. mejora F-score al menos 3% relativo con CI pareado 95% excluyendo 0, o reduce p95 de latencia/memoria al menos 20% con calidad dentro de -2 puntos;
5. memoria pico medida más reserva de 3 GiB cabe bajo 24 GiB sin presión crítica ni swap sostenido;
6. licencia, territorio, atribuciones y redistribución están aprobados;
7. revisión de código/pesos queda pinneada por digest;
8. cancelación, unload, cache y rollback pasan pruebas adversariales;
9. rollback al provider stable actual completa smoke real;
10. una persona aprueba explícitamente el registro de promoción.

Una revisión nueva vuelve a `lab` hasta repetir gates afectados.

## 17. Plan de gates de implementación

### Gate A: contratos y caracterización

- congelar baseline actual sin modificar outputs;
- caracterizar entrada, seed, shape, Paint y GLB existentes;
- definir schemas versionados para InputSet, descriptors, decisions y manifests;
- añadir fixtures single/captured/generated/mixed.

Salida medible: schemas rechazan origen falso, cámara no finita, roles incompatibles y manifests sin digest.

### Gate B: Reference Director

- preparación inmutable, máscaras, crop reversible, roles y cámaras;
- assessment desagregado y gate de reconstruibilidad;
- cache por digest/config y lineage de vistas generadas.

Salida medible: mismo input/config produce mismo digest; original no cambia; generated nunca migra a captured.

### Gate C: Registry y readiness

- descriptors pinneados, capability probes, resource/license profiles;
- readiness por provider/revision/profile/input mode;
- invalidación por digest/runtime/gate version.

Salida medible: provider descargado pero no verificado queda blocked; Pixal3D/Home3D no aparecen en selector runtime.

### Gate D: Provider Router

- filtering exacto, Pareto, tie-break determinista y decisión congelada;
- rutas stable/lab separadas;
- fallback acotado con terminación confirmada.

Salida medible: captured multiview nunca se entrega silenciosamente a provider single; selección lab exige opt-in.

### Gate E: artefactos canónicos

- manifests, cache keys, commit atómico y lineage;
- raw/validated/textured/optimized/delivery separados;
- migración de resultados legacy sin inventar procedencia.

Salida medible: crash antes de manifest no produce historial; startup reconcilia temporales; optimización no muta raw.

### Gate F: Hunyuan `lab` hacia stable objetivo

- Shape MLX pinneado detrás de `GeometryProvider`;
- Paint MLX pinneado detrás de `MaterialProvider`;
- seed end-to-end, unload receipt y admission fresco;
- PBR 1K real y 2K solo si benchmark pasa.

Salida medible: GLB shape y PBR pasan gates finales; fallo Paint conserva shape; 4K se rechaza antes de carga.

### Gate G: laboratorio aislado

- adaptadores TRELLIS.2 Swift y Hunyuan3D-Swift sin cambiar default;
- runner y cache separados;
- benchmarks de capability, memoria, parity, calidad y licencia.

Salida medible: cerrar lab no afecta stable; outputs permanecen marcados lab; Paint Swift se bloquea en 24 GB.

### Gate H: cadena y adversarial

- single/captured/generated end-to-end;
- fallos inyectados en preparación, load, infer, unload, Paint, commit y export;
- cancelación en cada transición;
- browser/UI muestra proveedor, tier, procedencia y degradaciones reales.

Salida medible: cero rutas arbitrarias, secretos, resultados stale o claims PBR falsos; reanudación evita trabajo ya comprometido.

## 18. Matriz mínima de pruebas

### Unitarias

- `InputSet`: cardinalidad por mode, origen, lineage, roles, cámaras, confianza y límites.
- `ReferenceDirector`: orientación, crop reversible, máscara vacía, duplicados, contradicción y determinismo.
- `CapabilityMatcher`: single vs multiview, cámaras requeridas, material maps, texture size y target.
- `ReadinessEvaluator`: digest/runtime/memory/license/report vencido.
- `ProviderRouter`: filtering, Pareto, tie-break, tier manual y decisión congelada.
- `MemoryAdmission`: bordes 16/24 GiB, memoria no liberada, reserva y operación concurrente.
- `ErrorPolicy`: retry/fallback prohibido por código y etapa.
- `Manifest`: digest, lineage, lab taint y cache compatibility.

### Contrato

- cada GeometryProvider retorna raw GLB recargable o error normalizado;
- cada MaterialProvider declara mapas reales y no controla `textureApplied`;
- unload devuelve receipt o bloquea siguiente carga;
- provider no puede leer/escribir fuera de su root;
- cambio de revisión invalida fixtures y readiness.

### Integración

- single -> Hunyuan Shape -> gate -> shape-only delivery;
- single -> Hunyuan Shape -> unload -> Paint 1K -> PBR gate -> GLB;
- Paint falla -> shape-only sin repetir Shape;
- captured multiview sin provider compatible -> diagnóstico, no flatten silencioso;
- generated support -> métricas separadas y autoridad reducida;
- provider stable no disponible -> fallback permitido solo antes de contenido;
- timeout/kill -> no liberar lease antes de confirmación;
- crash durante commit -> no manifest parcial ni historial corrupto;
- cache hit exacto y miss por seed/revision/gate version.

### Adversariales

- symlink swap, path traversal y asset ID ajeno;
- image bomb, mime falso, EXIF hostil y matriz con NaN;
- vista generada manipulada como capturada;
- manifest con pesos/revisión falsos;
- OOM preflight vs OOM durante kernel;
- doble cancel, resultado tardío, cancel durante commit;
- backend impostor en loopback;
- GLB con accessors fuera de rango, texturas vacías o UV NaN;
- remesh que destruye thin structures;
- provider que afirma PBR pero exporta material sin mapas;
- memoria que no baja después de unload;
- dos operaciones pesadas y tercera solicitud.

### Benchmark/live gates

- corpus completo con tres seeds;
- peak memory y presión observada, no solo tamaño de pesos;
- smoke real de ruta estable después de rollback;
- viewer carga delivery GLB y consola permanece sin errores;
- reporte ciego PBR y outputs auditables;
- build/tests con código de salida cero.

## 19. Criterios de aceptación finales

- `InputSet` distingue de forma irreversible `captured` y `generated`.
- Ningún provider single consume multiview como si fuera single sin decisión explícita y visible.
- Hunyuan Shape/Paint se acceden solo mediante contratos de provider.
- Stable automático usa revisión y pesos pinneados; `latest` queda prohibido.
- TRELLIS.2 Swift y Hunyuan3D-Swift requieren opt-in y producen lineage lab.
- Pixal3D/Home3D son referencias sin acciones de carga/descarga/ejecución.
- Readiness se calcula por capability/perfil y enumera razones.
- Admission impide superar presupuesto conservador de 24 GB.
- Shape y Paint nunca quedan residentes simultáneamente sin evidencia específica.
- Fallo Paint conserva shape válido y no activa regeneración.
- `textureApplied` depende del GLB final validado.
- Vistas capturadas y generadas tienen métricas separadas.
- Cache no cruza revisions, seeds, configs ni versiones de gate.
- Todos los errores son correlacionados, redactados y accionables.
- Artefactos raw son inmutables y lineage llega al original.
- Optimización/exportación vuelven a ejecutar gates afectados.
- Promoción lab exige benchmark, licencia, rollback y aprobación humana.

## 20. Riesgos residuales y mitigaciones

| Riesgo | Consecuencia | Mitigación vinculante |
|---|---|---|
| Una sola imagen no observa backside | geometría/textura alucinada | mostrar incertidumbre; no llamar reconstrucción métrica; evaluar vistas capturadas aparte |
| Vistas generadas se autoconsisten pero son falsas | score inflado | autoridad <=0.35, métricas separadas y veto a compensar regresión capturada |
| MLX comparte memoria con sistema/Electron/oMLX | swap, hang u OOM | presupuesto 16 GiB, single-flight, unload receipt y reserva 3 GiB |
| Tamaño de pesos TRELLIS.2 cercano al límite | activaciones/bake no caben | lab manual y benchmark end-to-end antes de admisión |
| Paint Hunyuan excede memoria según implementación | pérdida de Shape o crash | Shape comprometido primero, 1K inicial, fallback shape-only |
| Port comunitario diverge del upstream | calidad o semántica distintas | parity fixtures, revisión/digest pinneados y corpus común |
| Remesh/decimation destruye detalle o UV | output final peor que intermedio | artefactos derivados y gates posteriores a cada cambio |
| Licencias incompatibles por territorio/uso | distribución no autorizada | `LicenseProfile` en admission, inventario/atribución y bloqueo previo |
| Readiness stale | selección de runtime roto | TTL corto, digest/runtime probes y congelación por operación |
| Cancelación MLX no interrumpe kernel | concurrencia y memoria inseguras | estado requested, kill/ack confirmado antes de lease/fallback |
| Métrica única premia tradeoffs ocultos | promoción errónea | frontera Pareto y métricas geometry/PBR/latencia/memoria separadas |

## 21. Licencias y política inicial

- **Hunyuan3D 2.1:** Tencent Hunyuan Community License. El diseño debe bloquear automáticamente uso no autorizado por territorio; la licencia publicada excluye UE, Reino Unido y Corea del Sur de su territorio autorizado e impone condiciones adicionales para despliegues de gran escala. Requiere revisión legal antes de distribución mundial.
- **TRELLIS.2:** código/modelo principal MIT según upstream; dependencias y DINOv3 mantienen licencias/atribuciones propias. El manifest conserva inventario completo, no solo licencia del repo superior.
- **Hunyuan3D-Swift:** el código del port no reemplaza la licencia de pesos ni dependencias originales.
- **Stable Fast 3D/SPAR3D:** Stability AI Community License; no se incorporan por similitud técnica sin revisar umbrales comerciales, registro y atribución.
- **Apple SHARP:** pesos research-only y output Gaussian Splat, no mesh PBR; queda fuera de producto.
- **Pixal3D/Home3D:** citarlos como investigación no concede derecho de ejecutar, redistribuir pesos ni copiar datasets.

El `LicenseProfile` registra SPDX cuando exista, texto/digest de licencia, territorios, usos permitidos, umbral comercial, atribuciones, redistribución y fecha de revisión. `unknown` equivale a `license_blocked`, no a permitido.

## 22. Fuentes primarias

### Proveedores y ports

- Hunyuan3D 2.1 oficial: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Paper Hunyuan3D 2.1: https://arxiv.org/abs/2506.15442
- Licencia Hunyuan3D 2.1: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE
- Hunyuan3D 2/2mv oficial: https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- Pesos Hunyuan3D 2mv: https://huggingface.co/tencent/Hunyuan3D-2mv
- Port Hunyuan3D-Swift/MLX: https://github.com/ZimengXiong/Hunyuan3D-Swift
- TRELLIS.2 oficial: https://github.com/microsoft/TRELLIS.2
- Proyecto TRELLIS.2: https://microsoft.github.io/TRELLIS.2/
- Pesos TRELLIS.2 MLX comunitarios: https://huggingface.co/xocialize/trellis2-mlx
- Port TRELLIS.2 MLX Swift: https://github.com/xocialize/mlx-trellis2-swift
- Stable Fast 3D: https://github.com/Stability-AI/stable-fast-3d
- SPAR3D: https://github.com/Stability-AI/stable-point-aware-3d
- TripoSG: https://github.com/VAST-AI-Research/TripoSG
- TripoSR: https://github.com/VAST-AI-Research/TripoSR
- Apple SHARP: https://github.com/apple/ml-sharp
- Licencia de pesos SHARP: https://github.com/apple/ml-sharp/blob/main/LICENSE_MODEL

### Investigación arquitectónica

- Pixal3D: https://huggingface.co/papers/2605.10922
- Home3D 1.0: https://arxiv.org/abs/2606.27923
- ReLi3D: https://huggingface.co/papers/2603.19753
- GenRecon: https://arxiv.org/abs/2605.23888
- MeshGen: https://github.com/heheyas/MeshGen
- MVPainter: https://arxiv.org/abs/2505.12635
- PacTure: https://arxiv.org/abs/2505.22394

Las cifras externas de memoria son evidencia de orientación, no acceptance local. Solo mediciones reproducidas en el Mac objetivo alimentan admission y promoción.
