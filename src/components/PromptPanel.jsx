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

export default function PromptPanel({
  connected,
  models,
  model,
  setModel,
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

  return (
    <div className="scroll-dark flex h-full flex-col gap-5 overflow-y-auto p-4">
      {/* Model selector */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-400">
          Model
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          disabled={generating}
          className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm text-neutral-100 outline-none focus:border-accent disabled:opacity-50"
        >
          {models.length === 0 && (
            <option value={model}>{model} (not detected)</option>
          )}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      {/* Prompt */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-400">
          Prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Describe the image..."
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
            className={`transition-transform ${
              showAdvanced ? 'rotate-90' : ''
            }`}
          >
            ›
          </span>
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-4 border-t border-border p-3">
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

            {/* Seed */}
            <div>
              <label className="mb-1.5 block text-xs font-medium text-neutral-400">
                Seed
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={params.seed}
                  onChange={(e) =>
                    update('seed', Number(e.target.value) || 0)
                  }
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
            disabled={!connected}
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            Generate
          </button>
        )}
      </div>
    </div>
  );
}
