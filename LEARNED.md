2026-07-19: Python tests run as `python3 -m unittest engine.test_*` need explicit `engine/` sys.path when importing sibling modules.
2026-07-20: Ollama reasoning models can return HTTP 200 with empty `response` after spending output on thinking; Code 3D must send `think:false`, reserve `num_predict`, and normalize response shapes.
2026-07-20: Local model inventory must include authenticated oMLX `/v1/models/status`; Ollama `/api/tags` alone hides installed MLX coder models and misroutes Code 3D.
2026-07-20: Engine unit tests use system Python without runtime-only PBR packages; keep `pygltflib` imports lazy so fake Paint tests stay dependency-isolated.
2026-07-20: The Hunyuan `texture` request was metadata-only; real PBR requires invoking `Hunyuan3DPaintPipelineMLX` after Shape, clearing MLX cache, and gating the GLB on embedded base-color and metallic-roughness textures.
2026-07-20: Cleanup must not import `mlx.core` in fake/system-Python tests; clear Metal cache only when the runtime already loaded MLX.
2026-07-20: Reducing Paint 1K from 6 to 4 views kept PBR valid but regressed wall time 59.99s→69.20s with negligible memory gain; preserve 6-view quality and optimize model coexistence instead.
2026-07-20: DMG packaging needs write access to `~/Library/Caches/electron`; Vite can pass while electron-builder fails under a restricted filesystem.
2026-07-21: System Python lacks `trimesh`; geometry delivery changes need fake-mesh unit coverage here and runtime validation later in the Hunyuan environment.
2026-07-20: PBR packaging needs `engine/Hunyuan3D-2.1-mlx/hy3dpaint/**/*` in both `build.files` and `build.asarUnpack`; scripts-only packaging makes texture generation fail in the DMG.
2026-07-21: Image prompt enrichment must avoid the word `silhouette` for animals/custom subjects; FLUX/Klein can literalize it as a black cutout instead of a photorealistic reference.
2026-07-21: PBR continuation must persist reference images by path and rehydrate shape GLBs from history; otherwise E2E texture/comparator only works in the original in-memory session.
2026-07-21: A GLB can pass PBR structure validation while the renderer shows gray; verify embedded UV textures are actually visible in Three.js and avoid carrying lowpoly delivery into organic image-to-3D runs.
2026-07-21: Organic image-to-3D must be guarded server-side against `profile=lowpoly`; UI state, presets, or history can still send stale lowpoly params.
2026-07-22: Texture references alone do not prove a self-contained GLB; require referenced `bufferView` image bytes with a valid PNG/JPEG/WebP signature.
2026-07-22: COST T3, 2 verify iterations, pass.
2026-07-26: Un test de catálogo no debe buscar `exec` sobre el JSON completo porque coincide con la clave segura `executor`; validar URLs/comandos prohibidos y allowlist por separado.
2026-07-26: Root cause de VERIFY fallido: el entorno Python del motor está en `engine/venv`, no en `.venv`; usar `engine/venv/bin/python`.
2026-07-26: Los unittest del engine importan módulos vecinos como top-level; ejecutarlos con `cwd=engine`, no desde la raíz.
2026-07-26: Un fixture de segmentación no debe tocar el borde: `_foreground_mask` estima el fondo desde esos píxeles y altera el resultado.
2026-07-26: En React StrictMode no marcar un preview async como resuelto antes del `then`; el cleanup del primer efecto puede descartar el resultado y bloquear la segunda ejecución.
2026-07-26: COST T3, 3 audit agents, 2 verify iterations, pass.
2026-07-24: Un gate GLB estructural no detecta una textura semánticamente mala; anclar la vista frontal a la imagen fuente y reservar difusión para zonas ocultas preserva identidad sin cambiar la geometría.
2026-07-22: Root cause de VERIFY fallido: el repo no define `npm test`; usar el script real `npm run test:tools`.
2026-07-22: Hunyuan Paint `use_remesh=True` reprocesa una malla ya optimizada y puede invalidar el presupuesto/fidelidad Low Poly; texturizar con `use_remesh=False` tras el gate geométrico.
2026-07-22: Meshoptimizer 1.1 viene dentro de Three.js como WASM ESM, pero el engine Python empaquetado no tiene acceso seguro al módulo dentro de app.asar; no añadir un bridge Node no portable.
2026-07-22: Tras electron-builder, verificar la firma de la app dentro del DMG montado; la copia suelta puede fallar aunque el artefacto empaquetado sea válido.
2026-07-22: Añadir un módulo Python importado por `server.py` exige incluirlo tanto en packaging como en `prepareHunyuanEngineFiles`; si no, el server instalado muere antes de `/health`.
2026-07-22: La limpieza best-effort de temporales no puede abortar el arranque por un solo `PermissionError`; omitir el archivo bloqueado y continuar.
2026-07-22: Verificar imports del runtime con `cwd` en su carpeta engine; `python -c` no agrega automáticamente Application Support a `sys.path`.
2026-07-24: Antes de añadir otra arena o router, reutilizar `benchmark-arena-model-registry-design.md`; ya fija corpus sellado, orden ciego determinista, aislamiento y promoción estadística.
2026-07-24: El preset Paint 1K había recaído a 4 vistas/256 pese al benchmark adverso; mantenerlo en 6 vistas/512 y cubrir el perfil exacto con test.
2026-07-24: `unittest` no puede importar por ruta punteada un directorio llamado `Hunyuan3D-2.1-mlx`; ejecutar sus pruebas con `discover -s <tests> -p <archivo>`.
2026-07-24: `setup.sh --preflight` quedaba detrás del retorno por instalación existente; las acciones de diagnóstico deben resolverse antes de reutilizar el runtime.
2026-07-24: La prueba Shape vive en `Hunyuan3D-2.1-mlx/tests`, no en `hy3dshape/tests`; ejecutar verificaciones separadas para no ocultar un fallo con el exit code del último comando.
2026-07-22: GLTFLoader materializa imágenes GLB embebidas mediante URLs `blob:`; una CSP `img-src` limitada a `self data:` produce GLB gris aunque los mapas y UV sean válidos.
2026-07-22: Pre-decimation component metrics hid hundreds of fragments created later; audit and gate the final simplified mesh before Paint/export.
2026-07-22: `trimesh.repair.stitch` cannot generically repair these open GLBs, and Quick Look produced no thumbnail; use topology gates plus a deterministic local mesh render.
2026-07-22: COST T3, 2 verify iterations, pass.
