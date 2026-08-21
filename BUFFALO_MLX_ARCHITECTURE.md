# Buffalo Strategic MLX 2.0

> Arquitectura objetivo para Xreality Convert. Local-first, Apple-Silicon-first,
> medible, reanudable y fail-closed. Este documento reemplaza el plan 1.0; no
> afirma que las capacidades objetivo ya estén implementadas.

## 0. Decisión ejecutiva

Buffalo 2.0 no será «otro modelo» ni una colección indiscriminada de skills.
Será un **compilador de activos 3D dirigido por evidencia**:

1. sella intención, evidencia y restricciones;
2. construye contratos de partes, geometría y materiales;
3. ejecuta una sola etapa pesada por vez;
4. rechaza temprano, reintenta solo la etapa culpable y conserva el último
   artefacto aceptado;
5. deriva entregables desde un maestro inmutable;
6. permite challengers web únicamente con opt-in, presupuesto y comparación
   ciega contra el resultado local.

La ventaja defendible no será una captura bonita. Será el corpus versionado,
la política determinista, la telemetría por Mac y la capacidad de explicar por
qué un activo se aprobó, se degradó o se rechazó.

## 1. Principios no negociables

- **Local por defecto:** red desactivada durante una ejecución normal. Modelos,
  revisiones y hashes se fijan en un registro local.
- **Evidencia antes que imaginación:** una región oculta queda `not_measured`.
  Una vista sintética es hipótesis, nunca prueba.
- **Una sola verdad de promoción:** `pass | reject | attention | not_measured`.
  No hay promedio que oculte un fallo crítico.
- **Una sola etapa Metal pesada:** Shape y Paint jamás coexisten en memoria.
- **Maestro inmutable:** LOD, low-poly, USDZ y variantes web son derivados
  transaccionales; nunca reemplazan el maestro aceptado.
- **Cambios quirúrgicos:** reintentar la fase fallida, no regenerar todo.
- **Simplicidad Karpathy:** supuestos explícitos, mínimo mecanismo necesario,
  cambios trazables a un objetivo y éxito definido por pruebas.
- **Privacidad y coste como gates:** ninguna imagen sale del equipo ni se gasta
  un crédito sin consentimiento explícito.

## 2. Contrato sellado del trabajo

Cada job genera `job-contract.json`, inmutable y con SHA-256:

| Contrato | Campos mínimos | Gate de admisión |
|---|---|---|
| intención | `preview/mobile/xr/hifi/master`, runtime, presupuesto de caras/textura/tiempo | destino y tolerancias definidos |
| evidencia | vistas reales, EXIF, máscara, escala, licencia, privacidad | cobertura suficiente para el nivel solicitado |
| semántica | categoría, inventario de partes, cardinalidad, piezas críticas/delgadas | sin contradicciones no resueltas |
| geometría | escala, componentes, watertight por categoría, degenerados, winding | umbrales por arquetipo |
| materiales | regiones, mapas, extensiones glTF, rango físico, evidencia por texel | ninguna región relevante colapsada |
| ejecución | chip, RAM, presión, swap, revisiones, semilla, perfil | preflight admite cada etapa |
| economía | local/web, proveedor permitido, límite USD/créditos/reintentos | coste máximo firmado por usuario |

`synthetic`, `inferred` y `measured` son etiquetas distintas y persistentes.
Una corrección humana produce una nueva revisión del contrato, nunca una
mutación silenciosa.

## 3. Grafo de ejecución 2.0

```text
P0 intake/evidence
  -> P1 reference lab (CPU/ANE si está validado)
  -> P2 semantic + material contract
  -> P3 Shape MLX [Metal exclusivo]
  -> checkpoint + descarga total + gate geométrico
  -> P4 reparación/retopo/UV determinista
  -> checkpoint + gate de preservación
  -> P5 Paint MLX [Metal exclusivo]
  -> checkpoint + descarga total
  -> P6 PBR por regiones + bake
  -> P7 gates estructurales + renders canónicos + revisión humana
  -> P8 derivados GLB/LOD/USDZ/Web
  -> P9 manifiesto, hashes y aprendizaje de arena
```

Cada fase recibe artefactos sellados y emite un `stage-result.json`. Estados:
`pending`, `admitted`, `running`, `passed`, `rejected`, `cancelled`. La
reanudación parte del último checkpoint cuyo input hash coincida.

### Política de recuperación

| Fallo | Acción mínima segura |
|---|---|
| referencia ambigua | pedir otra vista o degradar honestamente a `preview` |
| OOM/presión | abortar subprocess, liberar caché, conservar checkpoint; no cambiar backend en secreto |
| parte crítica ausente | segundo seed secuencial o corrección localizada; máximo configurable |
| decimación destructiva | descartar candidato y conservar maestro |
| textura/seam | reejecutar Paint/PBR, no Shape |
| material incoherente | rehacer solo región y mapas sincronizados |
| export inválido | corregir empaquetado; no regenerar contenido |

## 4. Scheduler Apple Silicon

### Admisión dinámica, no promesas por marketing

El primer arranque ejecuta un calibration pack y guarda percentiles por
`chip + RAM + versión macOS + versión MLX + backend/revisión`. La admisión usa:

```text
available = physical_free + purgeable - os_reserve
required  = p95_peak(stage, profile) * 1.15 + assembly_headroom
admit iff available >= required
         and memory_pressure == normal
         and projected_swap_growth <= policy_limit
```

Sin una muestra válida, el perfil queda `unmeasured` y usa el nivel conservador.
El watchdog mide RSS, memoria activa MLX, presión y delta de swap; termina el
subprocess antes de comprometer la sesión. Los números de 16/24/32/64 GB son
clases de calibración, no garantías codificadas.

### Ciclo de vida por fase

1. cargar únicamente skill, código y pesos de la fase;
2. ejecutar con semilla y configuración selladas;
3. materializar artefactos y métricas;
4. eliminar referencias del modelo, `gc.collect()`, `mx.clear_cache()` y
   verificar descenso real;
5. si no libera bajo el umbral, reciclar el subprocess;
6. cargar la siguiente fase.

Preparación y validaciones CPU pueden paralelizarse con un pool acotado a
`min(performance_cores - 1, 4)`. Seeds, Shape, Paint y challengers se ejecutan
secuencialmente para mantener comparabilidad y estabilidad.

## 5. Superpowers temporales ad hoc

Se implementa una sola skill-router local en
`.codex/skills/xreality-buffalo-superpowers/`. Su `SKILL.md` es corto; los
detalles viven en referencias cargadas solo para la fase activa.

| Superpower | Fases | Mezcla útil | Artefacto y condición de descarga |
|---|---:|---|---|
| Evidence Surgeon | P0-P2 | principios Karpathy + 3D spatial | contrato y mapa de incertidumbre; descargar antes de Shape |
| Shape & Assembly TD | P3-P4 | 3d-modeling + pipeline Hunyuan + Blender headless | maestro/gates; descargar antes de Paint |
| PBR Material Surgeon | P5-P6 | 3d-modeling + Substance concepts, sin depender de Substance | mapas regionales/bake; descargar antes de QA |
| Production Gatekeeper | P7 | Blender expert + glTF Validator + renders canónicos | matriz de gates y revisión nominada |
| Delivery Optimizer | P8 | web3d/lightweight/game-assets | LOD/GLB/USDZ con presupuestos por runtime |
| Cloud Challenger | excepcional | Meshy/Rodin/Tripo adapters | resultado aislado, coste y licencia; purgar credenciales/contexto al cerrar |

Las skills son procedimiento, no procesos residentes. “Liberar memoria” exige
cerrar modelos, escenas temporales, imágenes de alta resolución y subprocesses;
quitar texto del contexto por sí solo no libera memoria Metal.

## 6. Veredicto sobre las skills investigadas

| Fuente | Decisión | Valor que sí se incorpora | Riesgo/dependencia |
|---|---|---|---|
| Karpathy guidelines | **adoptar núcleo** | supuestos explícitos, simplicidad, cambios quirúrgicos, criterios verificables | guía de ingeniería, no capacidad 3D |
| `omer-metin/3d-modeling` | **extraer selectivamente** | topología, UV, edge flow, producción | persona extensa; solapa con Art Director |
| `3d-spatial` | **extraer conceptos** | coordenadas, cámara, jerarquía, escala | orientada a spatial/animation, no genera assets |
| `image-to-3d-pipeline` | **referencia, no instalar** | preparación → Hunyuan → rig → web | promesa de “30 min/production” no sustituye gates; Mixamo añade SaaS |
| Rodin skill oficial | **adapter opt-in** | multi-image/high-poly/quad challenger | API; acceso completo desde Business, coste recurrente |
| Meshy skills (oficial y community) | **solo oficial, opt-in** | remesh/rig/animate/printing y challenger | API key + plan; duplicados community aumentan riesgo |
| `alphaonedev/3d-modeling` | **no incorporar sin auditoría de fuente** | potencial routing genérico | procedencia/valor diferencial insuficientes |
| web3d integration patterns | **incorporar en P8** | Three.js/R3F, Draco/KTX2, budgets, fallback | no mejora Shape/PBR maestro |
| dos `3d-web-experience` | **deduplicar** | selección de stack y performance web | contenido sustancialmente solapado |
| lightweight 3D effects | **fuera del core** | UI decorativa de bajo coste | no pertenece al compilador de activos |
| Substance 3D texturing | **conceptos, no dependencia** | capas/máscaras/bake PBR | Adobe/Substance opcional y propietario |
| game-3d-assets | **incorporar contrato de entrega** | pivote, escala, LOD, colisión, naming | no usar heurísticas de juego para un maestro hi-fi |

Regla de suministro: no ejecutar scripts de terceros por haber pasado una
auditoría de catálogo. Fijar commit, revisar `SKILL.md` y scripts, registrar
licencia y copiar únicamente conocimiento necesario y atribuible.

## 7. Blender como laboratorio determinista

Blender headless es herramienta local de reparación, baking y evidencia, no un
certificador artístico. Cada operación usa un `.blend` temporal y un script
versionado:

- import/export round-trip GLB;
- normales, non-manifold, loose geometry, degenerados y escala;
- UV overlap/stretch/gutters y densidad por región;
- retopo/decimate con bordes, UV y materiales protegidos;
- bake del maestro al derivado;
- renders canónicos: unlit, front/quarters, grazing, checker alpha/transmission;
- pruebas de animación, pivote, suelo, colisión y LOD cuando correspondan.

No aplicar “merge by distance”, remesh, triangulación o eliminación de piezas
globalmente. Toda reparación es un candidato reversible y debe superar la
huella pre/post.

## 8. Gates de promoción 2.0

```text
deliverable = input ∧ geometry ∧ parts ∧ topology ∧ UV ∧ texture
              ∧ material ∧ memory ∧ packaging ∧ target_runtime
master      = deliverable ∧ sufficient_real_evidence ∧ canonical_renders
              ∧ named_human_review
```

Métricas mínimas:

- geometría: finitud, degenerados, winding, componentes, silueta multivista,
  Hausdorff/screen error, escala y supervivencia de piezas delgadas;
- semántica: inventario y cardinalidad por categoría; `not_measured` bloquea
  `master` cuando afecta una parte crítica;
- UV: finitud, solapamiento intencional, stretch, seams, gutters/mips y texel
  density física;
- textura: alineación por vista, seam score, texto/logo, ausencia de iluminación
  horneada y cobertura de texeles;
- material: mapas sincronizados por región, rangos dieléctrico/metal, extensiones
  glTF y respuesta coherente bajo relighting;
- paquete: texturas embebidas/intencionalmente empaquetadas, glTF Validator,
  Blender/Three.js/macOS; `usdchecker --arkit --strict` para USDZ;
- operación: p50/p95 de tiempo, pico, swap, reintentos y coste.

Los umbrales se fijan por corpus y perfil, nunca se inventan como universal.
Automatización puede rechazar; solo el gate humano puede coronar un maestro.

## 9. Router local → web, siempre opt-in

### Escalera de decisión

1. local champion, un seed;
2. reparación local de la fase culpable;
3. segundo seed local si el perfil es `master` y el fallo es estocástico;
4. pedir mejor evidencia si el problema es informacional;
5. ofrecer challenger web solo si el valor esperado supera privacidad + coste;
6. importar como candidato no confiable y ejecutar exactamente los mismos gates.

No enviar a la web por OOM si un perfil local menor satisface el contrato. No
enviar propiedad intelectual, personas o ubicaciones sensibles sin confirmación.

### Coste observado al 8 de agosto de 2026

Los precios cambian: consultarlos de nuevo antes de comprar y mostrar un
estimado máximo antes de cada ejecución.

| Opción | Señal de precio oficial | Uso recomendado |
|---|---|---|
| Local Hunyuan3D 2.1 MLX | sin coste por llamada; hardware/energía local | default y corpus de mejora |
| Tripo API | USD 1 = 100 créditos; H2/H3 image→model 20 sin textura/30 con; P1 40/50; 300 créditos iniciales por 2 semanas | challenger barato puntual (~USD 0.20-0.50 base por generación, extras aparte) |
| Meshy API | Meshy 6 image→3D 20 sin textura/30 con; la API requiere plan/API key y el valor USD por crédito depende del plan | rig/animate/remesh o challenger cuando el usuario ya tenga plan |
| Rodin/Hyper3D | Free USD 0 con pago por resultado; Creator USD 30/mes sin API completa; Business USD 120/mes con API | hi-fi/quad/multi-image excepcional; no conviene para llamadas esporádicas vía API |

Todo adapter debe soportar `estimate → consent → submit → poll → download →
verify → reconcile`. Guardar `provider`, versión, parámetros, créditos estimados
y reales, licencia, latencia, hashes y resultado del gate. Desactivar auto-refill.

## 10. Arena y bucle de mejora

El corpus mínimo cubre orgánico, persona, producto, vehículo, maquinaria con
piezas delgadas, arquitectura abierta, vidrio, metal pintado y textil. Cada
cambio corre A/B sellado contra el mismo corpus y revisiones fijadas.

Promover un challenger solo si:

- no introduce regresión en ningún gate crítico;
- mejora al menos una métrica objetivo predeclarada;
- el beneficio supera ruido entre seeds en dos ejecuciones secuenciales;
- publica tiempo, pico, swap, artefactos y coste;
- pasa revisión visual ciega y queda documentada la licencia.

El registro mantiene `champion`, `challenger`, `research-only`, `quarantined` y
`retired`. Capturas, estrellas o claims del proveedor no cuentan como evidencia.

### Radar técnico al 8 de agosto de 2026

La popularidad de Hugging Face sirve para descubrir candidatos, no para
ordenarlos por calidad. El catálogo muestra a TRELLIS/TRELLIS.2 entre los más
descargados, junto con Hunyuan3D, TripoSR, InstantMesh y Stable Fast 3D; las
comparaciones del propio fabricante tampoco se consideran evaluación neutral.

| Candidato | Estado recomendado | Por qué importa | Prueba antes de promover |
|---|---|---|---|
| Hunyuan3D 2.1 MLX (`dgrauet`) | **champion actual condicionado a arena local** | Shape + Paint PBR ya integrables nativamente; pesos MLX y cuantización 8-bit | mantener corpus y revisión fijados; medir Paint real por clase de RAM |
| TRELLIS.2 upstream + PR Apple #175 | **challenger P0** | pipeline 512/1024, PBR, hashes y fallbacks Metal; MLX end-to-end aún experimental y aceptación actual MPS | pin del PR/fork, build reproducible, p95 RAM/swap, estructura, UV/PBR y fragmentación en el mismo corpus |
| `trellis2-apple` | **research-only acelerado** | backend MLX y postproceso Metal prometedores | no reutilizar tiempos H100; reproducir en Macs objetivo y revisar divergencia respecto de upstream |
| Pixal3D (SIGGRAPH 2026) | **challenger P1 cuando haya inferencia/pesos consumibles** | back-projection pixel→3D y salida PBR apuntan a fidelidad de referencia | confirmar licencia, checkpoints completos, inferencia local y port de una etapa aislada |
| ReLi3D | **challenger multivista/PBR** | reconstrucción con cámaras conocidas, UV, roughness/metalness e iluminación separada | calibración de poses, licencia comercial (enterprise desde USD 1M de revenue) y port/benchmark local |
| Step1X-3D | **baseline CUDA/research** | geometría/textura controlable y licencia Apache-2.0 | no portar pipeline completo: aislar técnica que venza un gate; medir coste del port MLX |
| Home3D 1.0 | **research de arquitectura/interiores** | SDF watertight, partes editables, segmentación/voting UV y biblioteca PBR | esperar código/pesos/licencia verificables; probar solo corpus interior/mobiliario |
| Stable Fast 3D / TripoSR / Hunyuan3D-mini | **fast baselines** | latencia y footprint bajos para preview | nunca promover a master por velocidad; medir thin-parts, PBR y error contra champion |
| Apple SHARP / DA3 / VGGT / MASt3R | **evidence helpers, no sustitutos automáticos** | profundidad/pose/estructura multivista pueden mejorar contrato y QA | validar escala, poses y confianza; no confundir reconstrucción/splat/depth con GLB productivo |

Señales comunitarias de Reddit reportan dos fallos recurrentes que el corpus
debe convertir en tests: TRELLIS.2 puede producir geometría tipo “vasija” poco
apta para impresión y la identidad facial desde una sola imagen sigue siendo
inestable. Son hipótesis útiles, no veredictos: añadir cortes de interior,
manifold/volumen, likeness multivista y pruebas separadas de cabeza/cuerpo.

### Embudo de investigación

1. **Descubrir:** GitHub/Hugging Face/papers/foros.
2. **Trust gate:** autor oficial, licencia de código/pesos/output, commit, scripts,
   telemetría y vulnerabilidades; cuarentena por defecto.
3. **Feasibility gate:** dependencias CUDA, ops sin Metal, RAM teórica y formato
   de salida. Rechazar temprano un port total si basta portar una técnica.
4. **Smoke gate:** un activo difícil, artefactos reproducibles y memoria segura.
5. **Arena:** corpus sellado, dos seeds secuenciales y mismos gates.
6. **Shadow:** genera candidatos sin exposición en UI ni reemplazo del campeón.
7. **Promoción/retirada:** decisión versionada, reversible y basada en evidencia.

## 11. Roadmap de implementación

### R0 — especificación y verdad (1 semana)

- versionar schemas de job/stage/evidence/economy;
- separar claramente `implemented`, `target` y `research` en UI/reportes;
- añadir estado `attention/not_measured` a promoción;
- verificar: contract tests y migración de reportes v1.

### R1 — resiliencia y memoria (1–2 semanas)

- aislar Shape/Paint/Blender en subprocesses reanudables;
- calibration pack, watchdog y checkpoints con hash;
- fault injection: OOM, cancelación, archivo corrupto y reinicio;
- verificar: cero job falso-positivo y reanudación desde última fase aceptada.

### R2 — Blender + gates (2 semanas)

- scripts headless de round-trip, UV, bake y renders canónicos;
- glTF Validator y matriz por primitive/material;
- golden corpus pequeño con defectos deliberados;
- verificar: cada defecto crítico es rechazado por el carril correcto.

### R3 — semántica y PBR regional (2–4 semanas)

- evidencia por parte/texel y material region masks;
- mapas baseColor/MR/normal/confidence sincronizados;
- corrección localizada y comparación de dos seeds para master;
- verificar: no mejora 2D a costa de incoherencia física.

En paralelo, ejecutar spikes pequeños y descartables: técnicas de ReLi3D para
separar iluminación, Pixal3D para correspondencia y Home3D para voting de
regiones. Ningún spike entra al runtime hasta vencer un gate predeclarado.

### R4 — derivados y runtime (1–2 semanas)

- LOD transaccional, rebake, Draco/Meshopt/KTX2 según target;
- perfiles mobile/XR/web/USDZ y presupuestos de pantalla;
- verificar en Blender, Three.js y macOS/RealityKit reales.

### R5 — web challenger (después de estabilizar R0–R4)

- comenzar con Tripo por coste transparente; luego Meshy si aporta rig/animate;
- Rodin solo con caso hi-fi y volumen que justifique Business;
- dashboard de coste/calidad y kill-switch global de red;
- verificar: ninguna llamada sin opt-in y conciliación exacta de créditos.

### R6 — arena Apple de siguiente generación (iniciar investigación en R1)

- sellar un commit del PR Apple de TRELLIS.2 y del fork MLX;
- ejecutar 512 primero, sin cascada ni 4K, en máquinas 16/24/32/64 GB;
- comparar Hunyuan MLX vs TRELLIS.2 en geometría, PBR, tiempo, pico y swap;
- probar explícitamente interiores huecos, partes delgadas e identidad humana;
- promover únicamente por la matriz completa; mantener Hunyuan como fallback
  reproducible hasta que el challenger gane sin regresiones críticas.

## 12. Definition of Done 2.0

Buffalo 2.0 está listo cuando 30 jobs mixtos consecutivos:

- producen contratos y manifiestos reproducibles;
- no solapan consumidores Metal pesados;
- reanudan tras fallo sin repetir etapas aceptadas;
- no promueven `not_measured` como `pass`;
- preservan maestro y partes críticas en todos los derivados;
- validan paquete y runtime objetivo;
- reportan p50/p95, pico/swap y coste real;
- requieren revisión humana nominada para `master`;
- ejecutan con red bloqueada salvo un challenger consentido y presupuestado.

## Referencias primarias y auditadas

- [Hunyuan3D-Buffalo 1.0](https://arxiv.org/abs/2608.02711)
- [Karpathy-inspired guidelines](https://github.com/multica-ai/andrej-karpathy-skills)
- [Meshy agent skill oficial](https://github.com/meshy-dev/meshy-3d-agent) y [precios](https://docs.meshy.ai/en/webapp/pricing)
- [Rodin skill oficial](https://github.com/DeemosTech/rodin3d-skills) y [precios Hyper3D](https://hyper3d.ai/pricing?lang=en)
- [Tripo API pricing](https://platform.tripo3d.ai/docs/billing)
- [3D modeling](https://www.skills.sh/omer-metin/skills-for-antigravity/3d-modeling)
- [Image-to-3D pipeline](https://www.skills.sh/guia-matthieu/clawfu-skills/image-to-3d-pipeline)
- [3D web experience](https://github.com/davila7/claude-code-templates/blob/main/cli-tool/components/skills/creative-design/3d-web-experience/SKILL.md)
- [Claude Design Skillstack](https://github.com/freshtechbro/claudedesignskills)
- [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html), [glTF Validator](https://github.com/KhronosGroup/glTF-Validator), [USD Preview Surface](https://openusd.org/dev/spec_usdpreviewsurface.html)
- [Hugging Face Image-to-3D catalog](https://huggingface.co/models?pipeline_tag=image-to-3d), [3DGen Leaderboard](https://huggingface.co/spaces/3DTopia/3DGen-Leaderboard)
- [TRELLIS.2](https://github.com/microsoft/TRELLIS.2), [Apple Silicon PR #175](https://github.com/microsoft/TRELLIS.2/pull/175), [fork MLX/Metal](https://github.com/pedronaugusto/trellis2-apple)
- [Pixal3D](https://huggingface.co/TencentARC/Pixal3D), [ReLi3D](https://huggingface.co/StabilityLabs/ReLi3D), [Step1X-3D](https://github.com/stepfun-ai/Step1X-3D)
- [Home3D 1.0](https://arxiv.org/abs/2606.27923), [MaterialMVP](https://arxiv.org/abs/2503.10289), [MeshGen](https://arxiv.org/abs/2505.04656)
- Señales comunitarias (no primarias): [local/printable stack](https://www.reddit.com/r/StableDiffusion/comments/1v78pgm/best_fully_opensourcelocal_workflow_for_2d_to_3d/), [Apple MLX reports](https://www.reddit.com/r/LocalLLaMA/comments/1uuga40/local_image_to_3d_2gb_ram_20s_apple_silicon_iphone/), [single-view human limitations](https://www.reddit.com/r/StableDiffusion/comments/1utwe4j/image_to_3d_model/)
