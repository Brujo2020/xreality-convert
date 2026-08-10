import React from 'react';
import { ClockCounterClockwise, Cpu } from '@phosphor-icons/react';

const MODE_LABELS = {
  image: 'Imagen',
  stl: 'Texto → malla',
  image3d: 'Imagen → activo 3D',
};

export default function Header({
  status,
  hunyuanUp,
  mode,
  engineProvider = 'local',
  onSelectEngineProvider,
  processing,
  progress,
  historyCount,
  historyOpen,
  onToggleHistory,
  onRefresh,
}) {
  const [showPricing, setShowPricing] = React.useState(false);
  const isMeshy = engineProvider === 'meshy';
  const localReady = isMeshy ? true : (mode === 'image3d' ? hunyuanUp : status.connected);
  const state = processing ? 'Procesando' : localReady ? 'Listo' : 'Preparando';
  const tone = processing ? 'working' : localReady ? 'ready' : 'standby';
  const dot = processing ? 'bg-amber-300 text-amber-300' : localReady ? 'bg-emerald-300 text-emerald-300' : 'bg-sky-300 text-sky-300';
  const detail = processing
    ? progress?.label || (isMeshy ? 'Meshy Cloud API activa' : 'Pipeline local activo')
    : isMeshy
    ? 'Meshy API v6 · Cloud Engine'
    : localReady
    ? mode === 'image3d' ? 'Buffalo MLX · Shape · Paint · PBR' : 'Servicios locales disponibles'
    : mode === 'image3d' ? 'Preparando motor MLX' : 'Comprobando servicios locales';

  return (
    <header className="app-header header-glass relative z-20 flex h-[64px] shrink-0 items-center justify-between border-b border-white/10 px-6 select-none backdrop-blur-2xl">
      <div className="flex min-w-0 items-center gap-3.5">
        <div className="brand-mark group relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-2xl border border-cyan-400/30 bg-gradient-to-br from-cyan-500/25 via-sky-500/15 to-indigo-600/30 shadow-[0_0_30px_rgba(56,189,248,0.25)] transition duration-300 hover:scale-105 hover:border-cyan-300/50 hover:shadow-[0_0_40px_rgba(56,189,248,0.4)]">
          <span className="text-base font-extrabold tracking-tight text-cyan-100 drop-shadow-[0_2px_10px_rgba(56,189,248,0.5)]">XR</span>
          <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-500 animate-pulse" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-[16px] font-bold tracking-tight bg-gradient-to-r from-white via-sky-100 to-cyan-200 bg-clip-text text-transparent">
              Xreality Convert
            </span>
            <span className="hidden rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider text-cyan-300 sm:inline shadow-[0_0_12px_rgba(56,189,248,0.15)]">
              {isMeshy ? '☁️ Meshy Cloud API v6' : '🖥️ MLX Apple Silicon'}
            </span>
          </div>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            {MODE_LABELS[mode]} · {isMeshy ? 'Aceleración en la Nube · 5cr Smart Preview' : 'Producción privada local $0 en este Mac'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2.5">
        {/* Engine Switcher Toggle Buttons */}
        <div className="flex items-center rounded-2xl border border-white/10 bg-black/50 p-1 shadow-inner backdrop-blur-md">
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('local')}
            className={`rounded-xl px-3 py-1.5 text-[11px] font-semibold transition duration-200 ${!isMeshy ? 'bg-gradient-to-r from-sky-500/30 to-cyan-400/20 text-white border border-cyan-400/40 shadow-[0_0_15px_rgba(56,189,248,0.25)]' : 'text-slate-400 hover:text-slate-200'}`}
            title="Usar motor local privado (Hunyuan3D / MLX)"
          >
            🖥️ Local ($0)
          </button>
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('meshy')}
            className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition duration-200 ${isMeshy ? 'bg-gradient-to-r from-indigo-500/35 to-purple-500/25 text-white border border-indigo-400/50 shadow-[0_0_20px_rgba(129,140,248,0.3)]' : 'text-slate-400 hover:text-slate-200'}`}
            title="Usar motor Meshy AI Cloud API v6"
          >
            ☁️ Meshy Cloud
          </button>
        </div>

        {/* Meshy Credit Dashboard Button */}
        {isMeshy && (
          <button
            onClick={() => setShowPricing((v) => !v)}
            className="flex items-center gap-1.5 rounded-2xl border border-amber-400/40 bg-gradient-to-r from-amber-500/20 to-orange-500/10 px-3 py-1.5 text-[11px] font-bold text-amber-200 shadow-[0_0_18px_rgba(251,191,36,0.18)] transition duration-200 hover:scale-105 hover:bg-amber-400/25 hover:border-amber-300/60"
          >
            💰 Tabla de Créditos (5cr)
          </button>
        )}

        {/* Modal de Precios & Santo Grial Meshy */}
        {showPricing && (
          <div className="absolute right-4 top-14 z-50 w-96 rounded-2xl border border-white/10 bg-[#061429]/95 p-4 shadow-2xl backdrop-blur-2xl text-left">
            <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-2">
              <span className="text-xs font-bold text-sky-200">💎 Detalles de costo de API (Santo Grial Meshy)</span>
              <button onClick={() => setShowPricing(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>
            
            <div className="flex flex-col gap-2 font-sans text-[11px]">
              <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-2 text-emerald-200">
                <strong className="block text-[10px] uppercase font-bold text-emerald-300">🛡️ Regla de Oro Anti-Quemado</strong>
                Valida primero en <strong>Smart Topology T2 (5 créditos sin textura)</strong>. Revisa la geometría y sólo si te gusta, ejecuta Refine o Texturizado (10-20cr).
              </div>

              <table className="w-full text-left text-[10px] text-slate-300">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="pb-1">Tipo de generación</th>
                    <th className="pb-1 text-right">Costo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  <tr className="bg-amber-400/10 text-amber-200 font-bold">
                    <td className="py-1">Imagen a 3D (Smart Topology T2, sin textura)</td>
                    <td className="py-1 text-right">⚡ 5 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Imagen a 3D (Smart Topology T2, con textura)</td>
                    <td className="py-1 text-right">15 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Imagen a 3D (Meshy 6, sin textura)</td>
                    <td className="py-1 text-right">20 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Imagen a 3D (Meshy 6, con textura PBR 8K)</td>
                    <td className="py-1 text-right">🚀 30 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Texto a 3D (Malla Meshy 6)</td>
                    <td className="py-1 text-right">20 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Re-texturizar / Generar Textura</td>
                    <td className="py-1 text-right">🎨 10 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Remesh / Auto-Rigging</td>
                    <td className="py-1 text-right">🛠️ 5 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1">Animación</td>
                    <td className="py-1 text-right">🎬 3 créditos</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        <button
          onClick={onToggleHistory}
          aria-pressed={historyOpen}
          className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[10px] transition ${historyOpen ? 'border-sky-300/30 bg-sky-300/10 text-sky-100' : 'border-sky-200/10 bg-white/[0.03] text-slate-400 hover:border-sky-300/25 hover:text-white'}`}
        >
          <ClockCounterClockwise size={14} weight="duotone" aria-hidden="true" />
          Historial <span className="font-mono text-[9px] text-sky-300">{historyCount}</span>
        </button>
        <button onClick={onRefresh} title="Comprobar servicios" className={`status-control status-control-${tone} flex items-center gap-2.5 rounded-xl px-3 py-2 transition`}>
          <Cpu size={17} weight="duotone" className={processing ? 'text-amber-200' : localReady ? 'text-emerald-200' : 'text-sky-200'} aria-hidden="true" />
          <span className="relative flex h-2.5 w-2.5">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-50 ${dot} ${processing ? 'animate-ping' : ''}`} />
            <span className={`state-dot relative inline-flex h-2.5 w-2.5 rounded-full ${dot}`} />
          </span>
          <span className="min-w-0 text-left">
            <span className="block text-[10px] font-medium text-slate-200">{state}</span>
            <span className="hidden max-w-[165px] truncate font-mono text-[8px] uppercase tracking-wider text-slate-400 md:block">{detail}</span>
          </span>
        </button>
      </div>
    </header>
  );
}

