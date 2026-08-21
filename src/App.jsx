import React, { useState, useEffect, useCallback, useRef } from 'react';
import Header from './components/Header.jsx';
import PromptPanel from './components/PromptPanel.jsx';
import ImageViewer from './components/ImageViewer.jsx';
import Gallery from './components/Gallery.jsx';
import JobsIveDesignReviewModal from './components/JobsIveDesignReviewModal.jsx';
import CommandPalette from './components/CommandPalette.jsx';
import { XR_PROFILES } from './lib/xrProfiles.js';
import { USE_CASES } from './lib/useCases.js';
import { MODEL_CATEGORIES } from './lib/modelCategories.js';
import { sounds } from './lib/soundEffects.js';

const IMAGE_MODEL = 'x/z-image-turbo:latest';
const PREFERRED_IMAGE_MODELS = ['x/flux2-klein:latest', 'x/flux2-klein', IMAGE_MODEL];
const MAX_HISTORY = 20;

function resolveAssetPreset(category, profileId) {
  const profile = XR_PROFILES[profileId];
  const semanticDefault = profileId === category.profile;
  return {
    ...profile,
    profile: profileId,
    octree: semanticDefault ? category.octree : Math.min(category.octree, profile.octree),
    targetFaces: semanticDefault ? category.targetFaces : Math.min(category.targetFaces, profile.targetFaces),
    texture: false,
    textureSize: semanticDefault ? category.textureSize || profile.textureSize : profile.textureSize,
    paintBackend: semanticDefault ? category.paintBackend || profile.paintBackend : profile.paintBackend,
  };
}

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
  const [multiViewInputs, setMultiViewInputs] = useState({});
  const [multiViewBackend, setMultiViewBackend] = useState(null);
  const [steps3d, setSteps3d] = useState(30);
  const [guidance3d, setGuidance3d] = useState(MODEL_CATEGORIES.industrial.guidance);
  const [backgroundMode, setBackgroundMode] = useState('auto');
  const [subjectPadding, setSubjectPadding] = useState(MODEL_CATEGORIES.industrial.padding);
  const [stlMm, setStlMm] = useState(60); // target longest-axis size for STL export
  const [asset, setAsset] = useState({ profile: 'xreal', ...XR_PROFILES.xreal, texture: true });
  const [hunyuanUp, setHunyuanUp] = useState(false);
  const [installingEngine, setInstallingEngine] = useState(false);
  const [installingModel, setInstallingModel] = useState(false);

  // --- Motor Selector & Meshy API Cloud ---
  const [engineProvider, setEngineProvider] = useState('local'); // 'local' | 'meshy'
  const [meshyApiKey, setMeshyApiKey] = useState('');
  const [meshyMode, setMeshyMode] = useState('preview'); // 'preview' | 'refine'
  const [meshyTopology, setMeshyTopology] = useState('quad');
  const [meshyTargetPolycount, setMeshyTargetPolycount] = useState(12000);
  const [meshyPreviewTaskId, setMeshyPreviewTaskId] = useState('');
  const [meshyAiModel, setMeshyAiModel] = useState('latest');
  const [meshyUltraMode, setMeshyUltraMode] = useState(false);
  const [meshyTextureResolution, setMeshyTextureResolution] = useState('2k');
  const [meshyShouldTexture, setMeshyShouldTexture] = useState(true);

  // --- Generation state ---
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState({ percent: 0, label: 'Preparando…', remaining: null });
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // --- Gallery & Modals & Preferences ---
  const [history, setHistory] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [showJobsReviewModal, setShowJobsReviewModal] = useState(false);
  const [lang, setLang] = useState(localStorage.getItem('xr_lang') || 'es');
  const [soundMuted, setSoundMuted] = useState(sounds.isMuted());
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [externalAction, setExternalAction] = useState(null);

  const handleToggleSound = useCallback(() => {
    const muted = sounds.toggleMute();
    setSoundMuted(muted);
  }, []);

  const handleSetLang = useCallback((nextLang) => {
    setLang(nextLang);
    localStorage.setItem('xr_lang', nextLang);
  }, []);

  // Global Keyboard Shortcuts Listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isInput = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable;

      // Cmd+K or Ctrl+K -> Command Palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen((open) => !open);
        return;
      }

      if (isInput) return; // Do not trigger shortcuts when typing

      if (e.key === ' ' || e.code === 'Space') {
        e.preventDefault();
        setExternalAction({ type: 'camera', payload: 'toggle_turntable' });
      } else if (e.key === '1') {
        setExternalAction({ type: 'camera', payload: 'front' });
      } else if (e.key === '2') {
        setExternalAction({ type: 'camera', payload: 'right' });
      } else if (e.key === '3') {
        setExternalAction({ type: 'camera', payload: 'back' });
      } else if (e.key === '4') {
        setExternalAction({ type: 'camera', payload: 'left' });
      } else if (e.key === '5') {
        setExternalAction({ type: 'camera', payload: 'top' });
      } else if (e.key === '6') {
        setExternalAction({ type: 'camera', payload: 'bottom' });
      } else if (e.key === '0') {
        setExternalAction({ type: 'camera', payload: 'iso' });
      } else if (e.key.toLowerCase() === 'w') {
        setExternalAction({ type: 'shading', payload: 'wireframe' });
      } else if (e.key.toLowerCase() === 'c') {
        setExternalAction({ type: 'shading', payload: 'clay' });
      } else if (e.key.toLowerCase() === 'p') {
        setExternalAction({ type: 'shading', payload: 'lit' });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (window.meshy?.getApiKey) {
      window.meshy.getApiKey().then((key) => {
        if (key) setMeshyApiKey(key);
      });
    }
  }, []);

  const hasInitStlModel = useRef(false);
  const hasInitImageModel = useRef(false);
  const hasAttemptedEngineBootstrap = useRef(false);
  const processing = generating || installingEngine || installingModel;

  useEffect(() => {
    if (!processing || engineProvider === 'meshy') return undefined;
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
        : Math.min(98, Math.round(90 + ((elapsed - estimatedSeconds) / Math.max(estimatedSeconds * 0.8, 20)) * 8));
      setProgress((curr) => ({
        percent: Math.max(curr.percent || 0, percent),
        label: curr.label || label,
        remaining: elapsed < estimatedSeconds ? Math.ceil(estimatedSeconds - elapsed) : Math.max(1, Math.ceil((100 - (curr.percent || percent)) * 0.6)),
      }));
    };
    updateProgress();
    const timer = setInterval(updateProgress, 1000);
    return () => clearInterval(timer);
  }, [processing, engineProvider, installingEngine, installingModel, mode, asset.texture, asset.profile]);

  const imageModels = status.allModels.filter(isImageModel);
  const imageModelAvailable = imageModels.includes(imageModel);
  // Text/code models usable for parametric 3D generation.
  const stlModels = status.allModels.filter((m) => !isImageModel(m));

  // --- Status polling --------------------------------------------------------
  const checkStatus = useCallback(async () => {
    try {
      const res = await window.ollama?.checkStatus?.();
      if (!res) return;
      setStatus({
        connected: !!res.connected,
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
    } catch (err) {
      console.warn('checkStatus failed:', err);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const inspect = async () => {
      try {
        const status = await window.hunyuan?.multiViewStatus?.();
        if (active && status) setMultiViewBackend(status);
      } catch (err) {
        console.warn('multiViewStatus failed:', err);
      }
    };
    inspect();
    return () => { active = false; };
  }, [hunyuanUp]);

  useEffect(() => {
    checkStatus();
    const tick = () => {
      if (!document.hidden) checkStatus();
    };
    const id = setInterval(tick, 5000);
    document.addEventListener('visibilitychange', tick);
    return () => {
      clearInterval(id);
      document.removeEventListener('visibilitychange', tick);
    };
  }, [checkStatus]);

  // Poll the local 3D server's health (only meaningful in image3d mode).
  useEffect(() => {
    let active = true;
    const ping = async () => {
      try {
        const r = await window.hunyuan?.health?.();
        if (active && r) setHunyuanUp(!!r.up);
      } catch (err) {
        if (active) setHunyuanUp(false);
      }
    };
    ping();
    const visiblePing = () => {
      if (!document.hidden) ping();
    };
    const id = setInterval(visiblePing, 5000);
    document.addEventListener('visibilitychange', visiblePing);
    return () => {
      active = false;
      clearInterval(id);
      document.removeEventListener('visibilitychange', visiblePing);
    };
  }, []);

  // --- Load persisted history on mount --------------------------------------
  useEffect(() => {
    try {
      window.ollama?.loadHistory?.().then((items) => {
        if (Array.isArray(items)) setHistory(items.slice(0, MAX_HISTORY));
      }).catch((e) => console.warn('loadHistory rejected:', e));
    } catch (err) {
      console.warn('loadHistory failed:', err);
    }
  }, []);

  useEffect(() => {
    const unsubscribe = window.hunyuan.onProgress?.((payload) => {
      if (!payload) return;
      setProgress((current) => ({
        ...current,
        percent: Number.isFinite(payload.percent) ? Math.max(current.percent || 0, payload.percent) : current.percent,
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
    if (generating) return;
    // --- Meshy Cloud API Mode (for 3D generation modes) ---
    if (engineProvider === 'meshy' && mode !== 'image') {
      if (!image3dInput && !prompt.trim()) {
        setError('Selecciona una imagen de referencia o escribe un prompt para generar con Meshy API.');
        return;
      }
      if (!meshyApiKey) {
        setError('Ingresa tu API Key de Meshy en el panel de configuración.');
        return;
      }
      setError(null);
      setGenerating(true);
      setProgress({ percent: 1, label: 'Enviando solicitud a Meshy Cloud API…', remaining: null });

      let res;
      try {
        let imageUrls = undefined;
        if (image3dInput && Object.keys(multiViewInputs).length > 0) {
          imageUrls = [
            `data:image/png;base64,${image3dInput.base64}`,
            ...Object.values(multiViewInputs).map(img => `data:image/png;base64,${img.base64}`)
          ].slice(0, 4);
        }

        res = await window.meshy.generate3D({
          apiKey: meshyApiKey,
          mode: meshyMode,
          prompt: prompt.trim() || image3dInput?.name || 'Game ready asset',
          imageBase64: imageUrls ? undefined : image3dInput?.base64,
          image_urls: imageUrls,
          preview_task_id: meshyMode === 'refine' ? meshyPreviewTaskId : undefined,
          art_style: 'realistic',
          topology: meshyTopology,
          target_polycount: meshyTargetPolycount,
          originAt: 'bottom',
          autoSize: true,
          removeLighting: true,
          ai_model: meshyAiModel,
          ultra_mode: meshyUltraMode,
          texture_resolution: meshyTextureResolution,
          should_texture: meshyShouldTexture,
        });
      } catch (genError) {
        setGenerating(false);
        setError(`Error en Meshy Cloud API: ${genError?.message || genError}`);
        return;
      }

      if (!res.ok) {
        setGenerating(false);
        setError(res.error || 'Generación fallida en Meshy Cloud.');
        return;
      }

      setProgress({ percent: 100, label: 'Activo 3D Meshy completado', remaining: 0 });
      setGenerating(false);

      if (res.taskId) {
        setMeshyPreviewTaskId(res.previewTaskId || res.taskId);
      }

      const entry = {
        id: `${Date.now()}-meshy`,
        type: 'glb',
        taskId: res.taskId,
        previewTaskId: res.previewTaskId || res.taskId,
        glbBase64: res.glbBase64,
        glbPath: res.glbPath,
        modelUrls: res.modelUrls,
        textureUrls: res.textureUrls,
        faces: res.faces,
        duration: res.duration,
        textured: res.textured !== false,
        textureSize: res.textureResolution ? res.textureResolution.toUpperCase() : 'PBR 2K',
        profile: meshyTopology === 'quad' ? 'lowpoly' : asset.profile,
        targetFaces: meshyTargetPolycount,
        prompt: prompt.trim() || image3dInput?.name || 'Meshy Asset',
        inputDataUrl: image3dInput?.dataUrl,
        model: `Meshy API v7 (${res.mode})`,
        provider: 'meshy',
        createdAt: Date.now(),
        filePath: null,
      };

      setResult(entry);
      const { glbBase64, inputDataUrl, ...light } = entry;
      persistHistory([light, ...history].slice(0, MAX_HISTORY));
      return;
    }

    // --- Image -> 3D mode (Hunyuan, no prompt) ---
    if (mode === 'image3d') {

      if (!image3dInput) {
        setError('Selecciona una imagen de referencia.');
        return;
      }
      const views = [{ viewId: 'front', base64: image3dInput.base64 }, ...Object.entries(multiViewInputs).map(([viewId, image]) => ({ viewId, base64: image.base64 }))];
      if (views.length > 1) {
        const admission = await window.hunyuan.admitMultiView({ views, profile: asset.profile });
        if (!admission.ok || !admission.admission?.passed) {
          setError(admission.error || 'Completa las seis vistas antes de solicitar la ruta multi-vista.');
          return;
        }
      }
      setError(null);
      setGenerating(true);
      setProgress({ percent: 1, label: 'Verificando motor local…', remaining: null });
      let res;
      try {
        const multiViewImages = Object.fromEntries(Object.entries(multiViewInputs).map(([viewId, image]) => [viewId, image.base64]));
        res = await window.hunyuan.generate3D({
          imageBase64: image3dInput.base64,
          multiViewImages,
          useMultiviewShape: views.length === 6 && multiViewBackend?.available === true,
          steps: steps3d,
          octree: asset.octree,
          texture: asset.texture,
          textureSize: asset.textureSize,
          paintBackend: asset.paintBackend || 'fast',
          materialHint: asset.materialHint || 'auto',
          targetFaces: asset.targetFaces,
          scale: asset.scale,
          profile: asset.profile,
          category: modelCategory,
          guidance: guidance3d,
          backgroundMode,
          subjectPadding,
        });
      } catch (generationError) {
        setGenerating(false);
        setError(`No se pudo iniciar la conversión 3D: ${generationError?.message || generationError}`);
        return;
      }
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
        steps: res.executionPlan?.steps ?? steps3d,
        textured: res.textureApplied === true,
        textureRequested: asset.texture,
        textureReport: res.textureReport,
        shapeGlbPath: res.shapeGlbPath,
        masterGlbPath: res.masterGlbPath,
        executionPlan: res.executionPlan,
        profile: asset.profile,
        targetFaces: res.executionPlan?.target_faces ?? asset.targetFaces,
        textureSize: res.executionPlan?.texture_resolution === 1024 ? '1K' : asset.textureSize,
        paintBackend: res.executionPlan?.paint_backend || asset.paintBackend || 'fast',
        materialHint: res.material || asset.materialHint || 'auto',
        artDirector: res.artDirector || null,
        buffaloStrategy: res.buffaloStrategy || null,
        prompt: image3dInput.name, // shown as the label
        inputDataUrl: image3dInput.dataUrl,
        multiViewImages: res.multiViewImages || multiViewImages || {},
        model: 'hunyuan3d-2.1-mlx',
        category: modelCategory,
        guidance: guidance3d,
        backgroundMode,
        createdAt: Date.now(),
        filePath: null,
      };
      setResult(entry);
      const { glbBase64, inputDataUrl, multiViewImages: _mv, ...light } = entry;
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
      setProgress({ percent: 5, label: 'Enviando prompt a Ollama FLUX…', remaining: 35 });
      let subStep = 0;
      const stepTimer = setInterval(() => {
        setProgress((curr) => {
          let pct;
          let label = curr.label;
          if (curr.percent < 90) {
            const next = curr.percent + Math.floor(Math.random() * 8) + 4;
            pct = Math.min(90, next);
          } else {
            subStep += 1;
            // Smoothly and dynamically tick 90% -> 91% -> 92% -> 93% -> 94% -> 95% -> 96% -> 97% -> 98%
            pct = Math.min(98, curr.percent + (subStep % 2 === 0 ? 1 : 0));
          }

          if (pct <= 20) label = 'Enviando prompt a Ollama FLUX…';
          else if (pct > 20 && pct <= 45) label = 'Cargando modelo FLUX en VRAM/RAM…';
          else if (pct > 45 && pct <= 70) label = 'Ejecutando muestreo de difusión…';
          else if (pct > 70 && pct <= 85) label = 'Decodificando píxeles con VAE…';
          else if (pct > 85 && pct <= 92) label = 'Optimizando matriz de color y contraste…';
          else if (pct > 92 && pct <= 95) label = 'Refinando resolución y detalles…';
          else if (pct > 95) label = 'Finalizando empaquetado de imagen…';

          const remaining = Math.max(1, Math.ceil((100 - pct) * 0.35));
          return { percent: pct, label, remaining };
        });
      }, 800);

      let res;
      try {
        res = await window.ollama.generate({
          model: imageModel,
          prompt: prompt.trim(),
          width: params.width,
          height: params.height,
          steps: params.steps,
          seed: usedSeed,
        });
      } catch (genErr) {
        clearInterval(stepTimer);
        setGenerating(false);
        setError(`Error al generar imagen: ${genErr?.message || genErr}`);
        return;
      }

      clearInterval(stepTimer);
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
    setProgress({ percent: 5, label: 'Iniciando generación LLM de código JSCAD…', remaining: 20 });
    let stlSubStep = 0;
    const stepTimer = setInterval(() => {
      setProgress((curr) => {
        let pct;
        let label = curr.label;
        if (curr.percent < 90) {
          const next = curr.percent + Math.floor(Math.random() * 10) + 5;
          pct = Math.min(90, next);
        } else {
          stlSubStep += 1;
          pct = Math.min(98, curr.percent + (stlSubStep % 2 === 0 ? 1 : 0));
        }

        if (pct <= 20) label = 'Iniciando generación LLM de código JSCAD…';
        else if (pct > 20 && pct <= 45) label = 'Ejecutando inferencia de código JSCAD…';
        else if (pct > 45 && pct <= 70) label = 'Compilando script geométrico en V8…';
        else if (pct > 70 && pct <= 88) label = 'Triangulando malla CSG a STL…';
        else if (pct > 88 && pct <= 94) label = 'Validando manifold y normales…';
        else if (pct > 94) label = 'Exportando archivo geométrico…';

        const remaining = Math.max(1, Math.ceil((100 - pct) * 0.25));
        return { percent: pct, label, remaining };
      });
    }, 700);

    let res;
    try {
      res = await window.ollama.generateStl({
        model: stlModel,
        prompt: prompt.trim(),
        seed: usedSeed,
        profile: asset.profile,
        targetFaces: asset.targetFaces,
      });
    } catch (genErr) {
      clearInterval(stepTimer);
      setGenerating(false);
      setError(`Error al generar STL: ${genErr?.message || genErr}`);
      return;
    }

    clearInterval(stepTimer);
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
    multiViewInputs,
    multiViewBackend,
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
    if (result.type === 'glb' && ['atencion', 'critico'].includes(result.qualityLevel)) {
      setError('La entrega requiere revisión; no se puede guardar este GLB todavía.');
      return null;
    }
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
      setError('La entrega está marcada como crítica; revisa o corrige el modelo antes de exportar STL.');
      return null;
    }
    const conv = await window.hunyuan.convertStl({
      glbPath: result.glbPath,
      targetMm: stlMm,
    });
    if (!conv.ok) {
      setError(conv.error || 'Conversión a STL fallida.');
      return null;
    }
    const dest = await window.hunyuan.saveGlb({
      srcPath: conv.stl_path,
      filename: timestampName(result.faces || 'model', 'stl'),
    });
    return { path: dest, dims: conv.dims_mm };
  }, [result, stlMm]);

  const handleSaveOpenUsd = useCallback(async () => {
    if (!result || result.type !== 'glb') return null;
    if (result.usdzPath) {
      const dest = await window.hunyuan.saveGlb({
        srcPath: result.usdzPath,
        filename: timestampName(result.faces || 'model', 'usdz'),
      });
      return { path: dest, report: { ok: true, usdz_path: result.usdzPath } };
    }
    if (result.qualityLevel === 'critico') {
      setError('La entrega está marcada como crítica; revisa o corrige el modelo antes de exportar OpenUSD.');
      return null;
    }
    const converted = await window.hunyuan.convertOpenUsd({ glbPath: result.glbPath });
    if (!converted.ok) {
      setError(converted.error || 'No se pudo validar la conversión OpenUSD.');
      return null;
    }
    const dest = await window.hunyuan.saveGlb({
      srcPath: converted.usdz_path,
      filename: timestampName(result.faces || 'model', 'usdz'),
    });
    return { path: dest, report: converted };
  }, [result]);

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
      const glbBase64 = entry.glbBase64 || null;
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
      if (entry.image) {
        setImage3dInput({
          name: `referencia-${entry.id}.png`,
          base64: entry.image,
          dataUrl: `data:image/png;base64,${entry.image}`,
        });
      }
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

  const handlePickMultiView = useCallback(async (viewId) => {
    const image = await window.hunyuan.pickImage();
    if (!image) return;
    setMultiViewInputs((current) => ({ ...current, [viewId]: image }));
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
    setResult(null);
    setError(null);
  }, [result]);

  const handleSelectUseCase = useCallback((id) => {
    const recipe = USE_CASES[id];
    const category = MODEL_CATEGORIES[recipe.category];
    const resolved = resolveAssetPreset(category, recipe.profile);
    setUseCase(id);
    setModelCategory(recipe.category);
    setMode(recipe.mode);
    setAsset({
      ...resolved,
      scale: recipe.scale,
    });
    setSteps3d(recipe.profile === category.profile ? category.steps : Math.min(category.steps, resolved.steps));
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
    const resolved = resolveAssetPreset(category, category.profile);
    setModelCategory(id);
    setAsset({
      ...resolved,
      scale: category.scale,
    });
    setSteps3d(category.steps);
    setGuidance3d(category.guidance);
    setBackgroundMode(category.backgroundMode);
    setSubjectPadding(category.padding);
    setError(null);
  }, []);

  // Handle Online Texture Swap (Meshy retexture mode)
  const handleOnlineTexture = useCallback(async ({ prompt: texPrompt, resolution }) => {
    if (!meshyApiKey) {
      setError('Ingresa tu API Key de Meshy para re-texturizar online.');
      return;
    }
    setError(null);
    setGenerating(true);
    setProgress({ percent: 1, label: 'Generando nueva textura PBR en Meshy Cloud…', remaining: null });

    try {
      let multiviewImageUrls = undefined;
      if (Object.keys(multiViewInputs).length > 0) {
        multiviewImageUrls = [
          ...(image3dInput ? [`data:image/png;base64,${image3dInput.base64}`] : []),
          ...Object.values(multiViewInputs).map(img => `data:image/png;base64,${img.base64}`)
        ].slice(0, 4);
      }

      const res = await window.meshy.generate3D({
        apiKey: meshyApiKey,
        mode: 'retexture',
        prompt: texPrompt,
        preview_task_id: meshyPreviewTaskId || result?.taskId || undefined,
        glbBase64: result?.glbBase64 || undefined,
        multiview_image_urls: multiviewImageUrls,
        art_style: 'realistic',
        ai_model: meshyAiModel,
        texture_resolution: (resolution || meshyTextureResolution || '2k').toLowerCase(),
      });

      setGenerating(false);
      if (!res?.ok) {
        setError(res?.error || 'Error al re-texturizar en Meshy Cloud.');
        return;
      }

      setProgress({ percent: 100, label: 'Textura PBR actualizada', remaining: 0 });
      setResult((curr) => ({
        ...curr,
        glbBase64: res.glbBase64 || curr?.glbBase64,
        glbPath: res.glbPath || curr?.glbPath,
        textured: true,
        textureSize: resolution,
        prompt: `Textura: ${texPrompt}`,
      }));
    } catch (err) {
      setGenerating(false);
      setError(`Error al re-texturizar: ${err?.message || err}`);
    }
  }, [meshyApiKey, meshyPreviewTaskId, result]);

  // Handle Online Model Correction / Remesh Quad (Meshy refine/remesh)
  const handleOnlineCorrection = useCallback(async ({ topology, target_polycount }) => {
    if (!meshyApiKey) {
      setError('Ingresa tu API Key de Meshy para corregir la topología online.');
      return;
    }
    setError(null);
    setGenerating(true);
    setProgress({ percent: 1, label: 'Optimizando geometría y topología Quad en Meshy Cloud…', remaining: null });

    try {
      const res = await window.meshy.generate3D({
        apiKey: meshyApiKey,
        mode: 'refine',
        preview_task_id: meshyPreviewTaskId || result?.taskId || undefined,
        topology,
        target_polycount,
        autoSize: true,
      });

      setGenerating(false);
      if (!res?.ok) {
        setError(res?.error || 'Error al corregir la topología en Meshy Cloud.');
        return;
      }

      setProgress({ percent: 100, label: 'Geometría corregida y optimizada', remaining: 0 });
      setResult((curr) => ({
        ...curr,
        glbBase64: res.glbBase64 || curr?.glbBase64,
        glbPath: res.glbPath || curr?.glbPath,
        faces: res.faces || target_polycount,
        qualityLevel: 'listo',
        qualityText: 'Topología Quad optimizada y corregida.',
      }));
    } catch (err) {
      setGenerating(false);
      setError(`Error al corregir modelo: ${err?.message || err}`);
    }
  }, [meshyApiKey, meshyPreviewTaskId, result]);

  return (
    <div className="app-shell relative flex h-full flex-col overflow-hidden bg-base text-neutral-200">
      <Header
        status={status}
        hunyuanUp={hunyuanUp}
        mode={mode}
        engineProvider={engineProvider}
        onSelectEngineProvider={setEngineProvider}
        meshyApiKey={meshyApiKey}
        processing={processing}
        progress={progress}
        historyCount={history.length}
        historyOpen={historyOpen}
        onToggleHistory={() => setHistoryOpen((open) => !open)}
        onRefresh={checkStatus}
        onOpenJobsReview={() => setShowJobsReviewModal(true)}
        lang={lang}
        setLang={handleSetLang}
        soundMuted={soundMuted}
        onToggleSound={handleToggleSound}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
      />

      <div className="workspace-grid relative z-10 flex min-h-0 flex-1 gap-3 p-3">
        {/* Left: form */}
        <aside className="control-rail workspace-window w-[356px] shrink-0 overflow-hidden rounded-[22px]">
          <PromptPanel
            connected={status.connected}
            engineProvider={engineProvider}
            setEngineProvider={setEngineProvider}
            meshyApiKey={meshyApiKey}
            setMeshyApiKey={(key) => {
              setMeshyApiKey(key);
              window.meshy?.saveApiKey(key);
            }}
            meshyMode={meshyMode}
            setMeshyMode={setMeshyMode}
            meshyTopology={meshyTopology}
            setMeshyTopology={setMeshyTopology}
            meshyTargetPolycount={meshyTargetPolycount}
            setMeshyTargetPolycount={setMeshyTargetPolycount}
            meshyPreviewTaskId={meshyPreviewTaskId}
            meshyAiModel={meshyAiModel}
            setMeshyAiModel={setMeshyAiModel}
            meshyUltraMode={meshyUltraMode}
            setMeshyUltraMode={setMeshyUltraMode}
            meshyTextureResolution={meshyTextureResolution}
            setMeshyTextureResolution={setMeshyTextureResolution}
            meshyShouldTexture={meshyShouldTexture}
            setMeshyShouldTexture={setMeshyShouldTexture}
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
            multiViewInputs={multiViewInputs}
            multiViewBackend={multiViewBackend}
            onPickImage={handlePickImage}
            onPickMultiView={handlePickMultiView}
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
        <main className="result-stage workspace-window min-w-0 flex-1 overflow-hidden rounded-[22px]">
          <ImageViewer
            result={result}
            generating={generating}
            processing={processing}
            progress={progress}
            useCase={useCase}
            mode={mode}
            error={error}
            onCancel={handleCancel}
            onSave={handleSave}
            onSaveStl={handleSaveStl3d}
            onSaveOpenUsd={handleSaveOpenUsd}
            onCopyPrompt={handleCopyPrompt}
            onReveal={(p) => window.ollama.revealInFinder(p)}
            asset={asset}
            onUseAs3dReference={handleUseImageAsReference}
            onApplyOnlineTexture={handleOnlineTexture}
            onApplyOnlineCorrection={handleOnlineCorrection}
            onErrorDismiss={() => setError(null)}
            externalAction={externalAction}
            onClearExternalAction={() => setExternalAction(null)}
          />
        </main>

        {/* Right: gallery */}
        {historyOpen && (
          <aside className="history-rail workspace-window w-[210px] shrink-0 overflow-hidden rounded-[22px]">
            <Gallery
              history={history}
              activeId={result?.id}
              onSelect={(entry) => {
                handleSelectFromGallery(entry);
                setHistoryOpen(false);
              }}
            />
          </aside>
        )}
      </div>

      {/* Steve Jobs & Jony Ive Design Review Modal */}
      <JobsIveDesignReviewModal
        isOpen={showJobsReviewModal}
        onClose={() => setShowJobsReviewModal(false)}
      />

      {/* Spotlight-Style Command Palette */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        mode={mode}
        setMode={setMode}
        engineProvider={engineProvider}
        setEngineProvider={setEngineProvider}
        onTriggerAction={(type, payload) => {
          setExternalAction({ type, payload });
        }}
        lang={lang}
        setLang={handleSetLang}
        soundMuted={soundMuted}
        onToggleSound={handleToggleSound}
      />
    </div>
  );
}
