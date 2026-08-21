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
  MagicWand,
  Gear,
} from '@phosphor-icons/react';
import XrProductionPanel from './XrProductionPanel.jsx';
import UseCasePicker from './UseCasePicker.jsx';
import TextureLibraryPicker from './TextureLibraryPicker.jsx';
import { MODEL_CATEGORIES } from '../lib/modelCategories.js';
import { XR_PROFILES } from '../lib/xrProfiles.js';
import { sounds } from '../lib/soundEffects.js';

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

// Technical CAD blueprint templates for instant parametric 3D (STL) generation
const STL_CAD_TEMPLATES = [
  {
    name: '⚙️ Engranaje Recto',
    prompt: 'Parametric mechanical spur gear with 24 teeth, 80mm outer diameter, 12mm thickness, central 15mm keyway bore and 4 weight reduction cutouts.',
  },
  {
    name: '📦 Carcasa Electrónica',
    prompt: 'Electronics enclosure box with rounded chamfered corners, internal PCB mounting bosses, snap-fit lid groove and cable entry cutout. Dimensions: 100x60x30mm.',
  },
  {
    name: '🔩 Brida de Tubería',
    prompt: 'Industrial high-pressure pipe flange with 6 bolt holes on a pitch circle, raised face gasket seal and central fluid passage bore of 40mm.',
  },
  {
    name: '🛸 Soporte Drone',
    prompt: 'Aerospace lightweight carbon-style drone motor mount with M3 mounting pattern, aerodynamic arm clamp and internal wiring relief.',
  },
  {
    name: '🔧 Mango Ergonómico',
    prompt: 'Ergonomic tool handle with textured grip finger grooves, contoured palm swell and solid 8mm hex tool drive socket.',
  },
];

// High-fidelity prompt enhancers for Image Mode
const IMAGE_PROMPT_ENHANCERS = [
  {
    name: '🌟 3D Asset Studio',
    suffix: ', clean isometric 3D asset, studio lighting, smooth bevels, white background, high geometric fidelity, octane render 8k',
  },
  {
    name: '🤖 Mecha Sci-Fi',
    suffix: ', futuristic high-tech mecha robot, metallic plating, carbon fiber accents, emissive cyan LED trim, solid neutral background, 3D game model',
  },
  {
    name: '🧸 Mascota 3D',
    suffix: ', stylized 3D character mascot, clean symmetrical T-pose, vibrant tactile materials, soft studio diffuse lighting, isolated on white',
  },
  {
    name: '🏛️ Arquitectura',
    suffix: ', miniature modern architectural pavilion, clean geometric facade, volumetric lighting, photorealistic scale model, neutral studio floor',
  },
];

function ModeSelector({ mode, setMode, disabled }) {
  return (
    <nav className="grid grid-cols-3 gap-1.5 rounded-full border border-sky-400/20 bg-[#020b1d]/80 p-1.5 shadow-inner backdrop-blur-xl">
      {MODES.map((item) => (
        <button
          key={item.id}
          disabled={disabled}
          onClick={() => {
            sounds.playSwitch();
            setMode(item.id);
          }}
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
  const selected = MODEL_CATEGORIES[value] || MODEL_CATEGORIES.industrial;
  return (
    <Section eyebrow="Contexto del modelo" title="¿Qué aparece en la imagen?">
      <div className="grid grid-cols-3 gap-1.5">
        {Object.entries(MODEL_CATEGORIES).map(([id, item]) => (
          <button
            key={id}
            disabled={disabled}
            onClick={() => {
              sounds.playClick();
              onChange(id);
            }}
            className={`rounded-2xl border px-2 py-2.5 text-center transition-all duration-300 ${
              value === id
                ? 'border-sky-400/50 bg-sky-500/20 text-white shadow-[0_8px_25px_rgba(56,189,248,0.25)] scale-[1.03]'
                : 'border-white/5 bg-black/20 text-slate-400 hover:border-sky-400/30 hover:text-slate-100'
            }`}
          >
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
  ['lowpoly', 'Low Poly', '15K · PBR opcional'],
  ['vrready', 'VR Ready', '45K · PBR opcional'],
  ['smart', 'Smart M', 'Memoria adaptativa'],
];

function QuickDeliverySelector({ asset, setAsset, setSteps3d, disabled }) {
  const selectProfile = (id) => {
    sounds.playClick();
    const profile = XR_PROFILES[id];
    setAsset((current) => ({
      ...current,
      profile: id,
      octree: profile.octree,
      targetFaces: profile.targetFaces,
      texture: current.texture === true,
      textureSize: current.textureSize || profile.textureSize,
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
  meshyAiModel,
  setMeshyAiModel,
  meshyUltraMode,
  setMeshyUltraMode,
  meshyTextureResolution,
  setMeshyTextureResolution,
  meshyShouldTexture,
  setMeshyShouldTexture,
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

  const getDynamicCreditCost = () => {
    if (mode === 'image3d') {
      let base = 5;
      if (meshyUltraMode) base += 5;
      return `${base}cr`;
    }
    if (meshyMode === 'refine') {
      return '20cr';
    }
    let base = 5;
    if (meshyUltraMode && (meshyAiModel === 'latest' || meshyAiModel === 'meshy-7')) {
      base += 5;
    }
    return `${base}cr`;
  };

  const actionLabel = isMeshy
    ? mode === 'image'
      ? '🎨 Generar Referencia 2D (FLUX)'
      : mode === 'stl'
      ? `⚡ Generar Modelo 3D Texto → Meshy (${getDynamicCreditCost()})`
      : `⚡ Reconstruir Modelo 3D Imagen → Meshy (${getDynamicCreditCost()})`
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
            onClick={() => {
              sounds.playSwitch();
              setEngineProvider('local');
            }}
            className={`rounded-full px-3 py-2 text-center transition-all duration-300 ${!isMeshy ? 'bg-gradient-to-r from-blue-600 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)] border border-sky-300/40 font-bold scale-[1.02]' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <span className="block text-[11px]">🖥️ Local (Hunyuan MLX)</span>
            <span className="block font-mono text-[8px] text-sky-300 font-bold">Privado · Coste $0</span>
          </button>
          <button
            type="button"
            onClick={() => {
              sounds.playSwitch();
              setEngineProvider('meshy');
            }}
            className={`rounded-full px-3 py-2 text-center transition-all duration-300 ${isMeshy ? 'bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)] border border-sky-300/40 font-bold scale-[1.02]' : 'text-slate-400 hover:text-slate-200'}`}
          >
            <span className="block text-[11px]">☁️ Meshy Cloud API</span>
            <span className="block font-mono text-[8px] text-indigo-300 font-bold">v7 · Quad Low-Poly</span>
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

            {/* Modo de Generación Meshy */}
            <div>
              <label className="mb-1.5 block text-[10px] font-bold text-slate-300">Modo de Operación Meshy Cloud</label>
              <div className="grid grid-cols-2 gap-1.5 rounded-2xl border border-sky-400/20 bg-black/40 p-1">
                <button
                  type="button"
                  onClick={() => {
                    sounds.playClick();
                    setMeshyMode('preview');
                  }}
                  className={`rounded-xl px-2.5 py-1.5 text-center transition-all ${
                    meshyMode === 'preview'
                      ? 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-bold shadow-[0_0_15px_rgba(16,185,129,0.4)]'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <span className="block text-[10px]">⚡ Preview Rápido</span>
                  <span className="block font-mono text-[8px] text-emerald-200">5 Créditos · Shape Económico</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    sounds.playClick();
                    setMeshyMode('refine');
                  }}
                  className={`rounded-xl px-2.5 py-1.5 text-center transition-all ${
                    meshyMode === 'refine'
                      ? 'bg-gradient-to-r from-amber-500 to-orange-600 text-white font-bold shadow-[0_0_15px_rgba(245,158,11,0.4)]'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  <span className="block text-[10px]">💎 Refinado HD</span>
                  <span className="block font-mono text-[8px] text-amber-200">20 Créditos · Textura PBR</span>
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

      {/* Direction & Input Section */}
      <Section eyebrow="Entrada" title={mode === 'image3d' ? 'Referencia del objeto' : mode === 'stl' ? 'Especificación Técnica CAD' : 'Dirección creativa'}>
        {mode === 'image3d' ? (
          <button
            onClick={() => {
              sounds.playClick();
              onPickImage();
            }}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              onDropImage(event.dataTransfer.files[0]);
            }}
            disabled={processing}
            className="group relative flex min-h-36 w-full flex-col items-center justify-center overflow-hidden rounded-3xl border-2 border-dashed border-sky-400/35 bg-gradient-to-br from-sky-500/10 via-blue-600/5 to-transparent p-4 transition-all duration-300 hover:border-sky-300 hover:bg-sky-400/15 disabled:opacity-50"
          >
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
            {/* Quick Templates Bar */}
            <div className="mb-2">
              <span className="flex items-center gap-1 font-mono text-[8px] font-extrabold uppercase tracking-wider text-cyan-300 mb-1.5">
                <MagicWand size={12} weight="duotone" />
                {mode === 'stl' ? 'Plantillas CAD Rápidas' : 'Optimizadores de Prompt'}
              </span>
              <div className="flex flex-wrap gap-1.5">
                {mode === 'stl'
                  ? STL_CAD_TEMPLATES.map((tmpl) => (
                      <button
                        key={tmpl.name}
                        type="button"
                        disabled={processing}
                        onClick={() => {
                          sounds.playClick();
                          setPrompt(tmpl.prompt);
                        }}
                        className="rounded-full border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[9px] font-bold text-sky-200 hover:bg-sky-500/25 transition-all"
                      >
                        {tmpl.name}
                      </button>
                    ))
                  : IMAGE_PROMPT_ENHANCERS.map((enh) => (
                      <button
                        key={enh.name}
                        type="button"
                        disabled={processing}
                        onClick={() => {
                          sounds.playClick();
                          setPrompt((prev) => (prev.includes(enh.suffix) ? prev : `${prev.trim()}${enh.suffix}`));
                        }}
                        className="rounded-full border border-sky-400/30 bg-sky-500/10 px-2.5 py-1 text-[9px] font-bold text-sky-200 hover:bg-sky-500/25 transition-all"
                      >
                        + {enh.name}
                      </button>
                    ))}
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={4}
              disabled={processing}
              placeholder={mode === 'stl' ? 'Describe una pieza, mecanismo o carcasa técnica en mm…' : 'Describe una referencia limpia, centrada y lista para convertir a 3D…'}
              className="field-modern scroll-dark resize-none leading-relaxed"
            />
            <TextureLibraryPicker
              disabled={processing}
              onSelectTexture={(suffix) => {
                sounds.playClick();
                setPrompt((prev) => (prev.includes(suffix) ? prev : `${prev.trim()}${suffix}`));
              }}
            />
          </>
        )}

        {/* Multi-view and Diagnosis in 3D Mode */}
        {mode === 'image3d' && (
          <div className="mt-3 rounded-2xl border border-sky-400/20 bg-sky-500/10 p-3">
            <p className="font-mono text-[8px] uppercase tracking-[0.2em] font-bold text-sky-300">Vistas para Shape multi-vista</p>
            <p className="mt-1 text-[9px] leading-relaxed text-slate-300">Añade fotos reales y etiquetadas para maximizar la fidelidad 360°.</p>
            <div className="mt-2.5 grid grid-cols-3 gap-1.5">
              {['front', 'right', 'back', 'left', 'top', 'bottom'].map((viewId) => (
                <button
                  key={viewId}
                  type="button"
                  disabled={processing}
                  onClick={() => {
                    sounds.playClick();
                    onPickMultiView?.(viewId);
                  }}
                  className={`rounded-full border px-2.5 py-1.5 text-center font-mono text-[8px] font-bold uppercase transition-all ${
                    multiViewInputs[viewId] ? 'border-emerald-400/40 bg-emerald-500/20 text-emerald-200' : 'border-white/10 bg-black/20 text-slate-400 hover:border-sky-400/30 hover:text-white'
                  }`}
                >
                  {multiViewInputs[viewId] ? `✓ ${viewId}` : `+ ${viewId}`}
                </button>
              ))}
            </div>
          </div>
        )}
      </Section>

      {mode === 'image3d' && <CategorySelector value={modelCategory} onChange={onSelectModelCategory} disabled={processing} />}

      {(mode === 'image3d' || mode === 'stl') && (
        <XrProductionPanel asset={asset} setAsset={setAsset} setSteps3d={setSteps3d} disabled={processing} />
      )}

      {/* Advanced Parameters Accordion */}
      <section className="overflow-hidden rounded-3xl border border-sky-500/20 bg-[#06173a]/75 backdrop-blur-2xl">
        <button
          onClick={() => {
            sounds.playClick();
            setAdvanced((current) => !current);
          }}
          className="flex w-full items-center justify-between px-4 py-3.5 text-xs font-bold text-slate-200"
        >
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
              </>
            )}
          </div>
        )}
      </section>

      {/* Main Execution Button */}
      <div className="mt-auto pt-2">
        {processing ? (
          <div className="loading-card loading-card-compact rounded-3xl p-4.5">
            <div className="mb-2 flex justify-between gap-3 text-xs">
              <span className="flex min-w-0 items-center gap-2 truncate text-sky-100 font-bold">
                <SpinnerGap size={16} weight="bold" className="shrink-0 animate-spin text-amber-300" aria-hidden="true" />
                {progress.label}
              </span>
              <strong className="font-mono text-white font-extrabold">{progress.percent}%</strong>
            </div>
            <div className="progress-track h-2.5 rounded-full">
              <div className="progress-fill progress-beam h-full rounded-full transition-all duration-700" style={{ width: `${progress.percent}%` }} />
            </div>
            {generating && (
              <button
                onClick={() => {
                  sounds.playWarning();
                  onCancel();
                }}
                className="mt-3 w-full rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-bold text-slate-200 hover:bg-white/20 transition-all"
              >
                Cancelar
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={() => {
              sounds.playClick();
              onGenerate();
            }}
            disabled={blocked}
            className="btn-glass-primary group relative w-full overflow-hidden rounded-full py-4 text-sm font-extrabold text-white shadow-[0_12px_40px_rgba(37,99,235,0.6)] transition-all duration-300 hover:scale-[1.03] hover:shadow-[0_20px_55px_rgba(37,99,235,0.75)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:scale-100"
          >
            <span className="relative z-10 flex items-center justify-center gap-2.5 font-outfit text-sm tracking-wide">
              {actionLabel}
              <ArrowRight size={19} weight="bold" className="transition-transform group-hover:translate-x-1.5" aria-hidden="true" />
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
