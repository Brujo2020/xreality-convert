# ProfilePolicy: Velocidad, Balanceado y Calidad

Fecha: 2026-07-19
Estado: diseño aprobado; pendiente de plan TDD
Ámbito: resolución y congelación de planes para Texto→Imagen, Texto→CSG IR e Imagen→3D/PBR

## 1. Resultado verificable

La aplicación tendrá un selector global cerrado:

- `Velocidad`
- `Balanceado` — valor predeterminado
- `Calidad`

El selector expresa un objetivo de Pareto, no parámetros directos. Electron main resuelve un `EffectivePlan` versionado usando workflow, destino XR, categoría, modelos promovidos, capacidades y memoria disponible. El plan se congela al crear la operación y se conserva en manifest/historial.

Éxito exige:

- misma intención + mismas capacidades + misma versión produce mismo plan/hash;
- renderer no puede inyectar parámetros derivados;
- `Calidad` nunca rompe límites del destino XR ni safety caps;
- cambiar selector durante una operación solo afecta la siguiente;
- UI muestra perfil solicitado, plan efectivo, clamps, bloqueos y degradación real;
- `Balanceado` es default global y por workflow nuevo.

## 2. Alternativas evaluadas

### Preset imperativo en React

Rechazado. Mutar `params`, `steps3d`, `asset` y `guidance3d` desde eventos produce estado compartido, herencias entre workflows y combinaciones imposibles.

### Resolver puro en renderer

Rechazado como autoridad. Sirve para preview, pero un renderer comprometido podría enviar planes stale o saltarse límites.

### Resolver main-owned con validación backend

Seleccionado. Renderer envía intención; main resuelve y firma/hash el plan; cada backend autentica la operación y revalida relaciones estructurales.

## 3. Separación de ejes

Los ejes no se sobrescriben entre sí:

1. **Seguridad/capacidad/memoria:** límites absolutos, siempre primero.
2. **Workflow/formato:** PNG, STL o GLB; PBR solo para GLB.
3. **Destino XR:** caras finales, escala, atlas máximo y formato.
4. **Override avanzado válido:** limitado al workflow activo.
5. **Perfil de calidad:** esfuerzo, modelo Pareto, resolución de trabajo y reparación.
6. **Categoría semántica:** guidance, background, padding y escala sugerida.
7. **Default seguro:** `balanced`.

`mobile + quality` conserva presupuesto mobile. `pcvr + speed` conserva presupuesto PCVR, pero reduce compute. Calidad puede aumentar detalle de trabajo; nunca eleva `deliveryTargetFaces`.

## 4. Contratos

```text
QualityProfile = speed | balanced | quality
Workflow = text_image | text_3d | image_3d
SourceKind = generated | imported
TextureIntent = off | auto | on
DeliveryProfile = xr_mobile | xr_desktop | web_xr | fabrication_preview

ProfileIntent {
  qualityProfile
  workflow?
  sourceKind
  category
  deliveryProfile
  outputFormat
  textureIntent
  selectedModelKey?
  advancedOverrides?
}

EffectivePlan {
  policyVersion
  operationClass
  requestedProfile
  effectiveProfile
  workflow?
  sourceKind
  stageCandidatePolicies[]
  inputSafetyAssessmentDigest
  inputSafetyReviewDecisionDigest?
  stagePlans
  deliveryPlan
  memoryAdmissionPreview  # informativo; no autoriza carga
  provenanceByField
  warnings
  blockers
  planHash
}
```

`ProfilePolicy.resolveConstraints(intent, capabilities)` es puro, determinista y sin I/O, red o descargas. `preview(intent)` usa snapshot de capacidades y marca `stale`. En `start(intent)`, main obtiene primero un `InputSafetyAssessment`, resuelve constraints y congela `stageCandidatePolicies[]`: allowlist ordenada, fallback y restricciones por etapa, no reservas. Todo queda embebido antes de `planHash`. Cada etapa se rutea exactamente una vez al ejecutarse; material solo después del Geometry Gate/unload y con un `StageAdmissionReceipt` fresco. No puede salir de la policy congelada ni cambiar silenciosamente.

`DeliveryProfile` es el único enum de entrega para política, router y auditor. `archive` es una política de conservación; no un destino geométrico.

`workflow` es requerido si y solo si `sourceKind=generated`; con `sourceKind=imported` está prohibido y el plan usa exclusivamente el perfil de auditoría/importación, sin inferir un origen generativo.

Si `InputSafetyAssessment.decision=review`, `inputSafetyReviewDecisionDigest` deja de ser opcional y debe referenciar `allow_generation`; ausencia, mismatch, `reject` o `quarantine` bloquean antes de routing.

Main genera `operationId`; renderer no lo aporta. Backend recibe plan autenticado, no intención ni parámetros libres.

## 5. Matriz provisional de benchmark

Los valores son candidatos de calibración. Solo valores promovidos desde Benchmark Arena se convierten en preset estable.

### Texto→Imagen

| Perfil | Objetivo | Resolución/steps iniciales | Política |
|---|---|---|---|
| Velocidad | extremo rápido con calidad reconstruible | 1024²/8 como baseline comparable | candidato Pareto rápido; cero retry generativo |
| Balanceado | rodilla Pareto | 1024²/8 | mejor `downstreamMeshAccepted@1` por coste |
| Calidad | fidelidad downstream | 1024²/8; 12 solo sweep | candidato de calidad si mejora holdout |

La resolución no se reduce automáticamente para aparentar velocidad: primero debe demostrar que no degrada reconstrucción 3D.

### Texto→CSG IR

| Perfil | Modelo | Tokens | Reparaciones |
|---|---|---:|---:|
| Velocidad | promovido latency-first | hasta 4096/cap | 0 |
| Balanceado | promovido knee | hasta 4096/cap | 1 |
| Calidad | promovido quality-first | hasta 4096/cap | 2 máximo |

Safety caps de CSG IR, CPU, RSS, profundidad, nodos y output son idénticos en los tres perfiles. Reparación no agrega proveedores ni supera tres completions totales.

### Imagen→3D/PBR

| Perfil | Shape steps | Octree | Shape de trabajo | PBR |
|---|---:|---:|---:|---|
| Velocidad | 20 | 128 | 12K candidato | off; 1K solo override |
| Balanceado | 30 | 192 | 50K candidato | 1K si ready/admitido |
| Calidad | 50 | 256 | 100K candidato | 2K si ready/admitido |

Shape master y derivado de entrega son artefactos distintos. Paint puede remeshear un derivado sin destruir el master. `targetFaces` actual debe separarse en `workingDetailBudget` y `deliveryTargetFaces`.

Guidance permanece propiedad de categoría hasta que un benchmark demuestre relación causal con perfil. 4K queda laboratorio.

## 6. Selección de modelos

Precedencia:

1. Modelo manual compatible y admitido.
2. Modelo promovido para objetivo de perfil dentro del frente Pareto.
3. Baseline estable pinneado.
4. Fallback pinneado al inicio.

Modelo manual incompatible bloquea con causa; nunca se sustituye en silencio. `lab` requiere opt-in y no se convierte en default por novedad, descargas o nombre.

## 7. Admisión de memoria

```text
pinned/non-evictable
+ target stage
+ transientReserve_p95
<= effectiveCeiling_live
```

Reglas:

- una operación GPU pesada;
- reserva desconocida bloquea autoejecución;
- unload/pause requiere ack y memoria observada antes de siguiente stage;
- `quality` bloquea con diagnóstico si no cabe; no degrada silenciosamente;
- safety limits no cambian por perfil;
- `speed.cost <= balanced.cost <= quality.cost` para el mismo provider/capability snapshot.

## 8. Overrides avanzados

Overrides son tipados y por workflow. No existe objeto global compartido.

- editar un campo gobernado por calidad muestra `Balanceado · personalizado` o el perfil base correspondiente;
- cambiar perfil limpia overrides gobernados por calidad del workflow activo;
- cambiar categoría limpia overrides semánticos;
- cambiar destino limpia overrides de entrega incompatibles;
- `Restaurar Balanceado` elimina overrides del workflow activo;
- campos derivados (`steps`, `octree`, `targetFaces`, `textureSize`, `maxTokens`, budgets CSG) no cruzan IPC desde renderer.

No se creará DSL genérico de constraints. Mappings tipados y validadores explícitos por pipeline son suficientes.

## 9. UX y estados

Selector segmentado visible en cada workflow con `Balanceado` preseleccionado. Preview resume efectos reales:

```text
Balanceado
Hunyuan Shape · 30 steps · detalle 50K
PBR 1K · destino XREAL 50K final
Memoria estimada 12.4/16 GiB
```

Estados:

- `Estable`: plan íntegramente promovido.
- `Provisional`: contiene valor de benchmark no promovido.
- `Laboratorio`: provider experimental con opt-in.
- `Bloqueado`: capability, licencia, modelo o memoria insuficiente.
- `Personalizado`: override avanzado válido.

Cambios entre preview y start se presentan antes de consumir GPU. Durante ejecución, selector permanece editable pero indica `Se aplicará a la próxima generación`.

## 10. Persistencia

Manifest registra:

- `qualityProfileRequested`;
- `qualityProfileEffective`;
- `policyVersion` y `planHash`;
- snapshot seguro de parámetros efectivos;
- provenance/clamp por campo;
- modelo/proveedor final y digest;
- fallback/degradación;
- métricas por stage;
- `textureApplied` derivado del GLB final.

Historial antiguo conserva su snapshot. Cambiar policy v2 no reinterpreta resultados v1.

## 11. Errores

- `invalid_profile`: enum/case/Unicode desconocido; no coerción.
- `invalid_override`: campo o relación no permitida.
- `capability_changed`: preview stale; requiere confirmar plan nuevo.
- `memory_blocked`: cero workload iniciado.
- `manual_model_incompatible`: usuario decide otro modelo.
- `provider_not_promoted`: requiere modo laboratorio.
- `too_late_to_cancel`: plan ya en commit transaccional.

Los mensajes distinguen requested/effective/real. Paint fallido muestra `Calidad solicitada · shape-only`, nunca `texturizado`.

## 12. Tests y gates

### Unitarios

- tabla completa workflow × perfil × destino × categoría;
- determinismo y hash estable;
- precedencia y provenance por campo;
- monotonía de coste;
- invariantes PBR/formato;
- números no finitos, boundaries y combinaciones contradictorias;
- policy versioning e historial antiguo.

### Contrato

- preload rechaza enum inválido y campos derivados antes de IPC;
- main repite validación;
- backend acepta solo plan autenticado y hash coincidente;
- preview stale se vuelve a resolver;
- memoria insuficiente produce cero workload;
- fallback conserva snapshot y lease.

### UI

- default Balanceado en instalación limpia;
- cambio mid-operation no altera manifest activo;
- advanced produce etiqueta personalizada;
- clamps/warnings/blockers accesibles;
- teclado, foco y lectores de pantalla;
- historial muestra plan original.

### Gate de promoción

Ningún mapping pasa a `stable` sin reporte Benchmark Arena, model manifest pinneado, licencia revisada y 20 ejecuciones consecutivas sin OOM. Balanceado selecciona rodilla Pareto; Speed/Quality seleccionan extremos solo dentro de tolerancias de no-regresión aprobadas.

## 13. Criterios de aceptación

1. Default efectivo es `balanced` en los tres workflows.
2. Renderer solo envía intención validada.
3. Plan se congela por `operationId` y coincide en main, backend, manifest y resultado.
4. Ningún perfil excede destino XR o safety caps.
5. `quality` bloqueado no inicia GPU ni degrada silenciosamente.
6. Profile change durante ejecución afecta solo siguiente operación.
7. Historial conserva requested/effective/real y policy version.
8. Matriz de bypass end-to-end termina sin parámetros fuera de policy.
9. Tests, build y navegador terminan con evidencia fresca.

## 14. Riesgos residuales

- Valores provisionales pueden no ocupar el frente Pareto en este M5 Pro; Benchmark Arena decide.
- Preview puede quedar stale entre polling y start; re-resolución y confirmación material lo cubren.
- Multiplicar categoría × destino × perfil puede explotar estados; separación de propiedad evita presets cartesianos.
- Backends comunitarios pueden reportar capacidades erróneas; contract smoke y manifest pinneado prevalecen.
