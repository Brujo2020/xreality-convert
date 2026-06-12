import React, { useState, useEffect } from 'react';

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
  error,
  onSave,
  onCopyPrompt,
  onReveal,
}) {
  const [saveLabel, setSaveLabel] = useState('💾 Save');
  const [copyLabel, setCopyLabel] = useState('📋 Copy prompt');

  // Reset transient button labels whenever the shown image changes.
  useEffect(() => {
    setSaveLabel(result?.filePath ? '✓ Saved' : '💾 Save');
    setCopyLabel('📋 Copy prompt');
  }, [result?.id, result?.filePath]);

  const handleSave = async () => {
    setSaveLabel('Saving…');
    const path = await onSave();
    setSaveLabel(path ? '✓ Saved' : '💾 Save');
  };

  const handleCopy = async () => {
    const ok = await onCopyPrompt();
    if (ok) {
      setCopyLabel('✓ Copied');
      setTimeout(() => setCopyLabel('📋 Copy prompt'), 1500);
    }
  };

  // --- States: error / generating / empty / image ---
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
      return (
        <div className="flex flex-col items-center gap-4 text-center">
          <span className="h-10 w-10 animate-spin rounded-full border-[3px] border-accent/30 border-t-accent" />
          <p className="text-sm text-neutral-400">Generating…</p>
        </div>
      );
    }

    if (!result) {
      return (
        <div className="flex flex-col items-center gap-2 text-center text-neutral-600">
          <div className="text-4xl">🖼️</div>
          <p className="text-sm">Your generated image will appear here.</p>
        </div>
      );
    }

    return (
      <div className="flex h-full w-full flex-col items-center gap-4">
        <div className="flex min-h-0 flex-1 items-center justify-center">
          <img
            src={`data:image/png;base64,${result.image}`}
            alt={result.prompt}
            className="max-h-full max-w-full rounded-xl border border-border object-contain shadow-2xl"
          />
        </div>

        {/* Metadata + actions */}
        <div className="w-full max-w-3xl shrink-0 rounded-xl border border-border bg-panel p-4">
          <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Meta label="Model" value={result.model} />
            <Meta label="Seed" value={result.seed} />
            <Meta
              label="Size"
              value={`${result.width}×${result.height}`}
            />
            <Meta label="Steps" value={result.steps} />
            <Meta
              label="Time"
              value={
                result.duration != null
                  ? `${result.duration.toFixed(1)}s`
                  : '—'
              }
            />
          </div>

          <p className="mb-3 line-clamp-2 text-xs leading-relaxed text-neutral-400">
            {result.prompt}
          </p>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleSave}
              className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition hover:bg-accent-hover"
            >
              {saveLabel}
            </button>
            <button
              onClick={handleCopy}
              className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
            >
              {copyLabel}
            </button>
            {result.filePath && (
              <button
                onClick={() => onReveal(result.filePath)}
                className="rounded-lg border border-border bg-elevated px-3 py-1.5 text-xs font-medium text-neutral-200 transition hover:border-neutral-600"
              >
                📂 Reveal
              </button>
            )}
          </div>
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
