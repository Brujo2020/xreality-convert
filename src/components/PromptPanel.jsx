import React, { useState, useEffect } from 'react';
import {
  ArrowRight,
  Armchair,
  Boat,
  Buildings,
  Bus,
  Car,
  Crane,
  Cube,
  CubeFocus,
  Drone,
  Engine,
  Factory,
  Image as ImageIcon,
  Package,
  PawPrint,
  Person,
  Plus,
  Polygon,
  Scan,
  SlidersHorizontal,
  Sparkle,
  SpinnerGap,
  Lightning,
  Motorcycle,
  SolarPanel,
  Tractor,
  Tree,
  Truck,
  Warehouse,
  Wrench,
} from '@phosphor-icons/react';
import XrProductionPanel from './XrProductionPanel.jsx';
import UseCasePicker from './UseCasePicker.jsx';
import TextureLibraryPicker from './TextureLibraryPicker.jsx';
import { MODEL_CATEGORIES } from '../lib/modelCategories.js';
import { XR_PROFILES } from '../lib/xrProfiles.js';

function Slider({ label, value, min, max, step, onChange, suffix = '' }) {
  return (
    <label className="block">
      <span className="mb-2 flex items-center justify-between text-[11px] text-slate-400">
        {label}
        <b className="rounded-md border border-sky-400/15 bg-sky-400/5 px-2 py-0.5 font-mono font-medium text-sky-100">
          {value}{suffix}
        </b>
      </span>
      <input type="range" className="slider-accent w-full" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

const MODES = [
  { id: 'image', step: '01', label: 'Crear imagen', hint: 'Referencia visual', Icon: ImageIcon },
  { id: 'stl', step: '02', label: 'Texto → 3D', hint: 'Geometría técnica', Icon: Polygon },
  { id: 'image3d', step: '03', label: 'Imagen → 3D', hint: 'Reconstrucción MLX', Icon: CubeFocus },
];

const CATEGORY_ICONS = {
  animal: PawPrint,
  person: Person,
  product: Package,
  industrial: Factory,
  construction: Buildings,
  warehouse: Warehouse,
  vehicle: Car,
  cargo_vehicle: Truck,
  truck: Truck,
  crane: Crane,
  electrical: Lightning,
  vegetation: Tree,
  building: Buildings,
  tool: Wrench,
  forklift: Tractor,
  excavator: Tractor,
  motorcycle: Motorcycle,
  bus: Bus,
  drone: Drone,
  boat: Boat,
  furniture: Armchair,
  solar: SolarPanel,
  architecture: Buildings,
  custom: Cube,
};

function ModeSelector({ mode, setMode, disabled }) {
  return (
    <nav className="grid grid-cols-3 gap-1.5 rounded-full border border-sky-400/20 bg-[#020b1d]/80 p-1.5 shadow-inner backdrop-blur-xl">
      {MODES.map((item) => (
        <button
          key={item.id}
          disabled={disabled}
          onClick={() => setMode(item.id)}
          className={`group relative overflow-hidden rounded-full px-3 py-2.5 text-center transition-all duration-300 ${
            mode === item.id
              ? 'bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 text-white shadow-[0_8px_30px_rgba(37,99,235,0.5)] border border-sky-300/40 scale-[1.03]'
              : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
          }`}
        >
          <span className="flex items-center justify-center gap-1.5">
            <span className={`font-mono text-[9px] font-bold ${mode === item.id ? 'text-white/80' : 'text-sky-400/70'}`}>{item.step}</span>
            <item.Icon size={16} weight="duotone" className={mode === item.id ? 'text-white' : 'text-sky-400/70'} aria-hidden="true" />
          </span>
          <span className="mt-0.5 block text-[11px] font-bold leading-tight">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function Section({ eyebrow, title, children }) {
  return (
    <section className="glass-card rounded-3xl p-4.5 border border-sky-500/20 bg-[#06173a]/75 backdrop-blur-2xl">
      <div className="mb-3">
        <p className="font-mono text-[9px] uppercase tracking-[0.2em] font-extrabold text-sky-400">{eyebrow}</p>
        <h2 className="mt-1 text-sm font-bold tracking-tight text-slate-100 font-outfit">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function CategorySelector({ value, onChange, disabled }) {
  const selected = MODEL_CATEGORIES[value];
  return (
    <Section eyebrow="Contexto del modelo" title="¿Qué aparece en la imagen?">
      <div className="grid grid-cols-3 gap-1.5">
        {Object.entries(MODEL_CATEGORIES).map(([id, item]) => (
          <button key={id} disabled={disabled} onClick={() => onChange(id)} className={`rounded-2xl border px-2 py-2.5 text-center transition-all duration-300 ${value === id ? 'border-sky-400/50 bg-sky-500/20 text-white shadow-[0_8px_25px_rgba(56,189,248,0.25)] scale-[1.03]' : 'border-white/5 bg-black/20 text-slate-400 hover:border-sky-400/30 hover:text-slate-100'}`}>
            {React.createElement(CATEGORY_ICONS[id] || Cube, { size: 20, weight: 'duotone', className: 'mx-auto text-sky-300', 'aria-hidden': true })}
            <span className="mt-1 block text-[9px] font-bold">{item.label}</span>
          </button>
        ))}
      </div>
      <div className="mt-2.5 rounded-2xl border border-sky-400/20 bg-sky-500/10 p-3">
        <p className="text-[10px] leading-relaxed text-slate-200">{selected.description}</p>
        <div className="mt-2 flex flex-wrap gap-1.5 font-mono text-[7px] font-bold uppercase tracking-wider text-sky-300">
          <span>{selected.steps} pasos</span><span>·</span><span>{selected.octree}px</span><span>·</span><span>{Math.round(selected.targetFaces / 1000)}K caras</span><span>·</span><span>{selected.backgroundMode === 'keep' ? 'Escena completa' : 'Fondo automático'}</span>
        </div>
      </div>
    </Section>
  );
}

const QUICK_DELIVERY_PROFILES = [
  ['lowpoly', 'Low Poly', '15K · PBR 1K'],
  ['vrready', 'VR Ready', '45K · PBR 1K'],
  ['smart', 'Smart M', 'Memoria adaptativa'],
];

function QuickDeliverySelector({ asset, setAsset, setSteps3d, disabled }) {
  const selectProfile = (id) => {
    const profile = XR_PROFILES[id];
    setAsset((current) => ({
      ...current,
      profile: id,
      octree: profile.octree,
      texture: profile.texture,
      targetFaces: profile.targetFaces,
      textureSize: profile.textureSize,
      paintBackend: profile.paintBackend,
    }));
    setSteps3d(profile.steps);
  };

  return (
    <section className="glass-card rounded-3xl border-sky-400/20 p-3.5 shadow-[0_15px_40px_rgba(1,10,30,0.4)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[8px] uppercase tracking-[0.2em] font-extrabold text-cyan-300">Salida rápida</p>
          <p className="mt-0.5 text-[11px] font-bold text-white">Elige la optimización</p>
        </div>
        <span className="rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-0.5 font-mono text-[8px] font-extrabold uppercase text-cyan-200">{asset.profile}</span>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        {QUICK_DELIVERY_PROFILES.map(([id, label, hint]) => (
          <button
            key={id}
            type="button"
            data-profile-id={id}
            aria-pressed={asset.profile === id}
            disabled={disabled}
            onClick={() => selectProfile(id)}
            className={`rounded-full px-2.5 py-2 text-center transition-all duration-300 ${asset.profile === id ? 'border border-sky-400/50 bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.4)] scale-[1.03]' : 'border border-white/10 bg-black/20 text-slate-400 hover:border-sky-400/30 hover:text-white'} disabled:cursor-not-allowed disabled:opacity-40`}
          >
            <span className="block text-[9.5px] font-bold">{label}</span>
            <span className="mt-0.5 block text-[7px] leading-tight text-slate-400">{hint}</span>
          </button>
        ))}
      </div>
      {disabled && <p className="mt-2 text-[8px] leading-relaxed text-amber-200/80">Hay un proceso activo. Cancélalo para cambiar el perfil de salida.</p>}
    </section>
  );
}

export default function PromptPanel({
  connected,
  engineProvider = 'local',
  setEngineProvider,
  meshyApiKey,
  setMeshyApiKey,
  meshyMode,
  setMeshyMode,
  meshyTopology,
  setMeshyTopology,
  meshyTargetPolycount,
  setMeshyTargetPolycount,
  meshyPreviewTaskId,
  useCase,
  onSelectUseCase,
  modelCategory,
  onSelectModelCategory,
  mode,
  setMode,
  imageModel,
  imageModels,
  setImageModel,
  imageModelAvailable,
  installingModel,
  onInstallImageModel,
  stlModels,
  stlModel,
  setStlModel,
  prompt,
  setPrompt,
  params,
  setParams,
  image3dInput,
  multiViewInputs,
  multiViewBackend,
  onPickImage,
  onPickMultiView,
  onDropImage,
  steps3d,
  setSteps3d,
  guidance3d,
  setGuidance3d,
  backgroundMode,
  setBackgroundMode,
  subjectPadding,
  setSubjectPadding,
  stlMm,
  setStlMm,
  analysis,
  analysisLoading,
  asset,
  setAsset,
  hunyuanUp,
  installingEngine,
  onInstallEngine,
  generating,
  progress,
  onGenerate,
  onCancel,
  randomSeed,
}) {
  const [advanced, setAdvanced] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [imageInfo, setImageInfo] = useState(null);
  const isMeshy = engineProvider === 'meshy';
  const processing = generating || installingEngine || installingModel;

  useEffect(() => {
    if (!image3dInput?.base64) {
      setImageInfo(null);
      return;
    }
    const img = new window.Image();
    img.src = `data:image/png;base64,${image3dInput.base64}`;
    img.onload = () => {
      setImageInfo({ width: img.naturalWidth, height: img.naturalHeight });
    };
  }, [image3dInput?.base64]);

  const update = (key, value) => setParams((current) => ({ ...current, [key]: value }));

  const blocked = isMeshy
    ? !meshyApiKey || (!image3dInput && !prompt.trim())
    : mode === 'image3d'
    ? !image3dInput || !hunyuanUp
    : mode === 'stl'
    ? !prompt.trim() || !stlModel
    : !prompt.trim() || !imageModelAvailable;

  const actionLabel = isMeshy
    ? mode === 'image'
      ? '🎨 Generar Referencia 2D (FLUX)'
      : mode === 'stl'
      ? '⚡ Generar Modelo 3D Texto → Meshy (5cr)'
      : '⚡ Reconstruir Modelo 3D Imagen → Meshy (5cr)'
    : mode === 'image3d'
    ? 'Convertir imagen a 3D'
    : mode === 'stl'
    ? 'Generar código y malla'
    : 'Generar imagen de referencia';

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4 select-none scroll-dark">
      {/* Selector de Motor: Local MLX vs Meshy Cloud API */}
      <Section eyebrow="Motor 3D" title="Proveedor de Procesamiento">
        <div className="grid grid-cols-2 gap-1.5 rounded-full border border-sky-400/20 bg-[#020b1d]/80 p-1.5">
          <button
            type="button"
            onClick={() => setEngineProvider('local')}
            className={`rounded-full px-3 py-2 text-center transition-all duration-300 ${!isMeshy ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)] border border-sky-300/40 font-bold scale-[1.02]' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <span className="block text-[11px]">🖥️ Local (Hunyuan MLX)</span>
            <span className="block font-mono text-[8px] text-sky-300 font-bold">Privado · Coste $0</span>
          </button>
          <button
            type="button"
            onClick={() => setEngineProvider('meshy')}
            className={`rounded-full px-3 py-2 text-center transition-all duration-300 ${isMeshy ? 'bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)] border border-sky-300/40 font-bold scale-[1.02]' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <span className="block text-[11px]">☁️ Meshy Cloud API</span>
            <span className="block font-mono text-[8px] text-indigo-300 font-bold">v6 · Quad Low-Poly</span>
          </button>
        </div>
      </Section>

      {/* Tarjeta de Configuración Meshy API */}
      {isMeshy && (
        <Section eyebrow="Meshy API Cloud Config" title="Parámetros y Clave de API">
          <div className="flex flex-col gap-3">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-[10px] font-bold text-slate-300">Meshy API Key</label>
                <span className={`font-mono text-[9px] ${meshyApiKey ? 'text-emerald-300 font-extrabold' : 'text-amber-300 font-bold'}`}>
                  {meshyApiKey ? '✓ Guardada' : '⚠️ Clave requerida'}
                </span>
              </div>
              <div className="flex gap-1.5">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  placeholder="msy_..."
                  value={meshyApiKey}
                  onChange={(e) => setMeshyApiKey(e.target.value)}
                  className="field-modern min-w-0 flex-1 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey((v) => !v)}
                  className="rounded-full border border-sky-400/20 bg-white/10 px-3 text-[10px] text-slate-300 hover:bg-white/20 transition-all"
                >
                  {showApiKey ? '🙈' : '👁️'}
                </button>
              </div>
            </div>

            {/* Topology & Polycount */}
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[10px] font-bold text-slate-300">Topología</label>
                <select
                  value={meshyTopology}
                  onChange={(e) => setMeshyTopology(e.target.value)}
                  className="field-modern w-full text-xs"
                >
                  <option value="quad">Quad (Clean Low-Poly)</option>
                  <option value="triangle">Triangle (Decimado)</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-[10px] font-bold text-slate-300">Target Polycount</label>
                <select
                  value={meshyTargetPolycount}
                  onChange={(e) => setMeshyTargetPolycount(Number(e.target.value))}
                  className="field-modern w-full text-xs font-mono"
                >
                  <option value={5000}>5.000 (Low Poly VR)</option>
                  <option value={12000}>12.000 (Juegos Std)</option>
                  <option value={30000}>30.000 (Hero Asset)</option>
                </select>
              </div>
            </div>
          </div>
        </Section>
      )}

      <ModeSelector mode={mode} setMode={setMode} disabled={processing} />

      <UseCasePicker value={useCase} onChange={onSelectUseCase} disabled={processing} />

      {!isMeshy && (mode === 'image3d' || mode === 'stl') && (
        <div className="sticky top-0 z-20 rounded-3xl bg-[#030d20]/95 py-1 backdrop-blur-xl">
          <QuickDeliverySelector asset={asset} setAsset={setAsset} setSteps3d={setSteps3d} disabled={processing} />
        </div>
      )}

      <Section eyebrow="Fuente" title={isMeshy ? 'Motor de IA en la Nube' : mode === 'image3d' ? 'Motor de reconstrucción' : mode === 'image' ? 'Modelo generativo' : 'Modelo de geometría'}>
        {isMeshy ? (
          <div className="rounded-2xl border border-sky-400/30 bg-sky-500/15 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_12px_rgba(52,211,153,0.8)]" />
                <strong className="text-xs font-bold text-white font-outfit">Meshy Cloud API v6 Engine</strong>
              </div>
              <span className="font-mono text-[9px] text-cyan-300 font-extrabold uppercase">5-20 Créditos</span>
            </div>
            <p className="mt-1 text-[10px] text-slate-300">
              {mode === 'image'
                ? 'Generación 2D con FLUX · Listo para conversión instantánea a 3D'
                : mode === 'stl'
                ? 'Texto → Modelo 3D GLB/USDZ de baja latencia'
                : 'Imagen → Reconstrucción 3D con PBR 6-Vistas'}
            </p>
          </div>
        ) : mode === 'image' ? (
          <>
            <select value={imageModel} onChange={(event) => setImageModel(event.target.value)} className="field-modern" disabled={processing}>
              <option value={imageModel}>{imageModelAvailable ? imageModel : `${imageModel} · no instalado`}</option>
              {imageModels.filter((model) => model !== imageModel).map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
            {!imageModelAvailable && <div className="mt-2 rounded-2xl border border-amber-400/30 bg-amber-400/10 p-3"><p className="text-[10px] leading-relaxed text-amber-100 font-medium">Este flujo necesita un modelo visual local.</p><button onClick={onInstallImageModel} disabled={installingModel} className="mt-2 w-full rounded-full bg-accent px-4 py-2 text-xs font-bold text-white shadow-lg">{installingModel ? 'Instalando FLUX…' : 'Instalar FLUX.2 Klein'}</button></div>}
          </>
        ) : mode === 'stl' ? (
          <select value={stlModel} onChange={(event) => setStlModel(event.target.value)} className="field-modern" disabled={processing}>
            {!stlModels.length && <option>Sin modelo disponible</option>}
            {stlModels.map((model) => <option key={model}>{model}</option>)}
          </select>
        ) : (
          <div className={`engine-status rounded-2xl p-3.5 ${hunyuanUp ? 'engine-status-ready' : installingEngine ? 'engine-status-working' : ''}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2">
                <Engine size={18} weight="duotone" className={`shrink-0 ${hunyuanUp ? 'text-emerald-300' : installingEngine ? 'text-amber-300' : 'text-sky-300'}`} aria-hidden="true" />
                <span className={`state-dot h-2.5 w-2.5 shrink-0 rounded-full ${hunyuanUp ? 'bg-emerald-400 text-emerald-400' : installingEngine ? 'bg-amber-400 text-amber-400 animate-pulse' : 'bg-sky-400 text-sky-400'}`} />
                <span className="truncate text-[12px] font-bold text-slate-100">Hunyuan3D · Apple MLX</span>
              </div>
              <span className={`shrink-0 font-mono text-[9px] font-extrabold uppercase tracking-wider ${hunyuanUp ? 'text-emerald-300' : installingEngine ? 'text-amber-300' : 'text-sky-300'}`}>{hunyuanUp ? 'Disponible' : installingEngine ? 'Inicializando' : 'Preparando'}</span>
            </div>
            <p className="mt-2 font-mono text-[8px] uppercase tracking-[0.15em] text-slate-400">{hunyuanUp ? 'Forma · textura · mapas PBR' : installingEngine ? 'Python · MLX · validación local' : 'Arranque privado en este Mac'}</p>
            {!hunyuanUp && !installingEngine && <button onClick={onInstallEngine} className="mt-3 w-full rounded-full bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-blue-900/40 transition hover:bg-blue-500">Inicializar motor</button>}
          </div>
        )}
      </Section>

      <Section eyebrow="Entrada" title={mode === 'image3d' ? 'Referencia del objeto' : 'Dirección creativa'}>
        {mode === 'image3d' ? (
          <button onClick={onPickImage} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onDropImage(event.dataTransfer.files[0]); }} disabled={processing} className="group relative flex min-h-36 w-full flex-col items-center justify-center overflow-hidden rounded-3xl border-2 border-dashed border-sky-400/35 bg-gradient-to-br from-sky-500/10 via-blue-600/5 to-transparent p-4 transition-all duration-300 hover:border-sky-300 hover:bg-sky-400/15 disabled:opacity-50">
            {image3dInput ? (
              <>
                <img src={image3dInput.dataUrl} alt="Referencia 3D" onLoad={(event) => setImageInfo({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} className="max-h-36 rounded-2xl object-contain shadow-2xl" />
                <span className="mt-2 max-w-full truncate text-[10px] font-semibold text-slate-300">{image3dInput.name} · cambiar</span>
              </>
            ) : (
              <>
                <span className="grid h-12 w-12 place-items-center rounded-full border border-sky-400/40 bg-sky-400/20 text-sky-200 shadow-[0_0_30px_rgba(56,189,248,0.3)] transition duration-300 group-hover:scale-110"><Plus size={24} weight="duotone" aria-hidden="true" /></span>
                <span className="mt-3 text-xs font-bold text-slate-100">Seleccionar o arrastrar imagen</span>
                <span className="mt-1 text-[10px] font-medium text-slate-400">PNG · JPG · WEBP</span>
              </>
            )}
          </button>
        ) : (
          <>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={4}
              disabled={processing}
              placeholder={mode === 'stl' ? 'Describe una pieza, equipo o activo industrial…' : 'Describe una referencia limpia, centrada y lista para convertir…'}
              className="field-modern scroll-dark resize-none leading-relaxed"
            />
            <div className="mt-2.5 flex flex-wrap gap-1.5 mb-2">
              {[
                { label: 'Fotorrealista', suffix: ', highly detailed, realistic 8k, pbr materials' },
                { label: 'Low Poly Game', suffix: ', clean low poly game asset, stylized quad topology' },
                { label: 'Estudio PBR', suffix: ', studio lighting, neutral background, pbr textures' },
                { label: 'Cyberpunk', suffix: ', cyberpunk style, neon accents, metallic surfaces' },
              ].map((style) => (
                <button
                  key={style.label}
                  type="button"
                  disabled={processing}
                  onClick={() => setPrompt((prev) => (prev.includes(style.suffix) ? prev : `${prev.trim()}${style.suffix}`))}
                  className="rounded-full border border-sky-400/30 bg-sky-500/15 px-3 py-1 font-mono text-[9px] font-bold text-sky-200 transition-all hover:scale-105 hover:bg-sky-500/25"
                >
                  + {style.label}
                </button>
              ))}
            </div>
            <TextureLibraryPicker
              disabled={processing}
              onSelectTexture={(suffix) => setPrompt((prev) => (prev.includes(suffix) ? prev : `${prev.trim()}${suffix}`))}
            />
          </>
        )}
        {mode === 'image3d' && (
          <div className="mt-3 rounded-2xl border border-sky-400/20 bg-sky-500/10 p-3">
            <p className="font-mono text-[8px] uppercase tracking-[0.2em] font-bold text-sky-300">Vistas para Shape multi-vista</p>
            <p className="mt-1 text-[9px] leading-relaxed text-slate-300">Añade fotos reales y etiquetadas. Las vistas auxiliares nunca se consideran evidencia para MASTER por sí solas.</p>
            {multiViewBackend?.available ? (
              <p className="mt-1 text-[8px] font-bold text-emerald-300">Backend Shape multi-vista listo: las cámaras admitidas se usarán en la reconstrucción.</p>
            ) : multiViewBackend?.state === 'installed_not_certified' ? (
              <p className="mt-1 text-[8px] leading-relaxed text-amber-200">Pesos Hunyuan3D-2mv instalados. El backend PyTorch/MPS permanece bloqueado hasta completar la certificación física en este Mac; estas fotos se conservarán como evidencia, pero Shape seguirá usando una sola referencia.</p>
            ) : (
              <p className="mt-1 text-[8px] leading-relaxed text-amber-200">Organización y validación activas. No se encontró un backend Shape multi-vista completo; estas fotos se conservarán como evidencia, pero no se enviarán a Shape.</p>
            )}
            <div className="mt-2.5 grid grid-cols-3 gap-1.5">
              {['front', 'right', 'back', 'left', 'top', 'bottom'].map((viewId) => (
                <button key={viewId} type="button" disabled={processing} onClick={() => onPickMultiView?.(viewId)} className={`rounded-full border px-2.5 py-1.5 text-center font-mono text-[8px] font-bold uppercase transition-all ${multiViewInputs[viewId] ? 'border-emerald-400/40 bg-emerald-500/20 text-emerald-200' : 'border-white/10 bg-black/20 text-slate-400 hover:border-sky-400/30 hover:text-white'}`}>
                  {multiViewInputs[viewId] ? `✓ ${viewId}` : `+ ${viewId}`}
                </button>
              ))}
            </div>
          </div>
        )}
        {mode === 'image3d' && imageInfo && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <span className="rounded-full border border-white/10 bg-black/25 px-2.5 py-1 font-mono text-[8px] font-bold text-slate-300">{imageInfo.width}×{imageInfo.height}</span>
            <span className={`rounded-full border px-2.5 py-1 font-mono text-[8px] font-bold ${Math.min(imageInfo.width, imageInfo.height) >= 768 ? 'border-sky-400/30 bg-sky-500/15 text-sky-200' : 'border-amber-400/30 bg-amber-500/15 text-amber-200'}`}>{Math.min(imageInfo.width, imageInfo.height) >= 768 ? 'Resolución correcta' : 'Resolución baja'}</span>
            <span className={`rounded-full border px-2.5 py-1 font-mono text-[8px] font-bold ${Math.max(imageInfo.width, imageInfo.height) / Math.min(imageInfo.width, imageInfo.height) <= 1.4 ? 'border-sky-400/30 bg-sky-500/15 text-sky-200' : 'border-amber-400/30 bg-amber-500/15 text-amber-200'}`}>{Math.max(imageInfo.width, imageInfo.height) / Math.min(imageInfo.width, imageInfo.height) <= 1.4 ? 'Encuadre óptimo' : 'Conviene recortar'}</span>
          </div>
        )}
        {mode === 'image3d' && (
          <div className="analysis-card mt-3 rounded-3xl p-3.5 border border-sky-500/20 bg-[#04122d]/70">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-sky-400"><Scan size={15} weight="duotone" aria-hidden="true" />Diagnóstico previo</p>
                <p className="mt-1 flex items-center gap-2 text-[10px] font-medium text-slate-300">
                  {analysisLoading && <span className="state-dot h-2 w-2 rounded-full bg-amber-400 text-amber-400 animate-pulse" />}
                  {analysisLoading ? 'Ojo de Águila analiza la referencia…' : analysis?.status || 'Esperando una referencia'}
                </p>
              </div>
              {analysis && <button onClick={() => setShowAnalysis((open) => !open)} className="rounded-full border border-sky-400/20 bg-white/10 px-3 py-1.5 text-[9px] font-bold text-slate-200 transition hover:bg-white/20">{showAnalysis ? 'Ocultar' : 'Revisar'}</button>}
            </div>
            {showAnalysis && analysis?.suggested_category && analysis?.suggested_category !== modelCategory && (
              <button disabled={processing} onClick={() => onSelectModelCategory(analysis.suggested_category)} className="mt-3 w-full rounded-full border border-sky-400/30 bg-sky-500/20 px-3 py-2 text-[9px] font-bold text-sky-100 transition hover:bg-sky-500/30">
                Aplicar categoría {MODEL_CATEGORIES[analysis.suggested_category]?.label || 'sugerida'}
              </button>
            )}
            {showAnalysis && analysis?.preview_base64 && image3dInput && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <figure className="rounded-2xl border border-white/10 bg-black/30 p-2">
                  <figcaption className="mb-2 font-mono text-[8px] font-bold uppercase tracking-[0.16em] text-slate-400">Original</figcaption>
                  <img src={image3dInput.dataUrl} alt="Referencia original" className="h-28 w-full rounded-xl object-contain" />
                </figure>
                <figure className="rounded-2xl border border-sky-400/20 bg-sky-500/10 p-2">
                  <figcaption className="mb-2 font-mono text-[8px] font-bold uppercase tracking-[0.16em] text-cyan-300">Preparada</figcaption>
                  <img src={`data:image/png;base64,${analysis.preview_base64}`} alt="Referencia preparada" className="h-28 w-full rounded-xl object-contain" />
                </figure>
              </div>
            )}
            {showAnalysis && analysis && (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  <span className={`rounded-full border px-2.5 py-1 font-mono text-[8px] font-bold ${analysis.status === 'Óptima' ? 'border-sky-400/30 bg-sky-500/15 text-sky-200' : analysis.status === 'Procesable con ajustes' ? 'border-amber-400/30 bg-amber-500/15 text-amber-200' : 'border-rose-400/30 bg-rose-500/15 text-rose-200'}`}>{analysis.status}</span>
                  {analysis.orientation && <span className="rounded-full border border-white/10 bg-black/25 px-2.5 py-1 font-mono text-[8px] font-bold text-slate-300">{analysis.orientation}</span>}
                  {analysis.subject_components != null && <span className="rounded-full border border-white/10 bg-black/25 px-2.5 py-1 font-mono text-[8px] font-bold text-slate-300">{analysis.subject_components} componentes</span>}
                  {analysis.has_alpha && <span className="rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-1 font-mono text-[8px] font-bold text-cyan-200">Transparencia detectada</span>}
                </div>
                {analysis.actions?.length ? (
                  <ul className="space-y-1 text-[10px] leading-relaxed text-slate-300">
                    {analysis.actions.slice(0, 3).map((action) => (
                      <li key={action} className="flex gap-2">
                        <span className="mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400" />
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )}
          </div>
        )}
      </Section>

      {mode === 'image3d' && <CategorySelector value={modelCategory} onChange={onSelectModelCategory} disabled={processing} />}

      {mode === 'image3d' && (
        <Section eyebrow="Preparación inteligente" title="Fondo y sujeto">
          <div className="grid grid-cols-3 gap-1.5 rounded-full border border-white/10 bg-black/20 p-1.5">
            {[
              ['auto', 'Automático', 'Recomendado'],
              ['remove', 'Quitar', 'Objeto aislado'],
              ['keep', 'Conservar', 'Escena completa'],
            ].map(([id, label, hint]) => (
              <button key={id} disabled={processing} onClick={() => setBackgroundMode(id)} className={`rounded-full px-2 py-2 text-center transition-all duration-300 ${backgroundMode === id ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white font-bold shadow-lg scale-[1.02]' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}>
                <span className="block text-[9.5px] font-bold">{label}</span>
                <span className="mt-0.5 block text-[7px] text-slate-300">{hint}</span>
              </button>
            ))}
          </div>
          <p className="mt-2.5 text-[9.5px] leading-relaxed text-slate-300">
            {backgroundMode === 'auto' ? (modelCategory === 'architecture' ? 'El orquestador conservará el entorno porque forma parte del modelo.' : 'El orquestador aislará el sujeto y eliminará el fondo antes de reconstruir.') : backgroundMode === 'remove' ? 'Se forzará una silueta limpia, incluso si la imagen contiene entorno.' : 'La imagen completa entrará al motor sin recorte de fondo.'}
          </p>
        </Section>
      )}

      {(mode === 'image3d' || mode === 'stl') && (
        <XrProductionPanel asset={asset} setAsset={setAsset} setSteps3d={setSteps3d} disabled={processing} />
      )}

      <section className="overflow-hidden rounded-3xl border border-sky-500/20 bg-[#06173a]/75 backdrop-blur-2xl">
        <button onClick={() => setAdvanced((current) => !current)} className="flex w-full items-center justify-between px-4 py-3.5 text-xs font-bold text-slate-200">
          <span className="flex items-center gap-2"><SlidersHorizontal size={17} weight="duotone" className="text-sky-400" aria-hidden="true" />Controles avanzados</span>
          <Plus size={16} weight="duotone" className={`text-sky-400 transition-transform duration-300 ${advanced ? 'rotate-45' : ''}`} aria-hidden="true" />
        </button>
        {advanced && (
          <div className="flex flex-col gap-4 border-t border-sky-500/15 p-4.5">
            {mode === 'image' && (
              <>
                <button onClick={() => setParams((current) => ({ ...current, width: 2048, height: 2048, steps: 20 }))} className="flex items-center justify-center gap-2 rounded-full border border-sky-400/30 bg-sky-500/15 px-4 py-2.5 text-xs font-bold text-sky-200 hover:bg-sky-500/25 transition-all"><Sparkle size={16} weight="duotone" aria-hidden="true" />Aplicar máxima calidad</button>
                <Slider label="Ancho" value={params.width} min={512} max={2048} step={64} suffix=" px" onChange={(value) => update('width', value)} />
                <Slider label="Alto" value={params.height} min={512} max={2048} step={64} suffix=" px" onChange={(value) => update('height', value)} />
                <Slider label="Pasos" value={params.steps} min={1} max={20} step={1} onChange={(value) => update('steps', value)} />
              </>
            )}
            {mode === 'image3d' && (
              <>
                <Slider label="Pasos de reconstrucción" value={steps3d} min={10} max={50} step={5} onChange={setSteps3d} />
                <Slider label="Resolución de malla" value={asset.octree} min={96} max={256} step={32} onChange={(value) => setAsset((current) => ({ ...current, octree: value }))} />
                <Slider label="Fidelidad al sujeto" value={guidance3d} min={1} max={12} step={0.5} onChange={setGuidance3d} />
                <Slider label="Margen alrededor" value={Math.round(subjectPadding * 100)} min={2} max={40} step={1} suffix="%" onChange={(value) => setSubjectPadding(value / 100)} />
                <Slider label="Presupuesto de caras" value={asset.targetFaces} min={10000} max={200000} step={5000} onChange={(value) => setAsset((current) => ({ ...current, targetFaces: value }))} />
                <button onClick={() => onSelectModelCategory(modelCategory)} className="rounded-full border border-sky-400/30 bg-sky-500/15 px-4 py-2.5 text-[10px] font-bold text-sky-200 hover:bg-sky-500/25 transition-all">Restaurar recomendación de {MODEL_CATEGORIES[modelCategory].label}</button>
              </>
            )}
            {mode !== 'image3d' && (
              <label className="block text-[11px] font-bold text-slate-300">
                Semilla reproducible
                <div className="mt-2 flex gap-2">
                  <input type="number" value={params.seed} onChange={(event) => update('seed', Number(event.target.value) || 0)} className="field-modern min-w-0 flex-1 font-mono" />
                  <button onClick={() => update('seed', randomSeed())} className="rounded-full border border-sky-400/20 bg-white/10 px-4 text-sm font-bold hover:bg-white/20">↻</button>
                </div>
              </label>
            )}
          </div>
        )}
      </section>

      <div className="mt-auto pt-2">
        {processing ? (
          <div className="loading-card loading-card-compact rounded-3xl p-4.5">
            <div className="mb-2 flex justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2 truncate text-sky-100 font-bold"><SpinnerGap size={16} weight="bold" className="shrink-0 animate-spin text-amber-300" aria-hidden="true" />{progress.label}</span><strong className="font-mono text-white font-extrabold">{progress.percent}%</strong></div>
            <div className="progress-track h-2.5 rounded-full"><div className="progress-fill progress-beam h-full rounded-full transition-all duration-700" style={{ width: `${progress.percent}%` }} /></div>
            <p className="mt-2 font-mono text-[8px] uppercase tracking-[0.15em] font-bold text-slate-400">Pipeline local · memoria unificada</p>
            {generating && <button onClick={onCancel} className="mt-3 w-full rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-white/20 transition-all">Cancelar y cambiar perfil</button>}
          </div>
        ) : (
          <button onClick={onGenerate} disabled={blocked} className="btn-glass-primary group relative w-full overflow-hidden rounded-full py-4 text-sm font-extrabold text-white shadow-[0_12px_40px_rgba(37,99,235,0.6)] transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_20px_55px_rgba(37,99,235,0.75)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:scale-100">
            <span className="relative z-10 flex items-center justify-center gap-2.5 font-outfit text-sm tracking-wide">{actionLabel}<ArrowRight size={19} weight="bold" className="transition-transform group-hover:translate-x-1.5" aria-hidden="true" /></span>
          </button>
        )}
      </div>
    </div>
  );
}
