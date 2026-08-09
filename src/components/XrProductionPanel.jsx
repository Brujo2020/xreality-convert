import React from 'react';
import { CheckCircle, Cpu, DesktopTower, DeviceMobile, Medal, Palette, Polygon, VirtualReality, Visor } from '@phosphor-icons/react';
import { XR_PROFILES } from '../lib/xrProfiles.js';

const PROFILE_ICONS = {
  lowpoly: Polygon,
  mobile: DeviceMobile,
  quest: VirtualReality,
  vrready: VirtualReality,
  smart: Cpu,
  xreal: Visor,
  pcvr: DesktopTower,
  maxquality: Medal,
};

const MATERIAL_HINTS = [
  ['auto', 'Auto · director técnico'],
  ['skin', 'Piel'], ['hair', 'Pelo'], ['fur', 'Pelaje'], ['foliage', 'Follaje'],
  ['metal', 'Metal desnudo'], ['painted_metal', 'Metal pintado'], ['rust', 'Óxido'],
  ['carpet', 'Alfombra'], ['fabric', 'Tela'], ['plastic', 'Plástico'], ['rubber', 'Goma'],
  ['ceramic', 'Loza / cerámica'], ['porcelain', 'Porcelana'], ['glass', 'Vidrio'],
  ['concrete', 'Hormigón'], ['wood', 'Madera'], ['matte_paint', 'Pintura mate'],
];

const FACE_BUDGETS = [15000, 20000, 30000, 35000, 40000, 45000, 50000, 60000, 70000, 80000, 90000, 100000, 110000, 200000];

export default function XrProductionPanel({ asset, setAsset, setSteps3d, disabled }) {
  const update = (patch) => setAsset((current) => ({ ...current, ...patch }));
  const selectProfile = (id) => {
    const profile = XR_PROFILES[id];
    update({
      profile: id,
      octree: profile.octree,
      texture: profile.texture,
      targetFaces: profile.targetFaces,
      textureSize: profile.textureSize,
      paintBackend: profile.paintBackend,
    });
    setSteps3d(profile.steps);
  };
  const current = XR_PROFILES[asset.profile];

  return (
    <section className="glass-card overflow-hidden rounded-2xl">
      <div className="flex items-start justify-between border-b border-white/5 px-4 py-3.5">
        <div>
          <p className="font-mono text-[9px] uppercase tracking-[0.18em] text-cyan-400/70">Destino</p>
          <h2 className="mt-1 text-sm font-semibold text-white">Perfil de entrega</h2>
        </div>
        <div className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 px-2 py-1 text-right">
          <span className="block font-mono text-[9px] text-cyan-200">{Math.round(asset.targetFaces / 1000)}K</span>
          <span className="block text-[7px] uppercase tracking-wider text-slate-500">{asset.textureSize === '1K' ? 'rápido · 1K' : asset.textureSize === '2K' ? 'maestro · 2K' : 'sin material'}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 p-3">
        {Object.entries(XR_PROFILES).map(([id, profile]) => (
          <button
            key={id}
            disabled={disabled}
            onClick={() => selectProfile(id)}
            title={profile.description}
            className={`relative min-h-[66px] overflow-hidden rounded-xl border p-2.5 text-left transition-all duration-250 ${
              asset.profile === id
                ? 'border-sky-300/45 bg-gradient-to-br from-blue-500/25 to-cyan-400/10 text-white shadow-[0_10px_25px_rgba(22,137,232,0.18)]'
                : 'border-white/[0.06] bg-black/15 text-slate-400 hover:-translate-y-0.5 hover:border-sky-300/20 hover:bg-white/[0.04]'
            }`}
          >
            {asset.profile === id && <CheckCircle size={15} weight="fill" className="absolute right-2 top-2 text-cyan-300" aria-hidden="true" />}
            {React.createElement(PROFILE_ICONS[id] || Polygon, { size: 20, weight: 'duotone', className: 'text-sky-300', 'aria-hidden': true })}
            <span className="mt-1 block text-[10px] font-semibold leading-tight">{profile.label}</span>
            <span className="mt-0.5 block font-mono text-[7px] uppercase tracking-wider text-slate-500">{profile.steps} pasos · {profile.octree}px</span>
          </button>
        ))}
      </div>

      <div className="mx-3 mb-3 rounded-xl border border-violet-300/15 bg-gradient-to-r from-violet-400/[0.07] to-cyan-300/[0.05] px-3 py-2.5">
        <p className="font-mono text-[8px] uppercase tracking-[0.16em] text-violet-200/80">Buffalo Strategic MLX · activo</p>
        <p className="mt-1 text-[8px] leading-relaxed text-slate-400">Contrato de partes, preservación transaccional y gates GLB/PBR. Shape y Paint usan Metal en secuencia; el análisis CPU queda acotado al chip.</p>
      </div>

      <div className="mx-3 mb-3 rounded-xl border border-white/5 bg-black/15 p-3">
        <div className="mb-3 flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-sky-400/10 text-sky-300">{React.createElement(PROFILE_ICONS[asset.profile] || Polygon, { size: 17, weight: 'duotone', 'aria-hidden': true })}</span>
          <div className="min-w-0"><p className="text-[10px] font-medium text-slate-200">{current.label}</p><p className="truncate text-[8px] text-slate-500">{current.description}</p></div>
        </div>
        {asset.profile === 'maxquality' && <p className="mb-3 rounded-lg border border-amber-300/15 bg-amber-300/5 px-2.5 py-2 text-[8px] leading-relaxed text-amber-200/75">Maestro es fail-closed: humanos, animales, vehículos, grúas y arquitectura pueden exigir 2–3 vistas reales. Las vistas sintéticas no cuentan como evidencia.</p>}
        {asset.profile === 'lowpoly' && <p className="mb-3 rounded-lg border border-emerald-300/15 bg-emerald-300/5 px-2.5 py-2 text-[8px] leading-relaxed text-emerald-200/75">Low Poly conserva PBR 1K y deriva la entrega desde una malla validada; ya no elimina la textura.</p>}
        {asset.profile === 'vrready' && <p className="mb-3 rounded-lg border border-cyan-300/15 bg-cyan-300/5 px-2.5 py-2 text-[8px] leading-relaxed text-cyan-200/75">VR Ready limita geometría y material para evitar caídas de rendimiento manteniendo lectura visual.</p>}
        {asset.profile === 'smart' && <p className="mb-3 rounded-lg border border-sky-300/15 bg-sky-300/5 px-2.5 py-2 text-[8px] leading-relaxed text-sky-200/75">Smart detecta la memoria unificada del Mac y aplica una sola ruta Shape → Paint, con límites de seguridad.</p>}
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[9px] uppercase tracking-wider text-slate-500">
            Geometría
            <select value={asset.targetFaces} disabled={disabled} onChange={(event) => update({ targetFaces: Number(event.target.value) })} className="field-modern mt-1.5 !py-2">
              {FACE_BUDGETS.map((faces) => <option key={faces} value={faces}>{Math.round(faces / 1000)}K caras</option>)}
            </select>
          </label>
          <label className="text-[9px] uppercase tracking-wider text-slate-500">
            Material
            <select value={asset.textureSize} disabled={disabled} onChange={(event) => update({ textureSize: event.target.value, texture: event.target.value !== 'Sin textura' })} className="field-modern mt-1.5 !py-2">
              <option>Sin textura</option><option value="1K">1K · Rápido</option><option value="2K">2K · Maestro</option>
            </select>
          </label>
          <label className="col-span-2 text-[9px] uppercase tracking-wider text-slate-500">
            <span className="flex items-center gap-1.5"><Palette size={13} weight="duotone" className="text-sky-300" aria-hidden="true" />Material dominante</span>
            <select value={asset.materialHint || 'auto'} disabled={disabled || !asset.texture} onChange={(event) => update({ materialHint: event.target.value })} className="field-modern mt-1.5 !py-2">
              {MATERIAL_HINTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <span className="mt-1.5 block normal-case leading-relaxed text-slate-500">El director exige mapas y extensiones distintos según el material.</span>
          </label>
          <label className="col-span-2 text-[9px] uppercase tracking-wider text-slate-500">
            Motor de textura
            <select value={asset.paintBackend || 'fast'} disabled={disabled || !asset.texture} onChange={(event) => update({ paintBackend: event.target.value })} className="field-modern mt-1.5 !py-2">
              <option value="fast">Hunyuan MLX · rápido</option>
              <option value="agentic">AgenticVibes · máxima fidelidad 1K</option>
            </select>
            {asset.paintBackend === 'agentic' && <span className="mt-1.5 block normal-case leading-relaxed text-amber-300/70">Reference lock 0.80 · 1K real · más lento · libera modelos entre etapas</span>}
            <span className="mt-1 block normal-case leading-relaxed text-cyan-300/60">La selección es contractual: Fast nunca activa una segunda pasada Agentic oculta.</span>
          </label>
          <label className="col-span-2 text-[9px] uppercase tracking-wider text-slate-500">
            Tamaño real del activo
            <div className="mt-1.5 flex items-center rounded-xl border border-sky-200/10 bg-black/20 pr-3">
              <input type="number" min="0.01" max="100" step="0.01" value={asset.scale} disabled={disabled} onChange={(event) => update({ scale: Number(event.target.value) || 1 })} className="min-w-0 flex-1 bg-transparent px-3 py-2 text-xs text-white outline-none" />
              <span className="font-mono text-[9px] text-sky-300">METROS</span>
            </div>
          </label>
        </div>
      </div>
    </section>
  );
}
