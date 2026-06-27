import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header.jsx';
import PromptPanel from './components/PromptPanel.jsx';
import ImageViewer from './components/ImageViewer.jsx';
import Gallery from './components/Gallery.jsx';

const IMAGE_MODEL = 'x/z-image-turbo:latest';
const MAX_HISTORY = 20;

// Models we prefer for STL code generation, in order. Falls back to the first
// available text model if none of these are installed.
const PREFERRED_STL_MODELS = [
  'qwen2.5-coder:latest',
  'qwen3-codex:latest',
  'gemma4-codex:latest',
  'qwen3:14b',
];

function randomSeed() {
  return Math.floor(Math.random() * 1_000_000_000);
}

function timestampName(seed, ext) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const stamp = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(
    d.getHours()
  )}${p(d.getMinutes())}${p(d.getSeconds())}`;
  return `${stamp}-${seed}.${ext}`;
}

// Image generators are filtered out of the STL model list.
const isImageModel = (name) => /z-image|flux/i.test(name);

export default function App() {
  // --- Ollama connection state ---
  const [status, setStatus] = useState({
    connected: false,
    models: [],
    allModels: [],
    checking: true,
    error: null,
  });

  // --- Mode: 'image' | 'stl' ---
  const [mode, setMode] = useState('image');

  // --- Form state ---
  const [stlModel, setStlModel] = useState('');
  const [prompt, setPrompt] = useState('');
  const [params, setParams] = useState({
    width: 1024,
    height: 1024,
    steps: 8,
    seed: randomSeed(),
  });

  // --- Generation state ---
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // --- Gallery ---
  const [history, setHistory] = useState([]);

  const hasInitStlModel = useRef(false);

  // Derived: is the fixed image model installed locally?
  const imageModelAvailable = status.allModels.includes(IMAGE_MODEL);
  // Text/code models usable for STL generation.
  const stlModels = status.allModels.filter((m) => !isImageModel(m));

  // --- Status polling --------------------------------------------------------
  const checkStatus = useCallback(async () => {
    const res = await window.ollama.checkStatus();
    setStatus({
      connected: res.connected,
      models: res.models || [],
      allModels: res.allModels || [],
      checking: false,
      error: res.error || null,
    });

    // Pick a default STL model the first time we see a model list.
    if (!hasInitStlModel.current && res.allModels && res.allModels.length > 0) {
      hasInitStlModel.current = true;
      const candidates = res.allModels.filter((m) => !isImageModel(m));
      const preferred = PREFERRED_STL_MODELS.find((m) => candidates.includes(m));
      setStlModel(preferred || candidates[0] || '');
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const id = setInterval(checkStatus, 5000);
    return () => clearInterval(id);
  }, [checkStatus]);

  // --- Load persisted history on mount --------------------------------------
  useEffect(() => {
    window.ollama.loadHistory().then((items) => {
      if (Array.isArray(items)) setHistory(items.slice(0, MAX_HISTORY));
    });
  }, []);

  const persistHistory = useCallback((next) => {
    setHistory(next);
    window.ollama.saveHistory(next);
  }, []);

  // --- Generate (branches on mode) ------------------------------------------
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt.');
      return;
    }

    const usedSeed = params.seed;
    setError(null);
    setGenerating(true);

    if (mode === 'image') {
      const res = await window.ollama.generate({
        model: IMAGE_MODEL,
        prompt: prompt.trim(),
        width: params.width,
        height: params.height,
        steps: params.steps,
        seed: usedSeed,
      });
      setGenerating(false);
      if (!res.ok) {
        if (!res.cancelled) setError(res.error || 'Generation failed.');
        return;
      }
      const entry = {
        id: `${Date.now()}-${usedSeed}`,
        type: 'image',
        image: res.image,
        prompt: prompt.trim(),
        model: IMAGE_MODEL,
        seed: usedSeed,
        width: params.width,
        height: params.height,
        steps: params.steps,
        duration: res.duration,
        createdAt: Date.now(),
        filePath: null,
      };
      setResult(entry);
      // Images keep their base64 inline so the gallery can show thumbnails.
      persistHistory([entry, ...history].slice(0, MAX_HISTORY));
      return;
    }

    // --- STL mode ---
    if (!stlModel) {
      setGenerating(false);
      setError('No code model selected for STL generation.');
      return;
    }
    const res = await window.ollama.generateStl({
      model: stlModel,
      prompt: prompt.trim(),
      seed: usedSeed,
    });
    setGenerating(false);
    if (!res.ok) {
      if (!res.cancelled) setError(res.error || 'STL generation failed.');
      return;
    }
    const entry = {
      id: `${Date.now()}-${usedSeed}`,
      type: 'stl',
      stl: res.stl, // kept in-memory for the current view only
      stlPath: res.stlPath, // cached on disk for gallery re-display
      code: res.code,
      prompt: prompt.trim(),
      model: stlModel,
      seed: usedSeed,
      triangles: res.triangles,
      duration: res.duration,
      createdAt: Date.now(),
      filePath: null,
    };
    setResult(entry);
    // Store everything except the heavy inline STL text.
    const { stl, ...lightEntry } = entry;
    persistHistory([lightEntry, ...history].slice(0, MAX_HISTORY));
  }, [prompt, mode, params, stlModel, history, persistHistory]);

  const handleCancel = useCallback(() => {
    window.ollama.cancel();
  }, []);

  // --- Save (branches on type) ----------------------------------------------
  const handleSave = useCallback(async () => {
    if (!result) return null;
    let filePath;
    if (result.type === 'stl') {
      const data = result.stl || (await window.ollama.readStl(result.stlPath));
      if (!data) return null;
      filePath = await window.ollama.saveStl(data, timestampName(result.seed, 'stl'));
    } else {
      filePath = await window.ollama.saveImage(
        result.image,
        timestampName(result.seed, 'png')
      );
    }
    const updated = { ...result, filePath };
    setResult(updated);
    persistHistory(
      history.map((h) => (h.id === result.id ? { ...h, filePath } : h))
    );
    return filePath;
  }, [result, history, persistHistory]);

  const handleCopyPrompt = useCallback(async () => {
    if (result?.prompt) {
      await navigator.clipboard.writeText(result.prompt);
      return true;
    }
    return false;
  }, [result]);

  // --- Gallery selection: show item + reload its params ----------------------
  const handleSelectFromGallery = useCallback(async (entry) => {
    setError(null);
    setPrompt(entry.prompt);
    setMode(entry.type === 'stl' ? 'stl' : 'image');
    if (entry.type === 'stl') {
      setStlModel(entry.model);
      // STL text isn't kept in history — read it back from the cache file.
      const stl = entry.stl || (await window.ollama.readStl(entry.stlPath));
      setResult({ ...entry, stl });
    } else {
      setParams({
        width: entry.width,
        height: entry.height,
        steps: entry.steps,
        seed: entry.seed,
      });
      setResult(entry);
    }
  }, []);

  return (
    <div className="flex h-full flex-col bg-base text-neutral-200">
      <Header status={status} onRefresh={checkStatus} />

      <div className="flex min-h-0 flex-1">
        {/* Left: form */}
        <aside className="w-[340px] shrink-0 border-r border-border bg-panel">
          <PromptPanel
            connected={status.connected}
            mode={mode}
            setMode={setMode}
            imageModel={IMAGE_MODEL}
            imageModelAvailable={imageModelAvailable}
            stlModels={stlModels}
            stlModel={stlModel}
            setStlModel={setStlModel}
            prompt={prompt}
            setPrompt={setPrompt}
            params={params}
            setParams={setParams}
            generating={generating}
            onGenerate={handleGenerate}
            onCancel={handleCancel}
            randomSeed={randomSeed}
          />
        </aside>

        {/* Center: result */}
        <main className="min-w-0 flex-1">
          <ImageViewer
            result={result}
            generating={generating}
            mode={mode}
            error={error}
            onSave={handleSave}
            onCopyPrompt={handleCopyPrompt}
            onReveal={(p) => window.ollama.revealInFinder(p)}
          />
        </main>

        {/* Right: gallery */}
        <aside className="w-[200px] shrink-0 border-l border-border bg-panel">
          <Gallery
            history={history}
            activeId={result?.id}
            onSelect={handleSelectFromGallery}
          />
        </aside>
      </div>
    </div>
  );
}
