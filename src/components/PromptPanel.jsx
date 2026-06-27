import React, { useState } from 'react';

function Slider({ label, value, min, max, step, onChange, suffix }) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-xs font-medium text-neutral-400">{label}</label>
        <span className="text-xs tabular-nums text-neutral-200">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        className="slider-accent w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

function ModeButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition ${
        active
          ? 'bg-accent text-white'
          : 'text-neutral-400 hover:text-neutral-200'
      }`}
    >
      {children}
    </button>
  );
}

export default function PromptPanel({
  connected,
  mode,
  setMode,
  imageModel,
  imageModelAvailable,
  stlModels,
  stlModel,
  setStlModel,
  prompt,
  setPrompt,
  params,
  setParams,
  generating,
  onGenerate,
  onCancel,
  randomSeed,
}) {
  const [showAdvanced, setShowAdvanced] = useState(true);
  const update = (key, value) => setParams((p) => ({ ...p, [key]: value }));

  const imageBlocked = mode === 'image' && !imageModelAvailable;
  const stlBlocked = mode === 'stl' && stlModels.length === 0;
  const generateDisabled = !connected || imageBlocked || stlBlocked;

  return (
    <div className="scroll-dark flex h-full flex-col gap-5 overflow-y-auto p-4">
      {/* Mode toggle */}
      <div className="flex gap-1 rounded-lg border border-border bg-elevated p-1">
        <ModeButton active={mode === 'image'} onClick={() => setMode('image')}>
          🖼️ Image
        </ModeButton>
        <ModeButton active={mode === 'stl'} onClick={() => setMode('stl')}>
          🧊 STL 3D
        </ModeButton>
      </div>

      {/* Model */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-400">
          Model
        </label>

        {mode === 'image' ? (
          // Image model is fixed. Shown in red with a tooltip if not installed.
          <div
            title={
              imageModelAvailable
                ? imageModel
                : `Modèle requis non installé. Lance dans un terminal :\nollama run ${imageModel}`
            }
            className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
              imageModelAvailable
                ? 'border-border bg-elevated text-neutral-100'
                : 'border-red-700 bg-red-950/40 text-red-400'
            }`}
          >
            <span className="truncate">{imageModel}</span>
            {!imageModelAvailable && (
              <span className="ml-2 shrink-0 text-[10px] uppercase">
                ⚠ non installé
              </span>
            )}
          </div>
        ) : (
          <select
            value={stlModel}
            onChange={(e) => setStlModel(e.target.value)}
            disabled={generating || stlModels.length === 0}
            className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-neutral-100 outline-none focus:border-accent disabled:opacity-50"
          >
            {stlModels.length === 0 && <option>Aucun modèle disponible</option>}
            {stlModels.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        )}

        {imageBlocked && (
          <p className="mt-1.5 text-[11px] leading-snug text-red-400">
            Modèle requis non installé. Lance&nbsp;:{' '}
            <code className="rounded bg-black/40 px-1">
              ollama run {imageModel}
            </code>
          </p>
        )}
        {mode === 'stl' && (
          <p className="mt-1.5 text-[11px] leading-snug text-neutral-500">
            Un modèle de code génère le modèle 3D (JSCAD → STL).
          </p>
        )}
      </div>

      {/* Prompt */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-400">
          Prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            mode === 'stl'
              ? 'Describe the 3D object... (e.g. a hexagonal pen holder)'
              : 'Describe the image...'
          }
          rows={6}
          disabled={generating}
          className="scroll-dark w-full resize-none rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-neutral-100 outline-none placeholder:text-neutral-600 focus:border-accent disabled:opacity-50"
        />
      </div>

      {/* Advanced (collapsible) */}
      <div className="rounded-lg border border-border">
        <button
          onClick={() => setShowAdvanced((s) => !s)}
          className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-neutral-300"
        >
          <span>Advanced parameters</span>
          <span
            className={`transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
          >
            ›
          </span>
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-4 border-t border-border p-3">
            {/* Image-only dimensions/steps */}
            {mode === 'image' && (
              <>
                <Slider
                  label="Width"
                  value={params.width}
                  min={512}
                  max={2048}
                  step={64}
                  suffix="px"
                  onChange={(v) => update('width', v)}
                />
                <Slider
                  label="Height"
                  value={params.height}
                  min={512}
                  max={2048}
                  step={64}
                  suffix="px"
                  onChange={(v) => update('height', v)}
                />
                <Slider
                  label="Steps"
                  value={params.steps}
                  min={1}
                  max={20}
                  step={1}
                  onChange={(v) => update('steps', v)}
                />
              </>
            )}

            {/* Seed (both modes) */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-neutral-400">
                Seed
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={params.seed}
                  onChange={(e) => update('seed', Number(e.target.value) || 0)}
                  className="min-w-0 flex-1 rounded-lg border border-border bg-elevated px-3 py-2 text-sm tabular-nums text-neutral-100 outline-none focus:border-accent"
                />
                <button
                  onClick={() => update('seed', randomSeed())}
                  title="Random seed"
                  className="shrink-0 rounded-lg border border-border bg-elevated px-3 py-2 text-sm transition hover:border-neutral-600"
                >
                  🎲
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="mt-auto flex flex-col gap-2 pt-2">
        {generating ? (
          <>
            <button
              disabled
              className="flex items-center justify-center gap-2 rounded-lg bg-accent/60 px-4 py-2.5 text-sm font-medium text-white"
            >
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Generating…
            </button>
            <button
              onClick={onCancel}
              className="rounded-lg border border-border bg-elevated px-4 py-2.5 text-sm font-medium text-neutral-200 transition hover:border-red-700 hover:text-red-400"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            onClick={onGenerate}
            disabled={generateDisabled}
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            {mode === 'stl' ? 'Generate STL' : 'Generate'}
          </button>
        )}
      </div>
    </div>
  );
}
