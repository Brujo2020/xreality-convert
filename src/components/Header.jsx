import React from 'react';
import { ClockCounterClockwise, Cpu } from '@phosphor-icons/react';
import DynamicIslandHud from './DynamicIslandHud.jsx';

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
  meshyApiKey,
  processing,
  progress,
  historyCount,
  historyOpen,
  onToggleHistory,
  onRefresh,
  onOpenJobsReview,
}) {
  const [showPricing, setShowPricing] = React.useState(false);
  const [realCredits, setRealCredits] = React.useState(null);
  const isMeshy = engineProvider === 'meshy';

  React.useEffect(() => {
    if (isMeshy && window.meshy?.getCredits) {
      window.meshy.getCredits(meshyApiKey).then((res) => {
        if (res?.ok && res.credits != null) {
          setRealCredits(res.credits);
        } else if (res?.error) {
          setRealCredits(res.error.includes('Key') ? 'Sin API Key' : 'Error API');
        }
      }).catch(() => {
        setRealCredits('Error');
      });
    }
  }, [isMeshy, processing, meshyApiKey]);

  const localReady = isMeshy ? true : (mode === 'image3d' ? hunyuanUp : status.connected);
  const state = processing ? 'Procesando' : localReady ? 'Listo' : 'Preparando';
  const tone = processing ? 'working' : localReady ? 'ready' : 'standby';
  const dot = processing ? 'bg-amber-400 text-amber-400' : localReady ? 'bg-emerald-400 text-emerald-400' : 'bg-sky-400 text-sky-400';
  const detail = processing
    ? progress?.label || (isMeshy ? 'Meshy Cloud API activa' : 'Pipeline local activo')
    : isMeshy
    ? 'Meshy API v6 · Cloud Engine'
    : localReady
    ? mode === 'image3d' ? 'Buffalo MLX · Shape · Paint · PBR' : 'Servicios locales disponibles'
    : mode === 'image3d' ? 'Preparando motor MLX' : 'Comprobando servicios locales';

  return (
    <header className="app-header header-glass relative z-20 flex h-[64px] shrink-0 items-center justify-between border-b border-sky-500/15 px-6 select-none backdrop-blur-2xl">
      <div className="flex min-w-0 items-center gap-3.5">
        <div className="brand-mark group relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-full border border-sky-400/40 bg-gradient-to-br from-blue-600/35 via-sky-500/20 to-indigo-700/40 shadow-[0_0_30px_rgba(56,189,248,0.3)] transition duration-300 hover:scale-105 hover:border-sky-300/60 hover:shadow-[0_0_40px_rgba(56,189,248,0.5)]">
          <span className="font-outfit text-base font-extrabold tracking-tight text-cyan-100 drop-shadow-[0_2px_10px_rgba(56,189,248,0.6)]">XR</span>
          <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-sky-400 via-blue-400 to-indigo-500 animate-pulse" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-outfit truncate text-[17px] font-extrabold tracking-tight bg-gradient-to-r from-white via-sky-100 to-cyan-300 bg-clip-text text-transparent">
              Xreality Convert
            </span>
            <span className="hidden rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-sky-300 sm:inline shadow-[0_0_15px_rgba(56,189,248,0.2)]">
              {isMeshy ? '☁️ Meshy Cloud API v6' : '🖥️ MLX Apple Silicon'}
            </span>
          </div>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            {MODE_LABELS[mode]} · {isMeshy ? 'Aceleración en la Nube · 5cr Smart Preview' : 'Producción privada local $0 en este Mac'}
          </p>
        </div>
      </div>

      {/* Dynamic Island HUD */}
      <div className="hidden lg:flex items-center justify-center mx-4">
        <DynamicIslandHud
          processing={processing}
          progress={progress}
          localReady={localReady}
          mode={mode}
          isMeshy={isMeshy}
        />
      </div>

      <div className="flex items-center gap-2.5">
        {/* Engine Switcher Toggle Buttons */}
        <div className="flex items-center rounded-full border border-sky-400/20 bg-[#020b1d]/85 p-1 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('local')}
            className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${!isMeshy ? 'bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 text-white shadow-[0_0_22px_rgba(37,99,235,0.6)] border border-sky-300/50 scale-[1.03]' : 'text-slate-400 hover:text-slate-200 hover:scale-[1.02]'}`}
            title="Usar motor local privado (Hunyuan3D / MLX)"
          >
            🖥️ Local ($0)
          </button>
          <button
            onClick={() => onSelectEngineProvider && onSelectEngineProvider('meshy')}
            className={`rounded-full px-4 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${isMeshy ? 'bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-500 text-white shadow-[0_0_22px_rgba(37,99,235,0.6)] border border-sky-300/50 scale-[1.03]' : 'text-slate-400 hover:text-slate-200 hover:scale-[1.02]'}`}
            title="Usar motor Meshy AI Cloud API v6"
          >
            ☁️ Meshy Cloud
          </button>
        </div>

        {/* Meshy Credit Dashboard Button */}
        {isMeshy && (
          <button
            onClick={() => {
              setShowPricing((v) => !v);
              if (window.meshy?.getCredits) {
                window.meshy.getCredits(meshyApiKey).then((res) => {
                  if (res?.ok && res.credits != null) setRealCredits(res.credits);
                  else if (res?.error) setRealCredits(res.error.includes('Key') ? 'Sin API Key' : 'Error');
                });
              }
            }}
            className="btn-glass-secondary flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[11px] font-extrabold text-amber-300 shadow-[0_0_20px_rgba(251,191,36,0.25)] transition-all duration-300 hover:scale-[1.03]"
            title="Haz clic para consultar tu saldo real de créditos API"
          >
            💳 Saldo Real: {realCredits !== null ? `${realCredits} cr` : 'Consultando...'}
          </button>
        )}

        {/* Modal de Precios & Santo Grial Meshy */}
        {showPricing && (
          <div className="absolute right-4 top-16 z-50 w-96 rounded-3xl border border-sky-400/25 bg-[#030d22]/95 p-5 shadow-[0_25px_80px_rgba(0,0,0,0.7)] backdrop-blur-2xl text-left">
            <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-2.5">
              <span className="text-xs font-bold text-sky-200">💎 Detalles de costo de API (Santo Grial Meshy)</span>
              <button onClick={() => setShowPricing(false)} className="h-6 w-6 grid place-items-center rounded-full bg-white/10 text-slate-400 hover:bg-white/20 hover:text-white">✕</button>
            </div>
            
            <div className="flex flex-col gap-2 font-sans text-[11px]">
              <div className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-2.5 text-emerald-200">
                <strong className="block text-[10px] uppercase font-bold text-emerald-300">🛡️ Regla de Oro Anti-Quemado</strong>
                Valida primero en <strong>Smart Topology T2 (5 créditos sin textura)</strong>. Revisa la geometría y sólo si te gusta, ejecuta Refine o Texturizado (10-20cr).
              </div>

              <table className="w-full text-left text-[10px] text-slate-300">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400">
                    <th className="pb-1.5">Tipo de generación</th>
                    <th className="pb-1.5 text-right">Costo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  <tr className="bg-amber-400/10 text-amber-200 font-bold">
                    <td className="py-1.5">Imagen a 3D (Smart Topology T2, sin textura)</td>
                    <td className="py-1.5 text-right">⚡ 5 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Imagen a 3D (Smart Topology T2, con textura)</td>
                    <td className="py-1.5 text-right">15 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Imagen a 3D (Meshy 6, sin textura)</td>
                    <td className="py-1.5 text-right">20 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Imagen a 3D (Meshy 6, con textura PBR 8K)</td>
                    <td className="py-1.5 text-right">🚀 30 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Texto a 3D (Malla Meshy 6)</td>
                    <td className="py-1.5 text-right">20 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Re-texturizar / Generar Textura</td>
                    <td className="py-1.5 text-right">🎨 10 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Remesh / Auto-Rigging</td>
                    <td className="py-1.5 text-right">🛠️ 5 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Animación</td>
                    <td className="py-1.5 text-right">🎬 3 créditos</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}

        <button
          onClick={onToggleHistory}
          aria-pressed={historyOpen}
          className={`flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-[11px] font-bold transition-all duration-300 ${historyOpen ? 'border-sky-400/40 bg-sky-500/20 text-sky-100 shadow-[0_0_20px_rgba(56,189,248,0.3)]' : 'border-white/10 bg-white/[0.04] text-slate-300 hover:border-sky-400/30 hover:bg-white/[0.08] hover:text-white'}`}
        >
          <ClockCounterClockwise size={15} weight="duotone" aria-hidden="true" />
          Historial <span className="rounded-full bg-sky-500/20 px-1.5 py-0.5 font-mono text-[9px] font-extrabold text-sky-300">{historyCount}</span>
        </button>
        <button onClick={onRefresh} title="Comprobar servicios" className={`status-control status-control-${tone} flex items-center gap-2.5 rounded-full px-3.5 py-2 transition-all duration-300 hover:scale-[1.02]`}>
          <Cpu size={17} weight="duotone" className={processing ? 'text-amber-300 animate-spin' : localReady ? 'text-emerald-300' : 'text-sky-300'} aria-hidden="true" />
          <span className="relative flex h-2.5 w-2.5">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-50 ${dot} ${processing ? 'animate-ping' : ''}`} />
            <span className={`state-dot relative inline-flex h-2.5 w-2.5 rounded-full ${dot}`} />
          </span>
          <span className="min-w-0 text-left">
            <span className="block text-[10px] font-bold text-slate-100">{state}</span>
            <span className="hidden max-w-[165px] truncate font-mono text-[8px] uppercase tracking-wider text-slate-400 md:block">{detail}</span>
          </span>
        </button>
      </div>
    </header>
  );
}

