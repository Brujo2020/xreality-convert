# Xreality Model Arena v1

Una comparación sólo cuenta si usa la misma entrada, seed, presupuesto y validadores. `preflight` falla cerrado ante pesos/código flotantes; `audit` separa estructura GLB/PBR de calidad visual.

## Estado de la primera batalla (M5 Pro, 24 GB)

| Candidato | Shape | Paint/PBR | Estado honesto |
|---|---:|---:|---|
| dgrauet Hunyuan3D 2.1 MLX | PASS operativo: 10 pasos, octree 128, 93.8 s, 179,368 caras | PASS estructural / REJECT visual: 1K, 6 vistas, 15 pasos, 248.3 s, MLX peak 15.17 GB | líder Shape provisional; textura sin corona |
| AgenticVibes Hunyuan Paint | N/A | E2E PASS estructural; 4 pasos/6 vistas: 117.1 s difusión + 7.1 s bake; correlación 0.8101 | líder visual; tras liberar UNet+DINO bajó a 23.45 GB, pero el watchdog lo bloquea cuando no hay presión/swap seguros |
| mirwox Hunyuan 2.1 MLX | bloqueado | bloqueado | repo HF inaccesible/eliminado/privado |
| pedronaugusto TRELLIS.2 Apple | PASS smoke: 512, 4 pasos, 60.4 s, 3.44 M caras decodificadas | GLB/PBR estructural PASS / visual REJECT: UV, 2 texturas 1K, 30.0 s | Metal E2E real; 13.99 GB MLX peak, 0 swap; 34,082 componentes y fragmentos flotantes impiden promoción |
| xocialize TRELLIS.2 MLX Swift | build release PASS | gates offline PASS; E2E no ejecutable | res512 declara 18 GB resident + 18 GB activación: no admite este Mac 24 GB; pesos gated |
| MV-Adapter SD2.1 | N/A | candidato moderno: adapter 708 MB y upstream declara <10 GB | el texturizador oficial es CUDA-only; portar sólo multivista y reutilizar nuestro bake Metal + reference lock |
| Kimi K3 | N/A | N/A | juez/agente remoto opcional; no genera 3D y ocupa ~1.6 TB |

AgenticVibes ya completó el mismo zorro/mesh que dgrauet. Conserva rostro, flores, patas y cola mucho mejor y es el **líder de calidad de textura**, pero no puede promoverse en el M5 Pro de 24 GB: mezcla UNet MLX con DINO/encoders/VAE/bake en PyTorch MPS, alcanzó 28.98 GB de footprint y añadió 11.32 GB de swap con sólo cuatro pasos. dgrauet mantiene el liderazgo **operativo de modelado**. TRELLIS completa Imagen→Mesh→UV→PBR→GLB por MLX/Metal, pero queda rechazado por fragmentos, agujeros y 34,082 componentes.

La mejor combinación medida es `multivista generativa + reference lock`: Agentic completa las caras ocultas y la foto original se reproyecta sólo en texels frontalmente observables. Con `min-facing=0.05`, la similitud de color subió a 0.9467, el error localizado bajó a 0.0463 y los seams severos quedaron en 0.015; el gate alineado pasó sin síntesis adicional. La geometría se puntúa por separado: el mesh común obtuvo IoU 0.7823 y no pasa el umbral nativo estricto 0.80.

El fork local endurecido libera el UNet PyTorch duplicado y DINOv2 después de extraer su embedding. La E2E de cuatro pasos produjo el GLB exacto de baseline (mismo SHA-256) mientras bajó RSS pico de 12.63 a 7.26 GB y footprint pico de 28.98 a 23.45 GB. Todavía falta repetir tras reinicio/estado limpio: el sistema conservaba presión de swap de las pruebas anteriores, por lo que Agentic queda disponible como modo explícito `máxima fidelidad`, no como default.

## Mundial por categoría · marcador honesto

China local juega de local: los contendores Hunyuan tienen compatibilidad y pesos disponibles, pero la localía no sustituye los gates. Esta tabla distingue ganadores medidos de rutas provisionales que aún necesitan corpus específico.

| Categoría | Campeón/ruta actual | Corona | Motivo |
|---|---|---|---|
| Shape general | dgrauet Hunyuan3D 2.1 MLX | provisional medida | único líder operativo con Shape MLX reproducible; falta ganar silueta ≥0.80 en el corpus completo |
| Textura visual | AgenticVibes + reference lock | líder de calidad, no operativo global | 0.8101 de correlación espacial y mejor detalle; memoria de 24 GB y silueta global todavía impiden coronarlo |
| Low-poly/móvil | dgrauet Shape + fast Paint | campeón operativo | entra en memoria, permite master→LOD y 1K; sigue obligado a gates visuales/materiales |
| Humano | dgrauet Shape + Agentic Paint | ruta provisional | Agentic es la mejor apuesta para rostro/piel/ropa; sin normal y multivista real no existe campeón premium |
| Animal | dgrauet Shape + Agentic Paint | ruta provisional con evidencia parcial | el zorro favorece claramente Agentic en marcas y detalle; anatomía/especies aún no tienen corpus suficiente |
| Producto simple | dgrauet Shape + fast Paint | ruta operativa provisional | mejor costo/memoria; vidrio, etiquetas o coating complejos promueven a Agentic |
| Industrial/construcción | dgrauet Shape preservando ensamblaje + Agentic Paint | sin campeón | faltan pruebas de bordes, planos, agujeros y piezas; el director ya impide borrar componentes por ser pequeños |
| Auto/grúa | dgrauet Shape por ensamblaje + Agentic Paint | sin campeón | una foto no prueba ruedas/piezas ocultas; exige multivista, inventario y materiales por región |
| Bodega/arquitectura | reconstrucción modular/multivista; Hunyuan sólo como challenger | sin campeón | single-image no demuestra planta, vanos ni dimensiones ocultas |
| Vidrio/piel/pelo/tela/porcelana | ningún generador actual | sin corona | baseColor+MR no basta; el contrato exige extensiones y marca normal/AO faltantes, y `maxquality` falla cerrado |

El campeón compuesto actual es: **dgrauet para Shape → gate geométrico → liberar memoria → Agentic para Paint cuando el watchdog lo admite → reference lock 0.80 → contrato PBR por material**. En 24 GB bajo presión, gana la ruta operativa dgrauet/fast; no se degrada Agentic silenciosamente.

Resultado reproducible: `battle-2026-08-02.json`.

## Comandos

```zsh
cd /Users/mramospe/Proyectos/Development/3DFromImage/ollama-image-studio
engine/venv/bin/python engine/benchmark_arena.py preflight --spec benchmarks/model-arena/arena-v1.json
engine/venv/bin/python engine/benchmark_arena.py seal --corpus benchmarks/model-arena/corpus-smoke.json
engine/venv/bin/python engine/benchmark_arena.py audit /ruta/shape.glb
engine/venv/bin/python engine/benchmark_arena.py audit /ruta/textured.glb --require-pbr --visual-evidence /ruta/render-report.json --human-decision reject
cd engine && venv/bin/python -m unittest test_benchmark_arena
```

`structural_score` no contiene juicio estético y nunca corona un ganador. Para coronar calidad: ejecutar 4 smoke + 24 casos, tres seeds, registrar wall/RSS/MLX/swap, renderizar frontal y cuartos sin HDRI y puntuar silueta, color, seams, manchas, proyección y regiones de material.
