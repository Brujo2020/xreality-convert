# Xreality Convert

Xreality Convert is a standalone macOS app maintained in [Brujo2020/xreality-convert](https://github.com/Brujo2020/xreality-convert).

[![Version](https://img.shields.io/badge/version-v1.2.2-0ea5e9?style=for-the-badge)](https://github.com/Brujo2020/xreality-convert/releases/tag/v1.2.2)
[![Release](https://img.shields.io/github/v/release/Brujo2020/xreality-convert?style=for-the-badge&label=release)](https://github.com/Brujo2020/xreality-convert/releases/tag/v1.2.2)
[![Download DMG](https://img.shields.io/badge/download-DMG-22c55e?style=for-the-badge)](https://github.com/Brujo2020/xreality-convert/releases/download/v1.2.2/Xreality.Convert-1.2.2-arm64.dmg)

Xreality Convert is a macOS desktop app for keeping local AI asset creation in one place:

- Image generation with Ollama
- Text to 3D STL generation with local JSCAD
- Image to 3D reconstruction with local Hunyuan3D MLX

La app está pensada para trabajar en local, con historial, diagnóstico y exportación segura para macOS.

## What it does

- Generates images locally through Ollama
- Turns prompts into 3D STL geometry with JSCAD
- Reconstructs images into 3D assets with local Hunyuan3D MLX
- Keeps history, previews, and diagnostics on your Mac
- Ships as a signed and notarized DMG for safer installation

## Quick Highlights

- Native macOS app with Electron + React
- Local-first workflows, no cloud required for the core app
- Automatic Ollama health checks and model discovery
- Cancelable jobs and local history
- Bilingual documentation and a complete user manual
- Current branding, favicon, icon, and dock identity

## Screenshots

![Xreality Convert - Image mode](docs/screenshot.png)

![Xreality Convert - STL mode](docs/screenshot-stl.png)

![Xreality Convert - Image to 3D](docs/screenshot-3d.png)

## Install

1. Download the latest `.dmg` from the GitHub release or use the direct DMG link above.
2. Drag `Xreality Convert.app` into `Applications`.
3. Launch the app.
4. On first launch, if macOS shows a warning, right-click the app and choose `Open`.

The release DMG is signed and notarized for safer installation on Mac.

## Requirements

- Apple Silicon macOS recommended
- Ollama installed and running locally
- Python 3.11 or 3.12 for Image to 3D
- Local access to the Ollama models you want to use

## Features

- Local-first Electron + React app
- Automatic Ollama health checks and model discovery
- Cancelable jobs and local history
- Bilingual documentation and a current user manual
- Native macOS branding, favicon, icon, and dock identity
- Signed and notarized DMG distribution

## Workflows

### Image

Use this mode to generate local images from prompts, then reuse them as references or export assets for the rest of the pipeline.

### Text to STL

Use this mode to generate parametric STL geometry from a natural-language description.

### Image to 3D

Use this mode to rebuild a single object or subject into a local 3D asset. The app validates the image, runs the Hunyuan3D MLX engine, and blocks export when quality is too low.

## Quick Start

```bash
git clone https://github.com/Brujo2020/xreality-convert.git
cd xreality-convert
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

## Image to 3D

The Image → 3D workflow uses a separate local Python server.

Expected setup:

1. Install Python 3.11 or 3.12.
2. Run the built-in installer from the app.
3. The app recreates the environment if it detects an incompatible venv.

Full steps are documented in [`docs/MANUAL.md`](docs/MANUAL.md).

## Troubleshooting

- If macOS warns on first launch, right-click the app and choose `Open`.
- If Ollama is not detected, start it locally before using the app.
- If Image to 3D says Python 3.11 or 3.12 is missing, install one of those versions and retry the 3D engine setup.
- If STL export is blocked, check the quality audit in the 3D workflow.

## Release Notes

- [`release-notes.md`](release-notes.md)

## Project Notes

This project focuses on:

- Xreality Convert branding and app identity
- Updated docs and bilingual manual
- Signed/notarized macOS distribution
- Local Image → 3D installer fixes
- Packaging and release workflow

## License

[MIT](LICENSE) © 2026 Brujo2020

Maintained by Brujo2020.
