# Xreality Convert

Xreality Convert lives in [Brujo2020/xr-image-3d-creator](https://github.com/Brujo2020/xr-image-3d-creator).
This repo is the maintained macOS fork for local AI asset creation.

[![Version](https://img.shields.io/badge/version-v1.2.2-0ea5e9?style=for-the-badge)](https://github.com/Brujo2020/xr-image-3d-creator/releases/tag/v1.2.2)
[![Release](https://img.shields.io/github/v/release/Brujo2020/xr-image-3d-creator?style=for-the-badge&label=release)](https://github.com/Brujo2020/xr-image-3d-creator/releases/tag/v1.2.2)
[![Download DMG](https://img.shields.io/badge/download-DMG-22c55e?style=for-the-badge)](https://github.com/Brujo2020/xr-image-3d-creator/releases/download/v1.2.2/Xreality.Convert-1.2.2-arm64.dmg)

Xreality Convert is a macOS desktop app for keeping local AI asset creation in one place:

- Image generation with Ollama
- Text to 3D STL generation with local JSCAD
- Image to 3D reconstruction with local Hunyuan3D MLX

La app está pensada para trabajar en local, con historial, diagnóstico y exportación segura para macOS.

## Screenshots

![Xreality Convert - Image mode](docs/screenshot.png)

![Xreality Convert - STL mode](docs/screenshot-stl.png)

![Xreality Convert - Image to 3D](docs/screenshot-3d.png)

## Install

1. Download the latest `.dmg` from the GitHub release or use the direct DMG link above.
2. Drag `Xreality Convert.app` into `Applications`.
3. Launch the app.
4. On first launch, if macOS shows a warning, right-click the app and choose `Open`.

The local build is code-signed when a signing identity is available. Apple
notarization is a separate release step and must be configured before claiming
that a published DMG is notarized.

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
- Code-signed macOS packaging; notarization when configured for a release

## Quick Start

```bash
git clone https://github.com/Brujo2020/xr-image-3d-creator.git
cd xr-image-3d-creator
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

## Release Notes

- [`release-notes.md`](release-notes.md)

## Fork Notes

This fork focuses on:

- Xreality Convert branding and app identity
- Updated docs and bilingual manual
- Signed/notarized macOS distribution
- Local Image → 3D installer fixes
- Fork packaging and release workflow

## License

[MIT](LICENSE) © 2026 Arnaud Soulas

Fork maintenance and packaging updates: Brujo2020.
