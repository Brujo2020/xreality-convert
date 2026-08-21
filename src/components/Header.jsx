import React from 'react';
import {
  ClockCounterClockwise,
  Cpu,
  Globe,
  MagnifyingGlass,
  Question,
  SpeakerHigh,
  SpeakerSlash,
} from '@phosphor-icons/react';
import DynamicIslandHud from './DynamicIslandHud.jsx';
import { sounds } from '../lib/soundEffects.js';
import { getTranslation } from '../lib/translations.js';

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
  lang = 'es',
  setLang,
  soundMuted,
  onToggleSound,
  onOpenCommandPalette,
  onOpenShortcuts,
}) {
  const [showPricing, setShowPricing] = React.useState(false);
  const [realCredits, setRealCredits] = React.useState(null);
  const isMeshy = engineProvider === 'meshy';
  const t = getTranslation(lang);

  const MODE_LABELS = {
    image: t.mode_image,
    stl: t.mode_stl,
    image3d: t.mode_image3d,
  };

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

  return (
    <header className="app-header header-glass relative z-20 flex h-[64px] shrink-0 items-center justify-between border-b border-sky-500/15 px-6 select-none backdrop-blur-2xl">
      {/* Brand & Mode Label */}
      <div className="flex min-w-0 items-center gap-3.5">
        <div className="brand-mark group relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-full border border-sky-400/40 bg-gradient-to-br from-blue-600/35 via-sky-500/20 to-indigo-700/40 shadow-[0_0_30px_rgba(56,189,248,0.3)] transition duration-300 hover:scale-105 hover:border-sky-300/60 hover:shadow-[0_0_40px_rgba(56,189,248,0.5)]">
          <span className="font-outfit text-base font-extrabold tracking-tight text-cyan-100 drop-shadow-[0_2px_10px_rgba(56,189,248,0.6)]">XR</span>
          <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-sky-400 via-blue-400 to-indigo-500 animate-pulse" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-outfit truncate text-[17px] font-extrabold tracking-tight bg-gradient-to-r from-white via-sky-100 to-cyan-300 bg-clip-text text-transparent">
              {t.app_title}
            </span>
            <span className="hidden rounded-full border border-sky-400/30 bg-sky-500/15 px-2.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider text-sky-300 sm:inline shadow-[0_0_15px_rgba(56,189,248,0.2)]">
              {isMeshy ? '☁️ Meshy Cloud v7' : '🖥️ MLX Apple Silicon'}
            </span>
          </div>
          <p className="mt-0.5 truncate text-[10px] font-medium text-slate-400">
            {MODE_LABELS[mode]} · {isMeshy ? 'Cloud Engine · 5cr Smart Preview' : 'Producción privada local $0 en este Mac'}
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

      {/* Right Controls & Quick Actions */}
      <div className="flex items-center gap-2">
        {/* Command Palette Trigger */}
        <button
          onClick={() => {
            sounds.playClick();
            onOpenCommandPalette && onOpenCommandPalette();
          }}
          className="flex items-center gap-1.5 rounded-full border border-sky-400/25 bg-[#020b1d]/85 px-3 py-1.5 text-xs text-slate-300 hover:border-sky-300/50 hover:text-white transition-all shadow-md"
          title="Abrir Command Palette (⌘K)"
        >
          <MagnifyingGlass size={14} className="text-cyan-300" />
          <span className="hidden md:inline font-mono text-[10px] text-slate-400">{t.cmd_k_hint}</span>
        </button>

        {/* Engine Switcher Toggle Buttons */}
        <div className="flex items-center rounded-full border border-sky-400/20 bg-[#020b1d]/85 p-1 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl">
          <button
            onClick={() => {
              sounds.playClick();
              onSelectEngineProvider && onSelectEngineProvider('local');
            }}
            className={`rounded-full px-3.5 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${!isMeshy ? 'bg-gradient-to-r from-blue-600 via-blue-500 to-sky-500 text-white shadow-[0_0_22px_rgba(37,99,235,0.6)] border border-sky-300/50 scale-[1.03]' : 'text-slate-400 hover:text-slate-200 hover:scale-[1.02]'}`}
            title={t.engine_local_title}
          >
            {t.engine_local}
          </button>
          <button
            onClick={() => {
              sounds.playClick();
              onSelectEngineProvider && onSelectEngineProvider('meshy');
            }}
            className={`rounded-full px-3.5 py-1.5 text-[11px] font-extrabold transition-all duration-300 ${isMeshy ? 'bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-500 text-white shadow-[0_0_22px_rgba(37,99,235,0.6)] border border-sky-300/50 scale-[1.03]' : 'text-slate-400 hover:text-slate-200 hover:scale-[1.02]'}`}
            title={t.engine_meshy_title}
          >
            {t.engine_meshy}
          </button>
        </div>

        {/* Meshy Credit Dashboard Button */}
        {isMeshy && (
          <button
            onClick={() => {
              sounds.playClick();
              setShowPricing((v) => !v);
              if (window.meshy?.getCredits) {
                window.meshy.getCredits(meshyApiKey).then((res) => {
                  if (res?.ok && res.credits != null) setRealCredits(res.credits);
                  else if (res?.error) setRealCredits(res.error.includes('Key') ? 'Sin API Key' : 'Error');
                });
              }
            }}
            className="btn-glass-secondary flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-[11px] font-extrabold text-amber-300 shadow-[0_0_20px_rgba(251,191,36,0.25)] transition-all duration-300 hover:scale-[1.03]"
            title="Haz clic para consultar tu saldo real de créditos API"
          >
            💳 {t.balance}: {realCredits !== null ? `${realCredits} cr` : '...'}
          </button>
        )}

        {/* Sound Toggle */}
        <button
          onClick={() => {
            sounds.playClick();
            onToggleSound && onToggleSound();
          }}
          className={`grid h-8 w-8 place-items-center rounded-full border transition-all ${
            soundMuted
              ? 'border-white/10 bg-white/5 text-slate-500'
              : 'border-sky-400/30 bg-sky-500/15 text-cyan-300 shadow-sm'
          }`}
          title={soundMuted ? t.sound_unmute : t.sound_mute}
        >
          {soundMuted ? <SpeakerSlash size={15} /> : <SpeakerHigh size={15} />}
        </button>

        {/* Language Selector */}
        <button
          onClick={() => {
            sounds.playClick();
            setLang && setLang(lang === 'es' ? 'en' : 'es');
          }}
          className="flex items-center gap-1 rounded-full border border-sky-400/20 bg-[#020b1d]/85 px-2.5 py-1 text-[10px] font-mono font-bold text-cyan-200 hover:border-sky-400/40"
          title="Cambiar idioma (ES / EN)"
        >
          <Globe size={13} className="text-cyan-300" />
          <span>{lang.toUpperCase()}</span>
        </button>

        {/* History Toggle */}
        <button
          onClick={() => {
            sounds.playClick();
            onToggleHistory && onToggleHistory();
          }}
          className={`relative grid h-8 w-8 place-items-center rounded-full border transition-all ${
            historyOpen
              ? 'border-sky-400 bg-sky-500 text-white shadow-[0_0_15px_rgba(56,189,248,0.5)]'
              : 'border-white/10 bg-white/5 text-slate-400 hover:border-sky-400/30 hover:text-white'
          }`}
          title="Historial de generaciones"
        >
          <ClockCounterClockwise size={16} />
          {historyCount > 0 && (
            <span className="absolute -right-1 -top-1 grid h-4 w-4 place-items-center rounded-full bg-cyan-400 text-[9px] font-bold text-black">
              {historyCount}
            </span>
          )}
        </button>

        {/* Pricing Modal */}
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
                    <td className="py-1.5">Imagen a 3D (Meshy 7, sin textura)</td>
                    <td className="py-1.5 text-right">20 créditos</td>
                  </tr>
                  <tr>
                    <td className="py-1.5">Imagen a 3D (Meshy 7, con textura PBR 8K)</td>
                    <td className="py-1.5 text-right">🚀 30 créditos</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
