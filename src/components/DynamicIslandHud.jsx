import React, { useEffect, useState } from 'react';
import { Cpu, Sparkle, CheckCircle, SpinnerGap, ShieldCheck } from '@phosphor-icons/react';

export default function DynamicIslandHud({ processing, progress, localReady, mode, isMeshy }) {
  const [expanded, setExpanded] = useState(false);
  const [justCompleted, setJustCompleted] = useState(false);

  useEffect(() => {
    if (progress?.percent === 100) {
      setJustCompleted(true);
      const timer = setTimeout(() => setJustCompleted(false), 4000);
      return () => clearTimeout(timer);
    }
  }, [progress?.percent]);

  return (
    <div
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      className={`group relative flex items-center justify-between gap-3 rounded-full border transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] select-none cursor-pointer ${
        processing
          ? 'border-amber-400/50 bg-amber-500/15 shadow-[0_0_30px_rgba(245,158,11,0.25)] px-4 py-2'
          : justCompleted
          ? 'border-emerald-400/60 bg-emerald-500/20 shadow-[0_0_35px_rgba(52,211,153,0.3)] px-4 py-2'
          : 'border-white/10 bg-black/60 hover:border-cyan-400/40 hover:bg-black/80 px-3.5 py-1.5 shadow-lg'
      } backdrop-blur-3xl`}
    >
      {/* Glow aura */}
      <span className={`absolute -inset-0.5 rounded-full blur-md opacity-40 transition duration-500 ${
        processing ? 'bg-amber-400 animate-pulse' : justCompleted ? 'bg-emerald-400' : 'bg-cyan-400/0 group-hover:bg-cyan-400/30'
      }`} />

      {/* Left Icon & Indicator */}
      <div className="relative z-10 flex items-center gap-2">
        <div className={`grid h-6 w-6 place-items-center rounded-full transition-transform duration-300 group-hover:scale-110 ${
          processing
            ? 'bg-amber-400/20 text-amber-300'
            : justCompleted
            ? 'bg-emerald-400/20 text-emerald-300'
            : 'bg-cyan-400/15 text-cyan-300'
        }`}>
          {processing ? (
            <SpinnerGap size={14} className="animate-spin" />
          ) : justCompleted ? (
            <CheckCircle size={14} weight="fill" />
          ) : (
            <Sparkle size={13} className="animate-pulse" />
          )}
        </div>

        <div className="min-w-0">
          <span className="block font-mono text-[8px] font-bold uppercase tracking-[0.18em] text-cyan-300/80">
            {processing ? 'Apple Silicon MLX Active' : justCompleted ? 'Deliverable Validated' : 'Apple Spatial Engine'}
          </span>
          <span className="block text-[10px] font-semibold text-white truncate max-w-[140px] sm:max-w-[200px]">
            {processing ? progress?.label || 'Procesando…' : justCompleted ? '¡Activo 3D Completado!' : isMeshy ? 'Meshy Cloud API v6' : 'Buffalo MLX · Private $0'}
          </span>
        </div>
      </div>

      {/* Right Percentage or Quick Badge */}
      <div className="relative z-10 flex items-center gap-2">
        {processing ? (
          <span className="font-mono text-xs font-extrabold text-amber-300 bg-amber-400/20 border border-amber-400/40 px-2.5 py-0.5 rounded-full tabular-nums shadow-sm">
            {progress?.percent}%
          </span>
        ) : justCompleted ? (
          <span className="font-mono text-xs font-extrabold text-emerald-300 bg-emerald-400/20 border border-emerald-400/40 px-2.5 py-0.5 rounded-full shadow-sm">
            100% ✓
          </span>
        ) : (
          <span className="hidden sm:inline-flex items-center gap-1 font-mono text-[9px] text-slate-400 bg-white/5 border border-white/10 px-2.5 py-0.5 rounded-full">
            <ShieldCheck size={11} className="text-emerald-300" />
            <span>Ready</span>
          </span>
        )}
      </div>

      {/* Expanded Apple Info Dropdown */}
      {expanded && !processing && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 w-72 rounded-3xl border border-white/15 bg-[#040e24]/95 p-3.5 shadow-2xl backdrop-blur-3xl text-left animate-fadeIn">
          <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
            <span className="font-mono text-[9px] font-bold uppercase text-cyan-300">
               Designed in California
            </span>
            <span className="text-[9px] font-mono text-slate-400">v1.4.1</span>
          </div>
          <p className="text-[10px] leading-relaxed text-slate-300">
            Arquitectura de baja latencia optimizada para chips Apple M1/M2/M3/M4 con soporte unificado de memoria y exportación directa a Apple Quick Look (USDZ).
          </p>
        </div>
      )}
    </div>
  );
}
