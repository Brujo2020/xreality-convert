import React, { Suspense, lazy, useState, useEffect, useCallback } from 'react';
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

function Meta({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="font-mono text-[8px] uppercase tracking-[0.15em] text-slate-500">
        {label}
      </span>
      <span className="mt-1 text-xs tabular-nums text-slate-200">{value}</span>
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
  generating,
  processing,
  progress,
  useCase,
  mode,
  error,
  onSave,
  onSaveStl,
  onTextureGlb,
  onCopyPrompt,
  onReveal,
  onUseAs3dReference,
  asset,
}) {
  const isStl = result?.type === 'stl';
  const isGlb = result?.type === 'glb';
  const recipe = USE_CASES[useCase];
  const auditProfile = XR_PROFILES[result?.profile || asset?.profile || 'xreal'] || XR_PROFILES.xreal;
  const missingRequestedTexture = isGlb && result?.textureRequested && !result?.textured;
  const qualityAudit = missingRequestedTexture
    ? {
        level: 'critico',
        text: 'PBR solicitado, pero este GLB no trae textura embebida.',
      }
    : result?.qualityLevel
    ? {
        level: result.qualityLevel,
        text: result.qualityText || 'Resultado validado.',
      }
    : profileAudit(auditProfile, result?.faces || result?.triangles);
  const audit = qualityAudit;
  const defaultSaveLabel = isGlb
    ? 'Guardar GLB'
    : isStl
    ? 'Guardar STL'
    : 'Guardar imagen';
  const [saveLabel, setSaveLabel] = useState(defaultSaveLabel);
  const [copyLabel, setCopyLabel] = useState('Copiar prompt');
  const [stlLabel, setStlLabel] = useState('Exportar STL');
  const [textureLabel, setTextureLabel] = useState('Texturizar ahora');
  const [showCode, setShowCode] = useState(false);
  const [texturePreview, setTexturePreview] = useState(null);
  const [canonicalRenders, setCanonicalRenders] = useState(null);
  const [textureApproved, setTextureApproved] = useState(false);
  const textureNeedsReview = result?.textured && result?.textureRequested && !textureApproved;
  const geometryBlocked = result?.qualityLevel === 'critico';
  const exportBlocked = geometryBlocked || missingRequestedTexture || textureNeedsReview;

  useEffect(() => {
    setSaveLabel(result?.filePath ? '✓ Guardado' : defaultSaveLabel);
    setCopyLabel('Copiar prompt');
    setStlLabel('Exportar STL');
    setTextureLabel(result?.textured ? 'Repintar desde imagen' : 'Texturizar ahora');
    setShowCode(false);
    setTexturePreview(null);
    setCanonicalRenders(null);
    setTextureApproved(false);
  }, [result?.id, result?.filePath, result?.glbBase64, defaultSaveLabel]);

  const handleGltfInspection = useCallback((inspection) => {
    setTexturePreview(inspection);
  }, []);
  const handleCanonicalRenders = useCallback((renderSet) => {
    setCanonicalRenders(renderSet);
  }, []);

  const handleSaveStl = async () => {
    if (geometryBlocked) {
      setStlLabel('Bloqueado');
      return;
    }
    setStlLabel('Convirtiendo…');
    const r = await onSaveStl();
    setStlLabel(r ? `✓ STL ${r.dims ? r.dims.join('×') + 'mm' : 'guardado'}` : 'Exportar STL');
  };

  const handleTexture = async () => {
    setTextureLabel('Texturizando...');
    const ok = await onTextureGlb?.();
    setTextureLabel(ok ? 'Borrador IA listo' : result?.textured ? 'Repintar desde imagen' : 'Texturizar ahora');
  };

  const handleSave = async () => {
    if (exportBlocked) {
      setSaveLabel('Bloqueado');
      return;
    }
    setSaveLabel('Guardando…');
    const path = await onSave();
    setSaveLabel(path ? '✓ Guardado' : defaultSaveLabel);
  };

  const handleCopy = async () => {
    const ok = await onCopyPrompt();
    if (ok) {
      setCopyLabel('✓ Copiado');
      setTimeout(() => setCopyLabel('Copiar prompt'), 1500);
    }
  };

  const renderBody = () => {
    if (processing) {
      const remaining = progress.remaining == null
        ? 'Finalizando…'
        : progress.remaining >= 60
        ? `≈ ${Math.ceil(progress.remaining / 60)} min restantes`
        : `≈ ${progress.remaining} s restantes`;
      return (
        <div className="flex w-full max-w-xl flex-col items-center gap-7 text-center">
          <div
            className="relative grid h-52 w-52 place-items-center rounded-full shadow-[0_0_80px_rgba(22,137,232,0.25)] transition-all duration-700"
            style={{ background: `conic-gradient(#35a7ff ${progress.percent * 3.6}deg, #173659 0deg)` }}
          >
            <div className="grid h-40 w-40 place-items-center rounded-full border border-sky-400/20 bg-base shadow-inner">
              <div>
                <strong className="block text-5xl font-semibold tabular-nums text-white">{progress.percent}%</strong>
                <span className="mt-1 block text-[10px] uppercase tracking-[0.18em] text-sky-300">Procesando</span>
              </div>
            </div>
          </div>
          <div className="w-full">
            <h2 className="text-lg font-medium text-white">{progress.label}</h2>
            <p className="mt-1 text-sm text-sky-200/70">{remaining}</p>
            <div className="mt-5 h-2.5 overflow-hidden rounded-full border border-border bg-slate-950">
              <div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-400 transition-all duration-700" style={{ width: `${progress.percent}%` }} />
            </div>
            <p className="mt-3 text-[11px] text-neutral-500">Estimación dinámica: puede variar según modelo, memoria y temperatura del equipo.</p>
          </div>
        </div>
      );
    }

    if (error) {
      const nextAction = nextActionForError(error, mode);
      return (
        <div className="flex max-w-md flex-col items-center gap-3 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-xl border border-rose-300/20 bg-rose-300/5 text-2xl text-rose-200">!</div>
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-rose-300/70">No se pudo completar</p>
            <p className="mt-2 text-sm leading-relaxed text-red-300">{error}</p>
          </div>
          <div className="rounded-xl border border-amber-300/15 bg-amber-300/5 px-4 py-3">
            <p className="font-mono text-[8px] uppercase tracking-[0.16em] text-amber-200/80">Siguiente acción</p>
            <p className="mt-1 text-[11px] leading-relaxed text-amber-50">{nextAction}</p>
          </div>
        </div>
      );
    }

    if (!result) {
      const text =
        mode === 'image3d'
          ? 'Selecciona una referencia para reconstruir tu activo 3D.'
          : mode === 'stl'
          ? 'Describe una geometría para construir la primera malla.'
          : 'Escribe una dirección creativa para generar una referencia.';
      return (
        <div className="flex h-full w-full items-center justify-center overflow-hidden">
          <div className="flex w-full max-w-md flex-col items-center text-center">
            <div className="grid h-12 w-12 place-items-center rounded-xl border border-sky-300/15 bg-sky-300/[0.055] font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-sky-200">XR</div>
            <p className="mt-5 font-mono text-[9px] uppercase tracking-[0.2em] text-sky-400/60">Escenario de producción</p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-200">Listo para comenzar</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{text}</p>
            <p className="mt-2 text-[11px] leading-relaxed text-slate-500">{mode === 'image3d' ? 'Siguiente acción: carga una imagen y confirma la categoría sugerida.' : mode === 'stl' ? 'Siguiente acción: define medidas, unidad y uso final.' : 'Siguiente acción: elige un caso de uso y genera una referencia limpia.'}</p>
            <div className="mt-6 grid w-full gap-1.5">
              {recipe.route.map((step, index) => (
                <div key={step} className="flex min-h-10 items-center justify-between rounded-xl border border-white/5 bg-black/15 px-3 text-left">
                  <span className="font-mono text-[8px] uppercase tracking-[0.16em] text-sky-400/60">{String(index + 1).padStart(2, '0')}</span>
                  <span className="text-[11px] font-medium text-slate-300">{step}</span>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-xl border border-sky-300/10 bg-sky-300/[0.035] px-4 py-3"><p className="font-mono text-[8px] uppercase tracking-[0.16em] text-sky-400/60">Receta activa · {recipe.tag}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-500">{recipe.description}</p></div>
          </div>
        </div>
      );
    }

    return (
      <div className="flex h-full w-full flex-col items-center gap-4">
        <div className="flex min-h-0 flex-1 items-stretch justify-center self-stretch">
          {isGlb && result.textured && result.shapeGlbBase64 ? (
            <div className="grid h-full w-full gap-2 md:grid-cols-2">
              <div className="relative min-h-0 overflow-hidden rounded-xl border border-border shadow-2xl">
                <div className="absolute z-10 m-2 rounded-md border border-white/10 bg-black/60 px-2 py-1 font-mono text-[8px] uppercase tracking-wider text-slate-200">Sin textura</div>
                <Suspense fallback={<ViewerFallback />}>
                  <GltfViewer glbBase64={result.shapeGlbBase64} />
                </Suspense>
              </div>
              <div className="relative min-h-0 overflow-hidden rounded-xl border border-cyan-300/30 shadow-2xl">
                <div className="absolute z-10 m-2 rounded-md border border-cyan-300/20 bg-cyan-950/70 px-2 py-1 font-mono text-[8px] uppercase tracking-wider text-cyan-100">PBR IA · revisar</div>
                <Suspense fallback={<ViewerFallback />}>
                  <GltfViewer glbBase64={result.glbBase64} onInspection={handleGltfInspection} onCanonicalRenders={handleCanonicalRenders} />
                </Suspense>
              </div>
            </div>
          ) : isGlb ? (
            <div className="h-full w-full overflow-hidden rounded-xl border border-border shadow-2xl">
              <Suspense fallback={<ViewerFallback />}>
                <GltfViewer glbBase64={result.glbBase64} onInspection={handleGltfInspection} onCanonicalRenders={handleCanonicalRenders} />
              </Suspense>
            </div>
          ) : isStl ? (
            <div className="h-full w-full overflow-hidden rounded-xl border border-border shadow-2xl">
              <Suspense fallback={<ViewerFallback />}>
                <StlViewer stl={result.stl} />
              </Suspense>
            </div>
          ) : (
            <div className="flex w-full items-center justify-center">
              <img
                src={`data:image/png;base64,${result.image}`}
                alt={result.prompt}
                className="max-h-full max-w-full rounded-xl border border-border object-contain shadow-2xl"
              />
            </div>
          )}
        </div>

        {/* Metadata + actions */}
        <div className="glass-card w-full max-w-3xl shrink-0 rounded-2xl p-4">
          <AssetIdentity result={result} />
          {(isGlb || isStl) && (
            <VisualAudit audit={audit} result={result} asset={asset} />
          )}
          {isGlb && <TexturePreview result={result} inspection={texturePreview} />}
          {isGlb && <CanonicalEvidence renderSet={canonicalRenders} />}
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Meta label="Modelo" value={result.model} />
            {isGlb ? (
              <>
                <Meta label="Caras" value={result.faces ?? '—'} />
                <Meta label="Pasos" value={result.steps ?? '—'} />
                <Meta label="LOD" value={result.lodPaths ? Object.keys(result.lodPaths).join('/') : '—'} />
              </>
            ) : isStl ? (
              <>
                <Meta label="Semilla" value={result.seed} />
                <Meta label="Triángulos" value={result.triangles ?? '—'} />
              </>
            ) : (
              <>
                <Meta label="Semilla" value={result.seed} />
                <Meta label="Tamaño" value={`${result.width}×${result.height}`} />
                <Meta label="Pasos" value={result.steps} />
              </>
            )}
            <Meta
              label="Tiempo"
              value={
                result.duration != null ? `${result.duration.toFixed(1)}s` : '—'
              }
            />
            {(isGlb || isStl) && <Meta label="Calidad" value={audit.level} />}
          </div>
          {isGlb && (
            <div className="mb-3 flex flex-wrap gap-1.5 font-mono text-[8px] uppercase tracking-wider text-slate-400">
              <span className={`rounded-md border px-2 py-1 ${result.textured ? 'border-cyan-300/20 bg-cyan-300/5 text-cyan-200' : result.textureRequested ? 'border-rose-300/20 bg-rose-300/5 text-rose-200' : 'border-white/5 bg-black/15'}`}>
                {result.textured ? `PBR ${result.textureSize || ''} embebido` : result.textureRequested ? `PBR ${result.textureSize || ''} falló` : 'Shape-only gris'}
              </span>
              <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">Pivot {result.pivot || 'center'}</span>
              {result.pivot === 'custom' && Array.isArray(result.pivotCustom) && (
                <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">
                  [{result.pivotCustom.map((value) => Number(value).toFixed(2)).join(', ')}]
                </span>
              )}
              <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">{(result.upAxis || 'y').toUpperCase()}-up</span>
              <span className="rounded-md border border-white/5 bg-black/15 px-2 py-1">Unidad {result.units || 'm'}</span>
            </div>
          )}

          <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-neutral-400">
            {isGlb ? `Fuente: ${result.prompt}` : result.prompt}
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleSave}
              disabled={exportBlocked}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-45"
            >
              {exportBlocked ? 'Bloqueado por calidad' : saveLabel}
            </button>
            {!isGlb && !isStl && (
              <button
                onClick={onUseAs3dReference}
                className="rounded-xl border border-cyan-300/25 bg-cyan-300/5 px-3 py-2 text-xs font-medium text-cyan-100 transition hover:bg-cyan-300/10"
              >
                ✦ Usar como referencia 3D
              </button>
            )}
            {isGlb && (
              result.inputDataUrl && (
                <button
                  onClick={handleTexture}
                  disabled={processing}
                  title="Ejecuta Hunyuan Paint sobre este GLB y muestra comparador sin/con textura"
                  className="rounded-lg border border-cyan-300/25 bg-cyan-300/5 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-300/10 disabled:cursor-not-allowed disabled:opacity-45"
                >
                  {textureLabel}
                </button>
              )
            )}
            {isGlb && textureNeedsReview && (
              <button
                onClick={() => setTextureApproved(true)}
                className="rounded-lg border border-emerald-300/25 bg-emerald-300/5 px-3 py-1.5 text-xs font-medium text-emerald-100 transition hover:bg-emerald-300/10"
              >
                Usar esta textura
              </button>
            )}
            {isGlb && (
              <button
                onClick={handleSaveStl}
                disabled={geometryBlocked}
                title="Exportar como STL para impresión 3D (escala aproximada de 60 mm)"
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {geometryBlocked ? 'Bloqueado por calidad' : stlLabel}
              </button>
            )}
            {!isGlb && (
              <button
                onClick={handleCopy}
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                {copyLabel}
              </button>
            )}
            {isStl && result.code && (
              <button
                onClick={() => setShowCode((s) => !s)}
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                {showCode ? 'Ocultar código' : 'Ver código'}
              </button>
            )}
            {result.filePath && (
              <button
                onClick={() => onReveal(result.filePath)}
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                Mostrar archivo
              </button>
            )}
            {isGlb && result.reportPath && (
              <button
                onClick={() => onReveal(result.reportPath)}
                className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 px-3 py-1.5 text-xs font-medium text-cyan-100 transition hover:bg-cyan-300/10"
              >
                Mostrar reporte
              </button>
            )}
          </div>

          {isStl && showCode && (
            <pre className="scroll-dark mt-3 max-h-48 overflow-auto rounded-lg border border-border bg-black/40 p-3 text-[11px] leading-relaxed text-neutral-300">
              <code>{result.code}</code>
            </pre>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="relative flex h-full items-center justify-center overflow-hidden p-6">
      {renderBody()}
    </div>
  );
}
