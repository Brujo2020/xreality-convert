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
      className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition ${
        active ? 'bg-accent text-white' : 'text-neutral-400 hover:text-neutral-200'
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
  image3dInput,
  onPickImage,
  steps3d,
  setSteps3d,
  stlMm,
  setStlMm,
  texture3d,
  setTexture3d,
  hunyuanUp,
  generating,
  onGenerate,
  onCancel,
  randomSeed,
}) {
  const [showAdvanced, setShowAdvanced] = useState(true);
  const update = (key, value) => setParams((p) => ({ ...p, [key]: value }));

  const imageBlocked = mode === 'image' && !imageModelAvailable;
  const stlBlocked = mode === 'stl' && stlModels.length === 0;
  const generateDisabled =
    mode === 'image3d'
      ? !hunyuanUp || !image3dInput
      : !connected || imageBlocked || stlBlocked;

  const generateLabel =
    mode === 'image3d' ? 'Générer la 3D' : mode === 'stl' ? 'Generate STL' : 'Generate';

  return (
    <div className="scroll-dark flex h-full flex-col gap-5 overflow-y-auto p-4">
      {/* Mode toggle */}
      <div className="flex gap-1 rounded-lg border border-border bg-elevated p-1">
        <ModeButton active={mode === 'image'} onClick={() => setMode('image')}>
          🖼️ Image
        </ModeButton>
        <ModeButton active={mode === 'stl'} onClick={() => setMode('stl')}>
          🧊 STL
        </ModeButton>
        <ModeButton active={mode === 'image3d'} onClick={() => setMode('image3d')}>
          🗿 Img→3D
        </ModeButton>
      </div>

      {/* Engine / model */}
      <div>
        <label className="mb-1.5 block text-xs font-medium text-neutral-400">
          {mode === 'image3d' ? 'Moteur 3D' : 'Model'}
        </label>

        {mode === 'image' && (
          <div
            title={
              imageModelAvailable
                ? imageModel
                : `Modèle requis non installé. Lance :\nollama run ${imageModel}`
            }
            className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
              imageModelAvailable
                ? 'border-border bg-elevated text-neutral-100'
                : 'border-red-700 bg-red-950/40 text-red-400'
            }`}
          >
            <span className="truncate">{imageModel}</span>
            {!imageModelAvailable && (
              <span className="ml-2 shrink-0 text-[10px] uppercase">⚠ non installé</span>
            )}
          </div>
        )}

        {mode === 'stl' && (
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

        {mode === 'image3d' && (
          <div
            className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
              hunyuanUp
                ? 'border-border bg-elevated text-neutral-100'
                : 'border-red-700 bg-red-950/40 text-red-400'
            }`}
          >
            <span className="truncate">Hunyuan3D 2.1 (MLX)</span>
            <span className="ml-2 flex shrink-0 items-center gap-1 text-[10px]">
              <span
                className={`h-2 w-2 rounded-full ${
                  hunyuanUp ? 'bg-green-500' : 'bg-red-500'
                }`}
              />
              {hunyuanUp ? 'serveur OK' : 'serveur off'}
            </span>
          </div>
        )}

        {imageBlocked && (
          <p className="mt-1.5 text-[11px] leading-snug text-red-400">
            Modèle requis non installé. Lance&nbsp;:{' '}
            <code className="rounded bg-black/40 px-1">ollama run {imageModel}</code>
          </p>
        )}
        {mode === 'stl' && (
          <p className="mt-1.5 text-[11px] leading-snug text-neutral-500">
            Un modèle de code génère le modèle 3D (JSCAD → STL).
          </p>
        )}
        {mode === 'image3d' && !hunyuanUp && (
          <p className="mt-1.5 text-[11px] leading-snug text-red-400">
            Démarre le serveur&nbsp;:{' '}
            <code className="rounded bg-black/40 px-1">
              cd hunyuan3d-mlx &amp;&amp; ./venv/bin/python server.py
            </code>
          </p>
        )}
      </div>

      {/* Input: prompt (image/stl) or image picker (image3d) */}
      {mode === 'image3d' ? (
        <div>
          <label className="mb-1.5 block text-xs font-medium text-neutral-400">
            Image source
          </label>
          <button
            onClick={onPickImage}
            disabled={generating}
            className="flex w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-elevated p-3 text-sm text-neutral-300 transition hover:border-neutral-600 disabled:opacity-50"
          >
            {image3dInput?.dataUrl ? (
              <>
                <img
                  src={image3dInput.dataUrl}
                  alt={image3dInput.name}
                  className="max-h-40 rounded-md object-contain"
                />
                <span className="truncate text-[11px] text-neutral-500">
                  {image3dInput.name} — cliquer pour changer
                </span>
              </>
            ) : (
              <>
                <span className="text-2xl">🖼️</span>
                <span>Choisir une image…</span>
              </>
            )}
          </button>
          <p className="mt-1.5 text-[11px] leading-snug text-neutral-500">
            Astuce : un objet centré sur fond neutre donne le meilleur résultat.
          </p>
        </div>
      ) : (
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
      )}

      {/* Advanced */}
      <div className="rounded-lg border border-border">
        <button
          onClick={() => setShowAdvanced((s) => !s)}
          className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-neutral-300"
        >
          <span>Advanced parameters</span>
          <span className={`transition-transform ${showAdvanced ? 'rotate-90' : ''}`}>
            ›
          </span>
        </button>

        {showAdvanced && (
          <div className="flex flex-col gap-4 border-t border-border p-3">
            {mode === 'image' && (
              <>
                <Slider label="Width" value={params.width} min={512} max={2048} step={64} suffix="px" onChange={(v) => update('width', v)} />
                <Slider label="Height" value={params.height} min={512} max={2048} step={64} suffix="px" onChange={(v) => update('height', v)} />
                <Slider label="Steps" value={params.steps} min={1} max={20} step={1} onChange={(v) => update('steps', v)} />
              </>
            )}

            {mode === 'image3d' && (
              <>
                <Slider
                  label="Steps (qualité)"
                  value={steps3d}
                  min={10}
                  max={50}
                  step={5}
                  onChange={setSteps3d}
                />
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-neutral-400">
                    Taille STL (mm)
                  </label>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={stlMm}
                    onChange={(e) => setStlMm(Number(e.target.value) || 60)}
                    className="w-full rounded-lg border border-border bg-elevated px-3 py-2 text-sm tabular-nums text-neutral-100 outline-none focus:border-accent"
                  />
                  <p className="mt-1 text-[10px] text-neutral-500">
                    Plus grande dimension de l'objet à l'export STL.
                  </p>
                </div>
                <label className="flex cursor-pointer items-start gap-2">
                  <input
                    type="checkbox"
                    checked={texture3d}
                    onChange={(e) => setTexture3d(e.target.checked)}
                    className="mt-0.5 accent-accent"
                  />
                  <span className="text-xs text-neutral-300">
                    Texture couleur (PBR)
                    <span className="block text-[10px] text-neutral-500">
                      Bake la couleur depuis l'image (+~9 min). Sinon mesh gris.
                    </span>
                  </span>
                </label>
                <p className="text-[11px] leading-snug text-neutral-500">
                  ⏱️ ~9 min/étape shape{texture3d ? ' + ~9 min texture' : ''} sur
                  M2 Pro.
                </p>
              </>
            )}

            {(mode === 'image' || mode === 'stl') && (
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
            )}
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
            {generateLabel}
          </button>
        )}
      </div>
    </div>
  );
}
