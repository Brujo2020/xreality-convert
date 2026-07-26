# Requirements — Xreality TruthLoop 3D

Status: Proposed | Language: es | Date: 2026-07-24

## Goal

Producir activos 3D locales, editables y verificables que preserven la identidad
observada, distingan regiones inferidas y se entreguen para un destino concreto.

## Requirements

1. **Views** — Cuando el usuario aporte una imagen, el sistema deberá registrar
   dirección, máscara, calidad, procedencia y si es observada o generada.
2. **Coverage** — Cuando falte cobertura, deberá visualizar incertidumbre y
   recomendar la vista con mayor ganancia esperada.
3. **Observed truth** — Mientras un texel esté respaldado por una referencia
   válida, ninguna inferencia deberá reemplazarlo sin aprobación.
4. **Materials** — Cuando genere apariencia, deberá producir base color de-lit y
   PBR por región material.
5. **Contradictions** — Si dos vistas se contradicen, deberá marcar la región y
   bloquear aprobación automática.
6. **Parts** — Cuando detecte componentes, deberá conservar IDs estables,
   jerarquía, nombre, transform y material.
7. **Locks** — Cuando una región esté bloqueada, una edición no deberá alterarla
   por encima de la tolerancia configurada.
8. **Regional editing** — Cuando el usuario pinte una máscara, deberá regenerar
   únicamente esa región y los márgenes necesarios para seams.
9. **TruthLoop** — Después de cada etapa generativa, deberá renderizar vistas
   deterministas y emitir scores y heatmaps.
10. **Recovery** — Cuando falle un gate, deberá conservar el último artefacto
    aprobado y recomendar una corrección concreta.
11. **Delivery profiles** — Para WebXR, Quest, PC VR, impresión o hero asset,
    deberá derivar topología, LOD, texturas, collider, unidades y formatos.
12. **Backend routing** — Cuando existan varios backends, deberá elegir mediante
    política observable basada en categoría, hardware y benchmark.
13. **Rigging** — Para activos articulados, deberá ejecutar prer rig check antes
    de generar skeleton y weights.
14. **Lineage** — Toda generación o edición deberá registrar seed, backend,
    versión del modelo, parámetros, inputs y parentesco.
15. **Evidence** — Toda exportación aprobada deberá incluir un Evidence Pack
    reproducible.

## Non-goals de la primera entrega

- Entrenar un foundation model propio de miles de millones de parámetros.
- Reconstrucción CAD exacta desde una sola foto.
- Escenas completas o world generation.
- Rigging antes de estabilizar partes y topología.

## Success

- Golden set mínimo de 60 activos.
- Reducción ≥50% de fallos visibles de textura frente al baseline actual.
- Cambios fuera de máscara <1% en edición regional.
- Cada exportación incluye turntable, heatmaps, métricas y lineage.
