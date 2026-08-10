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
    <header className="app-header header-glass relative z-20 flex h-[60px] shrink-0 items-center justify-between border-b pl-8 pr-4 select-none">
      <div className="flex min-w-0 items-center gap-3">
        <div className="brand-mark relative grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-xl border border-sky-300/20 bg-gradient-to-br from-blue-500/30 to-cyan-300/10 shadow-[0_0_25px_rgba(22,137,232,0.2)]">
          <span className="text-sm font-bold tracking-tighter text-sky-100">XR</span>
          <span className="absolute inset-x-1 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-[15px] font-semibold tracking-tight text-white">Xreality Convert</span>
            <span className="hidden rounded-md border border-sky-300/10 bg-sky-300/5 px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.16em] text-sky-300 sm:inline">
              {isMeshy ? '☁️ Meshy Cloud API' : '🖥️ MLX Local'}
            </span>
          </div>
          <p className="mt-0.5 truncate text-[10px] text-slate-500">
            {MODE_LABELS[mode]} · {isMeshy ? 'Procesamiento en la Nube con Meshy v6' : 'Producción privada en este Mac'}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Engine Switcher Toggle Buttons */}
        <div className="flex items-center rounded-xl border border-sky-300/10 bg-black/40 p-1">
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('local')}
            className={`rounded-lg px-2.5 py-1 text-[10px] font-medium transition ${!isMeshy ? 'bg-sky-500/20 text-sky-200 border border-sky-400/30 shadow-sm' : 'text-slate-400 hover:text-white'}`}
            title="Usar motor local privado (Hunyuan3D / MLX)"
          >
            🖥️ Local
          </button>
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('meshy')}
            className={`rounded-lg px-2.5 py-1 text-[10px] font-medium transition ${isMeshy ? 'bg-indigo-500/30 text-indigo-200 border border-indigo-400/40 shadow-sm' : 'text-slate-400 hover:text-white'}`}
            title="Usar motor Meshy AI Cloud API v6"
          >
            ☁️ Meshy Cloud
          </button>
        </div>

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

