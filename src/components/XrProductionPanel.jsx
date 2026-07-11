import React from 'react';
import { XR_PROFILES } from '../lib/xrProfiles.js';

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
          <span className="block text-[7px] uppercase tracking-wider text-slate-500">caras máx.</span>
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
            {asset.profile === id && <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_10px_#52d7ff]" />}
            <span className="block text-base text-sky-300">{profile.icon}</span>
            <span className="mt-1 block text-[10px] font-semibold leading-tight">{profile.label}</span>
            <span className="mt-0.5 block font-mono text-[7px] uppercase tracking-wider text-slate-500">{profile.steps} pasos · {profile.octree}px</span>
          </button>
        ))}
      </div>

      <div className="mx-3 mb-3 rounded-xl border border-white/5 bg-black/15 p-3">
        <div className="mb-3 flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-sky-400/10 text-xs text-sky-300">{current.icon}</span>
          <div className="min-w-0"><p className="text-[10px] font-medium text-slate-200">{current.label}</p><p className="truncate text-[8px] text-slate-500">{current.description}</p></div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[9px] uppercase tracking-wider text-slate-500">
            Geometría
            <select value={asset.targetFaces} disabled={disabled} onChange={(event) => update({ targetFaces: Number(event.target.value) })} className="field-modern mt-1.5 !py-2">
              <option value={12000}>12K · Low poly</option>
              <option value={20000}>20K · Móvil</option>
              <option value={50000}>50K · XR</option>
              <option value={100000}>100K · PC VR</option>
              <option value={200000}>200K · Máxima</option>
            </select>
          </label>
          <label className="text-[9px] uppercase tracking-wider text-slate-500">
            Material
            <select value={asset.textureSize} disabled={disabled} onChange={(event) => update({ textureSize: event.target.value, texture: event.target.value !== 'Sin textura' })} className="field-modern mt-1.5 !py-2">
              <option>Sin textura</option><option>1K</option><option>2K</option>
            </select>
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
