# Matriz de capacidades

La descripción operativa y los límites actuales están en [ULTRA_ENGINE.md](./ULTRA_ENGINE.md).

| Capacidad | Estado | Evidencia |
|---|---|---|
| Imagen → malla MLX | Implementada | `engine/server.py`, tests del contrato `ShapePipeline` |
| Hunyuan Paint 6 vistas | Implementada | `engine/paint_service.py`, perfil 1K/2K |
| GLB PBR embebido | Implementada | `engine/pbr_glb.py`, gate estructural |
| Fidelidad frontal | Implementada | correlación espacial y silueta, fail-closed |
| Cuartos sin pérdida de pintura | Implementada | gate de continuidad izquierda/derecha |
| Validación posterior a decimación | Implementada | quality gate sobre la malla entregada |
| Texto → 3D paramétrico | Implementada por Ollama/JSCAD | flujo Electron; no usa Hunyuan multi-vista |
| Texto → multi-vista Hunyuan | No implementada | no se publica endpoint ni placeholder |
| USDZ, rigging, animación | No implementada | fuera del alcance actual |

Los tiempos dependen del chip, memoria, perfil y corpus. No se declara una
aceleración porcentual sin un benchmark A/B reproducible sobre el mismo equipo.
