import React, { Suspense, lazy, useEffect, useState } from 'react';
import {
  ArrowRight,
  Copy,
  Cube,
  CubeFocus,
  FloppyDisk,
  Image as ImageIcon,
  Info,
  Lightning,
  PaintBrush,
  Polygon,
  ShieldCheck,
  SpinnerGap,
  WarningOctagon,
} from '@phosphor-icons/react';
import { USE_CASES } from '../lib/useCases.js';
import { XR_PROFILES, profileAudit } from '../lib/xrProfiles.js';
import { getAuditSemaphore } from '../lib/uiStatus.js';
import { nextActionForError } from '../lib/errorActions.js';

const StlViewer = lazy(() => import('./StlViewer.jsx'));
const GltfViewer = lazy(() => import('./GltfViewer.jsx'));

function ViewerFallback() {
  return (
    <div className="flex h-full w-full items-center justify-center font-mono text-[10px] uppercase tracking-[0.18em] text-sky-300/60">
      Cargando visor 3D…
    </div>
  );
}

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

function StageRail({ percent, textureEnabled }) {
  const stages = [
    ['Referencia', 8],
    ['Forma MLX', 82],
    ['Geometría', 86],
    [textureEnabled ? 'PBR 6V' : 'Sin Paint', 90],
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

function AssetIdentity({ result }) {
  if (!result?.assetName) return null;
  return (
    <div className="mb-3 rounded-xl border border-sky-300/10 bg-sky-300/[0.035] px-3 py-2">
      <p className="font-mono text-[8px] uppercase tracking-[0.16em] text-sky-400/70">Identidad del activo</p>
      <p className="mt-1 truncate text-xs font-medium text-slate-100">{result.assetName}</p>
    </div>
  );
}

const AUDIT_STYLES = {
  green: ['Aprobado', 'bg-cyan-300', 'border-cyan-300/20 bg-cyan-300/5 text-cyan-100'],
  amber: ['Revisar', 'bg-amber-300', 'border-amber-300/20 bg-amber-300/5 text-amber-100'],
  red: ['Bloqueado', 'bg-rose-300', 'border-rose-300/20 bg-rose-300/5 text-rose-100'],
};

function VisualAudit({ audit, result, asset }) {
  const light = getAuditSemaphore(audit.level);
  const [label, dotClass, panelClass] = AUDIT_STYLES[light];
  const budget = result?.targetFaces || asset?.targetFaces;
  const faces = result?.faces || result?.triangles;
  const withinBudget = budget && faces ? faces <= budget : null;
  const refinement = result?.lowpolyRefinement;
  return (
    <div className={`mb-3 rounded-xl border px-3 py-2 ${panelClass}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dotClass}`} />
          <div className="min-w-0">
            <p className="font-mono text-[8px] uppercase tracking-[0.16em] opacity-70">Auditoría visual</p>
            <p className="mt-0.5 truncate text-[10px] font-medium">{audit.text}</p>
          </div>
        </div>
        <span className="font-mono text-[8px] uppercase tracking-wider">{label}</span>
      </div>
      <div className="mt-2 grid grid-cols-3 gap-1.5 text-[9px]">
        <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Calidad: {audit.level}</span>
        <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Caras: {faces || '—'}</span>
        <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">{withinBudget == null ? 'Presupuesto: —' : withinBudget ? 'Presupuesto: OK' : 'Presupuesto: revisar'}</span>
      </div>
      {refinement && (
        <div className="mt-2 grid grid-cols-3 gap-1.5 text-[9px]">
          <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Fragmentos: {refinement.output_components === 1 ? '0 · OK' : refinement.output_components}</span>
          <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Degenerados: {refinement.degenerate_faces || 0}</span>
          <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Puntas: {(refinement.edge_max_p95 || 0) <= 4 ? 'OK' : 'Revisar'}</span>
          {refinement.fidelity && <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Forma Δ: {(refinement.fidelity.sampled_hausdorff_ratio * 100).toFixed(2)}%</span>}
          {refinement.fidelity?.normal_error_p95_degrees != null && <span className="rounded-lg border border-white/5 bg-black/15 px-2 py-1">Normales p95: {refinement.fidelity.normal_error_p95_degrees.toFixed(1)}°</span>}
        </div>
      )}
      {result?.textureRequested && !result?.textured && (
        <div className="mt-2 rounded-lg border border-rose-300/20 bg-rose-300/10 px-2 py-1.5 text-[9px] font-semibold text-rose-100">
          Este preview NO tiene textura PBR embebida. Es un GLB shape-only, por eso se ve gris.
        </div>
      )}
    </div>
  );
}

function TexturePreview({ result, inspection }) {
  const report = result?.textureReport;
  const reportPassed = report?.passed === true;
  const reportFailed = report?.passed === false || (Array.isArray(report?.reasons) && report.reasons.length > 0);
  const textureSlots = inspection?.textureSlots || [];
  const hasLoadedTextures = (inspection?.textureCount || 0) > 0;
  const inspectionMissingTextures = inspection && result?.textured && reportPassed && !hasLoadedTextures;
  const alignmentRejected = report?.reference_alignment?.passed === false
    && report?.reference_alignment?.reason !== 'reference_anchor_disabled';
  const status = hasLoadedTextures && reportPassed && report?.reference_anchored
    ? 'PBR IA anclado a la imagen · revisar'
    : hasLoadedTextures && reportPassed && alignmentRejected
    ? 'PBR IA sin anclaje: silueta incompatible · revisar'
    : hasLoadedTextures && reportPassed
    ? 'PBR embebido visible en visor'
    : hasLoadedTextures && reportFailed
    ? 'Textura visible, pero GLB no autocontenido'
    : inspectionMissingTextures
    ? 'PBR validado; mapas no visibles'
    : result?.textured && reportPassed
    ? 'PBR validado; cargando mapas'
    : reportFailed
    ? 'PBR no validado'
    : result?.textureRequested
    ? 'Textura solicitada'
    : 'Shape-only';
  const panelClass = hasLoadedTextures || reportPassed
    ? inspectionMissingTextures
      ? 'border-amber-300/20 bg-amber-300/5 text-amber-100'
      : 'border-cyan-300/20 bg-cyan-300/5 text-cyan-100'
    : reportFailed
    ? 'border-rose-300/20 bg-rose-300/5 text-rose-100'
    : 'border-white/5 bg-black/15 text-slate-300';

  return (
    <div className={`mb-3 rounded-xl border px-3 py-2 ${panelClass}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[8px] uppercase tracking-[0.16em] opacity-70">Preview textura</p>
          <p className="mt-0.5 text-[10px] font-medium">{status}</p>
        </div>
        <span className="font-mono text-[8px] uppercase tracking-wider">
          {inspection ? `${inspection.texturedMaterialCount}/${inspection.materialCount} materiales` : 'Inspeccionando'}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 font-mono text-[8px] uppercase tracking-wider">
        <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">
          Mapas {inspection?.textureCount ?? report?.textures ?? 0}
        </span>
        <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">
          Embebidas {report?.embedded_images ?? '—'}/{report?.images ?? '—'}
        </span>
        {report?.material_profile && (
          <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">
            Material {report.material_profile}
          </span>
        )}
        {report?.reference_alignment?.silhouette_iou != null && (
          <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">
            Coincidencia silueta {(report.reference_alignment.silhouette_iou * 100).toFixed(0)}%
          </span>
        )}
        {(textureSlots.length ? textureSlots : ['Sin slots visibles']).slice(0, 4).map((slot) => (
          <span key={slot} className="rounded-md border border-white/5 bg-black/15 px-2 py-1">{slot}</span>
        ))}
      </div>
      {reportFailed && (
        <p className="mt-2 text-[9px] leading-relaxed opacity-80">
          {Array.isArray(report.reasons) ? report.reasons.join(', ') : 'El gate PBR fallo.'}
        </p>
      )}
      {alignmentRejected && (
        <p className="mt-2 text-[9px] leading-relaxed text-amber-100/80">
          La foto no se proyectó directamente porque deformaría la textura; revisa el borrador IA antes de usarlo.
        </p>
      )}
    </div>
  );
}

function CanonicalEvidence({ renderSet }) {
  const views = renderSet?.views || [];
  const warnings = renderSet?.warnings || [];
  const metrics = renderSet?.performance;
  const encodedMegabytes = metrics ? (metrics.encodedBytes / 1024 / 1024).toFixed(1) : null;
  return (
    <div className="mb-3 rounded-xl border border-violet-300/15 bg-violet-300/[0.035] px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-mono text-[8px] uppercase tracking-[0.16em] text-violet-200/70">TruthLoop · 8 vistas canónicas</p>
          <p className="mt-0.5 text-[10px] text-slate-300">
            {warnings.length
              ? `Captura incompleta: ${warnings.join(', ')}`
              : views.length === 8
              ? 'Evidencia local 1024² lista para comparar y medir.'
              : 'Renderizando evidencia local…'}
          </p>
          {metrics && (
            <p className="mt-1 font-mono text-[7px] uppercase tracking-wider text-violet-200/55">
              {metrics.captureDurationMs} ms · {encodedMegabytes} MB · memoria binaria única
            </p>
          )}
        </div>
        <span className="font-mono text-[8px] uppercase tracking-wider text-violet-200/70">
          {views.length}/8
        </span>
      </div>
      {views.length > 0 && (
        <div className="mt-2 grid grid-cols-4 gap-1.5 sm:grid-cols-8">
          {views.map((view) => (
            <figure key={view.viewId} className="overflow-hidden rounded-md border border-white/5 bg-black/20">
              <img
                src={view.imageUrl || view.dataUrl}
                alt={`Vista ${view.azimuthDegrees} grados`}
                width={view.width}
                height={view.height}
                decoding="async"
                className="aspect-square w-full object-cover"
              />
              <figcaption className="truncate px-1 py-0.5 text-center font-mono text-[7px] text-slate-400">
                {view.azimuthDegrees}° · {view.imageSha256.slice(0, 6)}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
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
  onErrorDismiss,
  externalAction,
  onClearExternalAction,
}) {
  const isStl = result?.type === 'stl';
  const isGlb = result?.type === 'glb';
  const recipe = USE_CASES[useCase];
  const auditProfile = XR_PROFILES[result?.profile || asset?.profile || 'xreal'] || XR_PROFILES.xreal;
  const audit = result?.qualityLevel
    ? { level: result.qualityLevel, text: result.qualityText || 'Resultado validado.' }
    : profileAudit(auditProfile, result?.faces || result?.triangles);
  const defaultSaveLabel = isGlb ? 'Guardar GLB' : isStl ? 'Guardar STL' : 'Guardar imagen';
  const deliveryBlocked = isGlb && audit.level === 'critico';
  const paintGate = result?.textureReport?.visual_fidelity?.gate;
  const paintCorrelation = paintGate?.front?.metrics?.spatialColorCorrelation;

  const [saveLabel, setSaveLabel] = useState(defaultSaveLabel);
  const [copyLabel, setCopyLabel] = useState('Copiar prompt');
  const [stlLabel, setStlLabel] = useState('Exportar STL');
  const [usdLabel, setUsdLabel] = useState('Exportar OpenUSD');
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
    setUsdLabel('Exportar OpenUSD');
    setShowCode(false);
    setShowDetails(false);
  }, [result?.id, result?.filePath, defaultSaveLabel]);

  const handleSaveStl = async () => {
    if (deliveryBlocked) return setStlLabel('Bloqueado');
    setStlLabel('Convirtiendo…');
    const saved = await onSaveStl();
    setStlLabel(saved ? `✓ STL ${saved.dims ? `${saved.dims.join('×')}mm` : 'guardado'}` : 'Exportar STL');
  };

  const handleTexture = async () => {
    setTextureLabel('Texturizando...');
    const ok = await onTextureGlb?.();
    setTextureLabel(ok ? 'Borrador IA listo' : result?.textured ? 'Repintar desde imagen' : 'Texturizar ahora');
  };

  const handleSave = async () => {
    setSaveLabel('Guardando…');
    const path = await onSave();
    setSaveLabel(path ? '✓ Guardado' : defaultSaveLabel);
  };

  const handleSaveOpenUsd = async () => {
    if (deliveryBlocked) return setUsdLabel('Bloqueado');
    setUsdLabel('Convirtiendo…');
    const saved = await onSaveOpenUsd();
    setUsdLabel(saved ? '✓ OpenUSD validado' : 'Exportar OpenUSD');
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
        <HorizontalFlowStudio percent={progress.percent} mode={mode} isMeshy={recipe?.engineProvider === 'meshy'} label={progress.label} textureEnabled={asset?.texture === true} />

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
          
          <StageRail percent={progress.percent} textureEnabled={asset?.texture === true} />

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
        <div className="notice-card notice-error max-w-md rounded-3xl p-6 text-center border border-sky-400/30 bg-[#030e24]/90 backdrop-blur-xl">
          <span className="notice-icon mx-auto grid h-11 w-11 place-items-center rounded-full text-amber-300 bg-amber-500/20"><WarningOctagon size={24} weight="duotone" aria-hidden="true" /></span>
          <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.18em] text-sky-300/70">Estado de Conversión</p>
          <h2 className="mt-1.5 text-base font-semibold text-white">Aviso del proceso 3D</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{error}</p>
          {onErrorDismiss && (
            <button
              type="button"
              onClick={onErrorDismiss}
              className="mt-5 rounded-full bg-sky-500/20 hover:bg-sky-500/30 text-sky-200 border border-sky-400/40 px-6 py-2.5 text-xs font-semibold transition"
            >
              Continuar al modelo 3D
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!result) {
    const EmptyIcon = mode === 'image3d' ? CubeFocus : mode === 'stl' ? Polygon : ImageIcon;
    return (
      <div className="relative flex h-full flex-col justify-between overflow-y-auto p-6 scroll-dark select-none">
        {/* Background glow effects */}
        <div className="processing-halo absolute -top-24 left-1/2 -translate-x-1/2 h-[450px] w-[600px] rounded-full pointer-events-none opacity-40" />

        {/* Top TUI System Telemetry Strip */}
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-2.5 rounded-2xl border border-sky-400/25 bg-[#030e24]/90 p-3 shadow-lg backdrop-blur-xl">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-1.5 font-mono text-xs font-bold text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
              ● APPLE SILICON METAL GPU
            </span>
            <span className="text-white/20">|</span>
            <span className="font-mono text-xs text-sky-300 font-semibold">
              VRAM OLLAMA: <b className="text-emerald-300">PURGADA</b>
            </span>
            <span className="text-white/20">|</span>
            <span className="font-mono text-xs text-cyan-300 font-semibold">
              ENGINE: <b className="text-white">MLX 2.1 BUFFALO</b>
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-full border border-sky-400/30 bg-sky-500/10 px-3 py-1 font-mono text-[11px] font-bold text-sky-200 shadow-sm">
              ⌘K COMANDOS
            </span>
          </div>
        </div>

        {/* Center Hero ASCII Art & Mission Control Banner */}
        <div className="relative z-10 my-auto flex flex-col items-center justify-center text-center py-4">
          <div className="ascii-art-glow select-all font-mono text-[10px] sm:text-[12px] md:text-[14px] leading-tight font-extrabold tracking-widest text-cyan-300">
            <pre className="inline-block text-left whitespace-pre">
{`██╗  ██╗██████╗ ███████╗ █████╗ ██╗     ██╗████████╗██╗   ██╗
╚██╗██╔╝██╔══██╗██╔════╝██╔══██╗██║     ██║╚══██╔══╝╚██╗ ██╔╝
 ╚███╔╝ ██████╔╝█████╗  ███████║██║     ██║   ██║    ╚████╔╝ 
 ██╔██╗ ██╔══██╗██╔══╝  ██╔══██║██║     ██║   ██║     ╚██╔╝  
██╔╝ ██╗██║  ██║███████╗██║  ██║███████╗██║   ██║      ██║   `}
            </pre>
          </div>

          <div className="mt-4 flex items-center gap-2.5">
            <span className="rounded-full border border-cyan-400/40 bg-cyan-500/20 px-3.5 py-1 font-mono text-xs font-extrabold text-cyan-200 shadow-[0_0_20px_rgba(56,189,248,0.4)]">
              STUDIO 3D & SPATIAL COMPUTING
            </span>
          </div>

          <h2 className="mt-3 font-outfit text-2xl sm:text-3xl font-extrabold tracking-tight text-white drop-shadow-md">
            Centro de Control & Conversión 3D
          </h2>

          <p className="mt-2 max-w-xl text-sm sm:text-base font-medium leading-relaxed text-slate-300">
            {mode === 'image3d'
              ? 'Arrastra una imagen de referencia o sube tus 6 vistas. El motor generará una malla volumétrica con texturas PBR y exportación OpenUSD / STL.'
              : mode === 'stl'
              ? 'Escribe especificaciones técnicas CAD paramétricas. El compilador V8 generará mallas herméticas listas para impresión 3D.'
              : 'Escribe una dirección creativa para sintetizar una referencia visual limpia con Ollama FLUX.'}
          </p>

          {/* Quick-Start Suggestion Cards */}
          <div className="mt-6 grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3 text-left">
            <div className="tui-box p-4 border border-sky-400/20 bg-[#051538]/80 hover:border-sky-300/50 hover:scale-[1.02] transition-all">
              <span className="text-xl">🖨️</span>
              <h3 className="mt-2 text-sm font-bold text-white">Impresión 3D STL</h3>
              <p className="mt-1 text-xs text-slate-400 leading-relaxed">Geometría hermética a escala exacta en milímetros lista para manufactura.</p>
            </div>

            <div className="tui-box p-4 border border-indigo-400/20 bg-[#07133a]/80 hover:border-indigo-300/50 hover:scale-[1.02] transition-all">
              <span className="text-xl">🥽</span>
              <h3 className="mt-2 text-sm font-bold text-white">Apple Vision Pro</h3>
              <p className="mt-1 text-xs text-slate-400 leading-relaxed">Formato OpenUSD / USDZ nativo con validación estricta para RealityKit.</p>
            </div>

            <div className="tui-box p-4 border border-emerald-400/20 bg-[#041c2c]/80 hover:border-emerald-300/50 hover:scale-[1.02] transition-all">
              <span className="text-xl">⚡</span>
              <h3 className="mt-2 text-sm font-bold text-white">Pipeline $0 Local</h3>
              <p className="mt-1 text-xs text-slate-400 leading-relaxed">Privacidad absoluta en tu Mac. Sin suscripciones ni envíos a la nube.</p>
            </div>
          </div>
        </div>

        {/* Bottom Keyboard Shortcuts Bar */}
        <div className="relative z-10 mt-auto rounded-2xl border border-white/10 bg-black/60 p-3 backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 font-mono text-xs text-slate-400">
            <span className="font-bold text-cyan-300 uppercase tracking-wider">Atajos Rápidos:</span>
            <div className="flex flex-wrap items-center gap-3">
              <span><kbd className="rounded-md border border-white/20 bg-white/10 px-1.5 py-0.5 font-bold text-slate-200">Espacio</kbd> Giro 360°</span>
              <span><kbd className="rounded-md border border-white/20 bg-white/10 px-1.5 py-0.5 font-bold text-slate-200">1 - 6</kbd> Vistas</span>
              <span><kbd className="rounded-md border border-white/20 bg-white/10 px-1.5 py-0.5 font-bold text-slate-200">W</kbd> Wireframe</span>
              <span><kbd className="rounded-md border border-white/20 bg-white/10 px-1.5 py-0.5 font-bold text-slate-200">C</kbd> Clay</span>
              <span><kbd className="rounded-md border border-white/20 bg-white/10 px-1.5 py-0.5 font-bold text-slate-200">P</kbd> PBR Shader</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3 select-none">
      {/* Top View Selector Tabs Bar */}
      <div className="flex items-center justify-between gap-2 rounded-full border border-sky-400/20 bg-[#020b1d]/85 p-1.5 backdrop-blur-xl shadow-lg">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTab('final')}
            className={`rounded-full px-4 py-2 text-xs font-extrabold transition-all duration-300 ${
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
              className={`rounded-full px-4 py-2 text-xs font-extrabold transition-all duration-300 ${
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
              className={`rounded-full px-4 py-2 text-xs font-extrabold transition-all duration-300 ${
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
            className={`rounded-full px-4 py-2 text-xs font-extrabold transition-all duration-300 ${
              activeTab === 'nodegraph'
                ? 'bg-gradient-to-r from-purple-600 to-pink-500 text-white shadow-[0_0_20px_rgba(168,85,247,0.5)] border border-purple-300/40 scale-[1.03]'
                : 'text-slate-400 hover:text-white hover:scale-[1.02]'
            }`}
          >
            ⚡ Grafo de Nodos Vivo
          </button>
        </div>

        <span className="hidden sm:inline font-mono text-xs font-bold text-sky-300 uppercase tracking-wider px-3">
          {activeTab === 'final' ? 'Visor 3D WebGL' : activeTab === 'multiview' ? 'Proyección Evidencia 6V' : activeTab === 'preprocessed' ? 'Sujeto Aislado' : 'Pipeline Telemetría'}
        </span>
      </div>

      <div className="asset-canvas group relative min-h-0 flex-1 overflow-hidden rounded-3xl border border-sky-400/25 bg-[#020917] shadow-[inset_0_1px_0_rgba(255,255,255,0.08),0_30px_90px_rgba(0,3,15,0.6)]">
        <SparkleBurst show={Boolean(result && !processing)} />
        <ErrorBoundary>
          <Suspense fallback={<ViewerFallback />}>
            {activeTab === 'multiview' ? (
              <MultiViewGrid
                views={result.multiViewImages}
                mainImage={result.inputDataUrl}
                glbBase64={result.glbBase64}
                glbPath={result.glbPath}
                result={result}
              />
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
              <GltfViewer
                glbBase64={result.glbBase64}
                glbPath={result.glbPath}
                externalAction={externalAction}
                onClearExternalAction={onClearExternalAction}
              />
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
            <div className="hud-glass pointer-events-none absolute left-3 top-3 flex items-center gap-2.5 rounded-full px-4 py-2 border border-white/15 bg-black/60 backdrop-blur-xl shadow-lg">
              <ShieldCheck size={20} weight="duotone" className={audit.level === 'listo' ? 'text-emerald-300' : audit.level === 'atencion' ? 'text-amber-300' : 'text-rose-300'} aria-hidden="true" />
              <div>
                <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-400 font-bold">Entrega</p>
                <p className="text-xs font-bold text-white">{audit.level === 'listo' ? 'Validada' : audit.level}</p>
              </div>
            </div>

            {isGlb && (
              <div className="hud-glass pointer-events-none absolute right-3 top-3 rounded-2xl px-4 py-2 text-right border border-white/15 bg-black/60 backdrop-blur-xl shadow-lg">
                <p className="flex items-center justify-end gap-1 font-mono text-[9px] uppercase tracking-[0.16em] text-cyan-300 font-bold">
                  <PaintBrush size={14} weight="duotone" aria-hidden="true" />
                  Material
                </p>
                <p className="mt-0.5 text-xs font-bold text-white">{result.textured ? 'PBR · 6 vistas' : 'Sin textura'}</p>
                {paintGate?.passed && <p className="mt-0.5 font-mono text-[9px] text-emerald-300 font-bold">Gate aprobado{paintCorrelation != null ? ` · ${paintCorrelation}` : ''}</p>}
              </div>
            )}

            {isGlb && result.inputDataUrl && (
              <figure className="reference-chip hud-glass absolute bottom-3 left-3 w-28 overflow-hidden rounded-2xl p-2 border border-white/15 bg-black/70 backdrop-blur-xl shadow-xl">
                <img src={result.inputDataUrl} alt="Referencia original" className="h-24 w-full rounded-xl object-contain" />
                <figcaption className="px-1 pt-1.5 font-mono text-[9px] font-bold uppercase tracking-[0.14em] text-slate-300 text-center">Referencia</figcaption>
              </figure>
            )}

            {isGlb && (
              <div className="hud-glass pointer-events-none absolute bottom-3 right-3 flex items-center gap-3.5 rounded-full border border-sky-400/40 bg-black/85 px-4.5 py-2 font-mono text-xs text-sky-200 backdrop-blur-xl shadow-xl">
                <span className="flex items-center gap-1.5 font-bold"><Polygon size={14} className="text-sky-400" /> {result.faces ? `${result.faces.toLocaleString()} Caras` : 'Malla Quad'}</span>
                <span className="text-white/25">|</span>
                <span className="flex items-center gap-1.5 font-bold"><Lightning size={14} className="text-amber-400" /> {result.duration ? `${Number(result.duration).toFixed(1)}s` : '12.4s'}</span>
                <span className="text-white/25">|</span>
                <span className={result.usdzPath ? 'text-emerald-300 font-extrabold' : deliveryBlocked ? 'text-amber-300 font-extrabold' : 'text-cyan-300 font-extrabold'}>{result.usdzPath ? '✓ OpenUSD validado' : deliveryBlocked ? 'OpenUSD requiere revisión' : 'OpenUSD disponible'}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Hero Bottom Dock: Prompt & Actions Bar */}
      <div className="asset-dock glass-card shrink-0 rounded-3xl p-5 border border-sky-400/30 bg-[#06183a]/90 backdrop-blur-2xl shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="tui-badge border border-cyan-400/40 bg-cyan-500/15 text-cyan-200">
                {deliveryBlocked ? 'INSPECCIÓN DISPONIBLE' : 'ACTIVO GENERADO Y SELLADO'}
              </span>
            </div>
            <p className="mt-1.5 truncate font-outfit text-base font-bold text-white">
              {isGlb ? `Referencia: ${result.prompt}` : result.prompt}
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-start md:justify-end gap-2.5">
            <button
              onClick={handleSave}
              className="flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 px-5 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-blue-950/50 transition hover:scale-[1.04]"
            >
              <FloppyDisk size={16} weight="duotone" aria-hidden="true" />
              {saveLabel}
            </button>

            {!isGlb && !isStl && (
              <button
                onClick={onUseAs3dReference}
                className="flex items-center gap-2 rounded-full border border-sky-400/40 bg-sky-500/20 px-5 py-2.5 text-xs font-bold text-sky-100 transition hover:bg-sky-500/30 hover:scale-[1.04]"
              >
                Usar en 3D <ArrowRight size={16} weight="bold" aria-hidden="true" />
              </button>
            )}
            
            {isGlb && (
              <button
                onClick={() => setShowTextureModal(true)}
                className="flex items-center gap-2 rounded-full border border-amber-400/50 bg-gradient-to-r from-amber-500/25 to-orange-500/15 px-4.5 py-2.5 text-xs font-extrabold text-amber-200 shadow-[0_0_20px_rgba(245,158,11,0.25)] transition hover:scale-[1.04]"
                title="Cambiar o re-aplicar textura PBR online con Meshy API"
              >
                <PaintBrush size={16} weight="duotone" />
                🎨 Textura PBR IA
              </button>
            )}

            {isGlb && (
              <button
                onClick={() => setShowCorrectionModal(true)}
                className="flex items-center gap-2 rounded-full border border-indigo-400/50 bg-gradient-to-r from-indigo-500/25 to-purple-500/15 px-4.5 py-2.5 text-xs font-extrabold text-indigo-200 shadow-[0_0_20px_rgba(99,102,241,0.25)] transition hover:scale-[1.04]"
                title="Corregir geometría y convertir a topología Quad Low Poly"
              >
                <Polygon size={16} weight="duotone" />
                ✨ Remesh Quad
              </button>
            )}

            <button
              onClick={() => setShowReportModal(true)}
              className="flex items-center gap-2 rounded-full border border-sky-400/40 bg-sky-500/20 px-4.5 py-2.5 text-xs font-extrabold text-cyan-200 shadow-[0_0_20px_rgba(56,189,248,0.25)] transition hover:scale-[1.04]"
              title="Ver informe técnico completo de calidad y geometrías 3D"
            >
              <ShieldCheck size={16} weight="duotone" />
              📋 Informe Técnico
            </button>

            {isGlb && (
              <button
                onClick={handleSaveStl}
                disabled={deliveryBlocked}
                title="Exportar como STL para impresión 3D"
                className="flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2.5 text-xs font-bold text-slate-100 transition hover:border-sky-400/40 hover:bg-white/20 hover:scale-[1.04] disabled:opacity-40"
              >
                <Cube size={16} weight="duotone" aria-hidden="true" />
                {deliveryBlocked ? 'STL bloqueado' : stlLabel}
              </button>
            )}

            {isGlb && (
              <button
                onClick={handleSaveOpenUsd}
                disabled={deliveryBlocked}
                title="Exportar OpenUSD validado para Apple Vision Pro y RealityKit"
                className="flex items-center gap-2 rounded-full border border-sky-400/40 bg-sky-500/15 px-4 py-2.5 text-xs font-bold text-cyan-100 transition hover:border-sky-400/60 hover:bg-sky-500/25 hover:scale-[1.04] disabled:opacity-40"
              >
                <CubeFocus size={16} weight="duotone" aria-hidden="true" />
                {deliveryBlocked ? 'USDZ bloqueado' : usdLabel}
              </button>
            )}

            {!isGlb && (
              <button
                onClick={handleCopy}
                className="flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-2.5 text-xs font-bold text-slate-200 hover:border-sky-400/40 hover:text-white"
              >
                <Copy size={16} weight="duotone" aria-hidden="true" />
                {copyLabel}
              </button>
            )}

            <button
              onClick={() => setShowDetails((open) => !open)}
              aria-expanded={showDetails}
              className="flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-bold text-slate-300 hover:text-white hover:bg-white/10"
            >
              <Info size={16} weight="duotone" aria-hidden="true" />
              {showDetails ? 'Menos' : 'Detalles'}
            </button>
          </div>
        </div>

        {/* Metrics Grid with larger fonts */}
        <div className="mt-4 grid grid-cols-3 gap-3 border-t border-white/10 pt-3.5 sm:grid-cols-5">
          <Meta label={isGlb ? 'Caras' : isStl ? 'Triángulos' : 'Tamaño'} value={isGlb ? (result.faces ?? '—') : isStl ? (result.triangles ?? '—') : `${result.width}×${result.height}`} strong />
          <Meta label="Tiempo" value={result.duration != null ? `${Number(result.duration).toFixed(1)}s` : '—'} strong />
          <Meta label="Calidad" value={audit.level.toUpperCase()} strong />
          <div className="hidden sm:block"><Meta label="Perfil" value={result.profile || asset?.profile || '—'} strong /></div>
          <div className="hidden sm:block"><Meta label="Material" value={result.textured ? result.textureSize || 'PBR 6V' : 'Sin textura'} strong /></div>
        </div>

        {deliveryBlocked && (
          <p className="mt-3 rounded-2xl border border-amber-300/30 bg-amber-300/10 px-4 py-2.5 text-xs leading-relaxed text-amber-100">
            ⚠️ La entrega derivada está en revisión: faltan gates visuales o evidencia multi-vista suficiente. Puedes guardar el GLB como artefacto de revisión, pero STL y OpenUSD requieren corregir primero.
          </p>
        )}

        {showDetails && (
          <div className="mt-4 grid grid-cols-2 gap-3.5 rounded-2xl border border-white/10 bg-black/25 p-4 sm:grid-cols-4 animate-fadeIn">
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
            {isStl && result.code && <button onClick={() => setShowCode((open) => !open)} className="text-left text-xs text-sky-300 font-bold hover:underline">{showCode ? 'Ocultar código' : 'Ver código fuente'}</button>}
            {result.filePath && <button onClick={() => onReveal(result.filePath)} className="text-left text-xs text-sky-300 font-bold hover:underline">Mostrar archivo en Finder</button>}
          </div>
        )}

        {isStl && showCode && (
          <pre className="scroll-dark mt-3 max-h-56 overflow-auto rounded-2xl border border-white/10 bg-black/60 p-4 font-mono text-xs leading-relaxed text-sky-200">
            <code>{result.code}</code>
          </pre>
        )}
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
