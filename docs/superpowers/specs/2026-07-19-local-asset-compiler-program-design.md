# Local Asset Compiler: programa de innovación local 2026

Fecha de corte: 2026-07-19
Estado: arquitectura aprobada; pendiente de plan TDD por subsistema
Hardware objetivo verificado: Apple M5 Pro, 24 GiB, macOS 26.5.2
Producto: generación local de imagen, CSG/mesh, PBR, optimización y exportación XR

## 1. Tesis

No existe un modelo único que combine estado del arte, Apple Silicon 24 GiB, PBR completo, licencia mundial permisiva, estabilidad y evidencia independiente. El producto será un compilador adaptativo de activos: stages independientes, providers `stable/lab/reject`, planes versionados, evaluación cerrada y promoción por evidencia.

No se promete “500%” ni premios. La innovación se demuestra mediante deltas por etapa, Pareto reproducible, seguridad, control humano y activos finales auditables.

## 2. Resultado verificable

Desde prompt o imagen, la aplicación produce un asset local con:

- referencia reconstruible y lineage;
- geometría canónica validada;
- PBR real cuando capability/memoria permiten;
- derivado optimizado para destino XR;
- manifest de modelos, parámetros, hashes, licencia y validadores;
- reanudación desde cualquier stage comprometido;
- selector `Velocidad | Balanceado | Calidad`, default Balanceado;
- corrección automática dirigida y refinamiento humano acotado.

Calidad se mide sobre GLB/STL final recargado, no sobre tensores ni labels solicitados.

## 3. Investigación mundial julio 2026

### 3.1 Imagen→3D/PBR

| Candidato | Estado local | Decisión |
|---|---|---|
| Hunyuan3D 2.1 MLX actual | shape ya integrado; Paint presente pero no cableado/medido | `lab/capability_unverified`; stable objetivo tras promoción |
| Hunyuan3D-Swift | paridad declarada; shape ~5.6–7.3 GB/~21–22 s; Paint PBR ~39 GB | shape `lab`; Paint reject 24 GB |
| TRELLIS.2 upstream | 4B, O-Voxel, PBR/opacity; Linux + NVIDIA ≥24 GB | reject local |
| TRELLIS.2 Swift/MLX | port completo muy reciente; pesos ~17.6 GB; GLB/PBR | `lab` con margen crítico |
| Pixal3D SIGGRAPH 2026 | pixel-aligned, PBR; CUDA/NATTEN/TRELLIS.2 | research-only |
| Home3D 1.0 | arquitectura modular PBR/parts; sin runtime local demostrado | research transfer |
| Stable Fast 3D/SPAR3D | feed-forward rápido; MPS experimental/licencia Stability | baseline `lab` |
| Apple SHARP | preview 3DGS rápido, no mesh/PBR; pesos research license | reject producto |

Fuentes:

- [TRELLIS.2 oficial](https://github.com/microsoft/TRELLIS.2)
- [TRELLIS.2 Swift/MLX](https://github.com/xocialize/mlx-trellis2-swift)
- [pesos TRELLIS.2 MLX](https://huggingface.co/xocialize/trellis2-mlx)
- [Pixal3D](https://github.com/TencentARC/Pixal3D) y [paper](https://huggingface.co/papers/2605.10922)
- [Hunyuan3D 2.1](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1) y [paper](https://arxiv.org/abs/2506.15442)
- [Hunyuan3D-Swift](https://github.com/ZimengXiong/Hunyuan3D-Swift)
- [Home3D 1.0](https://arxiv.org/abs/2606.27923)
- [MeshGen](https://huggingface.co/papers/2505.04656)

### 3.2 Texto→Imagen local

| Candidato | Huella/soporte | Decisión |
|---|---|---|
| FLUX.2 Klein 4B | Ollama macOS 5.7 GB; MLX/MFLUX; Apache-2.0 | stable candidate |
| Z-Image Turbo 6B | Ollama FP8 13 GB; MLX/MFLUX; Apache-2.0 | quality candidate |
| Bonsai Image 4B 1-bit | payload 3.42 GB; 4 steps; kernels/fork MLX pendiente upstream | speed `lab` |
| FLUX.2 Klein 9B | 12 GB; licencia no comercial | lab no comercial |
| Qwen-Image-2512 4-bit | repo reporta 24–25.9 GB antes de margen | reject 24 GB |
| HunyuanImage 3.0 | 83B | reject 24 GB |
| Z-Image Turbo++ 2-step | paper 2026; sin artefacto MLX promovible observado | watchlist |

Fuentes:

- [FLUX.2 Klein Ollama](https://ollama.com/x/flux2-klein)
- [Z-Image Ollama](https://ollama.com/x/z-image-turbo)
- [MFLUX](https://github.com/filipstrand/mflux)
- [Bonsai Image MLX](https://huggingface.co/prism-ml/bonsai-image-binary-4B-mlx-1bit)
- [Qwen Image MLX 4-bit](https://huggingface.co/mlx-community/Qwen-Image-2512-4bit)
- [Z-Image Turbo++ paper](https://huggingface.co/papers/2606.12575)

### 3.3 Texto→CSG IR

Candidatos instalados:

- Gemma 4 12B Coder Fable5/Composer2.5 4-bit — hipótesis de calidad, fine-tune comunitario.
- gpt-oss-20b MXFP4-Q8 — structured output/procedencia sólida; requiere Harmony correcto.
- Qwen3-8B 4-bit — baseline eficiente.
- Qwen3.5-9B 4-bit — laboratorio simple por cap local 2048.

Ninguno es default por nombre o benchmark genérico. `schemaValid@1`, `compile@1`, fidelidad paramétrica, p95 y memoria deciden. P3D-Bench y 3DCodeBench aportan evaluación de estructura/partes/test-time refinement:

- [P3D-Bench](https://huggingface.co/papers/2606.11152)
- [3DCodeBench](https://huggingface.co/papers/2606.01057)
- [gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b)

### 3.4 Investigación transferida

- Pixal3D: back-projection/pixel alignment para fidelidad a input.
- Home3D: geometría, textura, material y parts como módulos separados.
- Hunyuan3D Studio: semantic UV/part-level/game-ready pipeline.
- 3DCodeBench: feedback de render y test-time scaling dirigido.
- Human-in-the-loop atlas: corrección semántica por regiones.
- Harmful Geometry 2026: defensa apilada input/model/output y falsos positivos medidos.

Fuentes:

- [Human-in-the-loop 3D, IEEE TVCG/ResearchGate](https://www.researchgate.net/publication/405177156_Orchestrating_Generative_AI_Paradigms_with_Human-In-The-Loop_for_3D_Generation)
- [Atlas segmentation 2026](https://arxiv.org/abs/2606.17824)
- [Harmful Geometry](https://arxiv.org/abs/2605.09606) y [mirror ResearchGate](https://www.researchgate.net/publication/404753553_On_the_Generation_and_Mitigation_of_Harmful_Geometry_in_Image-to-3D_Models)

ResearchGate se usa como índice/mirror solicitado; decisiones técnicas se apoyan en papers, repos y model cards primarios.

## 4. Arquitectura

```text
Prompt/Image
  -> ReferenceDirector
  -> ProfilePolicy
  -> ProviderRouter
  -> GeometryProvider
  -> GeometryGate
  -> CanonicalMeshArtifact
  -> MaterialProvider
  -> PBRGate
  -> RenderCritic / HumanRefinement
  -> Optimizer
  -> AssetAuditor
  -> FinalManifest + Export
```

Fundaciones:

- `WorkflowCoordinator`: lifecycle/lease GPU/cancel/commit.
- `AssetRepository`: IDs opacos, manifests y caché por contenido.
- `ModelRegistry`: revision/digest/licencia/capabilities.
- `BenchmarkArena`: stable/lab/reject y promoción Pareto.
- `ProfilePolicy`: intención→plan efectivo.

## 5. Innovaciones de producto

### 5.1 Reference Director

Produce `InputSet` con original inmutable, prepared reference, máscara, cámaras, vistas capturadas y vistas sintéticas separadas. Vistas sintéticas ayudan al prior, pero no cuentan como evidencia ni reemplazan silueta original.

### 5.2 Provider Router por stage

Geometría y materiales no dependen de un monolito. Un provider monolítico puede implementar ambos contratos, pero sus artefactos cruzan los mismos gates.

### 5.3 Closed-loop local

Después de cada candidato:

1. gates deterministas;
2. renders canónicos;
3. critic local con salida estructurada;
4. decisión `accept | repair_stage | ask_user | fail`;
5. máximo dos correcciones dirigidas en Calidad, una en Balanceado y cero en Velocidad.

Critic nunca puede saltar gates duros ni ejecutar código. Reparación reutiliza stages válidos.

### 5.4 Human Refinement

Usuario marca región/parte/material sobre turntable/atlas. La corrección crea derivado nuevo con lineage y no muta master. Esta ruta se diseña después del critic determinista, no como editor 3D general.

### 5.5 Evidence Card

Cada resultado muestra:

- perfil solicitado/efectivo;
- modelos, revisiones y licencia;
- tiempos/memoria por stage;
- gates superados/warnings;
- PBR/UV/materiales realmente presentes;
- degradaciones y reparaciones;
- comparación antes/después de optimización.

Esto convierte “calidad” en evidencia visible y diferenciador de producto.

## 6. Memoria y ejecución M5 Pro 24 GiB

Presupuesto inicial de benchmark:

- 6–8 GiB reservados para macOS/UI/procesos;
- ceiling operativo aproximado 16 GiB, leído/ajustado en runtime;
- un solo lease GPU pesado;
- workers terminan por stage para garantizar devolución de memoria;
- Shape y Paint nunca residentes juntos;
- oMLX se pausa/descarga si admission no permite coexistencia;
- memoria/reserva desconocida bloquea, no degrada.

MLX telemetry registra active, peak y cache; RSS/swap/memory pressure complementan porque unified memory es compartida. [MLX memory management](https://ml-explore.github.io/mlx/build/html/python/memory_management.html)

Toolchain local observado: macOS compatible con ports recientes, pero Xcode completo no está activo; TRELLIS.2 Swift queda bloqueado hasta instalar/validar toolchain con autorización específica.

## 7. Seguridad, licencia y supply chain

- Nunca `trust_remote_code`, pickle o scripts post-install en ruta estable.
- Descarga por repo+commit, allowlist de archivos, safetensors, SHA-256 y manifest agregado.
- Pesos convertidos comunitarios requieren origen, conversión reproducible y paridad.
- Licencia se evalúa por código, pesos, dataset/encoder y dependencias transitivas.
- Hunyuan Community License tiene restricciones territoriales/distribución; no puede ser único provider mundial sin revisión legal.
- TRELLIS.2 es MIT, pero DINOv3 y dependencias conservan términos propios.
- Bonsai requiere fork MLX con kernels 1-bit pendientes upstream: laboratorio.
- Cada asset guarda provenance local sin prompt sensible por defecto.

## 8. Perfiles

- **Velocidad:** extremo rápido Pareto, cero repair generativo, PBR off/1K manual.
- **Balanceado:** default, rodilla Pareto, una reparación, PBR 1K si admitido.
- **Calidad:** extremo quality dentro de límites, torneo/corrección dirigida, PBR 2K si admitido.

Destino XR conserva caras finales/formato. Perfil solo gobierna compute/modelo/detalle de trabajo.

Diseño detallado: `2026-07-19-profile-policy-design.md`.

## 9. Programa en cuatro specs

1. `ProfilePolicy + Provider Registry` — intención, plan y UX.
2. `Benchmark Arena + Model Registry` — evidencia, modelos y promoción.
3. `Reference Director + Provider Router` — inputs, geometría y materiales.
4. `Render Critic + Asset Auditor` — closed loop, humano, seguridad y export.

Cada spec obtiene plan TDD independiente. El orden de implementación respeta dependencias, no promete un big-bang.

## 10. Gates del programa

### Gate A: foundations

P0/P1 previos cerrados, lifecycle, asset repository, manifests y model digests.

### Gate B: baseline

Caracterizar pipeline actual en hardware objetivo; cero modelo nuevo.

### Gate C: ProfilePolicy

Default Balanceado, plan hash, UI honesta y matriz de bypass.

### Gate D: Benchmark Arena

Corpus versionado, telemetry, promoción y evidence reports.

### Gate E: providers stable

Hunyuan Shape, Paint condicionado, FLUX/Z-Image y CSG winner.

### Gate F: closed loop

Gates, canonical renders, critic y reparación dirigida.

### Gate G: labs

TRELLIS.2 Swift/MLX, Hunyuan3D-Swift, Bonsai Image; opt-in y rollback.

### Gate H: final utility

Cadena completa, reanudación, browser QA, 20 runs sin OOM y export GLB/STL validado.

## 11. Métricas de mejora

No se agregan a un “500%” artificial:

- Texto→Imagen: `downstreamMeshAccepted@1`, p95, peak memory.
- CSG: `schemaValid@1`, `compile@1`, geometría/partes/dimensiones.
- Shape: F-score, silhouette IoU, depth/normals, topology.
- PBR: UV coverage, seams, ΔE/LPIPS/SSIM, metallic/roughness, HDRI renders.
- Export: validator errors, tamaño, load time, delta visual post-opt.
- Sistema: OOM, crash, cancel, cache reuse, swap, thermal, energy cuando disponible.
- Humano: pairwise ciego, regiones corregidas y tiempo hasta aceptación.

Promoción exige CI pareado, margen predeclarado y no-regresión de gates.

## 12. Criterios finales

1. Toda inferencia permanece local.
2. Cada stage es cacheable, reanudable y reproducible.
3. Ningún modelo entra estable sin manifest/licencia/benchmark.
4. Ningún perfil rompe memoria, seguridad o destino XR.
5. Geometría y PBR se validan sobre archivo final.
6. Corrección automática es dirigida, acotada y observable.
7. Usuario puede corregir una región sin regenerar todo.
8. Lab nunca sustituye estable silenciosamente.
9. Evidence Card explica calidad y degradación.
10. Tests, build, smoke real y browser QA aportan evidencia fresca.

## 13. Riesgos residuales

- Ports Swift/MLX 2026 son recientes y pueden fallar en este hardware pese a paridad declarada.
- PBR de alta resolución puede exceder 24 GiB; 1K/2K dependen de medición.
- VLM critic puede preferir estética incorrecta; gates deterministas y humano prevalecen.
- Restricciones de licencia pueden impedir distribución mundial de ciertos providers.
- Single-view no recupera verdad backside; uncertainty debe mostrarse.
- Implementar parts/atlas completo antes de foundations sería sobrealcance; se secuencia después de closed loop básico.
