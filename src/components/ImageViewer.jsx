import React, { useState, useEffect } from 'react';
import StlViewer from './StlViewer.jsx';
import GltfViewer from './GltfViewer.jsx';

function Meta({ label, value }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-neutral-500">
        {label}
      </span>
      <span className="text-xs tabular-nums text-neutral-200">{value}</span>
    </div>
  );
}

export default function ImageViewer({
  result,
  generating,
  mode,
  error,
  onSave,
  onSaveStl,
  onCopyPrompt,
  onReveal,
}) {
  const isStl = result?.type === 'stl';
  const isGlb = result?.type === 'glb';
  const defaultSaveLabel = isGlb
    ? '💾 Save GLB'
    : isStl
    ? '💾 Save STL'
    : '💾 Save';

  const [saveLabel, setSaveLabel] = useState(defaultSaveLabel);
  const [copyLabel, setCopyLabel] = useState('📋 Copy prompt');
  const [stlLabel, setStlLabel] = useState('🖨️ Save STL');
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    setSaveLabel(result?.filePath ? '✓ Saved' : defaultSaveLabel);
    setCopyLabel('📋 Copy prompt');
    setStlLabel('🖨️ Save STL');
    setShowCode(false);
  }, [result?.id, result?.filePath, defaultSaveLabel]);

  const handleSaveStl = async () => {
    setStlLabel('Converting…');
    const r = await onSaveStl();
    setStlLabel(r ? `✓ STL ${r.dims ? r.dims.join('×') + 'mm' : 'saved'}` : '🖨️ Save STL');
  };

  const handleSave = async () => {
    setSaveLabel('Saving…');
    const path = await onSave();
    setSaveLabel(path ? '✓ Saved' : defaultSaveLabel);
  };

  const handleCopy = async () => {
    const ok = await onCopyPrompt();
    if (ok) {
      setCopyLabel('✓ Copied');
      setTimeout(() => setCopyLabel('📋 Copy prompt'), 1500);
    }
  };

  const renderBody = () => {
    if (error) {
      return (
        <div className="flex max-w-md flex-col items-center gap-3 text-center">
          <div className="text-3xl">⚠️</div>
          <p className="text-sm leading-relaxed text-red-300">{error}</p>
        </div>
      );
    }

    if (generating) {
      const msg =
        mode === 'image3d'
          ? 'Génération du modèle 3D… (~9 min, ne ferme pas)'
          : mode === 'stl'
          ? 'Generating 3D model…'
          : 'Generating…';
      return (
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="h-10 w-10 animate-spin rounded-full border-[3px] border-accent/30 border-t-accent" />
          <p className="text-sm text-neutral-400">{msg}</p>
        </div>
      );
    }

    if (!result) {
      const icon = mode === 'image3d' ? '🗿' : mode === 'stl' ? '🧊' : '🖼️';
      const text =
        mode === 'image3d'
          ? 'Ton modèle 3D (depuis une image) apparaîtra ici.'
          : mode === 'stl'
          ? 'Your generated 3D model will appear here.'
          : 'Your generated image will appear here.';
      return (
        <div className="flex flex-col items-center gap-2 text-center text-neutral-600">
          <div className="text-4xl">{icon}</div>
          <p className="text-sm">{text}</p>
        </div>
      );
    }

    return (
      <div className="flex h-full w-full flex-col items-center gap-4">
        <div className="flex min-h-0 flex-1 items-stretch justify-center self-stretch">
          {isGlb ? (
            <div className="h-full w-full overflow-hidden rounded-xl border border-border shadow-2xl">
              <GltfViewer glbBase64={result.glbBase64} />
            </div>
          ) : isStl ? (
            <div className="h-full w-full overflow-hidden rounded-xl border border-border shadow-2xl">
              <StlViewer stl={result.stl} />
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
        <div className="w-full max-w-3xl shrink-0 rounded-xl border border-border bg-panel p-4">
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Meta label="Model" value={result.model} />
            {isGlb ? (
              <>
                <Meta label="Faces" value={result.faces ?? '—'} />
                <Meta label="Steps" value={result.steps ?? '—'} />
              </>
            ) : isStl ? (
              <>
                <Meta label="Seed" value={result.seed} />
                <Meta label="Triangles" value={result.triangles ?? '—'} />
              </>
            ) : (
              <>
                <Meta label="Seed" value={result.seed} />
                <Meta label="Size" value={`${result.width}×${result.height}`} />
                <Meta label="Steps" value={result.steps} />
              </>
            )}
            <Meta
              label="Time"
              value={
                result.duration != null ? `${result.duration.toFixed(1)}s` : '—'
              }
            />
          </div>

          <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-neutral-400">
            {isGlb ? `Source : ${result.prompt}` : result.prompt}
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleSave}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent-hover"
            >
              {saveLabel}
            </button>
            {isGlb && (
              <button
                onClick={handleSaveStl}
                title="Exporter en STL pour l'impression 3D (mis à l'échelle ~60 mm)"
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                {stlLabel}
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
                {showCode ? '🙈 Hide code' : '🧩 View code'}
              </button>
            )}
            {result.filePath && (
              <button
                onClick={() => onReveal(result.filePath)}
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                📂 Reveal
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
    <div className="flex h-full items-center justify-center overflow-hidden p-6">
      {renderBody()}
    </div>
  );
}
