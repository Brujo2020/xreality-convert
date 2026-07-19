import React from 'react';
import LocalToolchainStatus from './LocalToolchainStatus.jsx';

export default function Header({ status, onRefresh, toolSnapshot, toolsChecking, onToolsRefresh }) {
  const { connected, checking } = status;
  const state = checking ? 'Conectando' : connected ? 'Sistema listo' : 'Reconectando';
  const dot = checking ? 'bg-amber-400' : connected ? 'bg-cyan-400' : 'bg-rose-400';

  return (
    <header className="relative z-20 flex h-16 shrink-0 items-center justify-between border-b border-sky-200/10 bg-[#061429]/75 pl-20 pr-5 shadow-[0_12px_40px_rgba(0,5,20,0.25)] backdrop-blur-2xl select-none">
      <div className="flex items-center gap-3">
        <div className="relative grid h-9 w-9 place-items-center overflow-hidden rounded-xl border border-sky-300/20 bg-gradient-to-br from-blue-500/30 to-cyan-300/10 shadow-[0_0_25px_rgba(22,137,232,0.2)]">
          <span className="text-sm font-bold tracking-tighter text-sky-100">XR</span>
          <span className="absolute inset-x-1 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="whitespace-nowrap text-[15px] font-semibold tracking-tight text-white">Xreality Convert</span>
            <span className="hidden rounded-md border border-sky-300/10 bg-sky-300/5 px-1.5 py-0.5 font-mono text-[8px] uppercase tracking-[0.16em] text-sky-300 min-[900px]:inline">Spatial asset lab</span>
          </div>
          <p className="mt-0.5 hidden text-[10px] text-slate-500 min-[760px]:block">Imagen, geometría y optimización XR en un flujo local</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <LocalToolchainStatus snapshot={toolSnapshot} checking={toolsChecking} onRefresh={onToolsRefresh} />
        <button type="button" onClick={onRefresh} title="Comprobar servicios" aria-label="Comprobar servicios locales" className="flex h-10 items-center gap-3 rounded-xl border border-sky-200/10 bg-white/[0.035] px-3 transition hover:border-sky-300/25 hover:bg-white/[0.06]">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`absolute inline-flex h-full w-full rounded-full opacity-50 ${dot} ${checking ? 'animate-ping' : ''}`} />
            <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${dot} ${connected ? 'shadow-[0_0_12px_#52d7ff]' : ''}`} />
          </span>
          <span className="hidden text-left min-[720px]:block">
            <span className="block text-[10px] font-medium text-slate-200">{state}</span>
            <span className="block font-mono text-[8px] uppercase tracking-wider text-slate-500">Ollama · MLX local</span>
          </span>
        </button>
      </div>
    </header>
  );
}
