import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header.jsx';
import PromptPanel from './components/PromptPanel.jsx';
import ImageViewer from './components/ImageViewer.jsx';
import Gallery from './components/Gallery.jsx';
import { XR_PROFILES } from './lib/xrProfiles.js';
import { USE_CASES } from './lib/useCases.js';
import { MODEL_CATEGORIES } from './lib/modelCategories.js';
import { getPipelineState } from './lib/pipelineStates.js';
import { enrichImagePrompt } from './lib/promptEnrichment.js';
import { estimateImage3dDelivery } from './lib/deliveryEstimates.js';
import { assetFilename, buildAssetName } from './lib/assetNaming.js';

const IMAGE_MODEL = 'x/z-image-turbo:latest';
const PREFERRED_IMAGE_MODELS = ['x/flux2-klein:latest', 'x/flux2-klein', IMAGE_MODEL];
const MAX_HISTORY = 20;
const PERSONAL_PRESETS_KEY = 'xrealityConvert.personalPresets.v1';

// Models we prefer for STL code generation, in order. Falls back to the first
// available text model if none of these are installed.
const PREFERRED_STL_MODELS = [
  'oMLX · gemma-4-12b-coder-fable5-composer2.5-4bit',
  'oMLX · gpt-oss-20b-MXFP4-Q8',
  'oMLX · qwen3-8b-4bit',
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
const isImageModel = (name) => !name.startsWith('oMLX · ') && /z-image|flux/i.test(name);

function recommendedAssetForCategory(id) {
  const category = MODEL_CATEGORIES[id] || MODEL_CATEGORIES.custom;
  const profile = XR_PROFILES[category.profile] || XR_PROFILES.xreal;
  return {
    ...profile,
    profile: category.profile,
    octree: category.octree,
    targetFaces: category.targetFaces,
    scale: category.scale,
  };
}

export default function App() {
  // --- Ollama connection state ---
  const [status, setStatus] = useState({
    connected: false,
    models: [],
    allModels: [],
    checking: true,
    error: null,
  });
  const [toolSnapshot, setToolSnapshot] = useState(null);
  const [toolsChecking, setToolsChecking] = useState(true);

  // --- Conversión: texto o imagen hacia un activo 3D ---
  const [mode, setMode] = useState('image3d');
  const [configMode, setConfigMode] = useState('essential');
  const [useCase, setUseCase] = useState('industrial');
  const [modelCategory, setModelCategory] = useState('industrial');
  const [manualOverrides, setManualOverrides] = useState(() => new Set());
  const [personalPresets, setPersonalPresets] = useState([]);

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
  const [pivot, setPivot] = useState('center');
  const [pivotCustom, setPivotCustom] = useState([0, 0, 0]);
  const [upAxis, setUpAxis] = useState('y');
  const [units, setUnits] = useState('m');
  const [stlMm, setStlMm] = useState(60); // target longest-axis size for STL export
  const [asset, setAsset] = useState({ profile: 'xreal', ...XR_PROFILES.xreal });
  const [hunyuanUp, setHunyuanUp] = useState(false);
  const [hunyuanHealth, setHunyuanHealth] = useState(null);
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
  const hasCheckedLocalTools = useRef(false);
  const processing = generating || installingEngine || installingModel;

  const resetOverrides = useCallback(() => setManualOverrides(new Set()), []);
  const clearOverrideKeys = useCallback((keys) => {
    setManualOverrides((current) => {
      const next = new Set(current);
      keys.forEach((key) => next.delete(key));
      return next;
    });
  }, []);
  const markOverride = useCallback((key) => {
    setManualOverrides((current) => {
      const next = new Set(current);
      next.add(key);
      return next;
    });
  }, []);

  const setManualBackgroundMode = useCallback((value) => {
    markOverride('background');
    setBackgroundMode(value);
  }, [markOverride]);

  const setManualSteps3d = useCallback((value) => {
    markOverride('steps');
    setSteps3d(value);
  }, [markOverride]);

  const setManualGuidance3d = useCallback((value) => {
    markOverride('guidance');
    setGuidance3d(value);
  }, [markOverride]);

  const setManualSubjectPadding = useCallback((value) => {
    markOverride('padding');
    setSubjectPadding(value);
  }, [markOverride]);

  const setManualPivot = useCallback((value) => {
    markOverride('delivery');
    setPivot(value);
  }, [markOverride]);

  const setManualPivotCustom = useCallback((index, value) => {
    markOverride('delivery');
    setPivotCustom((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)));
  }, [markOverride]);

  const setManualUpAxis = useCallback((value) => {
    markOverride('delivery');
    setUpAxis(value);
  }, [markOverride]);

  const setManualUnits = useCallback((value) => {
    markOverride('delivery');
    setUnits(value);
  }, [markOverride]);

  const setManualAsset = useCallback((updater) => {
    markOverride('asset');
    setAsset(updater);
  }, [markOverride]);

  const setManualParams = useCallback((updater) => {
    markOverride('imageParams');
    setParams(updater);
  }, [markOverride]);

  const applyRecommendedCategory = useCallback((id, { clearOverrides = true } = {}) => {
    const category = MODEL_CATEGORIES[id];
    setModelCategory(id);
    setAsset(recommendedAssetForCategory(id));
    setSteps3d(category.steps);
    setGuidance3d(category.guidance);
    setBackgroundMode(category.backgroundMode);
    setSubjectPadding(category.padding);
    if (clearOverrides) resetOverrides();
    setError(null);
  }, [resetOverrides]);

  const resetRecommendationSection = useCallback((section) => {
    const category = MODEL_CATEGORIES[modelCategory] || MODEL_CATEGORIES.custom;
    if (section === 'preparation') {
      setBackgroundMode(category.backgroundMode);
      setSubjectPadding(category.padding);
      clearOverrideKeys(['background', 'padding']);
    }
    if (section === 'reconstruction') {
      setSteps3d(category.steps);
      setGuidance3d(category.guidance);
      setAsset((current) => ({
        ...current,
        octree: category.octree,
        targetFaces: category.targetFaces,
      }));
      clearOverrideKeys(['steps', 'guidance', 'asset']);
    }
    if (section === 'delivery') {
      setPivot('center');
      setPivotCustom([0, 0, 0]);
      setUpAxis('y');
      setUnits('m');
      setAsset((current) => ({ ...current, scale: category.scale }));
      clearOverrideKeys(['delivery', 'asset']);
    }
    if (section === 'asset') {
      setAsset(recommendedAssetForCategory(modelCategory));
      setSteps3d(category.steps);
      clearOverrideKeys(['asset', 'steps']);
    }
    setError(null);
  }, [clearOverrideKeys, modelCategory]);

  const persistPersonalPresets = useCallback((items) => {
    setPersonalPresets(items);
    try {
      window.localStorage.setItem(PERSONAL_PRESETS_KEY, JSON.stringify(items));
    } catch {}
  }, []);

  const savePersonalPreset = useCallback((name) => {
    const cleanName = name.trim();
    if (!cleanName) return false;
    const preset = {
      id: `${Date.now()}-${cleanName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
      name: cleanName,
      mode,
      category: modelCategory,
      steps3d,
      guidance3d,
      backgroundMode,
      subjectPadding,
      pivot,
      pivotCustom,
      upAxis,
      units,
      asset,
      params,
      createdAt: Date.now(),
    };
    persistPersonalPresets([preset, ...personalPresets.filter((item) => item.name !== cleanName)].slice(0, 12));
    return true;
  }, [asset, backgroundMode, guidance3d, mode, modelCategory, params, persistPersonalPresets, personalPresets, pivot, pivotCustom, steps3d, subjectPadding, units, upAxis]);

  const applyPersonalPreset = useCallback((presetId) => {
    const preset = personalPresets.find((item) => item.id === presetId);
    if (!preset) return;
    setMode(preset.mode || 'image3d');
    setModelCategory(preset.category || 'custom');
    setSteps3d(preset.steps3d || 30);
    setGuidance3d(preset.guidance3d || MODEL_CATEGORIES[preset.category || 'custom'].guidance);
    setBackgroundMode(preset.backgroundMode || 'auto');
    setSubjectPadding(preset.subjectPadding || MODEL_CATEGORIES[preset.category || 'custom'].padding);
    setPivot(preset.pivot || 'center');
    setPivotCustom(Array.isArray(preset.pivotCustom) ? preset.pivotCustom : [0, 0, 0]);
    setUpAxis(preset.upAxis || 'y');
    setUnits(preset.units || 'm');
    setAsset(preset.asset || { profile: 'xreal', ...XR_PROFILES.xreal });
    setParams(preset.params || params);
    resetOverrides();
    setError(null);
  }, [params, personalPresets, resetOverrides]);

  const executionPlan = useCallback(() => {
    if (mode === 'image3d') {
      return [
        ['input', 'Entrada', image3dInput ? 'done' : 'active'],
        ['prepare', 'Preparación', generating && progress.percent < 15 ? 'active' : progress.percent >= 15 ? 'done' : 'pending'],
        ['engine', 'Motor MLX', generating && progress.percent >= 15 && progress.percent < 82 ? 'active' : progress.percent >= 82 ? 'done' : 'pending'],
        ['optimize', 'Optimización', generating && progress.percent >= 82 && progress.percent < 94 ? 'active' : progress.percent >= 94 ? 'done' : 'pending'],
        ['audit', 'Auditoría', result?.type === 'glb' ? 'done' : generating && progress.percent >= 94 ? 'active' : 'pending'],
        ['export', 'Exportación', result?.type === 'glb' ? 'active' : 'pending'],
      ];
    }
    if (mode === 'stl') {
      return [
        ['prompt', 'Dirección 3D', prompt.trim() ? 'done' : 'active'],
        ['reference', 'Referencia FLUX', generating && progress.percent < 12 ? 'active' : progress.percent >= 12 ? 'done' : 'pending'],
        ['engine', 'Hunyuan3D MLX', generating && progress.percent >= 12 && progress.percent < 94 ? 'active' : result?.type === 'glb' ? 'done' : 'pending'],
        ['audit', 'Auditoría GLB', result?.type === 'glb' ? 'done' : generating && progress.percent >= 94 ? 'active' : 'pending'],
      ];
    }
    return [
      ['prompt', 'Dirección', prompt.trim() ? 'done' : 'active'],
      ['model', 'Modelo visual', generating ? 'active' : result?.type === 'image' ? 'done' : 'pending'],
      ['reference', 'Referencia', result?.type === 'image' ? 'done' : 'pending'],
    ];
  }, [generating, image3dInput, mode, progress.percent, prompt, result?.type]);
  const deliveryEstimate = estimateImage3dDelivery({
    asset,
    analysis,
    textureEnabled: asset.texture,
  });

  useEffect(() => {
    if (!processing || ((mode === 'image3d' || mode === 'stl') && generating)) return undefined;
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
      ? 540
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
      ? 'Creando referencia y reconstruyendo con Hunyuan3D'
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
    const refreshWhenVisible = () => {
      if (!document.hidden) checkStatus();
    };
    refreshWhenVisible();
    const id = setInterval(refreshWhenVisible, 5000);
    document.addEventListener('visibilitychange', refreshWhenVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', refreshWhenVisible);
    };
  }, [checkStatus]);

  const checkLocalTools = useCallback(async (force = false) => {
    setToolsChecking(true);
    try {
      const snapshot = await window.localTools.list({ force });
      setToolSnapshot(snapshot);
    } catch {
      setToolSnapshot(null);
    } finally {
      setToolsChecking(false);
    }
  }, []);

  useEffect(() => {
    if (hasCheckedLocalTools.current) return;
    hasCheckedLocalTools.current = true;
    checkLocalTools();
  }, [checkLocalTools]);

  // Poll the local 3D server's health (only meaningful in image3d mode).
  useEffect(() => {
    let active = true;
    const ping = async () => {
      if (document.hidden) return;
      const r = await window.hunyuan.health();
      if (active) {
        setHunyuanUp(!!r.up);
        setHunyuanHealth(r);
      }
    };
    ping();
    const id = setInterval(ping, 5000);
    document.addEventListener('visibilitychange', ping);
    return () => {
      active = false;
      clearInterval(id);
      document.removeEventListener('visibilitychange', ping);
    };
  }, []);

  // --- Load persisted history on mount --------------------------------------
  useEffect(() => {
    window.ollama.loadHistory().then((items) => {
      if (Array.isArray(items)) setHistory(items.slice(0, MAX_HISTORY));
    });
  }, []);

  useEffect(() => {
    try {
      const items = JSON.parse(window.localStorage.getItem(PERSONAL_PRESETS_KEY) || '[]');
      if (Array.isArray(items)) setPersonalPresets(items.slice(0, 12));
    } catch {
      setPersonalPresets([]);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = window.hunyuan.onProgress?.((payload) => {
      if (!payload) return;
      const state = getPipelineState(payload.state);
      setProgress((current) => ({
        ...current,
        percent: Number.isFinite(payload.percent) ? payload.percent : current.percent,
        label: payload.stage || state?.label || current.label,
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
        textureSize: asset.textureSize,
        targetFaces: asset.targetFaces,
        scale: asset.scale,
        profile: asset.profile,
        category: modelCategory,
        guidance: guidance3d,
        backgroundMode,
        subjectPadding,
        pivot,
        pivotCustom,
        upAxis,
        units,
      });
      if (!res.ok) {
        setGenerating(false);
        if (!res.cancelled) setError(res.error || 'Génération 3D échouée.');
        return;
      }
      setProgress({ percent: 100, label: 'Activo 3D completado', remaining: 0 });
      setGenerating(false);
      const createdAt = Date.now();
      const assetName = buildAssetName({
        sourceName: image3dInput.name,
        category: modelCategory,
        profile: asset.profile,
        createdAt,
      });
      const entry = {
        id: `${createdAt}-3d`,
        type: 'glb',
        assetName,
        glbBase64: res.glbBase64,
        glbPath: res.glbPath,
        lodPaths: res.lodPaths,
        faces: res.faces,
        duration: res.duration,
        reportPath: res.reportPath,
        qualityLevel: res.qualityLevel,
        qualityScore: res.qualityScore,
        qualityText: res.qualityText,
        steps: steps3d,
        textured: res.textureApplied,
        textureRequested: res.textureRequested ?? asset.texture,
        textureReport: res.textureReport,
        shapeGlbPath: res.shapeGlbPath,
        profile: asset.profile,
        targetFaces: asset.targetFaces,
        textureSize: res.textureSize || asset.textureSize,
        scale: asset.scale,
        prompt: image3dInput.name, // shown as the label
        inputDataUrl: image3dInput.dataUrl,
        model: 'hunyuan3d-2.1-mlx',
        category: modelCategory,
        guidance: guidance3d,
        backgroundMode,
        pivot: res.pivot || pivot,
        pivotCustom: res.pivotCustom || pivotCustom,
        upAxis: res.upAxis || upAxis,
        units: res.units || units,
        createdAt,
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
      const enrichedPrompt = enrichImagePrompt(prompt, modelCategory);
      const res = await window.ollama.generate({
        model: imageModel,
        prompt: enrichedPrompt,
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
      const createdAt = Date.now();
      const assetName = buildAssetName({
        prompt: prompt.trim(),
        category: modelCategory,
        profile: asset.profile,
        createdAt,
      });
      const entry = { id: `${createdAt}-${usedSeed}`, type: 'image', assetName, image: res.image, prompt: prompt.trim(), enrichedPrompt, category: modelCategory, profile: asset.profile, model: imageModel, seed: usedSeed, width: params.width, height: params.height, steps: params.steps, duration: res.duration, createdAt, filePath: null };
      setResult(entry);
      persistHistory([entry, ...history].slice(0, MAX_HISTORY));
      return;
    }

    // --- Texto → referencia → Hunyuan3D ---
    if (!imageModelAvailable) {
      setGenerating(false);
      setError('Instala o selecciona FLUX para crear la referencia 3D.');
      return;
    }
    if (!hunyuanUp) {
      setGenerating(false);
      setError('Inicializa Hunyuan3D MLX antes de modelar.');
      return;
    }
    setProgress({ percent: 2, label: 'Creando referencia limpia con FLUX', remaining: null });
    const enrichedPrompt = enrichImagePrompt(prompt, modelCategory);
    const reference = await window.ollama.generate({
      model: imageModel,
      prompt: enrichedPrompt,
      width: params.width,
      height: params.height,
      steps: params.steps,
      seed: usedSeed,
    });
    if (!reference.ok) {
      setGenerating(false);
      if (!reference.cancelled) setError(reference.error || 'No fue posible crear la referencia 3D.');
      return;
    }
    setProgress({ percent: 12, label: 'Referencia lista · iniciando Hunyuan3D', remaining: null });
    const res = await window.hunyuan.generate3D({
      imageBase64: reference.image,
      steps: steps3d,
      octree: asset.octree,
      texture: asset.texture,
      textureSize: asset.textureSize,
      targetFaces: asset.targetFaces,
      scale: asset.scale,
      profile: asset.profile,
      category: modelCategory,
      guidance: guidance3d,
      backgroundMode: 'remove',
      subjectPadding,
      pivot,
      pivotCustom,
      upAxis,
      units,
    });
    if (!res.ok) {
      setGenerating(false);
      if (!res.cancelled) setError(res.error || 'Hunyuan3D no pudo reconstruir la referencia.');
      return;
    }
    setProgress({ percent: 100, label: 'Activo 3D completado', remaining: 0 });
    setGenerating(false);
    const createdAt = Date.now();
    const assetName = buildAssetName({
      prompt: prompt.trim(),
      category: modelCategory,
      profile: asset.profile,
      createdAt,
    });
    const entry = {
      id: `${createdAt}-3d`,
      type: 'glb',
      assetName,
      glbBase64: res.glbBase64,
      glbPath: res.glbPath,
      lodPaths: res.lodPaths,
      faces: res.faces,
      reportPath: res.reportPath,
      qualityLevel: res.qualityLevel,
      qualityScore: res.qualityScore,
      qualityText: res.qualityText,
      prompt: prompt.trim(),
      enrichedPrompt,
      inputDataUrl: `data:image/png;base64,${reference.image}`,
      model: 'hunyuan3d-2.1-mlx',
      referenceModel: imageModel,
      seed: usedSeed,
      duration: res.duration,
      steps: steps3d,
      textured: res.textureApplied,
      textureRequested: res.textureRequested ?? asset.texture,
      textureReport: res.textureReport,
      shapeGlbPath: res.shapeGlbPath,
      profile: asset.profile,
      category: modelCategory,
      targetFaces: asset.targetFaces,
      textureSize: res.textureSize || asset.textureSize,
      scale: asset.scale,
      guidance: guidance3d,
      backgroundMode: 'remove',
      pivot: res.pivot || pivot,
      pivotCustom: res.pivotCustom || pivotCustom,
      upAxis: res.upAxis || upAxis,
      units: res.units || units,
      createdAt,
      filePath: null,
    };
    setResult(entry);
    const { glbBase64, inputDataUrl, ...lightEntry } = entry;
    persistHistory([lightEntry, ...history].slice(0, MAX_HISTORY));
  }, [
    prompt,
    mode,
    params,
    stlModel,
    imageModel,
    imageModelAvailable,
    image3dInput,
    steps3d,
    asset,
    modelCategory,
    guidance3d,
    backgroundMode,
    subjectPadding,
    pivot,
    pivotCustom,
    upAxis,
    units,
    hunyuanUp,
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
        filename: assetFilename(result.assetName || timestampName(result.faces || 'model', 'glb'), 'glb'),
      });
    } else if (result.type === 'stl') {
      const data = result.stl || (await window.ollama.readStl(result.stlPath));
      if (!data) return null;
      filePath = await window.ollama.saveStl(data, assetFilename(result.assetName || timestampName(result.seed, 'stl'), 'stl'));
    } else {
      filePath = await window.ollama.saveImage(
        result.image,
        assetFilename(result.assetName || timestampName(result.seed, 'png'), 'png')
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
      setError(conv.error || 'Falló la conversión a STL.');
      return null;
    }
    const dest = await window.hunyuan.saveGlb({
      srcPath: conv.stl_path,
      filename: assetFilename(result.assetName ? `${result.assetName}-print` : timestampName(result.faces || 'model', 'stl'), 'stl'),
    });
    return { path: dest, dims: conv.dims_mm };
  }, [result, stlMm]);

  const handleTextureGlb = useCallback(async () => {
    if (!result || result.type !== 'glb') return false;
    if (!result.inputDataUrl) {
      setError('Para texturizar este GLB necesito la referencia original en esta sesión.');
      return false;
    }
    setError(null);
    setGenerating(true);
    setProgress({ percent: 94, label: `Texturizando GLB con Paint ${asset.textureSize || '2K'}`, remaining: null });
    const imageBase64 = result.inputDataUrl.split(',')[1] || result.inputDataUrl;
    const tex = await window.hunyuan.textureGlb({
      glbPath: result.shapeGlbPath || result.glbPath,
      imageBase64,
      textureSize: asset.textureSize === '1K' ? '1K' : '2K',
    });
    setGenerating(false);
    if (!tex.ok || !tex.textureApplied) {
      setError(tex.error || 'Paint MLX no produjo una textura PBR valida.');
      return false;
    }
    const updated = {
      ...result,
      shapeGlbBase64: result.shapeGlbBase64 || result.glbBase64,
      shapeGlbPath: result.shapeGlbPath || result.glbPath,
      glbBase64: tex.glbBase64,
      glbPath: tex.glbPath,
      textured: true,
      textureRequested: true,
      textureSize: tex.textureSize,
      textureReport: tex.textureReport,
    };
    setResult(updated);
    const { glbBase64, shapeGlbBase64, inputDataUrl, ...light } = updated;
    persistHistory([light, ...history.filter((item) => item.id !== updated.id)].slice(0, MAX_HISTORY));
    return true;
  }, [asset.textureSize, history, persistHistory, result]);

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
    resetOverrides();
    if (recipe.mode === 'image') {
      setParams((current) => ({ ...current, width: 1024, height: 1024, steps: 12 }));
    }
    setError(null);
  }, [resetOverrides]);

  const handleSelectModelCategory = useCallback((id) => {
    applyRecommendedCategory(id);
  }, [applyRecommendedCategory]);

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-base text-neutral-200 before:pointer-events-none before:absolute before:inset-0 before:bg-[linear-gradient(rgba(82,215,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(82,215,255,0.025)_1px,transparent_1px)] before:bg-[size:42px_42px]">
      <Header
        status={status}
        onRefresh={checkStatus}
        toolSnapshot={toolSnapshot}
        toolsChecking={toolsChecking}
        onToolsRefresh={() => checkLocalTools(true)}
      />

      <div className="relative z-10 grid min-h-0 flex-1 grid-cols-[minmax(300px,340px)_minmax(0,1fr)] gap-2 p-2 xl:grid-cols-[380px_minmax(0,1fr)_220px] xl:gap-3 xl:p-3">
        {/* Left: form */}
        <aside className="min-w-0 overflow-hidden rounded-[20px] border border-sky-200/10 bg-panel/65 shadow-[0_25px_70px_rgba(0,5,20,0.35)] backdrop-blur-xl xl:rounded-[24px]">
          <PromptPanel
            connected={status.connected}
            useCase={useCase}
            onSelectUseCase={handleSelectUseCase}
            modelCategory={modelCategory}
            onSelectModelCategory={handleSelectModelCategory}
            configMode={configMode}
            setConfigMode={setConfigMode}
            manualOverrides={manualOverrides}
            onResetRecommendations={() => applyRecommendedCategory(modelCategory)}
            onResetRecommendationSection={resetRecommendationSection}
            personalPresets={personalPresets}
            onSavePersonalPreset={savePersonalPreset}
            onApplyPersonalPreset={applyPersonalPreset}
            executionPlan={executionPlan()}
            deliveryEstimate={deliveryEstimate}
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
            setParams={setManualParams}
            image3dInput={image3dInput}
            onPickImage={handlePickImage}
            onDropImage={handleDropImage}
            steps3d={steps3d}
            setSteps3d={setManualSteps3d}
            guidance3d={guidance3d}
            setGuidance3d={setManualGuidance3d}
            backgroundMode={backgroundMode}
            setBackgroundMode={setManualBackgroundMode}
            subjectPadding={subjectPadding}
            setSubjectPadding={setManualSubjectPadding}
            pivot={pivot}
            setPivot={setManualPivot}
            pivotCustom={pivotCustom}
            setPivotCustom={setManualPivotCustom}
            upAxis={upAxis}
            setUpAxis={setManualUpAxis}
            units={units}
            setUnits={setManualUnits}
            stlMm={stlMm}
            setStlMm={setStlMm}
            analysis={analysis}
            analysisLoading={analysisLoading}
            asset={asset}
            setAsset={setManualAsset}
            hunyuanUp={hunyuanUp}
            hunyuanHealth={hunyuanHealth}
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
        <main className="min-w-0 overflow-hidden rounded-[20px] border border-sky-200/10 bg-[#041023]/70 shadow-[0_25px_80px_rgba(0,4,18,0.4)] backdrop-blur-xl xl:rounded-[24px]">
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
            onTextureGlb={handleTextureGlb}
            onCopyPrompt={handleCopyPrompt}
            onReveal={(p) => window.ollama.revealInFinder(p)}
            asset={asset}
            onUseAs3dReference={handleUseImageAsReference}
          />
        </main>

        {/* Right: gallery */}
        <aside className="hidden min-w-0 overflow-hidden rounded-[24px] border border-sky-200/10 bg-panel/65 shadow-[0_25px_70px_rgba(0,5,20,0.3)] backdrop-blur-xl xl:block">
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
