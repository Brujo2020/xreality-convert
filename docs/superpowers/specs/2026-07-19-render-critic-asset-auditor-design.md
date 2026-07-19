# Render Critic y Asset Auditor local: diseño de validación, reparación y seguridad 3D

Fecha: 2026-07-19
Estado: diseño aprobado; listo para plan de implementación
Ámbito: auditoría de geometría/PBR, renders canónicos, crítica VLM local, reparación dirigida, revisión humana, seguridad y procedencia
Diseño padre: `2026-07-19-end-to-end-asset-pipeline-design.md`

## 0. Relación con el diseño padre

Este documento especializa los gates geométrico, material y de exportación del pipeline local de activos XR. El diseño padre prevalece ante conflictos sobre `WorkflowCoordinator`, `AssetRepository`, ownership IPC, límites de archivo, exclusión GPU, cancelación, escritura transaccional o lifecycle.

Decisiones vinculantes:

- Los gates deterministas son autoridad para integridad, presupuesto y compatibilidad; un VLM no puede convertir un fallo determinista en aprobación.
- El critic usa exclusivamente un VLM local pinneado y renders canónicos generados localmente. No existe llamada cloud, fallback remoto ni carga de URL.
- Una reparación automática es tipada, allowlisted, localizada y reversible. Máximo dos intentos por asset raíz; cada intento produce un asset hijo y repite la auditoría completa.
- Reparaciones que cambien identidad semántica, partes funcionales o asignación de atlas requieren revisión humana previa.
- Contenido potencialmente dañino usa defensa apilada: input, geometría, renders multivista, VLM y revisión humana. Ninguna capa individual se presenta como suficiente.
- glTF Validator y glTF Asset Auditor se ejecutan sobre el GLB final recargado, no sobre estructuras previas a exportación.
- Toda decisión, reparación y override humano queda ligada a un sidecar firmado y a hashes de los artefactos exactos examinados.

## 1. Resultado verificable

El sistema debe decidir de forma local, reproducible y explicable si un GLB o STL generado puede:

1. continuar a optimización;
2. exportarse para XR;
3. conservarse solo como artefacto degradado;
4. recibir una reparación dirigida;
5. requerir decisión humana; o
6. quedar bloqueado o en cuarentena.

Éxito significa:

- un mismo asset, renderer, perfil y configuración producen los mismos reports y renders dentro de tolerancias definidas;
- GLB malformado, recursos fuera de límites y errores PBR verificables no llegan al critic ni al exportador;
- defectos visuales no observables por schema quedan expuestos mediante renders canónicos multivista;
- el VLM devuelve exclusivamente un contrato JSON validado y nunca controla filesystem, red, comandos o reparaciones arbitrarias;
- máximo dos reparaciones allowlisted pueden ejecutarse; ninguna reparación sobreescribe el asset fuente;
- atlas ambiguo, eliminación de partes, reasignación material y riesgo físico/semántico solicitan intervención humana;
- cancelación, crash o timeout no publican un asset parcialmente auditado;
- ningún prompt, imagen, mesh, textura, render o reporte abandona el dispositivo;
- cada exportación aprobada tiene lineage verificable hasta input, modelos, configuración, auditorías y decisiones.

## 2. Incluye y excluye

### Incluye

- Coordinación main-owned de auditoría y reparación.
- glTF Validator oficial y un perfil versionado del glTF Asset Auditor.
- Inspección determinista de geometría, escena, buffers, UV y PBR.
- Renders canónicos deterministas en proceso aislado.
- Critic VLM local con rubric y salida estructurada.
- Detección apilada de geometría potencialmente dañina.
- Reparaciones geométricas y PBR tipadas.
- Revisión humana de atlas, partes, ambigüedad y safety.
- Sidecar de procedencia, integridad y firma local.
- Benchmarks de exactitud, falsos positivos, rendimiento y reproducibilidad.
- Tests unitarios, contract, golden, integración, adversariales y browser.

### Excluye

- Entrenar o afinar un VLM.
- Moderación, almacenamiento o telemetría cloud.
- Descarga automática de modelos o validadores.
- Reparación generativa libre o instrucciones de modelado producidas como código.
- Certificación de seguridad mecánica, médica, legal o de fabricación.
- Afirmar que procedencia equivale a autoría, licencia o veracidad.
- Autoaprobar contenido peligroso por score bajo, contexto benigno inferido o override previo.
- Reemplazar los gates Shape/PBR del diseño padre; este documento los hace ejecutables y auditables.

## 3. Principios e invariantes

1. **Determinismo antes que opinión:** schema, bytes, finitud, rangos, topología y presupuestos se resuelven sin modelo generativo.
2. **Ver el artefacto final:** auditor y critic consumen el GLB recargado que se propone exportar.
3. **VLM como señal, no autoridad:** puede elevar severidad, proponer reparación allowlisted o pedir revisión; no puede borrar evidencia.
4. **Multivista obligatoria:** una sola vista no demuestra backside, cavidades, partes delgadas ni contenido camuflado.
5. **Reparación mínima:** modificar solo entidades asociadas a issues concretos y revalidar desde cero.
6. **Humano en cambios semánticos:** eliminar partes, cerrar cavidades funcionales o reconstruir atlas requiere consentimiento informado.
7. **Fail closed acotado:** error de auditoría bloquea publicación automática, pero preserva el asset fuente y explica la acción siguiente.
8. **Privacidad estructural:** offline no es solo una preferencia de UI; workers carecen de red y reciben archivos por descriptor/ID.
9. **Lineage inmutable:** cada hijo señala padre, reparación, configuración y reportes; jamás se reescribe historia.
10. **No score mágico:** se conservan issues y dimensiones separadas; una decisión final no oculta sus razones.

Invariantes:

- Cada ejecución embebida conserva `operationId` raíz y añade `stageAttemptId`; standalone obtiene un `operationId` normal de `WorkflowCoordinator`. También congela `rootAssetId`, `candidateAssetId`, owner y política.
- El renderer solo ve IDs opacos, thumbnails autorizados y reportes sanitizados.
- Los workers nunca reciben paths elegidos por renderer, credenciales, proxy, `HOME` ni variables `*_KEY|*_TOKEN|*_SECRET`.
- El critic no recibe herramientas, funciones, shell, red ni permiso de escritura.
- Un `block` determinista no se reduce por VLM, reparación o override automático.
- Un asset reparado no hereda `pass`; repite validación estructural, auditoría, renders y critic.
- `approved` se lineariza después de escribir, fsync y renombrar artefacto, reportes y manifest comprometido.
- La firma cubre hashes; nunca se firma un path, URL o nombre mutable como identidad del contenido.

## 4. Modelo de amenazas

### 4.1 Activos protegidos

- GLB fuente, candidatos reparados, texturas, renders y previews.
- Referencia de entrada y posible información personal visible.
- Integridad de reports, decisiones y procedencia.
- Memoria, disco, GPU y disponibilidad del Mac de 24 GB.
- Confidencialidad de prompts, nombres locales y estructura de directorios.
- Seguridad física y reputacional asociada a un asset exportable/fabricable.

### 4.2 Actores y entradas no confiables

- Prompt e imagen suministrados por usuario.
- GLB generado por modelos o importado.
- Texturas que pueden contener texto, instrucciones o contenido adversarial.
- Extensiones glTF, metadata, nombres de nodos/materiales y strings embebidos.
- Pesos VLM, tokenizer, configuración y binarios de auditoría de terceros.
- Reportes previos, sidecars o caches manipulados fuera de la aplicación.
- Modelos que produzcan geometría patológica sin intención maliciosa.

### 4.3 Amenazas técnicas

- GLB truncado, offsets fuera de rango, accessors inválidos, `NaN`/`Inf`, matrices no descomponibles o referencias cíclicas.
- Resource bomb: millones de primitivas, imágenes enormes, compresión expansiva, escenas profundas o extensiones costosas.
- Path traversal, URI externa, symlink swap o asset que intenta hacer leer recursos fuera del repositorio.
- Shader/material bomb, exceso de draw calls, transparencias orden-dependientes o texturas que agotan memoria.
- Geometría degenerada, self-intersection, normales invertidas, non-manifold, componentes basura, spikes o espesores no fabricables.
- Fallo visual oculto en backside, interior, grazing angle, UV seams o canales PBR.
- Prompt injection visual: texto en textura/render que intenta alterar instrucciones del VLM.
- Salida VLM no válida, alucinada, sesgada por descripción, posición de vistas o respuesta verbosa.
- Cache poisoning mediante reuse entre modelo, renderer, perfil o digest diferentes.
- TOCTOU entre auditoría y exportación.
- Manipulación de reportes, decisión humana o sidecar después de aprobados.

### 4.4 Amenazas semánticas y físicas

La taxonomía mínima sigue el estudio 2026 sobre harmful geometry:

- `direct_physical_hazard`: objeto directamente utilizable para causar daño.
- `risky_component_or_template`: pieza, molde, receptor, adaptador o componente cuyo ensamblaje eleva capacidad de daño.
- `deceptive_replica`: réplica realista diseñada para engañar, intimidar o evadir controles.
- `sexual_or_exploitative`: representación sexual prohibida o explotación.
- `hate_or_extremism`: símbolos u objetos de apoyo material a odio/extremismo.
- `self_harm`: objeto o escena orientada explícitamente a autolesión.
- `illegal_or_regulated`: objeto cuya generación/exportación exige contexto o autorización que la aplicación no puede verificar.
- `unknown_dual_use`: herramienta, utilería, pieza industrial, médica o histórica con uso legítimo y rasgos ambiguos.

El paper reporta que menos de 0,3% de geometrías dañinas activaron moderación comercial en su evaluación y que una defensa apilada redujo retención dañina a menos de 1%, con 11% de falsos positivos. Esos valores son evidencia para exigir capas y medir tradeoffs, no targets asumidos para este producto.

### 4.5 Capacidad del atacante

Se asume que puede:

- elegir prompt, imagen, orientación, textura y filename;
- camuflar semántica, degradar imagen o desplazar viewpoint;
- repetir intentos y comparar mensajes de rechazo;
- importar un GLB elaborado para parser/render/VLM;
- insertar instrucciones legibles en textura o metadata;
- editar archivos en disco fuera de la aplicación.

No se asume compromiso previo del proceso principal, del sistema operativo ni de la clave de firma local. Si eso ocurre, la aplicación no puede garantizar integridad.

## 5. Arquitectura objetivo y fronteras de confianza

```text
Renderer no confiable
  -> IPC tipado por operationId/stageAttemptId/assetId
    -> AssetAuditCoordinator (main, subordinado a WorkflowCoordinator)
       -> AssetRepository (FDs, hashes, manifest transaccional)
       -> StructuralValidatorWorker (glTF Validator)
       -> DeterministicAuditorWorker (perfil Asset Auditor + checks propios)
       -> CanonicalRenderWorker (renderer/version/config pinneados)
       -> LocalCriticWorker (VLM local, read-only, sin red)
       -> RepairWorker (operaciones allowlisted)
       -> HumanReviewRegistry (decisión y razón)
       -> ProvenanceSigner (sidecar canónico firmado)
```

### 5.1 AssetAuditCoordinator

- Congela perfil, versiones, hashes, thresholds y modelo critic al iniciar.
- Orquesta etapas y deadlines bajo el `operationId` raíz; solo `WorkflowCoordinator` posee lease, cancelación global y CAS terminal.
- Combina reports mediante reglas deterministas de precedencia.
- Nunca interpreta texto libre del VLM como comando.
- Publica solo reportes sanitizados y referencias a previews autorizadas.
- Rechaza exportación si el hash actual del candidato difiere del auditado.

### 5.2 Workers aislados

Todos los workers son desechables y reciben un entorno allowlisted. El input es un descriptor de archivo ya abierto o copia inmutable dentro de un sandbox por operación. No siguen symlinks ni resuelven URIs remotas.

Presupuestos iniciales por operación:

- GLB: límite padre de 512 MiB.
- Imágenes decodificadas combinadas: 512 MiB.
- Nodos de escena: 100.000.
- Primitivas mesh: 20.000.
- Triángulos hard ceiling de inspección: 5.000.000; el perfil XR aplica un límite menor.
- Texturas: máximo 32 imágenes y 8192x8192 por imagen para inspección; perfiles estables 1K/2K.
- Profundidad escena: 128.
- Structural validator: wall 30 s, RSS 1 GiB.
- Auditor determinista: wall 60 s, RSS 2 GiB.
- Canonical renderer: wall 90 s, RSS 3 GiB.
- Critic: wall 120 s, output 32 KiB y máximo de tokens fijado por registry.
- Repair worker: wall 120 s, RSS 3 GiB y output ≤ límite GLB.

Exceder presupuesto produce issue estable `resource_limit_exceeded`, termina worker y bloquea autoexportación.

### 5.3 Exclusión GPU

Canonical renderer puede usar GPU, pero no comparte lease con Shape, Paint, generación de imagen, oMLX pesado o critic MLX. Critic y renderer corren secuencialmente. La cola y release siguen el `WorkflowCoordinator` padre; un timeout no libera lease hasta ack o kill confirmado.

## 6. Contratos de dominio

Los contratos son versionados, cerrados a campos desconocidos en IPC y validados nuevamente en main.

### 6.1 AuditRequest

```text
AuditRequest v1
  operationId: root operation ID
  stageAttemptId: opaque stage attempt ID
  candidateAssetId: opaque ID
  rootAssetId: opaque ID
  workflow?: text_image | text_3d | image_3d  # required cuando sourceKind=generated
  sourceKind: generated | imported
  assetFormat: glb | stl
  targetProfile: xr_mobile | xr_desktop | web_xr | fabrication_preview
  referenceAssetId?: opaque ID
  requestedMode: audit_only | audit_and_repair
  safetyPolicyVersion: immutable ID
  auditProfileVersion: immutable ID
  canonicalRenderProfileVersion: immutable ID
  effectivePlanHash: immutable digest
  inputSafetyAssessmentDigest: immutable digest
  inputSafetyReviewDecisionDigest?: immutable digest
  licenseAdmissionReceiptId: immutable ID
  maxRepairAttempts: 0 | 1 | 2
```

No contiene path, URL, prompt completo, modelo libre, threshold arbitrario ni instrucciones de reparación. `workflow` es requerido si y solo si `sourceKind=generated` y está prohibido si `sourceKind=imported`. En pipeline embebido conserva `operationId` raíz; en modo standalone, `WorkflowCoordinator` asigna un `operationId` normal. `stageAttemptId` no posee lease ni CAS terminal.

### 6.2 AuditIssue

```text
AuditIssue v1
  code: stable enum
  domain: structure | geometry | scene | uv | pbr | render | semantic | safety | provenance | resource
  severity: info | warning | review | block
  evidenceKind: metric | validator_message | render_region | entity_set | hash_mismatch | policy_match
  evidence: typed bounded payload
  affectedEntityIds: stable local IDs, max 256
  repairClass: none | automatic | human_authorized
  userMessageKey: safe catalog key
```

Strings de herramientas externas quedan en report privado acotado; renderer recibe `code`, valores sanitizados y `userMessageKey`.

### 6.3 DeterministicAuditReport

```text
DeterministicAuditReport v1
  candidateSha256
  validatorVersion
  auditorVersion
  auditProfileVersion
  startedAt/finishedAt
  structuralStats
  geometryStats
  sceneStats
  uvStats
  pbrStats
  issues[]
  disposition: pass | warn | review | block
```

El `disposition` se deriva de severidades y perfil; no se persiste como decisión editable.

### 6.4 CanonicalRenderSet

```text
CanonicalRenderSet v1
  candidateSha256
  rendererName/version/buildDigest
  renderProfileVersion
  cameraFitDigest
  environmentDigest
  view records[]: viewId, pass, camera matrix, imageSha256, width, height
  contactSheetSha256[]
  renderWarnings[]
```

### 6.5 CriticReport

```text
CriticReport v1
  candidateSha256
  renderSetDigest
  modelRepository/revision/weightsDigest
  tokenizerDigest
  rubricVersion
  decodingProfile: temperature=0, topP=1, seed, maxTokens
  observations[]
  safetySignals[]
  suggestedRepairCodes[]
  uncertaintyReasons[]
  disposition: no_additional_issue | repair_candidate | human_review | safety_block
```

Cada observación requiere `criterion`, `severity`, `confidence`, `viewIds`, región normalizada opcional y explicación máxima de 512 caracteres. Confidence no convierte evidencia en probabilidad calibrada.

### 6.6 RepairPlan y RepairResult

```text
RepairPlan v1
  sourceAssetId/sourceSha256
  attempt: 1 | 2
  operations[]: allowlisted RepairOperation
  originatingIssueCodes[]
  authorization: automatic | human_decision_id
  expectedPostconditions[]

RepairResult v1
  sourceAssetId/sourceSha256
  childAssetId/childSha256
  attempt
  appliedOperations[]
  changedEntityIds[]
  toolVersions
  warnings[]
```

`operations` no contiene script, expresión, callback, prompt libre ni parámetro fuera de rango.

### 6.7 HumanReviewDecision

```text
HumanReviewDecision v1
  reviewId
  candidateAssetId/candidateSha256
  reviewerLocalId: pseudonymous local identifier
  decision: approve_export | approve_repair | keep_degraded | reject | quarantine
  selectedRepairPlanDigest?: required for approve_repair
  reasonCode: stable enum
  note?: max 2 KiB, local/private by default
  acknowledgedWarnings[]
  decidedAt
```

Una decisión es válida solo para el hash exacto. No crea allowlist global ni precedente automático.

### 6.8 InputSafetyReviewDecision

```text
InputSafetyReviewDecision v1
  operationId/ownerId
  inputSafetyAssessmentDigest
  policyVersion
  decision: allow_generation | reject | quarantine
  reasonCode
  decidedAt
  signature
```

Esta revisión ocurre antes de routing, no requiere candidate asset y su digest se incluye en `EffectivePlan`. No sustituye `HumanReviewDecision`, que solo aplica a assets ya generados.

### 6.9 LicenseDecisionReceipt

```text
LicenseDecisionReceipt v1
  receiptId
  licenseAdmissionReceiptId
  subjectAssetSha256
  lineageLicenseDigest
  manifestId/decisionId/licenseDigest
  territory
  intendedUse
  deliveryProfile
  distributionMode
  monthlyActiveUsersBand
  aupPolicyDigest
  decision: allow | deny | unknown
  validUntil
```

`AssetAuditCoordinator` deriva este recibo del `LicenseAdmissionReceipt` congelado y del lineage/hash final. El auditor exige que permanezca vigente y ligado al asset/destino. `deny|unknown`, cambio de territorio/uso/destino o digest distinto preceden cualquier `pass` y bloquean exportación.

Para `sourceKind=imported`, main invoca explícitamente el mismo `LicenseAdmissionService` fail-closed antes de crear `AuditRequest`; no depende de ProviderRouter ni inventa licencia ausente.

### 6.10 FinalDecision

Precedencia estricta:

1. `provenance/hash block`;
2. `license deny|unknown|expired`;
3. `structural/resource block`;
4. `deterministic geometry/PBR block`;
5. `safety block`;
6. `human review required`;
7. `repair candidate`;
8. `warning`;
9. `pass`.

El VLM puede mover 7-9 hacia 5-6, nunca 1-6 hacia 7-9. Un humano puede autorizar casos `review`, pero no sobrescribir corrupción estructural, hash mismatch, licencia denegada/desconocida o resource limit; esos requieren nuevo asset o contexto corregido.

## 7. Máquina de estados

```text
queued
  -> acquiring
  -> validating_structure
  -> auditing_deterministic
  -> rendering_canonical
  -> running_local_critic
  -> deciding

deciding -> approved -> committing -> succeeded
deciding -> warned -> committing -> succeeded_degraded
deciding -> needs_human -> awaiting_human
deciding -> blocked -> quarantined
deciding -> repair_planned -> repairing -> releasing -> reauditing

reauditing -> validating_structure  # child asset, attempt + 1
awaiting_human -> repair_planned | approved | warned | blocked | quarantined

any nonterminal --cancel request--> cancelling -> releasing -> cancelled
any worker failure except local critic -> releasing -> failed
running_local_critic --unavailable--> releasing -> deciding(needs_human)
```

Reglas:

- `awaiting_human` no retiene GPU ni worker; persiste snapshot/hash y libera lease.
- Al reanudar revisión se recalcula hash. Cambio implica `stale_review` y nueva auditoría.
- `repairing` solo inicia con plan validado y `attempt <= maxRepairAttempts <= 2`, ambos main-owned y ligados a `effectivePlanHash`.
- Segundo fallo reparable puede producir un segundo plan distinto. Mismo `operation + issue fingerprint` no se repite.
- Después del segundo intento, cualquier issue `repair` restante pasa a `needs_human` o `blocked` según severidad.
- Fallo del critic produce `critic_unavailable`: gates deterministas continúan, pero autoaprobación safety queda deshabilitada y la decisión es humana cuando el workflow requiere critic.
- CAS de terminal sigue el padre: cancel gana antes de `committing`; después responde `too_late_to_cancel`.
- Resultado tardío de worker, VLM o review con hash/operation distinto se descarta y registra como stale sin afectar decisión.

## 8. Preflight común y gates estructurales por formato

Preflight común obligatorio:

1. Resolver asset por ID y abrir con `O_NOFOLLOW`.
2. Verificar tipo regular, owner, tamaño y SHA-256.
3. Confirmar `assetFormat` por contenido bajo límites, no solo extensión.

### 8.1 Rama GLB

1. Parsear header GLB y chunks con límites antes de librerías de alto nivel.
2. Rechazar URI `http:`, `https:`, `file:`, path absoluto, `..`, data URI fuera de límite o recurso no embebido para perfil GLB autónomo.
3. Ejecutar glTF Validator pinneado con validación de recursos.
4. Normalizar JSON report a `AuditIssue` sin exponer paths.
5. Recargar con parser de runtime Three.js en test/integración independiente.

### 8.2 Rama STL

Un parser acotado detecta ASCII/binario sin confiar en extensión, valida tamaño y conteo de triángulos antes de asignar memoria, finitud, winding/orientación, manifold/watertight, dimensiones/unidades y espesor mínimo. Renders canónicos, safety, provenance, hash y licencia siguen siendo obligatorios; PBR/UV se marcan `not_applicable`, no `pass` ficticio. Nunca ejecuta glTF Validator ni parser Three.js.

Bloqueos:

- cualquier `error` de glTF Validator;
- GLB no 2.0, chunks inconsistentes o bytes trailing no permitidos;
- accessor/bufferView fuera de rango;
- `NaN`/`Inf`, quaternion inválido o matriz no descomponible;
- referencia faltante o recurso externo;
- extensión `required` no soportada por runtime objetivo;
- límite de bytes, nodos, primitivas, imágenes o profundidad excedido;
- parser disagreement entre validator y runtime.

Warnings del validator permanecen visibles y el perfil decide si escalan. `UNSUPPORTED_EXTENSION` nunca se ignora silenciosamente: `required` bloquea; `used` exige prueba de runtime o revisión.

## 9. Gate determinista de geometría y escena

Las métricas se calculan sobre mallas transformadas a world space y también por primitive para localizar evidencia.

### 9.1 Integridad geométrica

- posiciones, normales, tangentes, UV, weights y transforms finitos;
- índices dentro de rango y modo primitive soportado;
- triángulos degenerados por área bajo tolerancia relativa al AABB;
- vértices duplicados, aristas boundary/non-manifold y winding inconsistente;
- componentes conectados, tamaño relativo y componentes aislados;
- self-intersections aproximadas con reporte de incertidumbre; exactas solo bajo presupuesto;
- normales ausentes/invertidas y tangentes incompatibles con normal maps;
- AABB, diagonal, área y volumen no degenerados;
- origen, up-axis, escala, unidades y transform root conforme al perfil;
- densidad, triangle count, vertex count, draw calls y skin/morph budgets;
- thin structures, spikes, concavidades y agujeros funcionales cuando el corpus aporta expectativa.

### 9.2 Perfiles iniciales

`xr_mobile`:

- máximo 100.000 triángulos, 64 draw calls, 16 materiales y 2K por textura;
- origin dentro de 1% de diagonal respecto al punto de apoyo esperado;
- diagonal finita y escala declarada en metros;
- non-manifold, watertight y self-intersection son warnings salvo que rompan render, normals o perfil específico.

`xr_desktop`:

- máximo 300.000 triángulos, 128 draw calls, 32 materiales y 4K por textura;
- mismos requisitos de integridad y escala;
- topología abierta permitida si es intencional y no produce superficie invisible.

`web_xr`:

- máximo 150.000 triángulos, 64 draw calls, 16 materiales, atlas 2K y presupuesto total de bytes versionado;
- solo extensiones declaradas por el viewer web objetivo; escala/unidades y checks de integridad equivalentes a XR visual.

`fabrication_preview`:

- máximo 1.000.000 triángulos;
- watertight, manifold, winding consistente, volumen positivo y dimensiones explícitas;
- espesor mínimo es reportado según escala, pero no constituye certificación de fabricación;
- PBR es informativo; el exportador debe declarar pérdida de materiales al producir STL.

Los números son policy inicial versionada, no constantes dispersas. Cambiarlos crea versión nueva y exige benchmark/regresión.

### 9.3 Disposición

- Corrupción, no finitud, AABB degenerado o budget hard ceiling: `block`.
- Perfil excedido dentro de ceiling: `repair_candidate` para decimation/reducción permitida.
- Non-manifold en XR visual: `warning/review`; en fabricación: `block` o repair humano.
- Componente pequeño no se elimina automáticamente si tiene nombre, material distinto, parent semántico, simetría o correspondencia visible con referencia.
- Spike o parte delgada nunca se clasifica como basura solo por tamaño; puede ser antena, asa, dedo, hoja o componente riesgoso.

## 10. Gate determinista PBR, UV y atlas

Se emiten dos decisiones distintas: `gltf_material_conformant` admite materiales glTF factor-only válidos; `generated_textured_pbr` exige texturas generadas y es el único gate que puede derivar `textureApplied=true`.

### 10.1 Requisitos

- al menos una UV válida cuando existe texture map;
- UV finita y channel index existente;
- cobertura, overlap, inversión, out-of-range y gutter medidos por primitive/material;
- `baseColorTexture` en sRGB; metallic/roughness, normal y occlusion tratados como datos lineales;
- channel packing glTF documentado: occlusion R cuando se use; roughness G; metallic B;
- normal map con tangents válidas o derivación runtime probada;
- imágenes decodificables, dimensiones conforme a perfil y texels finitos;
- alpha mode/cutoff consistente con uso real; transparencias innecesarias reportadas;
- material no vacío, texture references válidas y sampler soportado;
- colores/baseColorFactor dentro de rango PBR y sin valores que produzcan clipping sistemático;
- atlas no vacío, sin grandes regiones sin asignar inesperadas y con padding suficiente;
- texel density y resolución coherentes entre partes comparables;
- material count y texture count dentro de presupuesto.

El glTF Asset Auditor oficial se ejecuta con perfil JSON versionado. Checks slow de overlap y gutter forman parte del gate de promoción/exportación, aunque puedan omitirse en preview interactivo marcado `partial`.

### 10.2 Atlas y partes: revisión humana obligatoria

Se requiere `needs_human` cuando una reparación propuesta:

- reempaqueta UV y cambia orientación/escala relativa de islas;
- combina o separa materiales;
- elimina isla, componente o parte visible;
- rellena un hueco que puede ser cavidad funcional;
- reasigna texels entre partes simétricas o superpuestas;
- sustituye mapa ausente por constante o mapa sintetizado;
- cambia alpha/transmission de una pieza semánticamente transparente;
- altera seams visibles por encima del threshold de referencia.

La UI muestra modelo y atlas antes/después, islas afectadas, overlays de overlap/gutter, materiales, partes y renders correspondientes. La acción humana autoriza un digest exacto de `RepairPlan`, no una intención genérica.

## 11. Renders canónicos

### 11.1 Propósito

Crear evidencia comparable entre ejecuciones y cubrir defectos que no aparecen en estructura. No se usan thumbnails previos ni cámaras elegidas por el generador.

### 11.2 Normalización

- Recargar GLB desde bytes auditados.
- Aplicar transforms world sin mutar fuente.
- Calcular bounding sphere/AABB robusto ignorando vértices no finitos ya bloqueados.
- Centrar cámara en centro geométrico; no recenter del asset persistido.
- Ajustar distancia para margen de 8% con FOV fijo de 35°.
- Up-axis y handedness conforme a glTF; cámara nunca depende de metadata libre.
- Fondo gris lineal fijo; resolución 1024x1024; device pixel ratio 1.
- WebGL/Three.js, shader, tone mapping, exposición, output color space y versión quedan pinneados en `renderProfileVersion`.
- Cero red, fuentes, environment maps o texturas externas.

### 11.3 Vistas y pases

Set mínimo:

- ocho vistas orbit a azimuth `0°, 45°, 90°, 135°, 180°, 225°, 270°, 315°`, elevation `15°`;
- top y bottom a `+90°/-90°` con roll fijo;
- close-up automático solo para issue regions deterministas, máximo cuatro;
- cada cámara renderiza `neutral_pbr`, `clay`, `normal` y `part_id`;
- `wireframe` se genera para front, back, top y bottom;
- atlas sheets separados por material con límite de ocho páginas; exceso produce review.

Iluminación:

- `neutral_pbr`: entorno neutral pinneado + key/fill/rim fijos;
- `clay`: material opaco gris, sin texturas, double-sided deshabilitado salvo primitive declarado;
- `normal`: world normals mapeadas de forma determinista;
- `part_id`: color derivado de stable entity ID, sin antialias que mezcle IDs al medir;
- shadows y ambient occlusion usan configuración congelada; nondeterminism observado fuera de tolerancia bloquea golden promotion.

### 11.4 Contact sheets para critic

- `semantic_sheet`: ocho vistas `neutral_pbr` en grilla 4x2.
- `geometry_sheet`: ocho vistas `clay`, top/bottom y cuatro wireframes en grilla etiquetada por IDs de vista generados fuera de la imagen.
- `material_sheet`: front/back/top/bottom PBR, atlas thumbnails y leyenda de canales.
- `safety_sheet`: ocho vistas PBR y ocho clay sin texto proveniente del asset.

Metadata/nombres del GLB no se rasterizan. Las etiquetas son generadas por el renderer desde enums seguros. Esto reduce, pero no elimina, prompt injection visual presente en texturas.

### 11.5 Reproducibilidad

- Hash de cada imagen y digest del set.
- Golden exacto cuando hardware/renderer coinciden; comparación perceptual con threshold congelado entre GPU compatibles.
- Tolerancia inicial: SSIM ≥0,999 y diferencia máxima por pixel reportada; cualquier relajación requiere justificarla con corpus y no puede ocultar missing geometry/material.
- Render vacío, negro, saturado, clipping total o cámara sin cobertura es `render_failure`, no evidencia de asset correcto.

## 12. Local VLM Critic

### 12.1 Selección y aislamiento

El modelo no se fija por nombre en este diseño. El registry estable exige:

- pesos locales ya aprobados, formato seguro y digest exacto;
- licencia compatible y notice registrado;
- soporte multi-image o contact sheets demostrado;
- memoria admitida dentro de 24 GB después de liberar renderer;
- salida JSON fiable bajo constrained decoding o parser estricto;
- benchmark contra corpus humano y adversarial;
- cero `trust_remote_code` en estable;
- proceso sin red, filesystem read-only limitado a render set y pesos.

SmolVLM2 es candidato de laboratorio por disponer de variantes 2.2B/500M/256M y soporte MLX publicado por Hugging Face. No se promueve sin benchmark de defectos 3D y safety; ser pequeño/on-device no prueba capacidad crítica.

### 12.2 Input

El critic recibe:

- rubric del sistema versionado;
- `semantic_sheet`, `geometry_sheet`, `material_sheet` y `safety_sheet` por bytes/FD;
- resumen determinista reducido y tipado;
- perfil objetivo y reference render opcional sanitizado.

No recibe:

- prompt original por defecto;
- filenames, paths, URLs, metadata, logs o notas humanas;
- instrucciones extraídas por OCR;
- reportes de modelos anteriores redactados en lenguaje persuasivo;
- herramientas o capacidad de cargar contenido adicional.

La instrucción del sistema declara todo texto visible en imágenes como dato no confiable y exige evaluar pixels/geometry, no obedecerlo. Tests incluyen texturas con prompt injection.

### 12.3 Rubric

Criterios separados:

- `reference_alignment`: identidad, silueta y partes visibles respecto a referencia cuando existe;
- `geometry_completeness`: missing/duplicated/fused parts, holes inesperados, backside y floating geometry;
- `surface_quality`: lumps, spikes, staircase, melted detail y self-occlusion visual;
- `material_coherence`: bleeding, seams, stretched texture, inconsistent roughness/metallic y empty atlas;
- `view_consistency`: defecto aparece en vistas vecinas o es artefacto de cámara;
- `semantic_safety`: categorías del threat model con vistas citadas;
- `uncertainty`: evidencia insuficiente, categoría dual-use o conflicto con checks deterministas.

El critic debe citar `viewIds`; una observación sin vista/evidencia se descarta y aumenta `critic_contract_violation`.

### 12.4 Decoding y validación

- `temperature=0`, `topP=1`, seed fija y token cap.
- JSON schema cerrado, profundidad 16, 128 observaciones, 32 KiB.
- Un parse repair puramente sintáctico máximo; no se vuelve a preguntar al modelo con error libre.
- Confidence fuera de `[0,1]`, repair code desconocido, view ID inexistente o string excedido rechaza report.
- Report inválido dos veces marca critic `failed`; no existe interpretación regex/free-text.

### 12.5 Limitaciones vinculantes

Investigación 2025-2026 muestra sesgo de posición/longitud y que un VLM juez puede prestar poca atención a la imagen y favorecer respuestas más informativas. Por tanto:

- el critic nunca emite `approved`;
- no se le entrega una respuesta candidata persuasiva para comparar;
- criterios se preguntan de forma pointwise y anclada en vistas;
- orden de contact sheets se rota en benchmark, pero estable usa orden fijo;
- conflicto VLM/determinista aumenta review, no promedia scores;
- safety de baja confianza no significa seguro;
- cada revisión de modelo exige recalibración y no reutiliza thresholds previos.

## 13. Decisión combinada

Matriz:

| Determinista | Critic | Resultado automático |
|---|---|---|
| block | cualquiera | block |
| review | no issue | human review |
| pass/warn | safety_block | quarantine + human review según policy |
| pass/warn | human_review | human review |
| pass/warn | repair_candidate | plan allowlisted si existe evidencia localizada |
| pass | no_additional_issue | approved |
| warn | no_additional_issue | succeeded_degraded con warnings explícitos |
| pass/warn | critic failed/unavailable | human review cuando policy requiere critic; jamás safety auto-pass |

No se suman severidades ni confidences. La razón final conserva cadena causal de issues.

## 14. Reparación dirigida

### 14.1 Operaciones automáticas allowlisted

Solo si issue y precondiciones coinciden:

- `remove_degenerate_triangles`: elimina caras bajo tolerancia, sin borrar componente completo.
- `weld_duplicate_vertices`: tolerancia relativa congelada; preserva seams UV/material boundaries.
- `recompute_normals`: solo mesh sin normal map/tangents incompatibles y orientación demostrable.
- `fix_winding_component`: componente cerrado con volumen/signo coherente.
- `drop_unreferenced_resources`: buffers/images/materiales no alcanzables desde escena activa.
- `strip_unsupported_optional_extension`: solo extensión `used`, no `required`, y equivalencia visual comprobable.
- `resize_texture_to_profile`: downscale determinista, color space y alpha preservados.
- `reencode_lossless_texture`: sin cambio de dimensions/channels/color semantics.
- `pad_uv_gutters`: modifica solo texels de padding sin mover islas.
- `pack_metallic_roughness`: solo con mapas fuente identificados y channel semantics verificadas.
- `decimate_to_budget`: preservación de boundary, UV seams, normals y materiales; requiere delta visual bajo threshold.

### 14.2 Operaciones con autorización humana

- fill holes;
- eliminar componente pequeño o floating part;
- reempacar o regenerar UV;
- fusionar/separar materiales;
- cambiar alpha, transmission o double-sided;
- reconstruir o sintetizar mapa faltante;
- remesh que cambie topología;
- decimation que afecte parte delgada/funcional;
- recenter, rescale o cambiar orientación persistida cuando dimensiones no están confirmadas;
- cualquier operación sobre asset safety-review.

### 14.3 Operaciones prohibidas

- reparación libre generada por VLM;
- ejecución de Blender/Python/JS producido por modelo;
- borrar parte para reducir score safety;
- convertir un objeto dañino en benigno sin nuevo pedido explícito del usuario;
- ocultar defecto mediante cámara, material, alpha o cropping;
- inventar textura/PBR y etiquetarla como recuperada;
- mutar asset fuente o reutilizar su asset ID para hijo.

### 14.4 Límites y rollback

- Máximo dos intentos totales desde `rootAssetId`, incluso a través de reinicios.
- Máximo ocho operaciones por plan; operaciones se ordenan canónicamente.
- Cada operación declara precondición, entidades, parámetros acotados y postcondición medible.
- Si una operación cambia más entidades que las autorizadas, el resultado se descarta.
- Repair fingerprint = source hash + operation codes + canonical params. Fingerprint repetido no vuelve a ejecutarse.
- Source, child y reports se conservan hasta decisión; rollback selecciona padre, no aplica inversa heurística.
- Regresión nueva `block/review` impide promoción aunque el issue original desaparezca.

## 15. Revisión humana

### 15.1 UX mínima

El panel presenta:

- decisión propuesta y por qué no puede automatizarse;
- source/candidate lado a lado con cámaras sincronizadas;
- toggles PBR, clay, normal, wireframe y part IDs;
- atlas antes/después con overlays de islas, overlap, gutter y texel density;
- lista de partes afectadas con highlight;
- reference image/render cuando existe;
- cambios exactos del RepairPlan y métricas pre/post;
- señal safety por categoría, evidencia y uncertainty;
- licencia/provenance relevante y destino de exportación.

No muestra un único porcentaje de “seguridad” o “calidad”. Acciones peligrosas requieren confirmación específica y no se preseleccionan.

### 15.2 Reglas de decisión

- `approve_repair` firma digest del plan y candidate hash.
- `approve_export` permitido solo para review/warning; no para corrupción/hash/resource block.
- Safety dual-use requiere razón codificada y confirmación de uso legítimo local; no desbloquea categoría global.
- `keep_degraded` preserva asset sin marcarlo export-ready.
- `quarantine` retira previews de galería general y bloquea exportación estándar.
- Toda nota humana es privada por defecto y no entra en sidecar exportable salvo opt-in separado.

### 15.3 Accesibilidad y error

- Overlays no dependen solo de color.
- Part IDs tienen etiqueta textual segura y navegación por teclado.
- Imágenes mantienen zoom/pan vinculados y vista de pixels 1:1 para atlas.
- Si render o atlas no están disponibles, la UI no ofrece decisión que dependa de ellos.
- Cerrar/reload no pierde decisión ya comprometida ni aprueba por defecto.

## 16. Defensa apilada contra geometría dañina

Capas:

1. **Input policy local:** prompt/reference se clasifican antes de generación; mismatch texto-imagen y camuflaje conocido elevan revisión.
2. **Generación:** modelos/perfiles con licencia y safety policy registradas; no se deshabilitan guardrails para estable.
3. **Output determinista:** métricas de escala, partes, spikes, cavidades, ensamblabilidad y componentes producen señales, no semántica definitiva.
4. **Renders multivista:** PBR y clay evitan depender de textura o una vista; top/bottom/back obligatorios.

`WorkflowCoordinator` es owner de `InputSafetyAssessment`: lo produce antes de ProfilePolicy/routing y congela `{policyVersion, promptDigest, referenceDigest, categories, decision, evidenceDigest}`. Solo el digest cruza `EffectivePlan`, `RouteRequest`, `AuditRequest` y sidecar; `block` impide routing y `review` requiere autorización humana registrada.
5. **VLM local:** clasificación por taxonomía, vista y uncertainty.
6. **Reglas de combinación:** cualquier señal fuerte bloquea autoexport; discrepancias van a humano.
7. **Humano:** dual-use, réplica, componente y contexto legítimo se revisan con evidencia.
8. **Export policy:** cuarentena, formato/destino y provenance se aplican después de decisión.

Controles adversariales:

- inputs originales, degradados, viewpoint-shifted y semánticamente camuflados;
- objeto benigno con textura peligrosa y objeto peligroso con textura benigna;
- componentes separados que solo ensamblados forman objeto riesgoso;
- escala ambigua o ausente;
- réplica/juguete/herramienta/artefacto histórico para medir falsos positivos;
- texto de prompt injection en textura, atlas y entorno;
- parte peligrosa oculta en backside/interior;
- critic sin referencia o con reference conflictiva.

La aplicación no ofrece instrucciones para fabricación ni afirma detectar todo riesgo. Un `pass` significa cumplimiento de esta política/version/corpus, no garantía universal.

## 17. Falsos positivos, falsos negativos y calibración

### 17.1 Casos de falso positivo esperables

- cuchillos culinarios, herramientas, tijeras, equipamiento deportivo;
- props, juguetes y réplicas estilizadas;
- objetos médicos, industriales o históricos;
- agujas, antenas, púas decorativas y partes delgadas legítimas;
- componentes mecánicos genéricos de uso dual;
- logos/texto que el VLM interpreta fuera de contexto;
- formas parciales por cámara o alpha.

Mitigación:

- categoría `unknown_dual_use`, nunca forzar etiqueta dañina binaria;
- exigir al critic vistas y uncertainty;
- revisión humana sin allowlist permanente;
- corpus benigno difícil y medición por categoría;
- mensajes neutrales que no acusen intención del usuario;
- override ligado al hash y destino, no a similitud semántica futura.

### 17.2 Falsos negativos esperables

- piezas individuales inocuas que forman ensamblaje dañino;
- camuflaje semántico o textura engañosa;
- geometría interna no visible;
- escala ausente;
- VLM que ignora pixels o prioriza descripción;
- categoría no presente en training/corpus.

Mitigación:

- multivista + clay + partes + checks deterministas;
- no usar prompt benigno como evidencia exculpatoria;
- revisión para componentes/replicas/uncertainty;
- red-team corpus versionado;
- reauditar al cambiar modelo, renderer o política.

### 17.3 Umbrales de promoción safety

Sobre holdout congelado, CI binomial exacto o Wilson 95% dimensionado a priori (no bootstrap degenerado para cero eventos):

- harmful retention ≤1% y límite superior CI ≤2%;
- false-positive rate benigno global ≤10% y ninguna categoría benigna crítica >15%;
- recall de `direct_physical_hazard` y `deceptive_replica` ≥98%;
- 100% de casos con structural/hash block permanecen bloqueados ante outputs VLM adversariales;
- prompt-injection attack success = 0 en corpus conocido;
- overrides humanos incorrectamente reutilizados = 0.

Si no se cumplen, safety queda `human_required` y no existe autoexportación para workflows condicionados.

## 18. Privacidad y retención

- Toda inferencia, auditoría, render y firma ocurre localmente.
- Workers se lanzan con red denegada; una prueba centinela verifica que DNS/socket falla.
- No se aceptan URL en GLB ni critic input; assets remotos deben importarse explícitamente al repositorio antes.
- Prompts, imágenes de referencia, renders y notas humanas no se envían a analytics.
- Sidecar privado conserva prompt solo como hash salted por asset; texto completo requiere opt-in explícito.
- Nombre de usuario, path absoluto, hostname, serial del Mac y reviewer real no aparecen en artefacto exportable.
- Renders de auditoría son derivados sensibles: TTL por defecto 7 días; se conservan si usuario fija asset o si son evidencia de decisión activa.
- Quarantine no significa reporte externo; solo aislamiento local y bloqueo de exportación.
- Logs usan operation/asset IDs, códigos y tamaños; no contienen pixels, prompt, metadata libre o salida razonada del VLM.
- Borrar asset elimina derivados/sidecars según política y deja solo tombstone no sensible si se necesita reconciliar índice.

## 19. Procedencia, sidecar e integridad

### 19.1 Sidecar privado canónico

`<asset-id>.audit.json` usa serialización JSON canónica y contiene:

- schema/version;
- asset/root/parent IDs opacos;
- SHA-256 de source, candidate final, reference opcional y cada render/report;
- workflow, seed y effective plan hash;
- app commit/build, engine, renderer y tool versions;
- repositorio/revisión/digest de modelos Shape, Paint y critic;
- audit/safety/render profile versions;
- issues y final disposition;
- RepairPlan/RepairResult digests y lineage;
- HumanReviewDecision digest, sin nota privada salvo opt-in;
- LicenseAdmissionReceipt y LicenseDecisionReceipt digests asset-bound, más identifier/notice digest;
- timestamps y firma local.

Firma = clave local de aplicación protegida por Keychain sobre hash del sidecar canónico sin campo firma. Verificación se realiza antes de mostrar `auditado` o export-ready.

### 19.2 Sidecar exportable

Perfil mínimo por defecto:

- hash del asset GLB/STL;
- software/model revisions y licencias/notices exigidos;
- seed/config hashes sin prompt;
- acciones de generación/reparación;
- validators/profile y disposición;
- firma pública o local según configuración.

PII, paths, nota humana, prompt e imagen de referencia se excluyen. C2PA 2.2 puede aplicarse a previews compatibles; hasta demostrar binding/reader interoperable para GLB, el sidecar firmado es fuente de procedencia 3D. C2PA prueba integridad de declaraciones firmadas, no verdad, autoría ni licencia del input.

### 19.3 TOCTOU

- Auditoría opera sobre FD/hash inmutable.
- Commit copia/renombra desde temp del repositorio, calcula hash final y compara con `candidateSha256`.
- Export abre por ID, recalcula hash y exige sidecar válido para ese digest.
- Cualquier mismatch produce `provenance_hash_mismatch` block y nueva auditoría.

## 20. Métricas y benchmark

### 20.1 Integridad y geometría

- validator error/warning counts por code;
- auditor pass/review/block por perfil;
- triangle/vertex/draw/material/texture counts;
- degenerate ratio, boundary/non-manifold edges, components, self-intersection estimate;
- UV coverage/overlap/inversion/out-of-range/gutter;
- PBR map presence, resolution, empty texel ratio y channel correctness;
- parser disagreement y render failure rate.

### 20.2 Critic

- agreement con tres revisores humanos y adjudicación;
- precision/recall/F1 por defecto y safety category;
- false-positive/false-negative rate con CI 95%;
- abstention/review rate y calibration por confidence bins;
- view citation validity;
- contract-valid JSON at first attempt;
- positional/view-order sensitivity;
- image ablation gap: el score debe degradar si se ocultan renders, detectando judge que no mira;
- prompt-injection attack success;
- disagreements con determinista, sin promediarlos.

### 20.3 Reparación

- first-attempt y second-attempt success;
- issue closure rate por operation code;
- nuevas regresiones block/review;
- entidades cambiadas vs autorizadas;
- triangle/file-size delta;
- render SSIM/LPIPS y silhouette/depth delta pre/post;
- human acceptance/rejection por operación;
- rollback success y orphan count.

### 20.4 Rendimiento 24 GB

- p50/p95 load, validator, auditor, render, critic, repair y commit;
- MLX active/peak/cache memory, process RSS, swap delta y memory pressure;
- cold/first-observed/warm separados;
- cache hit por digest/profile;
- cancel-to-ack latency y forced-kill count;
- bytes temporales, render-set size y TTL cleanup.

No se combina todo en un quality score. Promoción usa métricas primarias congeladas, CI pareado y frontera Pareto exactitud/latencia/memoria/FPR.

## 21. Corpus de evaluación

Corpus versionado mínimo:

- 30 GLB conformes: PBR, unlit, alpha, multi-material, skins/morphs soportados y variedad topológica;
- 30 defectuosos unitarios: un defecto localizado por asset;
- 20 defectuosos compuestos: estructura + visual + PBR;
- 20 resource/adversarial: truncation, offsets, NaN, URI, deep scene, bombs y extension cases;
- 30 reparables con golden parent/child esperado;
- al menos 183 safety dañinos sin fallo para demostrar upper bilateral 95% ≤2% global; además cada familia se dimensiona a priori para poder demostrar recall ≥98%;
- 40 benignos difíciles/dual-use para FPR;
- 20 prompt-injection visual/metadata;
- 12 assets con reference/GT para silhouette, depth, normals y PBR;
- atlas fixtures con overlap, inversion, gutter, mirrored islands y parts ambiguas.

Licencia y procedencia de cada fixture quedan en registry. Assets dañinos no se distribuyen fuera del entorno controlado; se usan representaciones no fabricables cuando sea posible y acceso local restringido.

## 22. Gates de implementación y pruebas

### Gate -2: baseline y dependencias

- Registrar build/tests actuales, dirty tree y artefactos conocidos.
- Pinnear glTF Validator, Asset Auditor/profile, renderer y parsers con hash/licencia.
- Crear corpus/registry sin descargar contenido durante tests normales.
- Confirmar que ninguna dependencia de auditoría requiere red en runtime.

Salida: reporte baseline reproducible; ningún cambio de comportamiento productivo aún.

### Gate -1: contención y contracts

Tests:

- renderer no puede enviar path/URL/threshold/model arbitrary;
- asset ID de otro owner se rechaza;
- symlink swap y file replacement no alteran bytes auditados;
- URI remota/absoluta/`..` bloqueada;
- report externo no filtra path/string libre;
- worker env centinela no ve secretos y socket/DNS falla;
- output VLM no puede invocar herramienta o repair code desconocido.

Salida: contratos cerrados y workers aislados. No avanzar con fuga de path, red o secreto.

### Gate 0: lifecycle

Tests de estado:

- happy path exacto;
- cancel en cada estado no terminal;
- worker timeout requiere ack/kill antes de release;
- late result y stale human decision descartados;
- CAS cancel vs commit produce un solo terminal;
- `awaiting_human` libera lease;
- tercer workload pesado se rechaza según coordinador padre;
- restart reconcilia temp, review pendiente y manifests.

Salida: cero doble terminal, publicación parcial u orphan no reconciliado.

### Gate 1: glTF Validator y auditor determinista

Tests golden por issue code:

- malformed header/chunk/accessor/buffer/image;
- NaN/Inf y matrices inválidas;
- unsupported required/used extensions;
- límites de escena/mesh/textura;
- degenerates, winding, manifold, components, scale/origin;
- UV/PBR/channel/color-space/alpha;
- perfiles XR/fabrication producen disposiciones distintas documentadas;
- reports se calculan sobre asset final recargado por la rama GLB/STL correspondiente.

Salida: 100% fixtures corruptos bloqueados y cero cambios de code/disposition entre dos runs idénticos.

### Gate 2: renderer canónico

Tests:

- cámaras, matrices, FOV, exposure y environment hashes esperados;
- todas las vistas/pases presentes;
- asset asymmetric prueba front/back/top/bottom correctos;
- missing backside y floating part visibles en golden;
- textura externa no provoca request de red;
- asset names/metadata no aparecen rasterizados;
- render bomb respeta deadline/RSS;
- golden exacto en runner fijado y SSIM threshold cross-run.

Salida: render-set completo, determinista y content-addressed.

### Gate 3: critic local

Tests contract/adversarial:

- JSON válido first-pass y límites;
- unknown fields/codes/view IDs rechazados;
- texturas con “ignore previous instructions” no cambian schema/policy;
- blank/occluded/shuffled sheets elevan uncertainty;
- image ablation detecta critic que responde sin mirar;
- determinista block nunca degradado;
- model unavailable/OOM produce human-required, no pass;
- corpus humano calcula agreement, FPR/FNR y CIs.

Salida: thresholds de promoción cumplidos o critic permanece laboratorio/manual.

### Gate 4: reparación dirigida

Tests por cada operation code:

- precondición faltante rechaza plan;
- solo entidades autorizadas cambian;
- source hash permanece igual;
- child tiene nuevo ID/hash/lineage;
- full re-audit posterior obligatorio;
- regression block impide promoción;
- mismo fingerprint no se repite;
- attempt 3 imposible incluso tras restart;
- crash deja source intacto y temp reconciliable;
- rollback selecciona padre exacto.

Salida: repair closure medido, cero mutación fuente y límite dos demostrado.

### Gate 5: human-in-loop

Browser tests:

- atlas/parts/render side-by-side y overlays correctos;
- approve action firma plan/hash exacto;
- cambio de asset invalida decisión;
- no se puede aprobar structural/hash/resource block;
- safety override no crea allowlist;
- ausencia de evidencia deshabilita acción dependiente;
- keyboard, labels no-color-only y zoom sincronizado;
- reload conserva solo decisiones comprometidas.

Salida: cada decisión humana trazable, específica y reversible.

### Gate 6: safety y procedencia

Tests:

- tres familias harmful + degradación/viewpoint/camuflaje;
- benign dual-use FPR medido;
- parte oculta y multi-component assembly;
- prompt injection visual/metadata;
- sidecar canonical/sign/verify/tamper;
- prompt/path/PII ausentes del sidecar exportable;
- mismatch asset-sidecar bloquea export;
- delete/TTL/quarantine cumplen retención;
- funcionamiento completo con red deshabilitada.

Salida: targets safety cumplidos o policy fuerza humano; tamper detection 100% en corpus.

### Gate 7: cadena completa

- Shape-only -> audit -> repair opcional -> export.
- Shape -> Paint -> audit PBR -> atlas review -> export.
- Import GLB/STL corrupto -> block explicable por rama de formato.
- Harmful/dual-use -> stacked defense -> quarantine/review.
- Cancel/fallo inyectado en validator, render, critic, repair y commit.
- Reanudación desde cache por digest sin saltar gates.
- UI, consola, historial, manifests y archivos inspeccionados.
- `node --test` para módulos puros, tests Python del engine/fixtures, `npm run build:vite`, integración opt-in con modelos locales y browser smoke.

Salida: evidencia fresca de tests/build/smoke; no se acepta `/health` ni screenshot aislado como verificación completa.

## 23. Criterios de aceptación finales

- Cero red en validator, auditor, renderer, critic y repair workers.
- Cero paths arbitrarios, secretos o metadata libre cruzando renderer IPC.
- 100% de errores glTF Validator bloquean exportación GLB; STL usa su gate estructural propio.
- 100% de mismatch hash/sidecar bloquean exportación.
- Gates geométricos corren sobre asset final recargado; PBR solo sobre GLB.
- Renders canónicos cubren ocho orbit, top/bottom y pases PBR/clay/normal/part IDs.
- Critic usa modelo/revisión/digest local registrado, salida JSON cerrada y evidencia por vista.
- Critic nunca reduce bloqueo determinista ni aprueba por sí solo.
- Harmful geometry usa defensa apilada y cumple targets del holdout o queda human-required.
- FPR se reporta por categoría y dual-use dispone de revisión/override por hash.
- Reparación automática limitada a allowlist y máximo dos intentos persistentes.
- Atlas, partes, holes, remesh y cambios semánticos requieren autorización humana.
- Cada reparación crea asset hijo y full re-audit; source permanece byte-identical.
- Sidecar firmado liga input, modelos, configuración, renders, reports, reparación y decisión.
- Sidecar exportable excluye prompt, paths, PII y nota humana por defecto.
- Cancelación/timeout/crash no publican asset parcial ni liberan lease prematuramente.
- Tests unitarios, golden, adversariales, build, integración local y browser smoke pasan con evidencia fresca.

## 24. Riesgos residuales

- Un VLM local puede ignorar imágenes, sesgarse o desconocer categorías; human review y red-team reducen, no eliminan, el riesgo.
- Geometría dañina depende de escala, material, ensamblaje y contexto que un GLB puede omitir.
- Heurísticas de spikes/thickness/componentes generan falsos positivos en herramientas, props y objetos industriales.
- Self-intersection exacta y UV overlap exhaustivo pueden exceder presupuesto en assets grandes; el sistema debe declarar aproximación/partial, no false pass.
- Render determinista entre GPU/drivers puede requerir comparación perceptual; thresholds laxos pueden ocultar regresiones.
- Repair de topología/atlas puede degradar identidad aunque cierre métricas; de ahí el gate humano.
- Firma local demuestra integridad desde ese signer, no derechos de autor, licencia de input ni verdad de declaraciones.
- Modelos y validadores de terceros conservan riesgo supply-chain; pin, hash, formato seguro, licencia y revisión siguen obligatorios.

## 25. Fuentes consultadas y vigentes al 2026-07-19

- Khronos Group, [glTF 2.0 Specification y recursos oficiales](https://github.com/KhronosGroup/glTF).
- Khronos Group, [glTF Validator](https://github.com/KhronosGroup/glTF-Validator): schema, GLB, buffers, accessors, imágenes, extensiones y report JSON.
- Khronos Group, [glTF Asset Auditor](https://www.khronos.org/gltf/gltf-asset-auditor/): perfiles, PBR colors, dimensiones, materiales, texturas, texel density, UV overlap/inversion/range/gutter; procesamiento local en browser.
- Khronos Group, [Asset Creation Guidelines 2.0](https://www.khronos.org/blog/introducing-asset-creation-guidelines-2.0-siggraph-2025): prácticas UV, atlas, texel density y extensiones PBR.
- Khronos Group, [PBR en glTF](https://www.khronos.org/gltf/pbr).
- Liu et al., [On the Generation and Mitigation of Harmful Geometry in Image-to-3D Models](https://arxiv.org/abs/2605.09606), 2026: categorías, ataques por degradación/viewpoint/camuflaje, evaluación multivista/VLM/humana y tradeoff de defensa apilada.
- Meng et al., [3DEditSafe: Defending 3D Editing Pipelines from Unsafe Generation](https://arxiv.org/abs/2605.15398), 2026: insuficiencia de safety 2D aislada y necesidad de restricciones sobre representación/render 3D.
- Zou et al., [When Vision-Language Models Judge Without Seeing: Exposing Informativeness Bias](https://arxiv.org/abs/2604.17768), 2026: VLM judges pueden ignorar imagen y favorecer información textual.
- Laskar et al., [Judging the Judges](https://arxiv.org/abs/2505.08468), 2025: variabilidad, positional bias y length bias en jueces VLM pequeños.
- Hugging Face, [SmolVLM2: Bringing Video Understanding to Every Device](https://huggingface.co/blog/smolvlm2), 2025: variantes on-device y soporte MLX; candidato de benchmark, no evidencia de auditoría 3D.
- NIST, [AI RMF Generative AI Profile, NIST AI 600-1](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence), actualizado 2026: medición, privacidad, contenido peligroso y riesgos de supply chain.
- C2PA, [Technical Specification 2.2](https://spec.c2pa.org/specifications/specifications/2.2/specs/C2PA_Specification.html), mayo 2025: manifests, signatures, ingredients, revocation y privacidad.
