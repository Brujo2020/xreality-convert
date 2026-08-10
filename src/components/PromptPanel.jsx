import React, { useState } from 'react';
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
  Image,
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
  { id: 'image', step: '01', label: 'Crear imagen', hint: 'Referencia visual', Icon: Image },
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
    <nav className="grid grid-cols-3 gap-1.5 rounded-2xl border border-white/5 bg-black/20 p-1.5 shadow-inner">
      {MODES.map((item) => (
        <button
          key={item.id}
          disabled={disabled}
          onClick={() => setMode(item.id)}
          className={`group relative overflow-hidden rounded-xl px-2 py-2.5 text-left transition-all duration-300 ${
            mode === item.id
              ? 'bg-gradient-to-br from-blue-500 to-sky-500 text-white shadow-[0_8px_30px_rgba(22,137,232,0.28)]'
              : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
          }`}
        >
          <span className="flex items-center justify-between gap-2">
            <span className={`font-mono text-[9px] ${mode === item.id ? 'text-white/65' : 'text-sky-500/60'}`}>{item.step}</span>
            <item.Icon size={16} weight="duotone" className={mode === item.id ? 'text-white' : 'text-sky-400/70'} aria-hidden="true" />
          </span>
          <span className="mt-0.5 block text-[11px] font-semibold leading-tight">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}

function Section({ eyebrow, title, children }) {
  return (
    <section className="glass-card rounded-2xl p-4">
      <div className="mb-3">
        <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-sky-400/70">{eyebrow}</p>
        <h2 className="mt-1 text-sm font-semibold tracking-tight text-slate-100">{title}</h2>
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
          <button key={id} disabled={disabled} onClick={() => onChange(id)} className={`rounded-xl border px-2 py-2.5 text-center transition ${value === id ? 'border-cyan-300/40 bg-cyan-300/10 text-white shadow-[0_8px_20px_rgba(22,137,232,0.14)]' : 'border-white/5 bg-black/10 text-slate-500 hover:border-sky-300/20 hover:text-slate-200'}`}>
            {React.createElement(CATEGORY_ICONS[id] || Cube, { size: 20, weight: 'duotone', className: 'mx-auto text-sky-300', 'aria-hidden': true })}
            <span className="mt-1 block text-[9px] font-semibold">{item.label}</span>
          </button>
        ))}
      </div>
      <div className="mt-2.5 rounded-xl border border-sky-300/10 bg-sky-300/[0.035] p-2.5">
        <p className="text-[10px] leading-relaxed text-slate-300">{selected.description}</p>
        <div className="mt-2 flex flex-wrap gap-1.5 font-mono text-[7px] uppercase tracking-wider text-sky-300/70">
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
    <section className="glass-card rounded-2xl border-cyan-300/15 p-3 shadow-[0_12px_35px_rgba(1,10,30,0.32)]">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[8px] uppercase tracking-[0.18em] text-cyan-300/70">Salida rápida</p>
          <p className="mt-0.5 text-[11px] font-semibold text-white">Elige la optimización</p>
        </div>
        <span className="rounded-md border border-cyan-300/15 bg-cyan-300/5 px-2 py-1 font-mono text-[8px] uppercase text-cyan-200">{asset.profile}</span>
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
            className={`rounded-xl border px-2 py-2 text-left transition ${asset.profile === id ? 'border-cyan-300/45 bg-cyan-300/12 text-white' : 'border-white/[0.06] bg-black/15 text-slate-400 hover:border-cyan-300/25 hover:text-white'} disabled:cursor-not-allowed disabled:opacity-40`}
          >
            <span className="block text-[9px] font-semibold">{label}</span>
            <span className="mt-0.5 block text-[7px] leading-tight text-slate-500">{hint}</span>
          </button>
        ))}
      </div>
      {disabled && <p className="mt-2 text-[8px] leading-relaxed text-amber-200/75">Hay un proceso activo. Cancélalo para cambiar el perfil de salida.</p>}
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
  const isMeshy = engineProvider === 'meshy';
  const processing = generating || installingEngine || installingModel;
          </div>
          <span className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_18px_#52d7ff]" />
        </div>
        <ModeSelector mode={mode} setMode={setMode} disabled={processing} />
      </div>

      <UseCasePicker value={useCase} onChange={onSelectUseCase} disabled={processing} />

      {(mode === 'image3d' || mode === 'stl') && (
        <div className="sticky top-0 z-20 rounded-2xl bg-[#031027]/95 py-1 backdrop-blur-xl">
          <QuickDeliverySelector asset={asset} setAsset={setAsset} setSteps3d={setSteps3d} disabled={processing} />
        </div>
      )}

      <Section eyebrow="Fuente" title={mode === 'image3d' ? 'Motor de reconstrucción' : mode === 'image' ? 'Modelo generativo' : 'Modelo de geometría'}>
        {mode === 'image' && (
          <>
            <select value={imageModel} onChange={(event) => setImageModel(event.target.value)} className="field-modern" disabled={processing}>
              <option value={imageModel}>{imageModelAvailable ? imageModel : `${imageModel} · no instalado`}</option>
              {imageModels.filter((model) => model !== imageModel).map((model) => <option key={model} value={model}>{model}</option>)}
            </select>
            {!imageModelAvailable && <div className="mt-2 rounded-xl border border-amber-400/20 bg-amber-400/5 p-2.5"><p className="text-[10px] leading-relaxed text-amber-100">Este flujo necesita un modelo visual local.</p><button onClick={onInstallImageModel} disabled={installingModel} className="mt-2 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white">{installingModel ? 'Instalando FLUX…' : 'Instalar FLUX.2 Klein'}</button></div>}
          </>
        )}
        {mode === 'stl' && (
          <select value={stlModel} onChange={(event) => setStlModel(event.target.value)} className="field-modern" disabled={processing}>
            {!stlModels.length && <option>Sin modelo disponible</option>}
            {stlModels.map((model) => <option key={model}>{model}</option>)}
          </select>
        )}
        {mode === 'image3d' && (
          <div className={`engine-status rounded-xl p-3 ${hunyuanUp ? 'engine-status-ready' : installingEngine ? 'engine-status-working' : ''}`}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-1.5">
                <Engine size={17} weight="duotone" className={`shrink-0 ${hunyuanUp ? 'text-emerald-200' : installingEngine ? 'text-amber-200' : 'text-sky-200'}`} aria-hidden="true" />
                <span className={`state-dot h-2 w-2 shrink-0 rounded-full ${hunyuanUp ? 'bg-emerald-300 text-emerald-300' : installingEngine ? 'bg-amber-300 text-amber-300 animate-pulse' : 'bg-sky-300 text-sky-300'}`} />
                <span className="truncate text-[11px] font-medium text-slate-100">Hunyuan3D · Apple MLX</span>
              </div>
              <span className={`shrink-0 font-mono text-[8px] uppercase tracking-wider ${hunyuanUp ? 'text-emerald-200' : installingEngine ? 'text-amber-200' : 'text-sky-200'}`}>{hunyuanUp ? 'Disponible' : installingEngine ? 'Inicializando' : 'Preparando'}</span>
            </div>
            <p className="mt-2 font-mono text-[8px] uppercase tracking-[0.13em] text-slate-500">{hunyuanUp ? 'Forma · textura · mapas PBR' : installingEngine ? 'Python · MLX · validación local' : 'Arranque privado en este Mac'}</p>
            {!hunyuanUp && !installingEngine && <button onClick={onInstallEngine} className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-white shadow-lg shadow-blue-900/30 transition hover:bg-accent-hover">Inicializar motor</button>}
          </div>
        )}
      </Section>

      <Section eyebrow="Entrada" title={mode === 'image3d' ? 'Referencia del objeto' : 'Dirección creativa'}>
        {mode === 'image3d' ? (
          <button onClick={onPickImage} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onDropImage(event.dataTransfer.files[0]); }} disabled={processing} className="group relative flex min-h-36 w-full flex-col items-center justify-center overflow-hidden rounded-2xl border border-dashed border-sky-400/25 bg-gradient-to-br from-sky-400/5 to-transparent p-3 transition hover:border-sky-300/60 hover:bg-sky-400/10 disabled:opacity-50">
            {image3dInput ? (
              <>
                <img src={image3dInput.dataUrl} alt="Referencia 3D" onLoad={(event) => setImageInfo({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} className="max-h-36 rounded-xl object-contain shadow-2xl" />
                <span className="mt-2 max-w-full truncate text-[10px] text-slate-400">{image3dInput.name} · cambiar</span>
              </>
            ) : (
              <>
                <span className="grid h-12 w-12 place-items-center rounded-full border border-sky-400/20 bg-sky-400/10 text-sky-200 shadow-[0_0_30px_rgba(82,215,255,0.12)]"><Plus size={24} weight="duotone" aria-hidden="true" /></span>
                <span className="mt-3 text-xs font-semibold text-slate-200">Seleccionar o arrastrar imagen</span>
                <span className="mt-1 text-[10px] text-slate-500">PNG · JPG · WEBP</span>
              </>
            )}
          </button>
        ) : (
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={5}
            disabled={processing}
            placeholder={mode === 'stl' ? 'Describe una pieza, equipo o activo industrial…' : 'Describe una referencia limpia, centrada y lista para convertir…'}
            className="field-modern scroll-dark resize-none leading-relaxed"
          />
        )}
        {mode === 'image3d' && (
          <div className="mt-3 rounded-xl border border-cyan-300/10 bg-cyan-300/[0.03] p-2.5">
            <p className="font-mono text-[8px] uppercase tracking-[0.15em] text-cyan-200">Vistas para Shape multi-vista</p>
            <p className="mt-1 text-[9px] leading-relaxed text-slate-500">Añade fotos reales y etiquetadas. Las vistas auxiliares nunca se consideran evidencia para MASTER por sí solas.</p>
            {multiViewBackend?.available ? (
              <p className="mt-1 text-[8px] text-emerald-200">Backend Shape multi-vista listo: las cámaras admitidas se usarán en la reconstrucción.</p>
            ) : multiViewBackend?.state === 'installed_not_certified' ? (
              <p className="mt-1 text-[8px] leading-relaxed text-amber-200/80">Pesos Hunyuan3D-2mv instalados. El backend PyTorch/MPS permanece bloqueado hasta completar la certificación física en este Mac; estas fotos se conservarán como evidencia, pero Shape seguirá usando una sola referencia.</p>
            ) : (
              <p className="mt-1 text-[8px] leading-relaxed text-amber-200/80">Organización y validación activas. No se encontró un backend Shape multi-vista completo; estas fotos se conservarán como evidencia, pero no se enviarán a Shape.</p>
            )}
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              {['front', 'right', 'back', 'left', 'top', 'bottom'].map((viewId) => (
                <button key={viewId} type="button" disabled={processing} onClick={() => onPickMultiView?.(viewId)} className={`rounded-lg border px-2 py-2 text-left font-mono text-[8px] uppercase ${multiViewInputs[viewId] ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-100' : 'border-white/10 bg-black/10 text-slate-400 hover:border-cyan-300/30'}`}>
                  {multiViewInputs[viewId] ? `✓ ${viewId}` : `+ ${viewId}`}
                </button>
              ))}
            </div>
          </div>
        )}
        {mode === 'image3d' && imageInfo && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1 font-mono text-[8px] text-slate-400">{imageInfo.width}×{imageInfo.height}</span>
            <span className={`rounded-md border px-2 py-1 font-mono text-[8px] ${Math.min(imageInfo.width, imageInfo.height) >= 768 ? 'border-cyan-300/15 bg-cyan-300/5 text-cyan-200' : 'border-amber-300/15 bg-amber-300/5 text-amber-200'}`}>{Math.min(imageInfo.width, imageInfo.height) >= 768 ? 'Resolución correcta' : 'Resolución baja'}</span>
            <span className={`rounded-md border px-2 py-1 font-mono text-[8px] ${Math.max(imageInfo.width, imageInfo.height) / Math.min(imageInfo.width, imageInfo.height) <= 1.4 ? 'border-cyan-300/15 bg-cyan-300/5 text-cyan-200' : 'border-amber-300/15 bg-amber-300/5 text-amber-200'}`}>{Math.max(imageInfo.width, imageInfo.height) / Math.min(imageInfo.width, imageInfo.height) <= 1.4 ? 'Encuadre óptimo' : 'Conviene recortar'}</span>
          </div>
        )}
        {mode === 'image3d' && (
          <div className="analysis-card mt-3 rounded-2xl p-3">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.18em] text-sky-400/70"><Scan size={14} weight="duotone" aria-hidden="true" />Diagnóstico previo</p>
                <p className="mt-1 flex items-center gap-2 text-[10px] text-slate-400">
                  {analysisLoading && <span className="state-dot h-1.5 w-1.5 rounded-full bg-amber-300 text-amber-300 animate-pulse" />}
                  {analysisLoading ? 'Ojo de Águila analiza la referencia…' : analysis?.status || 'Esperando una referencia'}
                </p>
              </div>
              {analysis && <button onClick={() => setShowAnalysis((open) => !open)} className="rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[9px] text-slate-300 transition hover:border-sky-300/25">{showAnalysis ? 'Ocultar' : 'Revisar'}</button>}
            </div>
            {showAnalysis && analysis?.suggested_category && analysis?.suggested_category !== modelCategory && (
              <button disabled={processing} onClick={() => onSelectModelCategory(analysis.suggested_category)} className="mt-3 w-full rounded-lg border border-cyan-300/20 bg-cyan-300/5 px-2.5 py-2 text-[9px] font-semibold text-cyan-100 transition hover:bg-cyan-300/10">
                Aplicar categoría {MODEL_CATEGORIES[analysis.suggested_category]?.label || 'sugerida'}
              </button>
            )}
            {showAnalysis && analysis?.preview_base64 && image3dInput && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <figure className="rounded-xl border border-white/5 bg-black/20 p-2">
                  <figcaption className="mb-2 font-mono text-[8px] uppercase tracking-[0.16em] text-slate-500">Original</figcaption>
                  <img src={image3dInput.dataUrl} alt="Referencia original" className="h-28 w-full rounded-lg object-contain" />
                </figure>
                <figure className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] p-2">
                  <figcaption className="mb-2 font-mono text-[8px] uppercase tracking-[0.16em] text-cyan-200/70">Preparada</figcaption>
                  <img src={`data:image/png;base64,${analysis.preview_base64}`} alt="Referencia preparada" className="h-28 w-full rounded-lg object-contain" />
                </figure>
              </div>
            )}
            {showAnalysis && analysis && (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap gap-1.5">
                  <span className={`rounded-md border px-2 py-1 font-mono text-[8px] ${analysis.status === 'Óptima' ? 'border-cyan-300/15 bg-cyan-300/5 text-cyan-200' : analysis.status === 'Procesable con ajustes' ? 'border-amber-300/15 bg-amber-300/5 text-amber-200' : 'border-rose-300/15 bg-rose-300/5 text-rose-200'}`}>{analysis.status}</span>
                  {analysis.orientation && <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1 font-mono text-[8px] text-slate-400">{analysis.orientation}</span>}
                  {analysis.subject_components != null && <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1 font-mono text-[8px] text-slate-400">{analysis.subject_components} componentes</span>}
                  {analysis.has_alpha && <span className="rounded-md border border-cyan-300/15 bg-cyan-300/5 px-2 py-1 font-mono text-[8px] text-cyan-200">Transparencia detectada</span>}
                </div>
                {analysis.actions?.length ? (
                  <ul className="space-y-1 text-[10px] leading-relaxed text-slate-400">
                    {analysis.actions.slice(0, 3).map((action) => (
                      <li key={action} className="flex gap-2">
                        <span className="mt-[6px] h-1.5 w-1.5 shrink-0 rounded-full bg-sky-400/70" />
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
          <div className="grid grid-cols-3 gap-1.5 rounded-xl border border-white/5 bg-black/15 p-1.5">
            {[
              ['auto', 'Automático', 'Recomendado'],
              ['remove', 'Quitar', 'Objeto aislado'],
              ['keep', 'Conservar', 'Escena completa'],
            ].map(([id, label, hint]) => (
              <button key={id} disabled={processing} onClick={() => setBackgroundMode(id)} className={`rounded-lg px-2 py-2 text-center transition ${backgroundMode === id ? 'bg-cyan-300/12 text-white ring-1 ring-cyan-300/35' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'}`}>
                <span className="block text-[9px] font-semibold">{label}</span>
                <span className="mt-0.5 block text-[7px] text-slate-500">{hint}</span>
              </button>
            ))}
          </div>
          <p className="mt-2.5 text-[9px] leading-relaxed text-slate-400">
            {backgroundMode === 'auto' ? (modelCategory === 'architecture' ? 'El orquestador conservará el entorno porque forma parte del modelo.' : 'El orquestador aislará el sujeto y eliminará el fondo antes de reconstruir.') : backgroundMode === 'remove' ? 'Se forzará una silueta limpia, incluso si la imagen contiene entorno.' : 'La imagen completa entrará al motor sin recorte de fondo.'}
          </p>
        </Section>
      )}

      {(mode === 'image3d' || mode === 'stl') && (
        <XrProductionPanel asset={asset} setAsset={setAsset} setSteps3d={setSteps3d} disabled={processing} />
      )}

      <section className="overflow-hidden rounded-2xl border border-white/5 bg-black/10">
        <button onClick={() => setAdvanced((current) => !current)} className="flex w-full items-center justify-between px-4 py-3 text-xs font-medium text-slate-300">
          <span className="flex items-center gap-2"><SlidersHorizontal size={16} weight="duotone" className="text-sky-300" aria-hidden="true" />Controles avanzados</span>
          <Plus size={15} weight="duotone" className={`text-sky-400 transition-transform ${advanced ? 'rotate-45' : ''}`} aria-hidden="true" />
        </button>
        {advanced && (
          <div className="flex flex-col gap-4 border-t border-white/5 p-4">
            {mode === 'image' && (
              <>
                <button onClick={() => setParams((current) => ({ ...current, width: 2048, height: 2048, steps: 20 }))} className="flex items-center justify-center gap-2 rounded-xl border border-sky-400/25 bg-sky-400/5 px-3 py-2.5 text-xs font-semibold text-sky-200 hover:bg-sky-400/10"><Sparkle size={16} weight="duotone" aria-hidden="true" />Aplicar máxima calidad</button>
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
                <button onClick={() => onSelectModelCategory(modelCategory)} className="rounded-xl border border-sky-400/20 bg-sky-400/5 px-3 py-2.5 text-[10px] font-semibold text-sky-200 hover:bg-sky-400/10">Restaurar recomendación de {MODEL_CATEGORIES[modelCategory].label}</button>
              </>
            )}
            {mode !== 'image3d' && (
              <label className="block text-[11px] text-slate-400">
                Semilla reproducible
                <div className="mt-2 flex gap-2">
                  <input type="number" value={params.seed} onChange={(event) => update('seed', Number(event.target.value) || 0)} className="field-modern min-w-0 flex-1 font-mono" />
                  <button onClick={() => update('seed', randomSeed())} className="rounded-xl border border-border bg-elevated px-3 text-sm hover:border-sky-400/50">↻</button>
                </div>
              </label>
            )}
          </div>
        )}
      </section>

      <div className="mt-auto pt-1">
        {processing ? (
          <div className="loading-card loading-card-compact rounded-2xl p-4">
            <div className="mb-2 flex justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2 truncate text-sky-100"><SpinnerGap size={15} weight="bold" className="shrink-0 animate-spin text-amber-200" aria-hidden="true" />{progress.label}</span><strong className="font-mono text-white">{progress.percent}%</strong></div>
            <div className="progress-track h-2 rounded-full"><div className="progress-fill progress-beam h-full rounded-full transition-all duration-700" style={{ width: `${progress.percent}%` }} /></div>
            <p className="mt-2 font-mono text-[8px] uppercase tracking-[0.13em] text-slate-500">Pipeline local · memoria unificada</p>
            {generating && <button onClick={onCancel} className="mt-3 w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:bg-white/10">Cancelar y cambiar perfil</button>}
          </div>
        ) : (
          <button onClick={onGenerate} disabled={blocked} className="group relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-blue-600 via-sky-500 to-cyan-400 px-4 py-3.5 text-sm font-semibold text-white shadow-[0_15px_40px_rgba(22,137,232,0.28)] transition hover:-translate-y-0.5 hover:shadow-[0_20px_50px_rgba(22,137,232,0.36)] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:translate-y-0">
            <span className="relative z-10 flex items-center justify-center gap-2">{actionLabel}<ArrowRight size={17} weight="bold" className="transition-transform group-hover:translate-x-1" aria-hidden="true" /></span>
          </button>
        )}
      </div>
    </div>
  );
}
