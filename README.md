# Ollama Image Studio

A native macOS desktop app for generating images locally with [Ollama](https://ollama.com) — no terminal required. Built with Electron + React, designed for Apple Silicon.

![Ollama Image Studio — dark UI with prompt panel, generated image, and gallery sidebar](docs/screenshot.png)

## Features

- 🔌 **Auto connection check** — detects whether Ollama is running on `localhost:11434` and lists your installed image models (`z-image`, `flux`, …).
- 🎨 **Full generation UI** — model picker, multiline prompt, and collapsible advanced controls: width/height (512–2048), steps, and seed with a 🎲 random button.
- 🖼️ **Result viewer** — large preview plus metadata (model, seed, size, steps, generation time).
- 💾 **Save & copy** — one-click save to `~/Pictures/OllamaImageStudio/` with timestamped filenames, plus copy-prompt and reveal-in-Finder.
- 🗂️ **Gallery** — your 20 most recent generations as thumbnails; click one to reload its parameters into the form. Metadata persists to disk.
- ⏹️ **Cancellable** — abort an in-flight generation at any time.
- 🌙 **Dark theme**, native macOS title bar.

## Requirements

- macOS (Apple Silicon recommended)
- [Ollama](https://ollama.com) installed and running: `ollama serve`
- An image-capable model, e.g.:
  ```bash
  ollama pull x/z-image-turbo
  ```
- Node.js 18+ (for building from source)

> **Note:** Image generation via Ollama's `/api/generate` is an experimental endpoint. It requires an Ollama build that supports image output for the selected model.

## Run from source

```bash
git clone https://github.com/<your-username>/ollama-image-studio.git
cd ollama-image-studio
npm install
npm run dev      # launches Vite + Electron in development mode
```

## Build a distributable app

```bash
npm run build    # produces a .app and .dmg in release/
```

Then drag **Ollama Image Studio.app** into your `/Applications` folder, or open the generated `.dmg`.

## Architecture

```
ollama-image-studio/
├── electron/
│   ├── main.js       # Electron main process: IPC handlers + HTTP calls to Ollama
│   └── preload.js    # contextBridge — exposes a safe `window.ollama` API
└── src/
    ├── App.jsx       # state container
    └── components/   # Header, PromptPanel, ImageViewer, Gallery
```

**Design notes**

- All Ollama HTTP calls happen in the **main process** (Node's built-in `http`, zero runtime deps) — this avoids CORS entirely and keeps the renderer sandboxed.
- Security: `nodeIntegration: false`, `contextIsolation: true`, `sandbox: true`, plus a strict Content-Security-Policy.
- Generation is cancellable via an `AbortController` wired through IPC.

### IPC surface (`window.ollama`)

| Method | Returns |
| --- | --- |
| `checkStatus()` | `{ connected, models[] }` |
| `generate(params)` | `{ ok, image, duration }` |
| `cancel()` | aborts the active generation |
| `saveImage(base64, filename)` | absolute file path |
| `loadHistory()` / `saveHistory(history)` | gallery persistence |

## License

[MIT](LICENSE) © 2026 Arnaud Soulas
