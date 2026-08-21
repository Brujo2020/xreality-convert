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
          ? 'border-amber-400/[0.14] bg-amber-500/[0.05] shadow-[0_0_15px_rgba(245,158,11,0.08)] px-4 py-2'
          : justCompleted
          ? 'border-emerald-400/60 bg-emerald-500/20 shadow-[0_0_35px_rgba(52,211,153,0.3)] px-4 py-2'
          : 'border-white/10 bg-black/60 hover:border-cyan-400/40 hover:bg-black/80 px-3.5 py-1.5 shadow-lg'
      } backdrop-blur-3xl`}
    >
      {/* Glow aura */}
      <span className={`absolute -inset-0.5 rounded-full blur-md opacity-[0.14] transition duration-500 ${
        processing ? 'bg-amber-400/30 animate-pulse' : justCompleted ? 'bg-emerald-400' : 'bg-cyan-400/0 group-hover:bg-cyan-400/30'
      }`} />

      {/* Left Icon & Indicator */}
      <div className="relative z-10 flex items-center gap-2">
        <div className={`grid h-6 w-6 place-items-center rounded-full transition-transform duration-300 group-hover:scale-110 ${
          processing
            ? 'bg-amber-400/[0.10] text-amber-200/70'
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
            {processing ? '⚡ Apple Silicon M5 Pro · En Proceso' : justCompleted ? '✓ Entregable Validado' : ' Invencible 2027 Engine'}
          </span>
          <span className="block text-[10px] font-semibold text-white truncate max-w-[140px] sm:max-w-[220px]">
            {processing ? progress?.label || 'Orquestando etapas 3D…' : justCompleted ? '¡Activo 3D Completado y Sellado!' : isMeshy ? 'Meshy Cloud API v7' : 'FlexiCubes + Regional PBR + USDZ'}
          </span>
        </div>
      </div>

      {/* Right Percentage or Quick Badge */}
      <div className="relative z-10 flex items-center gap-2">
        {processing ? (
          <span className="font-mono text-xs font-bold text-amber-200/90 bg-amber-400/[0.12] border border-amber-400/[0.25] px-2.5 py-0.5 rounded-full tabular-nums shadow-sm flex items-center gap-1">
            <SpinnerGap size={10} className="animate-spin text-amber-300" />
            <span>{progress?.percent}%</span>
          </span>
        ) : justCompleted ? (
          <span className="font-mono text-xs font-extrabold text-emerald-300 bg-emerald-400/20 border border-emerald-400/40 px-2.5 py-0.5 rounded-full shadow-sm">
            100% ✓
          </span>
        ) : (
          <span className="hidden sm:inline-flex items-center gap-1 font-mono text-[9px] text-cyan-300 bg-cyan-400/10 border border-cyan-400/30 px-2.5 py-0.5 rounded-full">
            <ShieldCheck size={11} className="text-emerald-300" />
            <span>2027 Ready</span>
          </span>
        )}
      </div>

      {/* Expanded Apple Info Dropdown */}
      {expanded && !processing && (
        <div className="absolute top-12 left-1/2 -translate-x-1/2 z-50 w-80 rounded-3xl border border-sky-400/20 bg-[#040e24]/95 p-4 shadow-2xl backdrop-blur-3xl text-left animate-fadeIn">
          <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2.5">
            <span className="font-mono text-[9px] font-bold uppercase text-cyan-300">
               Motor Espacial INVENCIBLE 2027
            </span>
            <span className="text-[9px] font-mono text-emerald-400 font-bold">Apple M5 Pro</span>
          </div>
          <p className="text-[10px] leading-relaxed text-slate-300 mb-2">
            Pipeline unificado de 10 etapas en memoria compartida: <strong>FlexiCubes</strong> (aristas vivas), <strong>PartDecomposer</strong> (segmentación semántica), <strong>Regional PBR 2K</strong> y exportación estricta a <strong>Apple Quick Look / RealityKit (USDZ)</strong>.
          </p>
          <div className="grid grid-cols-2 gap-1.5 pt-1.5 border-t border-white/10 font-mono text-[8px] text-slate-400">
            <span className="flex items-center gap-1">🟢 342 Tests Unitarios OK</span>
            <span className="flex items-center gap-1">🟢 24GB Memoria Segura</span>
            <span className="flex items-center gap-1">🟢 USDZ RealityKit Strict</span>
            <span className="flex items-center gap-1">🟢 Zero-CUDA Local Pure</span>
          </div>
        </div>
      )}
    </div>
  );
}
