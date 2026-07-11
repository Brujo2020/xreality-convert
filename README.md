# Xreality Convert

Forked version maintained in [Brujo2020/xr-forge-studio](https://github.com/Brujo2020/xr-forge-studio), based on the original [ollama-image-studio](https://github.com/koua29/ollama-image-studio) project.

Desktop app for generating, converting, and auditing local AI assets on macOS.
It combines three workflows in one interface:
- Image generation with Ollama
- Text to 3D STL generation with local JSCAD
- Image to 3D reconstruction with local Hunyuan3D MLX

Aplicación de escritorio para generar, convertir y auditar activos AI locales en macOS.
Combina tres flujos en una sola interfaz:
- Generación de imágenes con Ollama
- Texto a STL 3D con JSCAD local
- Reconstrucción Imagen a 3D con Hunyuan3D MLX local

![Xreality Convert - Image mode](docs/screenshot.png)

![Xreality Convert - STL mode](docs/screenshot-stl.png)

![Xreality Convert - Image to 3D](docs/screenshot-3d.png)

## What you get / Qué incluye

- Local-first macOS app with Electron + React
- Automatic Ollama health checks and model discovery
- Cancelable jobs and local history
- Bilingual docs and a current user manual
- Imagen, STL y reconstrucción 3D totalmente locales
- Verificación automática de Ollama y modelos instalados
- Cancelación de trabajos e historial local
- Documentación bilingüe y manual actualizado

## Quick start / Inicio rápido

```bash
git clone https://github.com/Brujo2020/xr-forge-studio.git
cd xr-forge-studio
npm install
npm run dev
```

## Build

```bash
npm run build
```

This produces a signed `.app` and a `.dmg` in `release/`.

## Manual

Read the full bilingual manual here:

- [`docs/MANUAL.md`](docs/MANUAL.md)

## Hunyuan3D setup

Image → 3D uses a separate local Python server. The bundled installer expects
Python 3.11 or 3.12 on Apple Silicon and will recreate the environment if an
older venv is detected.

See the full setup steps in [`docs/MANUAL.md`](docs/MANUAL.md).

## License

[MIT](LICENSE) © 2026 Arnaud Soulas

Fork maintenance and packaging updates: Brujo2020.
