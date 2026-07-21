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
