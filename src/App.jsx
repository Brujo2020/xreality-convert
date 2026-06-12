import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header.jsx';
import PromptPanel from './components/PromptPanel.jsx';
import ImageViewer from './components/ImageViewer.jsx';
import Gallery from './components/Gallery.jsx';

const PREFERRED_MODEL = 'x/z-image-turbo:latest';
const MAX_HISTORY = 20;

function randomSeed() {
  return Math.floor(Math.random() * 1_000_000_000);
}

function timestampName(seed) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const stamp = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(
    d.getHours()
  )}${p(d.getMinutes())}${p(d.getSeconds())}`;
  return `${stamp}-${seed}.png`;
}

export default function App() {
  // --- Ollama connection state ---
  const [status, setStatus] = useState({
    connected: false,
    models: [],
    checking: true,
    error: null,
  });

  // --- Form state ---
  const [model, setModel] = useState(PREFERRED_MODEL);
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

  const hasInitModel = useRef(false);

  // --- Status polling --------------------------------------------------------
  const checkStatus = useCallback(async () => {
    const res = await window.ollama.checkStatus();
    setStatus({
      connected: res.connected,
      models: res.models || [],
      checking: false,
      error: res.error || null,
    });

    // Pick a sensible default model the first time we get a model list.
    if (!hasInitModel.current && res.models && res.models.length > 0) {
      hasInitModel.current = true;
      setModel(
        res.models.includes(PREFERRED_MODEL) ? PREFERRED_MODEL : res.models[0]
      );
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

  // --- Generate --------------------------------------------------------------
  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt.');
      return;
    }
    if (!model) {
      setError('No image model selected.');
      return;
    }
    setError(null);
    setGenerating(true);

    const usedSeed = params.seed;
    const res = await window.ollama.generate({
      model,
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
      image: res.image,
      prompt: prompt.trim(),
      model,
      seed: usedSeed,
      width: params.width,
      height: params.height,
      steps: params.steps,
      duration: res.duration,
      createdAt: Date.now(),
      filePath: null,
    };

    setResult(entry);
    persistHistory([entry, ...history].slice(0, MAX_HISTORY));
  }, [prompt, model, params, history, persistHistory]);

  const handleCancel = useCallback(() => {
    window.ollama.cancel();
  }, []);

  // --- Save / copy -----------------------------------------------------------
  const handleSave = useCallback(async () => {
    if (!result) return null;
    const filename = timestampName(result.seed);
    const filePath = await window.ollama.saveImage(result.image, filename);

    // Record the file path back into the result + history entry.
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

  // --- Gallery selection: show image + reload its params into the form -------
  const handleSelectFromGallery = useCallback((entry) => {
    setResult(entry);
    setError(null);
    setPrompt(entry.prompt);
    setModel(entry.model);
    setParams({
      width: entry.width,
      height: entry.height,
      steps: entry.steps,
      seed: entry.seed,
    });
  }, []);

  return (
    <div className="flex h-full flex-col bg-base text-neutral-200">
      <Header status={status} onRefresh={checkStatus} />

      <div className="flex min-h-0 flex-1">
        {/* Left: form */}
        <aside className="w-[340px] shrink-0 border-r border-border bg-panel">
          <PromptPanel
            connected={status.connected}
            models={status.models}
            model={model}
            setModel={setModel}
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
