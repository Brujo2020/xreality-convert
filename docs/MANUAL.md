# Xreality Convert Manual / Manual de Xreality Convert

This manual is bilingual. The Spanish version comes first, followed by the English version.

Este manual es bilingüe. La versión en español aparece primero y luego la versión en inglés.

---

## Español

### 1. Qué es

Xreality Convert es una app de escritorio para macOS pensada para crear activos locales sin salir del flujo de trabajo:

- Imagen con Ollama
- Texto a STL 3D con JSCAD
- Imagen a 3D con Hunyuan3D MLX

La aplicación mantiene los modelos, pesos y geometría en local, y muestra diagnóstico, progreso y auditoría para cada trabajo.

### 2. Vista general

![Modo imagen](screenshot.png)

![Modo STL](screenshot-stl.png)

![Modo Imagen a 3D](screenshot-3d.png)

### 3. Instalación

1. Descarga el `.dmg` desde la release de GitHub.
2. Arrastra `Xreality Convert.app` a `Applications`.
3. Abre la app.
4. Si macOS muestra una advertencia de seguridad, haz clic derecho sobre la app y elige `Abrir` la primera vez.

### 4. Requisitos

- macOS en Apple Silicon recomendado
- Ollama instalado y en ejecución
- Python 3.11 o 3.12 para el flujo Imagen a 3D
- Conexión local a los modelos de Ollama
- Al menos 20 GB libres antes de instalar el motor Imagen a 3D
- Antes de generar: 2 GB libres para geometría o 6 GB si se solicitan texturas

### 5. Flujo Imagen

Usa este modo para crear una imagen local:

1. Elige `Crear imagen`.
2. Selecciona el modelo de imagen instalado.
3. Escribe un prompt.
4. Ajusta ancho, alto, pasos y seed si quieres repetibilidad.
5. Pulsa generar.

La imagen generada se guarda localmente y también puede reutilizarse como referencia para Imagen a 3D.

### 6. Flujo Texto a STL

Este modo genera geometría paramétrica con un modelo de código local:

1. Elige `Texto → 3D`.
2. Selecciona un modelo de código instalado.
3. Describe la pieza con la mayor precisión posible.
4. Ajusta perfil, presupuesto de caras y escala.
5. Genera la malla y revisa el visor 3D.
6. Exporta o guarda el STL.

Si el código falla, la app intenta autocorregirlo hasta 3 veces.

### 7. Flujo Imagen a 3D

Este es el flujo más avanzado:

1. Elige `Imagen → 3D`.
2. Selecciona o arrastra una imagen.
3. Revisa el diagnóstico previo.
4. Si hace falta, cambia la categoría o el fondo.
5. Pulsa `Construir activo 3D`.

La app muestra:

- Resolución y encuadre
- Estado de la entrada
- Vista preparada antes de reconstruir
- Progreso del trabajo
- Auditoría de calidad final

La exportación STL se bloquea si la calidad es crítica.

El resultado automático es un candidato de entrega, no un activo `MASTER`.
La promoción a `MASTER` exige evidencia adicional y una revisión humana con
nombre; una sola imagen no demuestra la geometría oculta.

### 8. Buenas prácticas para Imagen a 3D

- Usa una sola figura u objeto principal
- Prefiere PNG con fondo transparente
- Evita elementos cortados por los bordes
- Usa un encuadre casi cuadrado
- Mantén un contraste claro entre sujeto y fondo

### 9. Servidor local Hunyuan3D

El flujo Imagen a 3D usa un servidor Python local.

Instalación esperada:

1. Asegúrate de tener Python 3.11 o 3.12.
2. Ejecuta el instalador integrado de la app.
3. La app recrea el entorno si detecta un venv incompatible.

La app sólo permite una instancia y un trabajo pesado a la vez. Al abrirse,
comprueba el puerto local y reutiliza un servidor sano; no reemplaza un proceso
ajeno. Si el servidor se reinicia durante un trabajo, el trabajo queda marcado
como interrumpido y requiere un reintento explícito para preservar la evidencia.

El estado del motor puede ser:

- `ready`: listo; el modelo Shape puede cargarse de forma perezosa al primer trabajo.
- `degraded`: existe el runtime, pero falló una carga previa; revisa el log local y reinstala si persiste.
- `unavailable`: falta el runtime Shape; ejecuta el instalador integrado.

### 10. Calidad, seguridad y límites

El flujo conserva localmente el original, la referencia preparada, un checkpoint
de geometría y un reporte técnico. Shape y Paint se ejecutan en secuencia para
evitar solapar pesos Metal. Las gates pueden rechazar una malla por geometría,
normales, componentes, material o exportación STL insegura.

La app no sustituye silenciosamente un modelo, no fabrica vistas ocultas y no
convierte una métrica incompleta en una aprobación. Una calidad `atención`,
`not_measured` o una evidencia sintética no equivale a una aprobación maestra.

### 11. Resolución de problemas

- Si Ollama no aparece, comprueba que esté ejecutándose localmente.
- Si Imagen a 3D no inicia, verifica Python 3.11/3.12.
- Si la exportación STL queda bloqueada, revisa la calidad de la reconstrucción.
- Si la app no abre por seguridad, usa clic derecho > `Abrir` la primera vez.
- Si no hay espacio suficiente, libera almacenamiento y vuelve a instalar o generar.
- Si el motor aparece como `degraded`, consulta `engine-runtime.log` en el soporte de la app y reinstala el motor antes de reintentar.

### 12. Atajos útiles

- `Generar` inicia el flujo actual
- `Cancelar` detiene el trabajo en curso
- La galería reabre resultados e historial locales

---

## English

### 1. What it is

Xreality Convert is a macOS desktop app for keeping asset creation local:

- Image generation with Ollama
- Text to 3D STL with local JSCAD
- Image to 3D reconstruction with local Hunyuan3D MLX

The app keeps models, weights, and geometry on your machine and surfaces diagnosis, progress, and quality checks for every job.

Model weights use one shared Hugging Face cache. By default this is
`~/.cache/huggingface/hub` for both Terminal and Finder launches. Set
`HF_HUB_CACHE` before launching the app only when intentionally placing that
single cache on another volume; Xreality Convert does not create a second
weights cache under Application Support.

### 2. Overview

![Image mode](screenshot.png)

![STL mode](screenshot-stl.png)

![Image to 3D mode](screenshot-3d.png)

### 3. Installation

1. Download the `.dmg` from the GitHub release.
2. Drag `Xreality Convert.app` into `Applications`.
3. Launch the app.
4. If macOS warns you on first launch, right-click the app and choose `Open`.

### 4. Requirements

- Apple Silicon macOS recommended
- Ollama installed and running
- Python 3.11 or 3.12 for Image to 3D
- Local access to the Ollama models you want to use
- At least 20 GB free before installing the Image to 3D engine
- Before generation: 2 GB free for geometry or 6 GB when requesting textures

### 5. Image workflow

Use this mode to generate images locally:

1. Choose `Create image`.
2. Select an installed image model.
3. Write a prompt.
4. Adjust width, height, steps, and seed as needed.
5. Generate the image.

The result is saved locally and can be reused as a reference for Image to 3D.

### 6. Text to STL workflow

This mode generates parametric geometry with a local code model:

1. Choose `Text → 3D`.
2. Select an installed code model.
3. Describe the object as precisely as possible.
4. Adjust profile, face budget, and scale.
5. Generate and inspect the 3D preview.
6. Export or save the STL.

If the generated code fails, the app retries up to 3 times with repair feedback.

### 7. Image to 3D workflow

This is the most advanced path:

1. Choose `Image → 3D`.
2. Select or drag in an image.
3. Review the preflight diagnosis.
4. Change category or background if needed.
5. Click `Build 3D asset`.

The app shows:

- Resolution and framing
- Input status
- Prepared preview before reconstruction
- Live job progress
- Final quality audit

STL export is blocked when the quality gate is critical.

An automatic result is a delivery candidate, not a `MASTER` asset. Promotion
to `MASTER` requires additional evidence and a named human review; one image
does not prove hidden geometry.

### 8. Best practices for Image to 3D

- Use one main subject
- Prefer transparent PNGs
- Avoid cropped edges
- Keep the framing close to square
- Keep strong subject/background contrast

### 9. Local Hunyuan3D server

Image to 3D uses a separate local Python server.

Expected setup:

1. Make sure Python 3.11 or 3.12 is installed.
2. Run the built-in installer from the app.
3. The app recreates the environment if it detects an incompatible venv.

The app permits one application instance and one heavy job at a time. On
launch it checks the local port and reuses a healthy server; it does not replace
an unrelated process. If the server restarts mid-job, the job is marked as
interrupted and requires an explicit retry to preserve its evidence.

Engine status can be:

- `ready`: ready; Shape may be lazy-loaded on the first job.
- `degraded`: the runtime exists, but a previous load failed; inspect the local log and reinstall if it persists.
- `unavailable`: the Shape runtime is missing; run the built-in installer.

### 10. Quality, safety, and limits

The workflow keeps the original, prepared reference, geometry checkpoint, and
technical report locally. Shape and Paint run sequentially so Metal weights do
not overlap. Gates may reject a mesh for geometry, normals, components,
materials, or unsafe STL export.

The app does not silently substitute a model, manufacture hidden views, or
turn incomplete evidence into an approval. `attention`, `not_measured`, or
synthetic evidence is not a master approval.

### 11. Troubleshooting

- If Ollama is missing, check that it is running locally.
- If Image to 3D does not start, verify Python 3.11/3.12.
- If STL export is blocked, check the reconstruction quality.
- If macOS blocks the app on first launch, use right-click > `Open`.
- If free space is insufficient, free storage and install or generate again.
- If the engine is `degraded`, inspect `engine-runtime.log` in the app support folder and reinstall the engine before retrying.

### 12. Useful actions

- `Generate` starts the active workflow
- `Cancel` stops the current job
- The gallery reopens local results and history
