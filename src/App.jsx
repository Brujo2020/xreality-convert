import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header.jsx';
import PromptPanel from './components/PromptPanel.jsx';
import ImageViewer from './components/ImageViewer.jsx';
import Gallery from './components/Gallery.jsx';
import { XR_PROFILES } from './lib/xrProfiles.js';
import { USE_CASES } from './lib/useCases.js';
import { MODEL_CATEGORIES } from './lib/modelCategories.js';

const IMAGE_MODEL = 'x/z-image-turbo:latest';
const PREFERRED_IMAGE_MODELS = ['x/flux2-klein:latest', 'x/flux2-klein', IMAGE_MODEL];
const MAX_HISTORY = 20;

// Models we prefer for STL code generation, in order. Falls back to the first
// available text model if none of these are installed.
const PREFERRED_STL_MODELS = [
  'qwen3-coder:30b',
  'qwen3-coder:latest',
  'qwen2.5-coder:32b',
  'qwen2.5-coder:latest',
  'qwen3:30b',
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

  // --- Conversión: texto o imagen hacia un activo 3D ---
  const [mode, setMode] = useState('image3d');
  const [useCase, setUseCase] = useState('industrial');
  const [modelCategory, setModelCategory] = useState('industrial');

  // --- Form state (Texto → 3D) ---
  const [stlModel, setStlModel] = useState('');
  const [imageModel, setImageModel] = useState(IMAGE_MODEL);
  const [prompt, setPrompt] = useState('');
  const [params, setParams] = useState({
    width: 1024,
    height: 1024,
    steps: 8,
    seed: randomSeed(),
  });

  // --- Image -> 3D (Hunyuan, via local Python server) ---
  const [image3dInput, setImage3dInput] = useState(null); // { dataUrl, base64, name }
  const [steps3d, setSteps3d] = useState(30);
  const [guidance3d, setGuidance3d] = useState(MODEL_CATEGORIES.industrial.guidance);
  const [backgroundMode, setBackgroundMode] = useState('auto');
  const [subjectPadding, setSubjectPadding] = useState(MODEL_CATEGORIES.industrial.padding);
  const [stlMm, setStlMm] = useState(60); // target longest-axis size for STL export
  const [texture3d, setTexture3d] = useState(false); // Stage 2 PBR texture
  const [asset, setAsset] = useState({ profile: 'xreal', ...XR_PROFILES.xreal });
  const [hunyuanUp, setHunyuanUp] = useState(false);
  const [installingEngine, setInstallingEngine] = useState(false);
  const [installingModel, setInstallingModel] = useState(false);

  // --- Generation state ---
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState({ percent: 0, label: 'Preparando…', remaining: null });
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // --- Gallery ---
  const [history, setHistory] = useState([]);

  const hasInitStlModel = useRef(false);
  const hasInitImageModel = useRef(false);
  const hasAttemptedEngineBootstrap = useRef(false);
  const processing = generating || installingEngine || installingModel;

  useEffect(() => {
    if (!processing || (mode === 'image3d' && generating)) return undefined;
    const startedAt = Date.now();
    const estimatedSeconds = installingEngine
      ? 240
      : installingModel
      ? 600
      : mode === 'image3d'
      ? asset.texture
        ? 900
        : 480
      : mode === 'stl'
      ? 150
      : 60;
    const label = installingEngine
      ? 'Instalando el motor 3D'
      : installingModel
      ? 'Descargando el modelo de imagen'
      : mode === 'image3d'
      ? asset.profile === 'lowpoly'
        ? 'Reconstruyendo y optimizando Low Poly'
        : 'Reconstruyendo el activo 3D'
      : mode === 'stl'
      ? 'Generando y validando la malla'
      : 'Generando la imagen de referencia';
    const updateProgress = () => {
      const elapsed = (Date.now() - startedAt) / 1000;
      const percent = elapsed <= estimatedSeconds
        ? Math.min(90, Math.round(3 + (elapsed / estimatedSeconds) * 87))
        : Math.min(97, Math.round(90 + ((elapsed - estimatedSeconds) / estimatedSeconds) * 7));
      setProgress({
        percent,
        label,
        remaining: elapsed < estimatedSeconds ? Math.ceil(estimatedSeconds - elapsed) : null,
      });
    };
    updateProgress();
    const timer = setInterval(updateProgress, 1000);
    return () => clearInterval(timer);
  }, [processing, installingEngine, installingModel, mode, asset.texture, asset.profile]);

  const imageModels = status.allModels.filter(isImageModel);
  const imageModelAvailable = imageModels.includes(imageModel);
  // Text/code models usable for parametric 3D generation.
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
    if (!hasInitImageModel.current && res.allModels?.length) {
      const availableImages = res.allModels.filter(isImageModel);
      const preferredImage = PREFERRED_IMAGE_MODELS.find((m) => availableImages.includes(m));
      if (preferredImage) {
        hasInitImageModel.current = true;
        setImageModel(preferredImage);
      }
    }
  }, []);

  useEffect(() => {
    checkStatus();
    const id = setInterval(checkStatus, 5000);
    return () => clearInterval(id);
  }, [checkStatus]);

  // Poll the local 3D server's health (only meaningful in image3d mode).
  useEffect(() => {
    let active = true;
    const ping = async () => {
      const r = await window.hunyuan.health();
      if (active) setHunyuanUp(!!r.up);
    };
    ping();
    const id = setInterval(ping, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  // --- Load persisted history on mount --------------------------------------
  useEffect(() => {
    window.ollama.loadHistory().then((items) => {
      if (Array.isArray(items)) setHistory(items.slice(0, MAX_HISTORY));
    });
  }, []);

  useEffect(() => {
    const unsubscribe = window.hunyuan.onProgress?.((payload) => {
      if (!payload) return;
      setProgress((current) => ({
        ...current,
        percent: Number.isFinite(payload.percent) ? payload.percent : current.percent,
        label: payload.stage || current.label,
        remaining: payload.remaining ?? current.remaining,
      }));
    });
    return typeof unsubscribe === 'function' ? unsubscribe : undefined;
  }, []);

  useEffect(() => {
    if (mode !== 'image3d' || !image3dInput?.base64) {
      setAnalysis(null);
      setAnalysisLoading(false);
      return undefined;
    }
    let active = true;
    setAnalysisLoading(true);
    const timer = setTimeout(async () => {
      const res = await window.hunyuan.analyze({
        imageBase64: image3dInput.base64,
        category: modelCategory,
        backgroundMode,
      });
      if (!active) return;
      if (res.ok) {
        setAnalysis(res);
      } else {
        setAnalysis({
          status: 'No se pudo analizar',
          error: res.error || 'Diagnóstico no disponible.',
          actions: [],
        });
      }
      setAnalysisLoading(false);
    }, 220);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [mode, image3dInput?.base64, modelCategory, backgroundMode]);

  const persistHistory = useCallback((next) => {
    setHistory(next);
    window.ollama.saveHistory(next);
  }, []);

  // --- Generate (branches on mode) ------------------------------------------
  const handleGenerate = useCallback(async () => {
    // --- Image -> 3D mode (Hunyuan, no prompt) ---
    if (mode === 'image3d') {
      if (!image3dInput) {
        setError('Selecciona una imagen de referencia.');
        return;
      }
      setError(null);
      setGenerating(true);
      setProgress({ percent: 0, label: 'Enviando referencia…', remaining: null });
      const res = await window.hunyuan.generate3D({
        imageBase64: image3dInput.base64,
        steps: steps3d,
        octree: asset.octree,
        texture: asset.texture,
        targetFaces: asset.targetFaces,
        scale: asset.scale,
        profile: asset.profile,
        category: modelCategory,
        guidance: guidance3d,
        backgroundMode,
        subjectPadding,
      });
      if (!res.ok) {
        setGenerating(false);
        if (!res.cancelled) setError(res.error || 'Génération 3D échouée.');
        return;
      }
      setProgress({ percent: 100, label: 'Activo 3D completado', remaining: 0 });
      setGenerating(false);
      const entry = {
        id: `${Date.now()}-3d`,
        type: 'glb',
        glbBase64: res.glbBase64,
        glbPath: res.glbPath,
        faces: res.faces,
        duration: res.duration,
        reportPath: res.reportPath,
        qualityLevel: res.qualityLevel,
        qualityScore: res.qualityScore,
        qualityText: res.qualityText,
        steps: steps3d,
        textured: asset.texture,
        profile: asset.profile,
        targetFaces: asset.targetFaces,
        textureSize: asset.textureSize,
        scale: asset.scale,
        prompt: image3dInput.name, // shown as the label
        inputDataUrl: image3dInput.dataUrl,
        model: 'hunyuan3d-2.1-mlx',
        category: modelCategory,
        guidance: guidance3d,
        backgroundMode,
        createdAt: Date.now(),
        filePath: null,
      };
      setResult(entry);
      const { glbBase64, inputDataUrl, ...light } = entry;
      persistHistory([light, ...history].slice(0, MAX_HISTORY));
      return;
    }

    if (!prompt.trim()) {
      setError('Escribe una dirección creativa antes de generar.');
      return;
    }

    const usedSeed = params.seed;
    setError(null);
    setGenerating(true);

    if (mode === 'image') {
      const res = await window.ollama.generate({
        model: imageModel,
        prompt: prompt.trim(),
        width: params.width,
        height: params.height,
        steps: params.steps,
        seed: usedSeed,
      });
      if (!res.ok) {
        setGenerating(false);
        if (!res.cancelled) setError(res.error || 'No fue posible generar la imagen.');
        return;
      }
      setProgress({ percent: 100, label: 'Imagen completada', remaining: 0 });
      setGenerating(false);
      const entry = { id: `${Date.now()}-${usedSeed}`, type: 'image', image: res.image, prompt: prompt.trim(), model: imageModel, seed: usedSeed, width: params.width, height: params.height, steps: params.steps, duration: res.duration, createdAt: Date.now(), filePath: null };
      setResult(entry);
      persistHistory([entry, ...history].slice(0, MAX_HISTORY));
      return;
    }

    // --- Texto → 3D ---
    if (!stlModel) {
      setGenerating(false);
      setError('Selecciona un modelo de código para generar la malla.');
      return;
    }
    const res = await window.ollama.generateStl({
      model: stlModel,
      prompt: prompt.trim(),
      seed: usedSeed,
      profile: asset.profile,
      targetFaces: asset.targetFaces,
    });
    if (!res.ok) {
      setGenerating(false);
      if (!res.cancelled) setError(res.error || 'STL generation failed.');
      return;
    }
    setProgress({ percent: 100, label: 'Malla completada', remaining: 0 });
    setGenerating(false);
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
      profile: asset.profile,
      targetFaces: asset.targetFaces,
      textureSize: asset.textureSize,
      scale: asset.scale,
      createdAt: Date.now(),
      filePath: null,
    };
    setResult(entry);
    // Store everything except the heavy inline STL text.
    const { stl, ...lightEntry } = entry;
    persistHistory([lightEntry, ...history].slice(0, MAX_HISTORY));
  }, [
    prompt,
    mode,
    params,
    stlModel,
    imageModel,
    image3dInput,
    steps3d,
    asset,
    modelCategory,
    guidance3d,
    backgroundMode,
    subjectPadding,
    history,
    persistHistory,
  ]);

  const handleCancel = useCallback(() => {
    if (mode === 'image3d') window.hunyuan.cancel3D();
    else window.ollama.cancel();
  }, [mode]);

  // --- Save (branches on type) ----------------------------------------------
  const handleSave = useCallback(async () => {
    if (!result) return null;
    let filePath;
    if (result.type === 'glb') {
      filePath = await window.hunyuan.saveGlb({
        srcPath: result.glbPath,
        base64: result.glbBase64,
        filename: timestampName(result.faces || 'model', 'glb'),
      });
    } else if (result.type === 'stl') {
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

  // For a glb (Hunyuan) result: convert to a printable STL (server-side scale
  // to 60mm) then save it to ~/Documents/OllamaImageStudio/.
  const handleSaveStl3d = useCallback(async () => {
    if (!result || result.type !== 'glb') return null;
    if (result.qualityLevel === 'critico') {
      setError('La calidad del modelo es crítica; corrige la entrada antes de exportar STL.');
      return null;
    }
    const conv = await window.hunyuan.convertStl({
      glbPath: result.glbPath,
      targetMm: stlMm,
    });
    if (!conv.ok) {
      setError(conv.error || 'Conversion STL échouée.');
      return null;
    }
    const dest = await window.hunyuan.saveGlb({
      srcPath: conv.stl_path,
      filename: timestampName(result.faces || 'model', 'stl'),
    });
    return { path: dest, dims: conv.dims_mm };
  }, [result, stlMm]);

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
    if (entry.type === 'glb') {
      setMode('image3d');
      const glbBase64 =
        entry.glbBase64 || (await window.hunyuan.readGlb(entry.glbPath));
      setResult({ ...entry, glbBase64 });
      return;
    }
    setPrompt(entry.prompt);
    setMode(entry.type === 'stl' ? 'stl' : 'image');
    if (entry.type === 'stl') {
      setStlModel(entry.model);
      // STL text isn't kept in history — read it back from the cache file.
      const stl = entry.stl || (await window.ollama.readStl(entry.stlPath));
      setResult({ ...entry, stl });
    } else {
      setParams({ width: entry.width, height: entry.height, steps: entry.steps, seed: entry.seed });
      setResult(entry);
    }
  }, []);

  const handlePickImage = useCallback(async () => {
    const img = await window.hunyuan.pickImage();
    if (img) setImage3dInput(img);
  }, []);

  const handleDropImage = useCallback((file) => {
    if (!file?.type?.startsWith('image/')) {
      setError('Arrastra un archivo PNG, JPG o WEBP válido.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      setImage3dInput({ name: file.name, dataUrl, base64: dataUrl.split(',')[1] });
      setMode('image3d');
      setError(null);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleInstallEngine = useCallback(async () => {
    setInstallingEngine(true);
    setError(null);
    const res = await window.hunyuan.install();
    if (!res.ok) {
      setInstallingEngine(false);
      setError(res.error || 'No fue posible instalar el motor 3D.');
      return;
    }
    setProgress({ percent: 100, label: 'Motor 3D instalado', remaining: 0 });
    setInstallingEngine(false);
    checkStatus();
    setTimeout(() => window.hunyuan.health().then((r) => setHunyuanUp(!!r.up)), 1500);
  }, [checkStatus]);

  const handleInstallImageModel = useCallback(async () => {
    const model = 'x/flux2-klein';
    setInstallingModel(true);
    setError(null);
    const res = await window.ollama.pullModel(model);
    if (!res.ok) {
      setInstallingModel(false);
      setError(res.error || 'No fue posible instalar el modelo de imagen.');
      return;
    }
    setProgress({ percent: 100, label: 'Modelo de imagen instalado', remaining: 0 });
    setImageModel('x/flux2-klein:latest');
    setInstallingModel(false);
    checkStatus();
  }, [checkStatus]);

  useEffect(() => {
    if (
      mode === 'image3d' &&
      !hunyuanUp &&
      !installingEngine &&
      !hasAttemptedEngineBootstrap.current
    ) {
      hasAttemptedEngineBootstrap.current = true;
      handleInstallEngine();
    }
  }, [mode, hunyuanUp, installingEngine, handleInstallEngine]);

  const handleUseImageAsReference = useCallback(() => {
    if (!result?.image) return;
    setImage3dInput({
      name: `referencia-${result.id}.png`,
      base64: result.image,
      dataUrl: `data:image/png;base64,${result.image}`,
    });
    setMode('image3d');
    setError(null);
  }, [result]);

  const handleSelectUseCase = useCallback((id) => {
    const recipe = USE_CASES[id];
    const category = MODEL_CATEGORIES[recipe.category];
    const profile = XR_PROFILES[recipe.profile];
    setUseCase(id);
    setModelCategory(recipe.category);
    setMode(recipe.mode);
    setAsset({ ...profile, profile: recipe.profile, octree: category.octree, scale: recipe.scale });
    setSteps3d(category.steps);
    setGuidance3d(category.guidance);
    setBackgroundMode(category.backgroundMode);
    setSubjectPadding(category.padding);
    setStlMm(recipe.stlMm);
    setPrompt(recipe.prompt);
    if (recipe.mode === 'image') {
      setParams((current) => ({ ...current, width: 1024, height: 1024, steps: 12 }));
    }
    setError(null);
  }, []);

  const handleSelectModelCategory = useCallback((id) => {
    const category = MODEL_CATEGORIES[id];
    const profile = XR_PROFILES[category.profile];
    setModelCategory(id);
    setAsset({ ...profile, profile: category.profile, octree: category.octree, targetFaces: category.targetFaces, scale: category.scale });
    setSteps3d(category.steps);
    setGuidance3d(category.guidance);
    setBackgroundMode(category.backgroundMode);
    setSubjectPadding(category.padding);
    setError(null);
  }, []);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-base text-neutral-200 before:pointer-events-none before:absolute before:inset-0 before:bg-[linear-gradient(rgba(82,215,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(82,215,255,0.025)_1px,transparent_1px)] before:bg-[size:42px_42px]">
      <Header status={status} onRefresh={checkStatus} />

      <div className="relative z-10 flex min-h-0 flex-1 gap-3 p-3">
        {/* Left: form */}
        <aside className="w-[380px] shrink-0 overflow-hidden rounded-[24px] border border-sky-200/10 bg-panel/65 shadow-[0_25px_70px_rgba(0,5,20,0.35)] backdrop-blur-xl">
          <PromptPanel
            connected={status.connected}
            useCase={useCase}
            onSelectUseCase={handleSelectUseCase}
            modelCategory={modelCategory}
            onSelectModelCategory={handleSelectModelCategory}
            mode={mode}
            setMode={setMode}
            imageModel={imageModel}
            imageModels={imageModels}
            setImageModel={setImageModel}
            imageModelAvailable={imageModelAvailable}
            installingModel={installingModel}
            onInstallImageModel={handleInstallImageModel}
            stlModels={stlModels}
            stlModel={stlModel}
            setStlModel={setStlModel}
            prompt={prompt}
            setPrompt={setPrompt}
            params={params}
            setParams={setParams}
            image3dInput={image3dInput}
            onPickImage={handlePickImage}
            onDropImage={handleDropImage}
            steps3d={steps3d}
            setSteps3d={setSteps3d}
            guidance3d={guidance3d}
            setGuidance3d={setGuidance3d}
            backgroundMode={backgroundMode}
            setBackgroundMode={setBackgroundMode}
            subjectPadding={subjectPadding}
            setSubjectPadding={setSubjectPadding}
            stlMm={stlMm}
            setStlMm={setStlMm}
            texture3d={texture3d}
            setTexture3d={setTexture3d}
            analysis={analysis}
            analysisLoading={analysisLoading}
            asset={asset}
            setAsset={setAsset}
            hunyuanUp={hunyuanUp}
            installingEngine={installingEngine}
            onInstallEngine={handleInstallEngine}
            generating={generating}
            progress={progress}
            onGenerate={handleGenerate}
            onCancel={handleCancel}
            randomSeed={randomSeed}
          />
        </aside>

        {/* Center: result */}
        <main className="min-w-0 flex-1 overflow-hidden rounded-[24px] border border-sky-200/10 bg-[#041023]/70 shadow-[0_25px_80px_rgba(0,4,18,0.4)] backdrop-blur-xl">
          <ImageViewer
            result={result}
            generating={generating}
            processing={processing}
            progress={progress}
            useCase={useCase}
            mode={mode}
            error={error}
            onSave={handleSave}
            onSaveStl={handleSaveStl3d}
            onCopyPrompt={handleCopyPrompt}
            onReveal={(p) => window.ollama.revealInFinder(p)}
            asset={asset}
            onUseAs3dReference={handleUseImageAsReference}
          />
        </main>

        {/* Right: gallery */}
        <aside className="w-[220px] shrink-0 overflow-hidden rounded-[24px] border border-sky-200/10 bg-panel/65 shadow-[0_25px_70px_rgba(0,5,20,0.3)] backdrop-blur-xl">
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
