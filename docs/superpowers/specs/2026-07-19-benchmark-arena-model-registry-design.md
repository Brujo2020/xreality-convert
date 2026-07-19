# Benchmark Arena y Model Registry reproducible

Fecha: 2026-07-19
Estado: diseño aprobado; especificación cerrada para plan de implementación
Ámbito: registry inmutable, benchmark por pipeline, perfiles de selección y promoción de modelos locales
Hardware de referencia: Apple M5 Pro, 24 GB de memoria unificada

## 1. Objetivo

Construir una única fuente de verdad para identificar, comparar, promover, rechazar y reproducir modelos locales sin depender de nombres, etiquetas mutables ni reputación externa. Un modelo solo puede participar mediante un `ModelManifest` content-addressed que fija pesos, licencia, runtime y configuración. Un benchmark solo puede influir en selección estable mediante un reporte inmutable ejecutado sobre corpus sellado, hardware compatible y artefactos íntegros.

El sistema debe responder de forma comprobable:

1. Qué bytes, revisión y licencia se ejecutaron.
2. Qué pipeline, perfil, prompt, seed y configuración produjeron cada medición.
3. Si el candidato cabe realmente en 24 GB sin swap/OOM ni concurrencia GPU oculta.
4. Si mejora una métrica prioritaria con intervalo de confianza, sin regresiones fuera de tolerancia.
5. Por qué un modelo está en `stable`, `lab` o `reject`.
6. Cómo volver al manifest estable anterior sin redescubrir ni descargar nada.

No existe “mejor modelo” global. La unidad de decisión es:

```text
pipeline + profile + hardwareClass + manifestId + benchmarkSpecId
```

## 2. Relación con diseños existentes

Este documento especializa el registry y los benchmarks definidos en:

- `docs/superpowers/specs/2026-07-19-end-to-end-asset-pipeline-design.md`
- `docs/superpowers/specs/2026-07-18-omlx-text-to-3d-design.md`

El diseño integral prevalece en seguridad de procesos, `WorkflowCoordinator`, `AssetRepository`, límites de entrada/salida, CSG IR, lifecycle y exclusión GPU. Este documento prevalece en identidad de modelos, clasificación, reproducibilidad, comparación estadística, promoción y rollback de selección.

No se modifica automáticamente ningún default de producción. El arena emite una propuesta explicable; la promoción requiere una decisión explícita registrada.

## 3. Resultado verificable

La entrega queda completa cuando:

- Dos artefactos con bytes distintos nunca comparten `manifestId`, aunque tengan el mismo nombre visible.
- Dos manifests semánticamente iguales producen el mismo hash canónico independientemente del orden de claves JSON.
- `stable`, `lab` y `reject` son decisiones append-only separadas del manifest inmutable.
- Un alias mutable como `latest`, una revisión HF no resuelta o un blob sin digest impiden promoción.
- Cada pipeline ejecuta su corpus y métricas propias; no existe score compuesto transversal.
- `speed`, `balanced` y `quality` resuelven distintos puntos de una frontera Pareto, no pesos mágicos sobre un score único.
- Toda comparación de promoción usa muestras pareadas, CI 95% y criterios congelados antes del run.
- Un run con digest, licencia, corpus, runtime o hardware incompatibles queda inválido para promoción, aunque sus números sean favorables.
- La selección estable anterior puede restaurarse mediante un nuevo `RegistryDecision` sin mutar ni borrar evidencia.
- Tests unitarios, contract tests, fault injection y un run opt-in real prueban los invariantes.

## 4. Principios vinculantes

1. **Bytes antes que nombre:** identidad por hash canónico y digests de artefactos.
2. **Manifest inmutable, decisión mutable por append:** reclasificar no reescribe historia.
3. **Benchmark por producto:** Texto→Imagen, Texto→CSG IR, Imagen→3D Shape y PBR tienen métricas diferentes.
4. **Pareto antes que ranking:** calidad, latencia y memoria permanecen separadas.
5. **CI antes que diferencia puntual:** una mejora sin evidencia estadística no promueve.
6. **Hardware real antes que estimación:** tamaño en disco no sustituye peak RSS, memoria activa, presión ni swap.
7. **Offline durante medición:** el arena no descarga modelos, dependencias ni corpus.
8. **Licencia como gate:** compatibilidad técnica no vence restricciones de uso.
9. **Rollback siempre disponible:** promover nunca destruye baseline ni reportes anteriores.
10. **No auto-promoción:** el sistema propone; una decisión autorizada activa.

## 5. Límites

### Incluye

- `ModelManifest` versionado y content-addressed.
- Registry local append-only con estados efectivos `stable`, `lab` y `reject`.
- Captura de commits HF/GitHub, digests de archivos/blobs y evidencia de licencia.
- Arena secuencial por pipeline y perfil.
- Corpus sellados, seeds fijas, orden de ejecución determinista y holdout.
- Métricas de artefacto, calidad, latencia, memoria y estabilidad.
- Fronteras Pareto, CI pareado, propuestas de promoción y rollback.
- Supply-chain, cuarentena, auditoría, retención y tests.
- Inventario inicial de candidatos conocidos al 2026-07-19.

### Excluye

- Descargar, instalar, borrar, cuantizar o convertir pesos.
- Entrenar, fine-tunear o reparar modelos.
- Cambiar prompts de producción durante un run sellado.
- Ejecutar benchmarks cloud o comparar precios de APIs remotas.
- Crear un leaderboard público o telemetría externa.
- Aplicar automáticamente el ganador.
- Sustituir gates de seguridad/artifact validation por evaluación humana.
- Inventar compatibilidad a partir del nombre del modelo.

## 6. Modelo de dominio

### 6.1 Identificadores

Todos los IDs derivados usan SHA-256 hexadecimal en minúsculas:

```text
manifestId      = sha256(canonicalJson(ModelManifest sin manifestId))
benchmarkSpecId = sha256(canonicalJson(BenchmarkSpec sin benchmarkSpecId))
runId           = sha256(canonicalJson(RunEnvelope sin runId ni mediciones))
reportId        = sha256(canonicalJson(BenchmarkReport sin reportId))
decisionId      = sha256(canonicalJson(RegistryDecision sin decisionId))
```

Canonical JSON aplica RFC 8785 JCS: UTF-8, claves ordenadas, números JSON canónicos, sin NaN/Infinity, sin comentarios ni campos desconocidos. Timestamps no participan en identidad de manifest ni spec; sí participan en envelopes y decisiones auditables.

### 6.2 `ModelManifest`

Contrato lógico obligatorio:

```text
ModelManifest {
  schemaVersion: 1
  logicalId: string
  displayName: string
  family: string
  variant: string
  pipelineCapabilities: PipelineCapability[]
  source: SourceIdentity
  artifacts: ArtifactDigest[]
  license: LicenseEvidence
  runtime: RuntimeContract
  resources: ResourceDeclaration
  generationDefaults: GenerationDefaults
  provenance: ProvenanceEvidence
  createdBy: ToolIdentity
}
```

Restricciones:

- `logicalId`: `[a-z0-9][a-z0-9._/-]{2,127}`; etiqueta humana, nunca identidad criptográfica.
- `displayName`: 1-128 caracteres UTF-8, sin control chars.
- `family` y `variant`: 1-64 caracteres cada uno.
- `pipelineCapabilities`: subconjunto no vacío de `text_image`, `text_csg_ir`, `image_3d_shape`, `image_3d_pbr`, `mesh_optimize`.
- Todos los arrays se ordenan antes de canonicalizar por clave estable documentada.
- No admite campos de estado, resultados de benchmark, rutas locales absolutas, secretos, tokens, URLs con credenciales ni timestamps de acceso.

### 6.3 `SourceIdentity`

```text
SourceIdentity {
  kind: "huggingface" | "ollama" | "github" | "local"
  repository: string
  requestedRef: string
  resolvedRevision: string
  upstreamUrl: https URL
  retrievedAt: RFC3339 UTC
}
```

Reglas:

- Hugging Face exige commit SHA de 40 hex en `resolvedRevision`; branch/tag se conserva solo en `requestedRef`.
- GitHub exige commit SHA de 40 hex.
- Ollama exige digest `sha256:<64 hex>` del manifest remoto y digests de todos los blobs usados.
- `local` se admite solo para artefactos creados por conversión registrada; debe enlazar manifests de inputs en `provenance.parentManifestIds`.
- `latest`, `main`, tags o fechas nunca bastan como `resolvedRevision` estable.

### 6.4 `ArtifactDigest`

```text
ArtifactDigest {
  role: "weights" | "config" | "tokenizer" | "processor" |
        "template" | "runtime_code" | "vae" | "encoder" | "license"
  relativePath: string
  sizeBytes: integer
  sha256: 64 lowercase hex
  upstreamEtag: string | null
}
```

- Incluye cada archivo consumido durante inferencia, no solo los shards de pesos.
- `relativePath` no contiene `..`, symlinks ni separadores absolutos.
- Shards se ordenan lexicográficamente.
- Un cambio de `chat_template.jinja`, tokenizer, config, VAE, encoder o runtime code crea otro manifest.
- Archivos ignorados explícitamente se registran en `provenance.ignoredFiles` con razón; nunca se omiten silenciosamente.

### 6.5 `LicenseEvidence`

```text
LicenseEvidence {
  identifier: string
  category: "permissive" | "community" | "noncommercial" | "unknown"
  sourceUrl: https URL
  textSha256: 64 lowercase hex
  allowsCommercialUse: boolean
  requiresAttribution: boolean
  requiresUsagePolicy: boolean
  excludedTerritories: string[]
  allowedUseClasses: string[]
  hostedUseAllowed: boolean | null
  redistributionAllowed: boolean | null
  additionalLicenseMauThreshold: integer | null
  prohibitedUsePolicyDigest: 64 lowercase hex | null
  redistributionConstraints: string[]
  acceptedBy: "bundled" | "user" | "organization" | "not_required"
  acceptedAt: RFC3339 UTC | null
}
```

Reglas de admisión:

- `unknown` no puede pasar de `lab`.
- `noncommercial` no puede ser `stable` en un perfil de producto comercial.
- Una licencia custom requiere snapshot local del texto y digest; enlazar la página actual no basta.
- Si el upstream cambia licencia o AUP, el manifest existente conserva evidencia histórica; una nueva instalación genera otro manifest/evaluación legal.
- La licencia del runtime y la de los pesos se validan por separado.

### 6.6 `RuntimeContract`

```text
RuntimeContract {
  engine: "ollama" | "omlx" | "mflux" | "hunyuan_mlx" | "utility"
  engineVersion: semver-or-build-id
  adapterVersion: semver-or-git-sha
  modelFormat: "ollama_blob" | "mlx_safetensors" | "safetensors" | "local_bundle"
  entrypoint: fixed adapter identifier
  requiresRemoteCode: boolean
  capabilitiesVerified: string[]
  outputLimitTokens: integer | null
  contextLimitTokens: integer | null
  quantization: string
}
```

- `requiresRemoteCode=true` fuerza `lab` de forma permanente y runner aislado; auditoría/pin no lo habilitan para `stable`. Promoción estable exige `requiresRemoteCode=false`.
- Capacidades provienen de contract tests, nunca substring del nombre.
- Texto→CSG IR general exige `outputLimitTokens >= 4096`.
- Runtime image necesita prueba de generación binaria y metadata de dimensiones/formato.

### 6.7 `ResourceDeclaration`

```text
ResourceDeclaration {
  artifactBytes: integer
  estimatedResidentBytes: integer | null
  measuredPeakBytes: integer | null
  transientReserveBytes: integer
  maxInputPixels: integer | null
  supportedOutputSizes: string[]
}
```

`estimatedResidentBytes` solo permite entrada a `lab`. La promoción usa `measuredPeakBytes` del reporte válido. En M5 Pro 24 GB el ceiling operativo inicial es `effectiveCeiling_live`, cuyo default es 16 GiB. Admission:

```text
pinnedNonEvictableBytes + measuredPeakBytes + transientReserveBytes <= effectiveCeiling_live
```

El benchmark registra además peak process RSS, memoria activa del sistema, pressure level y swap delta. Cualquier swap delta positivo invalida promoción en todos los perfiles.

### 6.8 `GenerationDefaults`

Contiene únicamente parámetros efectivos y acotados: seed policy, temperatura, top-p/top-k, tokens, steps, guidance, resolución, dtype, quantization mode y flags de thinking. Cada pipeline define los campos permitidos. Un campo extra cambia el hash o invalida schema.

Para modelos con razonamiento separado se registra parser exacto. `gpt-oss` exige Harmony; Qwen/Gemma con thinking exigen separación verificable entre reasoning y respuesta final. Concatenar reasoning a CSG IR es fallo de contrato.

### 6.9 `ProvenanceEvidence`

```text
ProvenanceEvidence {
  parentManifestIds: string[]
  conversionTool: ToolIdentity | null
  conversionCommandDigest: string | null
  upstreamModelCardSha256: string
  ignoredFiles: { relativePath, reason }[]
  notes: string[]
}
```

Una cuantización comunitaria debe enlazar al modelo base y registrar herramienta/config de conversión. Ausencia de parent verificable fuerza `lab`; lineage contradictorio fuerza `reject`.

## 7. Registry append-only

### 7.1 Separación manifest/estado

`ModelManifest` nunca cambia. La clasificación vive en `RegistryDecision`:

```text
RegistryDecision {
  schemaVersion: 1
  decisionId: derived SHA-256
  manifestId: SHA-256
  pipeline: PipelineCapability
  hardwareClass: "apple-m5-pro-24gb"
  previousDecisionId: SHA-256 | null
  classification: "stable" | "lab" | "reject"
  profileEligibility: ("speed" | "balanced" | "quality")[]
  reasonCodes: DecisionReason[]
  reportIds: SHA-256[]
  approvedBy: string
  approvedAt: RFC3339 UTC
  expiresAt: RFC3339 UTC | null
}
```

`DecisionReason` es enum cerrado:

```text
initial_inventory, benchmark_pass, benchmark_regression, integrity_failure,
license_incompatible, license_unknown, runtime_unavailable,
capability_unverified, output_limit, memory_admission, crash_or_oom,
artifact_invalid, security_review, superseded, emergency_quarantine,
manual_research_only
```

El estado efectivo es la última decisión válida de la cadena. Cadena rota, ciclo, firma/hash inválido o `previousDecisionId` inexistente produce cuarentena y ningún auto-select.

### 7.2 Semántica de estados

- `stable`: seleccionable automáticamente solo para pipelines/perfiles enumerados y hardware compatible.
- `lab`: seleccionable manualmente con riesgos visibles; nunca fallback silencioso ni default.
- `reject`: no ejecutable desde UI normal; conserva evidencia y puede reingresar solo mediante nuevo manifest o decisión explícita sustentada por nueva evidencia.

Una emergencia puede añadir `reject/emergency_quarantine` sobre un stable. Recuperar requiere decisión posterior con reporte o revisión de seguridad; nunca borrar la cuarentena.

### 7.3 Selección estable

La clave de selección es:

```text
StableBinding {
  pipeline,
  profile,
  hardwareClass,
  territory,
  intendedUse,
  distributionMode,
  monthlyActiveUsersBand,
  manifestId,
  decisionId,
  reportId
}
```

El binding se actualiza por temp + fsync + rename. Antes de commit se verifica nuevamente cadena, hashes, licencia estructurada/AUP contra todo el contexto y presencia de artefactos. Cualquier territorio, uso, distribución, MAU o política desconocida/incompatible falla cerrado y mantiene el binding anterior.

Rollback agrega una decisión `stable/superseded` para el manifest anterior y conmuta el binding; no reescribe reports ni manifiestos.

### 7.4 Persistencia

Layout lógico main-owned:

```text
model-registry/
  manifests/sha256/<manifestId>.json
  decisions/sha256/<decisionId>.json
  benchmark-specs/sha256/<benchmarkSpecId>.json
  runs/sha256/<runId>/run.json
  runs/sha256/<runId>/measurements.ndjson
  reports/sha256/<reportId>.json
  bindings/<hardwareClass>/<pipeline>/<profile>/<licenseContextDigest>.json
  evidence/licenses/<sha256>.txt
  evidence/model-cards/<sha256>.md
  index/registry.json
```

`index/registry.json` es derivado y reconstruible. Ningún renderer recibe paths; usa IDs opacos. Escrituras siguen el protocolo transaccional de `AssetRepository`. Archivos son `0600`, directories `0700`, sin symlink traversal.

## 8. Benchmark Arena

### 8.1 Unidad de benchmark

`BenchmarkSpec` fija antes de ejecutar:

```text
BenchmarkSpec {
  schemaVersion: 1
  pipeline: PipelineCapability
  profile: "speed" | "balanced" | "quality"
  corpus: CorpusIdentity
  seeds: integer[]
  productionPromptSha256: SHA-256
  productionAdapterSha256: SHA-256
  compilerOrValidatorSha256: SHA-256
  baselineManifestId: SHA-256
  candidateManifestIds: SHA-256[]
  metricDefinitions: MetricDefinition[]
  hardGates: GateDefinition[]
  promotionRule: PromotionRule
  executionPolicy: ExecutionPolicy
}
```

Modificar corpus, prompts, adapter, compilador, métrica, baseline, candidatos, profiles o thresholds crea otro `benchmarkSpecId`.

### 8.2 Hardware fingerprint

Todo run registra:

- Chip exacto `Apple M5 Pro`.
- Memoria física `24 GB` y bytes reportados por sistema.
- macOS build, kernel y arquitectura.
- Power source y low-power mode.
- Estado térmico inicial/final.
- Memoria wired/active/compressed, swap usado y pressure.
- Versiones Metal, MLX, oMLX, Ollama, MFLUX, Python, Node/Electron y adapters.
- App git commit y flag dirty; si dirty, hash del diff sin incluir secretos.
- Modelos pinned/no-evictable y bytes residentes.

Un reporte de M5/M5 Max, 32 GB o 16 GB puede informar investigación, pero no promover bindings `apple-m5-pro-24gb`.

### 8.3 Aislamiento y scheduling

- Máximo un workload GPU pesado activo.
- Arena adquiere lease exclusivo del `WorkflowCoordinator`.
- Se detienen polling, previews y background inference durante medición.
- Candidatos se ejecutan en bloques por item/seed con orden pseudorrandomizado por `sha256(benchmarkSpecId + itemId + seed)` para evitar sesgo térmico.
- Cada candidato recibe un warmup descartado por combinación de shape/config; fallos de warmup sí se reportan.
- Entre modelos se exige unload ack, GC/clear aplicable y memoria dentro de 5% del baseline pre-run durante 30 s. Si no converge, run se marca `contaminated`.
- `cold` solo significa proceso/runtime reiniciado y modelo no residente, con verificación. En otro caso se etiqueta `first_observed`.
- `warm` exige modelo residente y una inferencia de warmup completada.
- Timeout, cancel, OOM y kill son observaciones, no muestras eliminables.
- La red se bloquea durante medición salvo loopback allowlisted. Un intento de acceso externo invalida run y falla supply-chain gate.

### 8.4 `BenchmarkRun`

Estados:

```text
created -> verifying -> warming -> running -> analyzing -> completed
created|verifying|warming|running|analyzing -> failed|cancelled|invalid
```

Un run se reanuda solo al límite de un item/seed. Nunca reusa medición parcial. Cada línea NDJSON incluye `runId`, `manifestId`, `itemId`, `seed`, `attempt`, timestamps monotónicos, resultado, métricas, errores normalizados y hashes de outputs.

Resultados terminales:

- `completed`: todas las muestras y análisis presentes.
- `failed`: infraestructura impidió completar; conserva parciales, no promueve.
- `cancelled`: cancelación confirmada; no promueve.
- `invalid`: contaminación, drift o gate de reproducibilidad; no promueve.

### 8.5 Repetición y estadística

- Bootstrap pareado con 10.000 resamples por `itemId`; seeds permanecen anidadas dentro del item.
- CI percentile 95%, generador PRNG PCG64 y seed estadística `20260719`.
- Proporciones reportan estimación, CI y numerador/denominador.
- Latencia/memoria reportan mediana, p95, MAD y CI del cambio pareado.
- Comparación humana usa orden ciego randomizado, opción empate y al menos tres evaluadores por muestra.
- Correcciones post-hoc no cambian el reporte. Un bug de métrica invalida spec/run y exige nueva identidad.

## 9. Corpus sellados

### 9.1 Reglas comunes

Cada corpus incluye `corpus.json`, items y assets; su identidad es SHA-256 del árbol Merkle ordenado. Dev y holdout no comparten items. La UI de benchmark puede mostrar categoría e ID, pero el holdout no se usa para tuning de prompt/modelo. Promoción usa holdout una sola vez por manifest/spec; reintentar tras observar resultados exige nuevo manifest o cambio sustantivo pre-registrado y nuevo spec.

Todos los prompts usan UTF-8 exacto, sin normalización implícita. Adapters reciben el mismo prompt de producción y parámetros salvo diferencias obligatorias registradas por runtime.

### 9.2 Texto→Imagen orientado a 3D

Corpus: 20 prompts, 4 seeds `[17, 271, 2026, 65537]`, 1024×1024, 80 muestras por manifest.

Categorías y prompts exactos:

1. `ti_simple_01`: “A single matte red ceramic mug, complete object, three-quarter view, centered, neutral studio lighting, plain light gray background, no text, no props.”
2. `ti_simple_02`: “A single blue hiking boot, complete object including sole and laces, three-quarter view, centered, neutral studio lighting, plain background.”
3. `ti_simple_03`: “A single wooden dining chair with four visible legs, three-quarter view, centered, isolated on a plain background.”
4. `ti_simple_04`: “A single yellow construction hard hat, complete object, three-quarter view, isolated, soft neutral shadows.”
5. `ti_symmetry_01`: “A single white game controller, front three-quarter view, both grips and all buttons visible, centered, plain background.”
6. `ti_symmetry_02`: “A single compact twin-engine toy airplane, complete wings and tail, front three-quarter view, isolated.”
7. `ti_thin_01`: “A single black desk lamp with a thin articulated arm and circular base, complete object, three-quarter view, isolated.”
8. `ti_thin_02`: “A single metal watering can with intact handle and long narrow spout, complete object, three-quarter view, isolated.”
9. `ti_hole_01`: “A single carabiner with a clearly visible central opening and closed gate, three-quarter view, centered, isolated.”
10. `ti_hole_02`: “A single torus-shaped life buoy without rope or text, complete circular opening visible, three-quarter view, isolated.”
11. `ti_material_01`: “A single transparent green glass bottle with cork, complete object, three-quarter view, neutral lighting, plain background.”
12. `ti_material_02`: “A single brushed stainless-steel kettle with black handle, complete object, three-quarter view, plain background.”
13. `ti_material_03`: “A single worn brown leather satchel with flap, buckles and handle visible, three-quarter view, isolated.”
14. `ti_organic_01`: “A single stylized low-poly fox standing on all four legs, full body, three-quarter view, isolated.”
15. `ti_organic_02`: “A single green cactus with three arms in a simple round pot, complete object, three-quarter view, isolated.”
16. `ti_function_01`: “A single adjustable bench vise with jaws slightly open, handle and base visible, three-quarter view, isolated.”
17. `ti_function_02`: “A single padlock with the shackle open, complete mechanism visible, three-quarter view, isolated.”
18. `ti_complex_01`: “A single retro tabletop radio with two knobs, speaker grille and carrying handle, complete object, three-quarter view, isolated.”
19. `ti_complex_02`: “A single medieval lantern with frame, glass panels and top ring, complete object, three-quarter view, isolated.”
20. `ti_adversarial_01`: “A single impossible fork with exactly three tines at the tips and two stems at the base, centered, plain background, no extra objects.”

El prompt adversarial mide honestidad/coherencia; no se exige reconstruibilidad imposible como hard gate. Se reporta separado y no puede dominar promoción.

### 9.3 Texto→CSG IR

Corpus: 24 prompts, 3 seeds `[17, 271, 2026]`, 72 muestras por manifest. Cada item contiene assertions geométricos machine-readable.

1. Cubo 20×20×20 mm centrado.
2. Cilindro vertical radio 10 mm, altura 30 mm, 64 segmentos.
3. Esfera radio 12 mm centrada.
4. Caja 40×30×10 mm con agujero cilíndrico pasante central radio 5 mm.
5. Arandela: radio exterior 15 mm, interior 8 mm, altura 3 mm.
6. Soporte en L: base 40×20×5 mm y pared 5×20×30 mm unidas.
7. Perilla: cilindro radio 12 mm, altura 15 mm con seis ranuras radiales simples.
8. Tubo hueco vertical: exterior radio 12 mm, interior 9 mm, altura 40 mm.
9. Placa 60×40×4 mm con cuatro agujeros radio 3 mm a 6 mm de cada esquina.
10. Caja abierta 50×40×30 mm, pared 3 mm, sin tapa.
11. Bisagra simplificada con dos hojas y tres nudillos coaxiales, agujero de pasador continuo.
12. Abrazadera C simplificada con apertura funcional mínima 15 mm.
13. Rueda dentada simplificada de 12 dientes, espesor 5 mm y agujero central radio 4 mm.
14. Embudo con boca radio 20 mm, cuello radio 5 mm y abertura pasante.
15. Gancho J con sección circular aproximada y apertura visible.
16. Base rectangular con poste cilíndrico inclinado 20 grados sobre eje X.
17. Dos cubos 20 mm unidos por puente 20×8×8 mm sin componentes separados.
18. Organizador con tres compartimentos internos abiertos y paredes 2 mm.
19. Clip de cable en U con canal funcional de 8 mm.
20. Trípode simplificado con tres patas simétricas y plataforma superior.
21. Rechazar dimensión `NaN`, infinita o expresada como código.
22. Rechazar profundidad booleana 33 cuando límite es 32.
23. Rechazar 4.097 nodos cuando límite es 4.096.
24. Rechazar intento de propiedad `constructor`, módulo, callback o expresión JavaScript.

Items 21-24 esperan rechazo seguro; cuentan en `safeReject@1`, no en `compile@1` de prompts válidos.

### 9.4 Imagen→3D Shape

Corpus: 16 objetos con assets redistribuibles o propios, cámaras y mallas GT versionadas; seeds `[17, 271, 2026]` cuando el pipeline sea estocástico.

Distribución fija:

- 4 primitivas/objetos rígidos simples.
- 3 objetos con agujero funcional.
- 3 objetos con partes finas.
- 3 objetos orgánicos.
- 3 objetos de topología compleja o concavidad.

Cada item incluye imagen original, máscara GT, intrinsics/extrinsics, escala canónica, malla GT, licencia del asset y renders de referencia en ocho vistas azimutales cada 45 grados a elevación 20 grados. La alineación usa el mismo algoritmo/version para todos los candidatos y queda incluida en `compilerOrValidatorSha256`.

### 9.5 Imagen→3D PBR

Subconjunto de 12 objetos Shape con UV y materiales GT licenciados:

- 3 dieléctricos mate.
- 2 metálicos.
- 2 materiales mixtos metal/no-metal.
- 2 superficies con seams difíciles.
- 2 detalles finos pintados.
- 1 transparente, reportado como categoría exploratoria y excluido de la primaria.

Cada item incluye albedo lineal, roughness, metallic, normal map cuando exista, UV GT y renders bajo tres HDRI pinned. Exposición, tonemapping, color management, cámara y renderer quedan fijados en el spec.

## 10. Métricas por pipeline

### 10.1 Comunes

- `successRate`: terminal válido / total.
- `crashRate`, `oomRate`, `timeoutRate`.
- `latencyWarmMs` y `latencyFirstObservedMs`: p50/p95.
- `peakResidentBytes`, `peakSystemActiveBytes`, `swapDeltaBytes`.
- `artifactBytes` y tiempo de load/preprocess/infer/postprocess/export separados.
- Determinismo: hash idéntico cuando runtime promete determinismo; si no, variación se reporta, no se penaliza automáticamente.

### 10.2 Texto→Imagen

Primaria: `downstreamMeshAccepted@1`, proporción de imágenes que, usando el mismo manifest Shape estable y configuración, producen GLB que pasa gate geométrico final.

Secundarias:

- `referenceGate@1`: sujeto único, completo, cobertura 55-85%, fondo separable, sin recorte crítico.
- GenEval por conteo, posición, color y composición.
- Silhouette agreement y mask connectedness.
- Fidelidad pairwise ciega al prompt.
- Preferencia pairwise de reconstruibilidad.
- OCR exacto solo en subcorpus que solicite texto; corpus inicial no lo usa como primaria.
- Latencia, memoria, swap y tasa de outputs inválidos.

No se usa FID sobre 80 muestras ni estética aislada como criterio de promoción.

### 10.3 Texto→CSG IR

Primaria: `compile@1` sobre los 20 prompts válidos, sin reparación.

Secundarias:

- `schemaValid@1`.
- `safeReject@1` sobre los 4 adversariales.
- `geometryValid@1`: finitud, AABB, volumen/superficie, componentes y topología esperada.
- `semanticAssertions@1`: dimensiones, agujeros, simetría, apertura y conteos.
- `recovery@3`: éxito dentro de original + dos reparaciones, reportado separado.
- Nodos, profundidad y coste CSG.
- Tokens, latencia completion/compile y memoria incremental.

Un rechazo correcto nunca se cuenta como compilación fallida. Una reparación no mejora `compile@1`.

### 10.4 Imagen→3D Shape

Primaria: F-score de superficie al threshold canónico del corpus.

Secundarias:

- Chamfer-L1 bidireccional.
- Normal consistency.
- Silhouette IoU y depth error en ocho vistas.
- Watertight/manifold, componentes, self-intersections y winding.
- Thin-structure recall y functional-hole recall.
- Faces/vertices raw, clean y final.
- GLB parse/buffer validity y escala.

Todas se calculan tras simplificación y recarga del GLB final.

### 10.5 Imagen→3D PBR

No se mezcla con score Shape.

Primarias:

- Con GT: albedo se decodifica sRGB → RGB lineal → XYZ/Lab D65 y se calcula CIEDE2000; roughness MAE se reporta por separado. Promoción exige mejorar al menos uno sin regresión del otro fuera de tolerancia.
- Sin GT: win-rate humano pairwise ≥60% con límite inferior CI 95% >50%.

Secundarias:

- UV validity y cobertura.
- Seam energy y bleeding.
- Metallic F1.
- LPIPS/SSIM de albedo.
- Render LPIPS/SSIM bajo tres HDRI.
- Presencia/resolución de baseColor y metallicRoughness, channel packing correcto.
- Texels finitos, atlas no vacío y material GLB recargado.

## 11. Perfiles

Los perfiles no alteran corpus ni métricas; solo configuración permitida y criterio de elección en la frontera elegible.

### `speed`

- Prioriza p95 warm latency; desempata por peak memory.
- Calidad primaria no inferior al stable por más de 2 puntos porcentuales para tasas o 2% relativo para métricas continuas, con límite inferior CI dentro de margen.
- Promoción exige mejora ≥20% en p95 latency o peak memory con CI 95% del cambio excluyendo 0.
- Swap delta debe ser 0; crash/OOM/timeout 0 en holdout.

### `balanced`

- Prioriza métrica primaria del pipeline.
- Mejora requerida: ≥5 puntos porcentuales para tasas, ≥3% relativa para Shape F-score o ≥5% relativa de reducción para errores PBR; CI pareado debe excluir 0 en dirección favorable.
- p95 latency ≤+25% y peak memory ≤+15% respecto del stable.
- Swap delta 0 y todos los hard gates pasan.

### `quality`

- Prioriza métrica primaria; desempata por métricas semánticas/geométricas y luego memoria.
- Misma mejora estadística mínima de `balanced`.
- p95 latency ≤+75%, peak memory dentro de admission y swap delta = 0.
- No relaja integridad, licencia, crash/OOM, artifact gates ni seguridad.

Una sola decisión puede habilitar distintos manifests por perfil. Si un candidato no domina ni cumple regla de un perfil, permanece `lab` aunque gane otro perfil.

## 12. Pareto y promoción

### 12.1 Frontera elegible

Antes de Pareto se eliminan candidatos que fallen hard gates. Dimensiones:

```text
maximizar: métrica primaria, validez semántica/artefacto
minimizar: p95 warm latency, peak resident bytes, crash/oom/timeout
```

Un candidato domina a otro solo si no es peor fuera de tolerancia en todas las dimensiones y es mejor con evidencia CI en al menos una. Los empates reales se conservan en la frontera.

### 12.2 Propuesta

`PromotionProposal` contiene:

- baseline/candidate manifests y decisiones.
- spec/run/report IDs.
- hard gates y evidencia.
- deltas pareados, CI y muestras.
- posición Pareto por perfil.
- licencia y restricciones visibles.
- cambio de memoria/latencia.
- riesgos residuales y comando/acción de rollback.

No existe botón “promover ganador” si hay más de un punto Pareto. La UI presenta una opción por perfil y razones crudas.

### 12.3 Aprobación

Promoción requiere:

1. Reporte `completed`, íntegro y reproducible.
2. Manifest y artefactos re-verificados inmediatamente antes del commit.
3. Licencia compatible con modo de producto.
4. Candidate en frontera Pareto del perfil.
5. Regla CI/threshold satisfecha.
6. `reliabilitySoakReport` completa 20 ejecuciones consecutivas del workflow/corpus/config congelados, con unload/reset verificado entre runs, cero OOM, swap, crash o timeout.
7. Baseline estable aún disponible para rollback.
8. Aprobador explícito distinto del proceso de benchmark automático.

La promoción agrega `RegistryDecision(classification=stable)` y conmuta binding atómicamente. No cambia manifests, reports ni defaults embebidos en código.

### 12.4 Rechazo y expiración

- Integridad, lineage contradictorio o licencia incompatible: `reject` inmediato.
- OOM/crash/artifact inválido: `reject` para hardware/pipeline evaluado.
- Calidad insuficiente pero segura: permanece `lab` con `benchmark_regression`.
- Runtime/capability no verificados: `lab`.
- Decisiones stable expiran cuando cambia major/minor del runtime adapter, prompt/validator de producción, hardware class o texto de licencia. Expirar deshabilita auto-selection hasta revalidar; no reclasifica el manifest.

## 13. Supply-chain

### 13.1 Ingreso

Ingreso de un candidato es una operación separada y explícitamente autorizada:

1. Resolver identidad upstream a commit/digest inmutable.
2. Enumerar archivos requeridos desde metadata, sin ejecutar código remoto.
3. Hash SHA-256 streaming de cada archivo local por descriptor seguro.
4. Verificar tamaños, shards e index de safetensors.
5. Capturar y hashear model card, licencia y AUP.
6. Resolver lineage/base model y herramienta de conversión.
7. Ejecutar static checks de config/template; no inferencia todavía.
8. Construir canonical JSON y `manifestId`.
9. Añadir decisión inicial `lab/initial_inventory`.

El ingreso no ocurre dentro del benchmark y nunca descarga sin aprobación previa.

### 13.2 Política de formatos/código

- Se prefieren safetensors y blobs Ollama con digest.
- Pickle u objetos ejecutables se rechazan.
- Custom Python/remote code requiere pin, digest, revisión y utility process sin red/secretos y permanece `lab/security_review`; nunca promociona a `stable`.
- Templates se tratan como código/config crítico y forman parte del manifest.
- El runtime hijo recibe entorno allowlisted y paths/FDs confinados según diseño padre.

### 13.3 Verificación en uso

- Full hash al ingresar y antes de promoción.
- En arranque normal: size + metadata cache autenticada; full hash rotativo o ante cambio de inode/mtime.
- Antes de un benchmark promocionable: full hash de todos los artifacts.
- Mismatch mueve binding a cuarentena, impide ejecución y conserva evidencia.

### 13.4 Privacidad

- Registry/reportes no guardan claves, headers, variables de entorno ni prompts del usuario.
- Corpus contiene solo prompts/activos aprobados y versionados.
- Outputs de benchmark quedan locales y sujetos a cuota/TTL; hashes y métricas pueden conservarse tras purga.
- Model cards/licencias se consideran evidencia pública; rutas locales y username se redactan en reportes exportables.

## 14. Inventario inicial al 2026-07-19

Todos ingresan como `lab` salvo exclusión explícita. Ningún candidato queda stable por esta tabla.

### 14.1 Texto→Imagen

| Candidato | Fecha | Tamaño/params | Runtime real | Licencia | Clasificación inicial |
|---|---:|---:|---|---|---|
| `x/flux2-klein:4b` | 2026-01-15 | 4B; Ollama 5.7 GB | Ollama macOS experimental; MFLUX MLX | Apache-2.0 | `lab`; candidato speed/balanced |
| `x/z-image-turbo:fp8` | 2025-11-27; rev. paper 2026-07-06 | 6B; Ollama 13 GB | Ollama macOS experimental; MFLUX MLX | Apache-2.0 | `lab`; candidato quality |
| `x/flux2-klein:9b` | 2026-01-15 | 9B; Ollama 12 GB | Ollama/MFLUX | FLUX Non-Commercial v2.1 | `lab/manual_research_only`; no stable comercial |
| Krea 2 Turbo MLX mixed 4/8 | 2026-06-22 | 12B; bundle MLX 9.85 GB | MFLUX/conversión comunitaria | Krea 2 Community License | `lab`; adapter/licencia/safeguards pendientes de gate |
| Ideogram 4 NF4/FP8 | 2026-06-03 | 5B NF4 / 9B FP8 | MFLUX, gated | Ideogram Non-Commercial | `lab/manual_research_only`; no stable comercial |
| Qwen-Image-2512 BF16 | 2025-12 | repo 57.7 GB | Diffusers MPS teórico, sin adapter actual | Apache-2.0 | `reject/memory_admission` para 24 GB |

Fuentes primarias:

- [Ollama FLUX.2 Klein](https://ollama.com/x/flux2-klein)
- [Ollama Z-Image-Turbo](https://ollama.com/x/z-image-turbo)
- [Ollama image generation experimental](https://ollama.com/blog/image-generation)
- [FLUX.2 repo oficial](https://github.com/black-forest-labs/flux2)
- [FLUX.2 Klein 4B en HF](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- [Z-Image paper](https://arxiv.org/abs/2511.22699)
- [Z-Image-Turbo en HF](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)
- [MFLUX](https://github.com/filipstrand/mflux)
- [Krea 2 Turbo](https://huggingface.co/krea/Krea-2-Turbo)
- [Krea 2 Turbo MLX mixed 4/8](https://huggingface.co/avlp12/Krea-2-Turbo-Alis-MLX-mixed-4-8)
- [Ideogram 4 licencia](https://huggingface.co/ideogram-ai/ideogram-4-fp8/blob/main/LICENSE.md)
- [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512)

### 14.2 Texto→CSG IR

| Candidato | Fecha | Params/pesos | Runtime real observado | Licencia | Clasificación inicial |
|---|---:|---:|---|---|---|
| Gemma-4-12B Coder Fable5/Composer2.5 4-bit | 2026-06-19 | 12B; pesos 6.24 GiB; footprint local 6.55 GiB | instalado oMLX; output 4096 | Apache-2.0 | `lab`; benchmark obligatorio por fine-tune comunitario |
| gpt-oss-20b MXFP4-Q8 | 2025-08-29 | 21B total/3.6B activos; pesos 11.25 GiB; local 11.81 GiB | instalado oMLX; output 4096; Ollama oficial 14 GB | Apache-2.0 | `lab`; exige parser Harmony |
| Qwen3-8B 4-bit | 2025-04-28 | 8B; local 4.51 GiB | instalado oMLX; output 4096; Ollama oficial 5.2 GB | Apache-2.0 | `lab`; control eficiente |
| Qwen3.5-9B MLX 4-bit | 2026-03-02 | 9B; pesos 5.54 GiB; local 5.82 GiB | instalado oMLX; output observado 2048; Ollama oficial | Apache-2.0 | `lab/output_limit`; solo perfil simple/manual |
| Gemma-4-12B-it QAT 4-bit | 2026-06-05 | 11.95B; pesos 10.23 GiB | conversión MLX publicada, no instalada | Apache-2.0 | `lab/runtime_unavailable` local |
| Qwen3-Coder-30B-A3B 4-bit | 2025-07-31 | 30.5B/3.3B activos; MLX 16.0 GiB; Ollama 19 GB | upstream MLX/Ollama; no instalado | Apache-2.0 | `lab/memory_admission`; no convivencia bajo ceiling actual |
| Devstral Small 2 24B 4-bit | 2025-11-28 | MLX 14.1 GiB; upstream recomienda Mac 32 GB | cache local incompleto; no listado por oMLX | Apache-2.0 | `reject/memory_admission` en 24 GB |

Fuentes primarias:

- [Gemma 4 12B oficial](https://huggingface.co/google/gemma-4-12B-it)
- [Gemma 4 Technical Report](https://arxiv.org/abs/2607.02770)
- [Gemma Coder fine-tune](https://huggingface.co/yuxinlu1/gemma-4-12B-coder-fable5-composer2.5-v1)
- [Gemma Coder MLX](https://huggingface.co/mlx-community/gemma-4-12b-coder-fable5-composer2.5-4bit)
- [gpt-oss-20b oficial](https://huggingface.co/openai/gpt-oss-20b)
- [gpt-oss model card paper](https://arxiv.org/abs/2508.10925)
- [gpt-oss MLX](https://huggingface.co/mlx-community/gpt-oss-20b-MXFP4-Q8)
- [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B)
- [Qwen3-8B MLX](https://huggingface.co/mlx-community/Qwen3-8B-4bit)
- [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Qwen3.5-9B MLX](https://huggingface.co/mlx-community/Qwen3.5-9B-MLX-4bit)
- [Qwen3-Coder-30B-A3B](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)
- [Qwen3-Coder MLX](https://huggingface.co/mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit)
- [Qwen3-Coder Ollama](https://ollama.com/library/qwen3-coder/tags)
- [Devstral Small 2 24B](https://huggingface.co/mistralai/Devstral-Small-2-24B-Instruct-2512)
- [oMLX](https://github.com/jundot/omlx)

### 14.3 Imagen→3D Shape/PBR

| Candidato | Pipeline | Evidencia | Clasificación inicial |
|---|---|---|---|
| `dgrauet/Hunyuan3D-2.1-mlx@58e61ee` | Shape + Paint | fork/commit operativo conocido; pesos aún deben resolverse a revisión/digests antes del manifest | `lab/capability_unverified` hasta cerrar supply-chain y benchmark |
| TRELLIS.2 oficial 4B | Shape/PBR | upstream Linux/NVIDIA ≥24 GB | `reject/runtime_unavailable` en M5 Pro |
| `xocialize/trellis2-mlx` | Shape/PBR | port comunitario Apple Silicon | `lab`; runner separado, commit/pesos/licencia y contract benchmark obligatorios |

Fuentes primarias:

- [Hunyuan3D 2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)
- [Fork Hunyuan3D 2.1 MLX](https://github.com/dgrauet/Hunyuan3D-2.1-mlx)
- [TRELLIS.2 oficial](https://github.com/microsoft/TRELLIS.2)
- [TRELLIS.2 MLX](https://github.com/xocialize/trellis2-mlx)

La ausencia de revisión exacta de pesos no se representa con un hash ficticio: impide crear un manifest promocionable.

## 15. Contratos de servicio

### 15.1 `ModelRegistry`

```text
ingestManifest(candidate) -> manifestId
appendDecision(decision) -> decisionId
getManifest(manifestId) -> ModelManifest
getEffectiveDecision(manifestId, pipeline, hardwareClass) -> RegistryDecision
listEligible(pipeline, profile, hardwareClass, licenseContext) -> EligibleModel[]
getStableBinding(pipeline, profile, hardwareClass, licenseContext) -> StableBinding | null
proposePromotion(reportId, profile) -> PromotionProposal
commitPromotion(proposalId, approver) -> StableBinding
rollback(bindingId, approver, reason) -> StableBinding
verifyIntegrity(manifestId, mode) -> IntegrityResult
rebuildIndex() -> RegistryIndex
```

Todas las mutaciones son main-only y auditables. `commitPromotion` reevalúa precondiciones bajo lock. Renderer solo puede listar estado sanitizado, iniciar benchmark, consultar progreso, solicitar propuesta y presentar confirmación; no escribe decisions ni bindings.

### 15.2 `BenchmarkArena`

```text
validateSpec(specId) -> SpecValidation
start(specId, owner) -> operationId
status(operationId) -> ArenaStatus
cancel(operationId, owner) -> CancelResult
resume(operationId, owner) -> ResumeResult
result(operationId, owner) -> BenchmarkReport | null
```

Arena usa lifecycle/ownership/CAS del diseño padre. Cancelar espera ack/kill antes de liberar lease. Resultados tardíos se descartan. Resume verifica manifests, corpus y environment fingerprint antes de continuar.

### 15.3 Errores normalizados

```text
manifest_invalid, digest_mismatch, source_unresolved, license_missing,
license_incompatible, artifact_missing, runtime_incompatible,
capability_unverified, corpus_mismatch, environment_drift,
network_attempt, memory_admission, pressure_critical, swap_exceeded,
model_load_failed, inference_failed, timeout, crash, oom,
artifact_invalid, metric_failed, contaminated, cancelled,
approval_required, stale_proposal
```

Cada error incluye code, etapa, manifest/item/seed cuando aplique y mensaje redactado. Nunca incluye prompts privados, paths absolutos, cuerpos HTTP, environment o secretos.

## 16. Gates de implementación

### Gate 0: schemas e identidad

- Golden fixtures para canonical JSON y hashes.
- Schema rechaza unknown fields, NaN/Infinity, paths inseguros y revisiones mutables.
- Mutar un byte de weights/config/template/license cambia manifest o falla digest.
- Round-trip preserva identidad exacta.

### Gate 1: registry append-only

- Decisiones encadenadas, estado efectivo y reconstrucción de índice.
- `stable/lab/reject` nunca mutan manifest.
- Binding transaccional y rollback probado.
- Cadena rota/cíclica o decisión corrupta produce cuarentena.

### Gate 2: supply-chain

- HF commit, Ollama manifest/blob y GitHub commit resueltos.
- Hash de todos los archivos consumidos.
- Licencia/AUP snapshot y policy matrix.
- Symlink swap, path traversal, corrupt shard, pickle y remote-code tests.
- Benchmark opera con red externa bloqueada.

### Gate 3: arena determinista

- Corpus Merkle, seeds, orden de bloques y resume boundary reproducibles.
- Hardware/environment fingerprint completo.
- Warm/cold/first-observed etiquetados honestamente.
- Fault injection para cancel, timeout, crash, OOM, pressure y contaminación.

### Gate 4: métricas por pipeline

- CSG schema/compile/recovery/safe-reject separados.
- Texto→Imagen downstream mesh y reference gate reproducibles.
- Shape evalúa GLB final recargado.
- PBR valida estructura, mapas y renders sin mezclar Shape.
- Metric failure invalida run; no sustituye cero silenciosamente.

### Gate 5: estadística/Pareto

- Bootstrap pareado golden con 10.000 resamples/seed 20260719.
- Tests de dominancia, tolerancias, empates y múltiples puntos Pareto.
- Cada perfil selecciona solo entre candidatos elegibles.
- Diferencia puntual sin CI nunca promueve.

### Gate 6: promoción/rollback

- Propuesta contiene evidencia completa y expira ante drift.
- Approval separado del proceso automático.
- Revalidación pre-commit detecta TOCTOU de artifact/decision.
- Rollback restaura baseline sin red ni descarga.
- Emergency quarantine desactiva binding de forma atómica.

### Gate 7: validación real M5 Pro 24 GB

- Run opt-in secuencial con modelos ya instalados.
- `effectiveCeiling_live` (default 16 GiB) y reservas aplicados; swap delta debe ser cero.
- Cero cargas GPU concurrentes.
- Reporte completo, outputs hasheados, logs redactados.
- Build, tests y smoke UI con código de salida cero.

## 17. Matriz mínima de tests

### Unitarios

- Canonicalización/hash, schemas, enums y límites.
- Resolución HF/Ollama/GitHub con fixtures.
- License policy por categoría/product mode.
- Decision chain, effective state, bindings y rollback.
- Admission arithmetic con overflow/boundaries.
- PRNG/order, bootstrap, CI y Pareto.
- Redacción de errores/reportes.

### Contract

- oMLX devuelve modelo/tokens/capability compatible con manifest.
- Ollama `/api/show` y blobs coinciden con digest.
- MFLUX genera asset con metadata válida.
- Hunyuan challenge/version/capabilities y output asset ID.
- CSG compiler consume solo IR declarativa y rechaza adversariales.

### Integración

- Ingreso local sin descarga.
- Benchmark de corpus reducido de smoke: 2 items × 1 seed por pipeline, marcado no-promocionable.
- Benchmark completo opt-in produce report promocionable.
- Resume tras cierre entre items; nunca duplica muestra.
- Cancel durante load/infer/postprocess.
- Modelo cambia en disco entre verify y run: abort/digest mismatch.
- Runtime cambia de versión: environment drift.
- Network call externo: invalid/network_attempt.
- Pressure crítico o swap sobre límite: abort/invalid.

### UI/browser

- Lista muestra state, manifest corto, licencia, runtime y razones.
- `lab` requiere confirmación; `reject` no tiene acción ejecutar.
- Arena muestra pipeline/profile, progreso item/seed y cancelación honesta.
- Pareto presenta métricas crudas/CI, no score único.
- Promoción muestra licencia, cambios, riesgos y rollback.
- Resultados stale de otra `operationId` se ignoran.

## 18. Criterios de aceptación medibles

### Registry

- 100% de stable bindings refieren manifest, decision y report existentes e íntegros.
- 0 aliases mutables en revisions stable.
- 100% de artifacts consumidos tienen size + SHA-256.
- 100% de licencias custom tienen snapshot digest y categoría.
- Rebuild del índice produce bytes canónicos idénticos.
- Rollback local completa sin red y selecciona baseline anterior.

### Arena

- Mismo spec/environment produce mismo orden de muestras.
- 100% de muestras tienen item, seed, manifest y output/error terminal.
- 0 muestras fallidas omitidas del denominador.
- 0 workloads GPU pesados concurrentes.
- 0 acceso de red externa durante fase de medición.
- Resume repite como máximo la muestra incompleta, nunca una completada.

### Promoción

- 100% de propuestas pasan hard gates y están en frontera Pareto del perfil.
- 100% de deltas incluyen CI pareado y n efectivo.
- 0 promociones automáticas sin aprobación.
- 0 stable comercial con licencia noncommercial/unknown.
- 0 promoción CSG general con output <4096.
- 0 promoción fuera de `effectiveCeiling_live` (default 16 GiB) o con swap delta positivo.

### Seguridad y privacidad

- 0 JavaScript generado ejecutado.
- 0 secrets/paths absolutos/prompts privados en registry, reportes o errores.
- Digest mismatch, symlink y pickle bloquean ejecución; cualquier remote-code bloquea promoción estable.
- Cancelación no libera lease hasta ack/kill confirmado.

## 19. Observabilidad y reporte

El reporte humano contiene:

- Identidad completa de spec, run, manifests y baseline.
- Hardware/environment y validez promocional.
- Gates por candidato.
- Métricas crudas, CI, denominadores y errores.
- Gráficos/tablas Pareto por perfil.
- Outliers identificados por item/seed, sin borrarlos.
- Restricciones de licencia y supply-chain.
- Propuesta o razón precisa para permanecer `lab`/pasar a `reject`.
- Riesgos residuales y rollback.

El reporte machine-readable contiene las mismas decisiones sin Markdown como autoridad. HTML/Markdown son vistas derivadas.

## 20. Operación y retención

- Manifests, decisions, specs, reports y license evidence se conservan mientras exista un binding o lineage dependiente.
- Outputs pesados usan cuota/TTL; su purga conserva hash, metadata y métricas.
- Runs fallidos/cancelados se conservan 30 días; reportes referenciados por decisión no expiran.
- Un GC nunca borra baseline de rollback ni evidencia legal.
- Export/import de registry verifica todos los hashes y no activa bindings importados hasta aprobación local.

## 21. Riesgos residuales

- Bootstrap sobre corpus pequeño no reemplaza diversidad real; categorías y holdout deben ampliarse con evidencia, creando specs nuevos.
- Evaluación humana puede introducir sesgo; ceguera, randomización, empate y tres evaluadores lo reducen, no lo eliminan.
- Peak memory depende de macOS, runtime y temperatura; por eso la promoción queda atada a hardware/runtime fingerprint.
- Pesos cuantizados pueden degradar casos raros no cubiertos por corpus.
- Licencias custom pueden cambiar o requerir interpretación jurídica; el registry preserva texto/evidencia, no emite opinión legal.
- Ports MLX comunitarios pueden divergir de upstream; lineage y benchmark local prueban bytes ejecutados, no equivalencia matemática.
- Cancelar request puede no detener inmediatamente un kernel MLX; lease se conserva hasta ack/kill.
- Un modelo Pareto hoy puede dejar de serlo tras cambiar prompt, compiler, corpus o runtime; expirar decisiones evita arrastrar evidencia incompatible.

## 22. Definition of Done

- `ModelManifest` inmutable, canónico y content-addressed.
- Registry append-only con `stable`, `lab`, `reject`, decisiones encadenadas y bindings atómicos.
- HF/GitHub commits, Ollama digests, artifacts, lineage y licencias verificables.
- Arena por pipeline, corpus/seed sellados, ejecución secuencial y environment fingerprint M5 Pro 24 GB.
- Métricas de producto, memoria, latencia, artefacto y seguridad separadas.
- Perfiles `speed`, `balanced`, `quality` resueltos sobre Pareto/CI.
- Promoción explícita, reproducible y reversible.
- Supply-chain, privacidad, fault injection, tests y gates completos.
- Inventario julio 2026 documentado con fuentes primarias, sin presentar candidato como ganador.
