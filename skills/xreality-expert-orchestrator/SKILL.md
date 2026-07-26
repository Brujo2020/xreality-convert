---
name: xreality-expert-orchestrator
description: Orquesta expertos locales de Xreality sin repetir trabajo validado. Usar ante problemas de textura PBR o UV, rendimiento MLX, geometría o LOD, auditoría visual/runtime, o pedidos de expertos, superagentes, paralelización y simplificación.
---

# Xreality Expert Orchestrator

Aplicar siempre:

`CLASSIFY → EVIDENCE → ROUTE → EXECUTE → VERIFY → MERGE`

## Evidencia primero

1. Leer `LEARNED.md`.
2. Localizar el job, reporte, JSONL, benchmark y test más recientes.
3. Reutilizar resultados cuyo artefacto, configuración y código sigan vigentes.
4. Repetir solo verificaciones afectadas por el diff.
5. No declarar calidad visual usando únicamente estructura GLB o metadatos.

## Expertos

| Experto | Responsabilidad exclusiva | Evidencia mínima |
|---|---|---|
| Textura/PBR | Proyección, UV, Paint, materiales y fidelidad | atlas, GLB embebido y render visible |
| Rendimiento MLX | Perfil, batching, memoria y tiempos | baseline A/B, paridad y pico de memoria |
| Geometría/LOD | Silueta, topología, simplificación y entrega | métricas de malla y vistas canónicas |
| Auditor runtime-visual | Electron, backend, visor y artefacto final | ejecución local y captura/render |

No crear otro experto si una responsabilidad ya tiene dueño y gate independiente.

## Delegación

- Delegar solo dominios independientes.
- Asignar un único dueño por archivo.
- Mantener especialistas read-only por defecto.
- Usar un solo integrador para aplicar cambios.
- Serializar propuestas que toquen el mismo estado o GPU.
- No ejecutar Shape y Paint simultáneamente en memoria unificada.

Cada experto debe devolver:

```text
evidence:
root_cause:
minimal_change:
verify:
risks:
assumptions:
```

## Gates

- Estructural: archivos, UV, mapas, topología y firmas válidas.
- Runtime: app, backend, cola, cancelación y recuperación reales.
- Visual: textura visible, identidad, cobertura, seams y vistas canónicas.
- Rendimiento: comparación antes/después con la misma entrada y seed.

Un poll repetido o atrasado no invalida evidencia posterior. Una misión solo termina cuando el último gate aporta evidencia explícita.

Registrar en `LEARNED.md` únicamente causas nuevas, supuestos rotos o regresiones verificadas.
