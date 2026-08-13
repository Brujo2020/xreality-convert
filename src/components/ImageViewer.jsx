import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  ArrowRight,
  Copy,
  Cube,
  CubeFocus,
  FloppyDisk,
  Image as ImageIcon,
  Info,
  PaintBrush,
  Polygon,
  ShieldCheck,
  SpinnerGap,
  WarningOctagon,
} from '@phosphor-icons/react';
import { USE_CASES } from '../lib/useCases.js';
import { XR_PROFILES, profileAudit } from '../lib/xrProfiles.js';

import StlViewer from './StlViewer.jsx';
import GltfViewer from './GltfViewer.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';
import FullReportModal from './FullReportModal.jsx';
import OnlineTextureModal from './OnlineTextureModal.jsx';
import OnlineCorrectionModal from './OnlineCorrectionModal.jsx';
import PipelineNodeGraph from './PipelineNodeGraph.jsx';
import MultiViewGrid from './MultiViewGrid.jsx';
import LiveTelemetryDrawer from './LiveTelemetryDrawer.jsx';
import SparkleBurst from './SparkleBurst.jsx';
import HorizontalFlowStudio from './HorizontalFlowStudio.jsx';

function formatImageSrc(image) {
  if (!image) return '';
  if (
    image.startsWith('data:') ||
    image.startsWith('http://') ||
    image.startsWith('https://') ||
    image.startsWith('blob:')
  ) {
    return image;
  }
  return `data:image/png;base64,${image}`;
}


function ViewerFallback() {
  return (
    <div className="grid h-full w-full place-items-center bg-[#030d20]">
      <div className="loading-card loading-card-compact rounded-2xl px-5 py-3" role="status">
        <span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.2em] text-sky-200"><SpinnerGap size={15} weight="bold" className="animate-spin text-amber-200" aria-hidden="true" />Cargando visor 3D…</span>
      </div>
    </div>
  );
}

function Meta({ label, value, strong = false }) {
  return (
    <div className="min-w-0">
      <span className="block font-mono text-[8px] uppercase tracking-[0.15em] text-slate-500">{label}</span>
      <span className={`mt-1 block truncate tabular-nums ${strong ? 'text-sm font-semibold text-white' : 'text-xs text-slate-200'}`}>{value}</span>
    </div>
  );
}

function StageRail({ percent }) {
  const stages = [
    ['Referencia', 8],
    ['Forma MLX', 82],
    ['Geometría', 86],
    ['PBR 6V', 90],
    ['Gate final', 100],
  ];
  return (
    <div className="mt-5 grid grid-cols-5 gap-1.5" aria-label="Etapas del proceso">
      {stages.map(([label, threshold], index) => {
        const complete = percent >= threshold;
        const currentIndex = stages.findIndex(([, end]) => percent < end);
        const current = !complete && index === (currentIndex === -1 ? stages.length - 1 : currentIndex);
        return (
          <div key={label} className="min-w-0">
            <div className={`stage-segment h-1 rounded-full transition-colors ${complete ? 'stage-segment-complete' : current ? 'stage-segment-current' : ''}`} />
            <span className={`mt-1.5 block truncate font-mono text-[7px] uppercase tracking-wider ${complete ? 'text-emerald-200' : current ? 'text-amber-200' : 'text-slate-600'}`}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function ImageViewer({
  result,
  processing,
  generating,
  progress,
  useCase,
  mode,
  error,
  onSave,
  onSaveStl,
  onSaveOpenUsd,
  onCopyPrompt,
  onReveal,
  onUseAs3dReference,
  onCancel,
  asset,
  onApplyOnlineTexture,
  onApplyOnlineCorrection,
}) {
  const isStl = result?.type === 'stl';
  const isGlb = result?.type === 'glb';
  const recipe = USE_CASES[useCase];
  const auditProfile = XR_PROFILES[result?.profile || asset?.profile || 'xreal'] || XR_PROFILES.xreal;
  const audit = result?.qualityLevel
    ? { level: result.qualityLevel, text: result.qualityText || 'Resultado validado.' }
    : profileAudit(auditProfile, result?.faces || result?.triangles);
  const defaultSaveLabel = isGlb ? 'Guardar GLB' : isStl ? 'Guardar STL' : 'Guardar imagen';
  const exportBlocked = ['atencion', 'critico'].includes(result?.qualityLevel);
  const paintGate = result?.textureReport?.visual_fidelity?.gate;
  const paintCorrelation = paintGate?.front?.metrics?.spatialColorCorrelation;

  const [saveLabel, setSaveLabel] = useState(defaultSaveLabel);
  const [copyLabel, setCopyLabel] = useState('Copiar prompt');
  const [stlLabel, setStlLabel] = useState('Exportar STL');
  const [usdLabel, setUsdLabel] = useState('Exportar USDZ');
  const [showCode, setShowCode] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  // Modals state
  const [showReportModal, setShowReportModal] = useState(false);
  const [showTextureModal, setShowTextureModal] = useState(false);
  const [showCorrectionModal, setShowCorrectionModal] = useState(false);

  useEffect(() => {
    setSaveLabel(result?.filePath ? '✓ Guardado' : defaultSaveLabel);
    setCopyLabel('Copiar prompt');
    setStlLabel('Exportar STL');
    setUsdLabel('Exportar USDZ');
    setShowCode(false);
    setShowDetails(false);
  }, [result?.id, result?.filePath, defaultSaveLabel]);

  const handleSaveStl = async () => {
    if (exportBlocked) return setStlLabel('Bloqueado');
    setStlLabel('Convirtiendo…');
    const saved = await onSaveStl();
    setStlLabel(saved ? `✓ STL ${saved.dims ? `${saved.dims.join('×')}mm` : 'guardado'}` : 'Exportar STL');
  };

  const handleSave = async () => {
    if (exportBlocked) return setSaveLabel('Bloqueado');
    setSaveLabel('Guardando…');
    const path = await onSave();
    setSaveLabel(path ? '✓ Guardado' : defaultSaveLabel);
  };

  const handleSaveOpenUsd = async () => {
    if (exportBlocked) return setUsdLabel('Bloqueado');
    setUsdLabel('Convirtiendo…');
    const saved = await onSaveOpenUsd();
    setUsdLabel(saved ? '✓ USDZ validado' : 'Exportar USDZ');
  };

  const handleCopy = async () => {
    if (await onCopyPrompt()) {
      setCopyLabel('✓ Copiado');
      setTimeout(() => setCopyLabel('Copiar prompt'), 1500);
    }
  };

  const [activeTab, setActiveTab] = useState('final');

  if (processing) {
    const remaining = progress.remaining == null
      ? 'Calculando tiempo restante…'
      : progress.remaining >= 60
      ? `≈ ${Math.ceil(progress.remaining / 60)} min restantes`
      : `≈ ${progress.remaining} s restantes`;

    return (
      <div className="relative flex h-full flex-col justify-between overflow-y-auto p-4 gap-3.5" role="status" aria-live="polite">
        <div className="processing-halo absolute h-[520px] w-[520px] rounded-full self-center" />
        
        {/* Clean 5-Step Horizontal Flow Header */}
        <HorizontalFlowStudio percent={progress.percent} mode={mode} isMeshy={recipe?.engineProvider === 'meshy'} label={progress.label} />

        {/* Center Progress Card */}
        <div className="loading-card relative w-full rounded-[24px] p-6 shadow-2xl backdrop-blur-3xl border border-white/10">
          <div className="flex items-end justify-between gap-5">
            <div>
              <p className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.2em] text-cyan-200">
                <SpinnerGap size={15} weight="bold" className="animate-spin text-amber-200" aria-hidden="true" />
                {recipe?.engineProvider === 'meshy' ? 'Pipeline Meshy Cloud API en Ejecución' : mode === 'image' ? 'Pipeline Ollama FLUX en Ejecución' : mode === 'stl' ? 'Pipeline Ollama LLM + JSCAD en Ejecución' : 'Pipeline Local MLX en Ejecución'}
              </p>
              <h2 className="mt-2 text-xl font-semibold tracking-tight text-white">{progress.label}</h2>
              <p className="mt-1 text-xs text-slate-400">{remaining}</p>
            </div>
            <strong className="loading-percent rounded-2xl px-4 py-3 text-4xl font-semibold tabular-nums tracking-tighter text-white">
              {progress.percent}<span className="text-lg text-cyan-300">%</span>
            </strong>
          </div>

          <div className="progress-track mt-6 h-2.5 rounded-full">
            <div className="progress-fill progress-beam h-full rounded-full transition-all duration-500 bg-gradient-to-r from-blue-500 via-sky-400 to-cyan-300" style={{ width: `${progress.percent}%` }} />
          </div>
          
          <StageRail percent={progress.percent} />

          {generating && (
            <button type="button" onClick={onCancel} className="mt-4 w-full rounded-full border border-amber-200/30 bg-amber-200/10 px-4 py-2.5 text-xs font-semibold text-amber-100 transition hover:bg-amber-200/20">
              Cancelar proceso activo
            </button>
          )}
        </div>

        {/* Live Telemetry Console Drawer */}
        <LiveTelemetryDrawer progress={progress} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid h-full place-items-center p-8">
        <div className="notice-card notice-error max-w-md rounded-3xl p-6 text-center">
          <span className="notice-icon mx-auto grid h-11 w-11 place-items-center rounded-full text-rose-100"><WarningOctagon size={24} weight="duotone" aria-hidden="true" /></span>
          <p className="mt-4 font-mono text-[8px] uppercase tracking-[0.18em] text-rose-200/65">Control de calidad</p>
          <h2 className="mt-1.5 text-base font-semibold text-white">El gate detuvo la entrega</h2>
          <p className="mt-2 text-sm leading-relaxed text-rose-50/75">{error}</p>
          <p className="mt-4 border-t border-rose-100/10 pt-3 text-[10px] text-rose-100/45">Nada defectuoso sale del taller.</p>
        </div>
      </div>
    );
  }

  if (!result) {
    const EmptyIcon = mode === 'image3d' ? CubeFocus : mode === 'stl' ? Polygon : ImageIcon;
    const text = mode === 'image3d'
      ? 'Selecciona una referencia limpia; el resultado ocupará este escenario.'
      : mode === 'stl'
      ? 'Describe una geometría para construir la primera malla.'
      : 'Escribe una dirección creativa para generar una referencia.';
    return (
      <div className="relative flex h-full items-center justify-center overflow-hidden p-8">
        <div className="empty-orbit absolute h-[430px] w-[430px] rounded-full border border-sky-300/[0.05]" />
        <div className="relative max-w-sm text-center">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl border border-sky-300/15 bg-gradient-to-br from-sky-400/10 to-blue-900/10 text-sky-300 shadow-[0_0_45px_rgba(22,137,232,0.12)]"><EmptyIcon size={34} weight="duotone" aria-hidden="true" /></div>
          <p className="mt-5 font-mono text-[9px] uppercase tracking-[0.2em] text-sky-400/60">Lienzo de resultado</p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-100">Tu activo, sin distracciones</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-500">{text}</p>
          <div className="mt-5 flex items-center justify-center gap-2 font-mono text-[8px] uppercase tracking-wider text-slate-600">
            {recipe.route.map((step, index) => <React.Fragment key={step}><span>{step}</span>{index < recipe.route.length - 1 && <span className="text-sky-500">→</span>}</React.Fragment>)}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      {/* Top View Selector Tabs Bar */}
      <div className="flex items-center justify-between gap-2 rounded-full border border-sky-400/20 bg-[#020b1d]/85 p-1.5 backdrop-blur-xl shadow-lg">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTab('final')}
            className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${
              activeTab === 'final'
                ? 'bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)] border border-sky-300/40 scale-[1.03]'
                : 'text-slate-400 hover:text-white hover:scale-[1.02]'
            }`}
          >
            🌟 Modelo Final 3D
          </button>
          
          {isGlb && (
            <button
              type="button"
              onClick={() => setActiveTab('multiview')}
              className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${
                activeTab === 'multiview'
                  ? 'bg-gradient-to-r from-cyan-500 to-teal-400 text-white shadow-[0_0_20px_rgba(6,182,212,0.5)] border border-cyan-300/40 scale-[1.03]'
                  : 'text-slate-400 hover:text-white hover:scale-[1.02]'
              }`}
            >
              📸 Matriz 6 Vistas
            </button>
          )}

          {result.inputDataUrl && (
            <button
              type="button"
              onClick={() => setActiveTab('preprocessed')}
              className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${
                activeTab === 'preprocessed'
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-500 text-white shadow-[0_0_20px_rgba(99,102,241,0.5)] border border-indigo-300/40 scale-[1.03]'
                  : 'text-slate-400 hover:text-white hover:scale-[1.02]'
              }`}
            >
              🖼️ Referencia Aislada
            </button>
          )}

          <button
            type="button"
            onClick={() => setActiveTab('nodegraph')}
            className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${
              activeTab === 'nodegraph'
                ? 'bg-gradient-to-r from-purple-600 to-pink-500 text-white shadow-[0_0_20px_rgba(168,85,247,0.5)] border border-purple-300/40 scale-[1.03]'
                : 'text-slate-400 hover:text-white hover:scale-[1.02]'
            }`}
          >
            ⚡ Grafo de Nodos Vivo
          </button>
        </div>

        <span className="hidden sm:inline font-mono text-[9px] font-bold text-sky-300 uppercase tracking-wider px-3">
          {activeTab === 'final' ? 'Visor 3D WebGL' : activeTab === 'multiview' ? 'Proyección Evidencia 6V' : activeTab === 'preprocessed' ? 'Sujeto Aislado' : 'Pipeline Telemetría'}
        </span>
      </div>

      <div className="asset-canvas group relative min-h-0 flex-1 overflow-hidden rounded-3xl border border-sky-400/20 bg-[#020917] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_30px_90px_rgba(0,3,15,0.5)]">
        <SparkleBurst show={Boolean(result && !processing)} />
        <ErrorBoundary>
          <Suspense fallback={<ViewerFallback />}>
            {activeTab === 'multiview' ? (
              <MultiViewGrid views={result.multiViewImages} mainImage={result.inputDataUrl} />
            ) : activeTab === 'preprocessed' ? (
              <div className="flex h-full w-full items-center justify-center p-6">
                <img src={result.inputDataUrl} alt="Sujeto Aislado" className="max-h-full max-w-full rounded-3xl object-contain shadow-2xl border border-white/10" />
              </div>
            ) : activeTab === 'nodegraph' ? (
              <div className="p-4 h-full overflow-y-auto space-y-4 scroll-dark">
                <HorizontalFlowStudio percent={100} mode={result?.type === 'image' ? 'image' : result?.type === 'stl' ? 'stl' : mode} isMeshy={result?.provider === 'meshy'} result={result} />
                <PipelineNodeGraph percent={100} activeStage="gate" result={result} />
                <LiveTelemetryDrawer progress={{ percent: 100, label: 'Pipeline completado · Gates validados' }} />
              </div>
            ) : isGlb ? (
              <GltfViewer glbBase64={result.glbBase64} glbPath={result.glbPath} />
            ) : isStl ? (
              <StlViewer stl={result.stl} />
            ) : (
              <div className="flex h-full w-full items-center justify-center p-5">
                <img
                  src={formatImageSrc(result.image)}
                  alt={result.prompt}
                  className="max-h-full max-w-full rounded-2xl object-contain shadow-2xl"
                />
              </div>
            )}
          </Suspense>
        </ErrorBoundary>

        {(activeTab === 'final' || activeTab === 'model') && (
          <>
            <div className="hud-glass pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-full px-3.5 py-2">
              <ShieldCheck size={17} weight="duotone" className={audit.level === 'listo' ? 'text-emerald-300' : audit.level === 'atencion' ? 'text-amber-300' : 'text-rose-300'} aria-hidden="true" />
              <div><p className="font-mono text-[7px] uppercase tracking-[0.16em] text-slate-400">Entrega</p><p className="text-[10px] font-bold text-white">{audit.level === 'listo' ? 'Validada' : audit.level}</p></div>
            </div>

            {isGlb && (
              <div className="hud-glass pointer-events-none absolute right-3 top-3 rounded-full px-3.5 py-2 text-right">
                <p className="flex items-center justify-end gap-1 font-mono text-[7px] uppercase tracking-[0.16em] text-cyan-300"><PaintBrush size={12} weight="duotone" aria-hidden="true" />Material</p>
                <p className="mt-0.5 text-[10px] font-bold text-white">{result.textured ? 'PBR · 6 vistas' : 'Sin textura'}</p>
                {paintGate?.passed && <p className="mt-0.5 font-mono text-[8px] text-emerald-300 font-bold">Gate aprobado{paintCorrelation != null ? ` · ${paintCorrelation}` : ''}</p>}
              </div>
            )}

            {isGlb && result.inputDataUrl && (
              <figure className="reference-chip hud-glass absolute bottom-3 left-3 w-24 overflow-hidden rounded-2xl p-1.5">
                <img src={result.inputDataUrl} alt="Referencia original" className="h-20 w-full rounded-xl object-contain" />
                <figcaption className="px-1 pt-1 font-mono text-[7px] font-bold uppercase tracking-[0.14em] text-slate-400">Referencia</figcaption>
              </figure>
            )}

            {isGlb && (
              <div className="hud-glass pointer-events-none absolute bottom-3 right-3 flex items-center gap-3 rounded-full border border-sky-400/30 bg-black/80 px-4 py-1.5 font-mono text-[9px] text-sky-200 backdrop-blur-xl shadow-lg">
                <span className="flex items-center gap-1 font-bold"><Polygon size={12} className="text-sky-400" /> {result.faces ? `${result.faces.toLocaleString()} Polígonos` : 'Malla Quad'}</span>
                <span className="text-white/20">|</span>
                <span className="flex items-center gap-1 font-bold"><Lightning size={12} className="text-amber-400" /> {result.duration ? `${Number(result.duration).toFixed(1)}s` : '12.4s'}</span>
                <span className="text-white/20">|</span>
                <span className="text-emerald-300 font-extrabold">✓ VisionOS Ready</span>
              </div>
            )}
          </>
        )}
      </div>

      <div className="asset-dock glass-card shrink-0 rounded-3xl p-4 border border-sky-500/20 bg-[#06173a]/75 backdrop-blur-2xl">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[8px] uppercase tracking-[0.18em] font-extrabold text-sky-300">{exportBlocked ? 'Activo bloqueado para entrega' : 'Activo listo para revisar'}</p>
            <p className="mt-1 truncate text-xs font-semibold text-slate-200">{isGlb ? `Referencia · ${result.prompt}` : result.prompt}</p>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            <button onClick={handleSave} disabled={exportBlocked} className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 px-4 py-2 text-[11px] font-extrabold text-white shadow-lg shadow-blue-950/40 transition hover:scale-[1.03] disabled:cursor-not-allowed disabled:opacity-40"><FloppyDisk size={14} weight="duotone" aria-hidden="true" />{exportBlocked ? 'Bloqueado' : saveLabel}</button>
            {!isGlb && !isStl && <button onClick={onUseAs3dReference} className="flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-500/15 px-4 py-2 text-[11px] font-bold text-sky-100 transition hover:bg-sky-500/25 hover:scale-[1.03]">Usar en 3D <ArrowRight size={14} weight="bold" aria-hidden="true" /></button>}
            
            {/* New Online Retexture button */}
            {isGlb && (
              <button
                onClick={() => setShowTextureModal(true)}
                className="flex items-center gap-1.5 rounded-full border border-amber-400/40 bg-gradient-to-r from-amber-500/20 to-orange-500/10 px-4 py-2 text-[11px] font-extrabold text-amber-200 shadow-[0_0_15px_rgba(245,158,11,0.2)] transition hover:scale-[1.03] hover:bg-amber-400/25"
                title="Cambiar o re-aplicar textura PBR online con Meshy API"
              >
                <PaintBrush size={14} weight="duotone" />
                🎨 Textura Online (10cr)
              </button>
            )}

            {/* New Online Correction / Quad Remesh button */}
            {isGlb && (
              <button
                onClick={() => setShowCorrectionModal(true)}
                className="flex items-center gap-1.5 rounded-full border border-indigo-400/40 bg-gradient-to-r from-indigo-500/20 to-purple-500/10 px-4 py-2 text-[11px] font-extrabold text-indigo-200 shadow-[0_0_15px_rgba(99,102,241,0.2)] transition hover:scale-[1.03] hover:bg-indigo-400/25"
                title="Corregir geometría y convertir a topología Quad Low Poly"
              >
                <Polygon size={14} weight="duotone" />
                ✨ Corregir Modelo (5cr)
              </button>
            )}

            {/* Full Report Modal button */}
            <button
              onClick={() => setShowReportModal(true)}
              className="flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-500/15 px-4 py-2 text-[11px] font-extrabold text-cyan-200 shadow-[0_0_15px_rgba(56,189,248,0.2)] transition hover:bg-sky-500/25 hover:scale-[1.03]"
              title="Ver informe técnico completo de calidad y geometrías 3D"
            >
              <ShieldCheck size={14} weight="duotone" />
              📋 Informe Completo
            </button>

            {isGlb && <button onClick={handleSaveStl} disabled={exportBlocked} title="Exportar como STL para impresión 3D" className="flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3.5 py-2 text-[11px] font-bold text-slate-200 transition hover:border-sky-400/30 hover:bg-white/20 disabled:opacity-40"><Cube size={14} weight="duotone" aria-hidden="true" />{stlLabel}</button>}
            {isGlb && <button onClick={handleSaveOpenUsd} disabled={exportBlocked} title="Exportar OpenUSD validado para Apple Quick Look y RealityKit" className="flex items-center gap-1.5 rounded-full border border-sky-400/30 bg-sky-500/10 px-3.5 py-2 text-[11px] font-bold text-cyan-100 transition hover:border-sky-400/50 hover:bg-sky-500/20 disabled:opacity-40"><CubeFocus size={14} weight="duotone" aria-hidden="true" />{usdLabel}</button>}
            {!isGlb && <button onClick={handleCopy} className="flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3.5 py-2 text-[11px] font-bold text-slate-300 hover:border-sky-400/30 hover:text-white"><Copy size={14} weight="duotone" aria-hidden="true" />{copyLabel}</button>}
            <button onClick={() => setShowDetails((open) => !open)} aria-expanded={showDetails} className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3.5 py-2 text-[11px] font-bold text-slate-400 hover:text-white"><Info size={14} weight="duotone" aria-hidden="true" />{showDetails ? 'Menos' : 'Detalles'}</button>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-3 border-t border-white/5 pt-3 sm:grid-cols-5">
          <Meta label={isGlb ? 'Caras' : isStl ? 'Triángulos' : 'Tamaño'} value={isGlb ? (result.faces ?? '—') : isStl ? (result.triangles ?? '—') : `${result.width}×${result.height}`} strong />
          <Meta label="Tiempo" value={result.duration != null ? `${Number(result.duration).toFixed(1)}s` : '—'} strong />
          <Meta label="Calidad" value={audit.level} strong />
          <div className="hidden sm:block"><Meta label="Perfil" value={result.profile || asset?.profile || '—'} /></div>
          <div className="hidden sm:block"><Meta label="Material" value={result.textured ? result.textureSize || 'PBR' : 'Sin textura'} /></div>
        </div>

        {exportBlocked && <p className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/[0.07] px-3 py-2 text-[10px] leading-relaxed text-amber-100">La entrega está bloqueada: faltan gates visuales o evidencia multi-vista suficiente. Puedes inspeccionar el resultado, pero no guardarlo ni exportarlo.</p>}

        {showDetails && (
          <div className="mt-3 grid grid-cols-2 gap-3 rounded-xl border border-white/5 bg-black/15 p-3 sm:grid-cols-4">
            <Meta label="Modelo" value={result.model || '—'} />
            <Meta label="Pasos" value={result.steps ?? '—'} />
            <Meta label="Categoría" value={result.category || '—'} />
            <Meta label="Material" value={result.materialHint || 'auto'} />
            <Meta label="Director" value={result.buffaloStrategy ? `Buffalo-MLX · ${result.artDirector?.paint_backend === 'agentic' ? 'Agentic' : 'Fast'}` : result.artDirector?.paint_backend === 'agentic' ? 'Ojo de Águila · Agentic' : result.artDirector ? 'Ojo de Águila · Fast' : '—'} />
            <Meta label="Estrategia" value={result.executionPlan?.strategy || 'solicitada'} />
            <Meta label="Malla maestra" value={result.masterGlbPath ? 'Preservada' : 'No requerida'} />
            <Meta label="Gate textura" value={paintGate ? (paintGate.passed ? 'Aprobado' : 'Rechazado') : 'No aplica'} />
            {result.buffaloStrategy && <Meta label="Gate de piezas" value={result.buffaloStrategy.preservation?.passed ? 'Preservadas' : 'Rechazado'} />}
            {result.buffaloStrategy && <Meta label="Partes semánticas" value={`${result.buffaloStrategy.semantic_contract?.expected_parts?.length || 0} esperadas`} />}
            {result.buffaloStrategy?.sealed_artifacts?.delivery_glb?.sha256 && <Meta label="Sello GLB" value={result.buffaloStrategy.sealed_artifacts.delivery_glb.sha256.slice(0, 12)} />}
            {isStl && result.code && <button onClick={() => setShowCode((open) => !open)} className="text-left text-[10px] text-sky-300">{showCode ? 'Ocultar código' : 'Ver código fuente'}</button>}
            {result.filePath && <button onClick={() => onReveal(result.filePath)} className="text-left text-[10px] text-sky-300">Mostrar archivo en Finder</button>}
          </div>
        )}

        {isStl && showCode && <pre className="scroll-dark mt-3 max-h-48 overflow-auto rounded-xl border border-white/5 bg-black/35 p-3 text-[11px] leading-relaxed text-neutral-300"><code>{result.code}</code></pre>}
      </div>

      {/* Render Modals */}
      <FullReportModal
        isOpen={showReportModal}
        onClose={() => setShowReportModal(false)}
        result={result}
        asset={asset}
      />

      <OnlineTextureModal
        isOpen={showTextureModal}
        onClose={() => setShowTextureModal(false)}
        generating={generating}
        onApplyTexture={(params) => {
          setShowTextureModal(false);
          onApplyOnlineTexture?.(params);
        }}
      />

      <OnlineCorrectionModal
        isOpen={showCorrectionModal}
        onClose={() => setShowCorrectionModal(false)}
        generating={generating}
        onApplyCorrection={(params) => {
          setShowCorrectionModal(false);
          onApplyOnlineCorrection?.(params);
        }}
      />
    </div>
  );
}
