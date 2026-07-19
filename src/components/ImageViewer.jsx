import React, { Suspense, lazy, useState, useEffect } from 'react';
import { USE_CASES } from '../lib/useCases.js';
import { XR_PROFILES, profileAudit } from '../lib/xrProfiles.js';

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
  onCopyPrompt,
  onReveal,
  onUseAs3dReference,
  asset,
}) {
  const isStl = result?.type === 'stl';
  const isGlb = result?.type === 'glb';
  const recipe = USE_CASES[useCase];
  const auditProfile = XR_PROFILES[result?.profile || asset?.profile || 'xreal'] || XR_PROFILES.xreal;
  const qualityAudit = result?.qualityLevel
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
  const exportBlocked = result?.qualityLevel === 'critico';

  const [saveLabel, setSaveLabel] = useState(defaultSaveLabel);
  const [copyLabel, setCopyLabel] = useState('Copiar prompt');
  const [stlLabel, setStlLabel] = useState('Exportar STL');
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    setSaveLabel(result?.filePath ? '✓ Guardado' : defaultSaveLabel);
    setCopyLabel('Copiar prompt');
    setStlLabel('Exportar STL');
    setShowCode(false);
  }, [result?.id, result?.filePath, defaultSaveLabel]);

  const handleSaveStl = async () => {
    if (exportBlocked) {
      setStlLabel('Bloqueado');
      return;
    }
    setStlLabel('Convirtiendo…');
    const r = await onSaveStl();
    setStlLabel(r ? `✓ STL ${r.dims ? r.dims.join('×') + 'mm' : 'guardado'}` : 'Exportar STL');
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
      return (
        <div className="flex max-w-md flex-col items-center gap-3 text-center">
          <div className="text-3xl">⚠️</div>
          <p className="text-sm leading-relaxed text-red-300">{error}</p>
        </div>
      );
    }

    if (!result) {
      const icon = mode === 'image3d' ? '◈' : mode === 'stl' ? '◇' : '▧';
      const text =
        mode === 'image3d'
          ? 'Selecciona una referencia para reconstruir tu activo 3D.'
          : mode === 'stl'
          ? 'Describe una geometría para construir la primera malla.'
          : 'Escribe una dirección creativa para generar una referencia.';
      return (
        <div className="relative flex h-full w-full items-center justify-center overflow-hidden">
          <div className="absolute h-[420px] w-[420px] rounded-full border border-sky-300/[0.045] shadow-[0_0_100px_rgba(22,137,232,0.08)]" />
          <div className="absolute h-[290px] w-[290px] rounded-full border border-dashed border-sky-300/[0.07]" />
          <div className="relative flex max-w-sm flex-col items-center text-center">
            <div className="grid h-16 w-16 place-items-center rounded-2xl border border-sky-300/15 bg-gradient-to-br from-sky-400/10 to-blue-900/10 text-3xl text-sky-300 shadow-[0_0_45px_rgba(22,137,232,0.12)]">{icon}</div>
            <p className="mt-5 font-mono text-[9px] uppercase tracking-[0.2em] text-sky-400/60">Escenario de producción</p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-slate-200">Listo para comenzar</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-500">{text}</p>
            <div className="mt-5 flex items-center gap-2 font-mono text-[8px] uppercase tracking-wider text-slate-600">{recipe.route.map((step, index) => <React.Fragment key={step}><span>{step}</span>{index < recipe.route.length - 1 && <span className="text-sky-500">→</span>}</React.Fragment>)}</div>
            <div className="mt-5 rounded-xl border border-sky-300/10 bg-sky-300/[0.035] px-4 py-3"><p className="font-mono text-[8px] uppercase tracking-[0.16em] text-sky-400/60">Receta activa · {recipe.tag}</p><p className="mt-1 text-[10px] leading-relaxed text-slate-500">{recipe.description}</p></div>
          </div>
        </div>
      );
    }

    return (
      <div className="flex h-full w-full flex-col items-center gap-4">
        <div className="flex min-h-0 flex-1 items-stretch justify-center self-stretch">
          {isGlb ? (
            <div className="h-full w-full overflow-hidden rounded-xl border border-border shadow-2xl">
              <Suspense fallback={<ViewerFallback />}>
                <GltfViewer glbBase64={result.glbBase64} />
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
          {(isGlb || isStl) && (
            <div className={`mb-3 flex items-center justify-between rounded-xl border px-3 py-2 ${audit.level === 'listo' ? 'border-cyan-300/15 bg-cyan-300/5' : audit.level === 'atencion' ? 'border-amber-300/15 bg-amber-300/5' : 'border-rose-300/15 bg-rose-300/5'}`}>
              <div><p className="font-mono text-[8px] uppercase tracking-[0.16em] text-slate-500">Auditoría de entrega</p><p className="mt-0.5 text-[10px] text-slate-200">{audit.text}</p></div>
              <span className="font-mono text-[9px] uppercase text-sky-300">{result.profile || asset?.profile}</span>
            </div>
          )}
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Meta label="Modelo" value={result.model} />
            {isGlb ? (
              <>
                <Meta label="Caras" value={result.faces ?? '—'} />
                <Meta label="Pasos" value={result.steps ?? '—'} />
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
              <button
                onClick={handleSaveStl}
                disabled={exportBlocked}
                title="Exportar como STL para impresión 3D (escala aproximada de 60 mm)"
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {exportBlocked ? 'Bloqueado por calidad' : stlLabel}
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
