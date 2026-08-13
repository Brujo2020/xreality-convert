import React, { useState } from 'react';
import { Sparkle, CheckCircle, SpinnerGap, ArrowRight, Eye, ShieldCheck, Cube, Image as ImageIcon } from '@phosphor-icons/react';

export default function PipelineNodeGraph({ percent = 0, onSelectStage, activeStage = 'final', result, imageInput }) {
  const [hoveredNode, setHoveredNode] = useState(null);

  const nodes = [
    {
      id: 'input',
      title: '01. Entrada',
      label: 'Referencia',
      percent: Math.min(100, Math.round(percent * 1.5)),
      icon: ImageIcon,
      color: 'from-blue-500 to-cyan-400',
      status: percent > 5 ? 'complete' : 'working',
      preview: imageInput?.dataUrl || imageInput?.base64,
    },
    {
      id: 'preproc',
      title: '02. Preproceso',
      label: 'Fondo & Sujeto',
      percent: Math.max(0, Math.min(100, Math.round((percent - 10) * 1.6))),
      icon: Eye,
      color: 'from-cyan-400 to-teal-400',
      status: percent >= 25 ? 'complete' : percent > 10 ? 'working' : 'waiting',
      preview: result?.inputDataUrl || imageInput?.dataUrl,
    },
    {
      id: 'shape',
      title: '03. Shape MLX',
      label: 'Campo de Volumen',
      percent: Math.max(0, Math.min(100, Math.round((percent - 25) * 1.8))),
      icon: Cube,
      color: 'from-teal-400 to-indigo-500',
      status: percent >= 75 ? 'complete' : percent > 25 ? 'working' : 'waiting',
      preview: result?.shapeGlbPath || null,
    },
    {
      id: 'paint',
      title: '04. Paint PBR',
      label: 'Textura 6-Vistas',
      percent: Math.max(0, Math.min(100, Math.round((percent - 70) * 4.0))),
      icon: Sparkle,
      color: 'from-indigo-500 to-purple-500',
      status: percent >= 95 ? 'complete' : percent > 70 ? 'working' : 'waiting',
      preview: result?.glbBase64 ? 'textured' : null,
    },
    {
      id: 'gate',
      title: '05. Gate Final',
      label: 'Sello & Export',
      percent: percent >= 100 ? 100 : 0,
      icon: ShieldCheck,
      color: 'from-purple-500 to-pink-500',
      status: percent >= 100 ? 'complete' : 'waiting',
      preview: result?.glbPath || result?.stlPath,
    },
  ];

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-cyan-400/25 bg-gradient-to-r from-[#030d22]/95 via-[#061838]/95 to-[#030d22]/95 p-3.5 backdrop-blur-2xl shadow-[0_0_50px_rgba(56,189,248,0.15)] select-none font-sans">
      
      {/* Top Banner */}
      <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500" />
          </span>
          <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">
            Pipeline Vivo · Conexiones Animadas en Tiempo Real
          </span>
        </div>

        <span className="font-mono text-[10px] font-bold text-emerald-300 bg-emerald-500/10 border border-emerald-400/30 px-2.5 py-0.5 rounded-full">
          {percent}% COMPLETADO
        </span>
      </div>

      {/* SVG Animated Connection Beams */}
      <div className="relative flex items-center justify-between gap-1 sm:gap-2">
        
        {/* SVG Flow Lines Behind Nodes */}
        <svg className="absolute inset-0 h-full w-full pointer-events-none z-0" preserveAspectRatio="none">
          <defs>
            <linearGradient id="beamGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#818cf8" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0.8" />
            </linearGradient>
          </defs>
          <line
            x1="5%"
            y1="50%"
            x2="95%"
            y2="50%"
            stroke="url(#beamGrad)"
            strokeWidth="3"
            strokeDasharray="8,6"
            className="animate-pulse"
          />
        </svg>

        {/* Interactive Nodes */}
        {nodes.map((node) => {
          const isActive = activeStage === node.id;
          const isHovered = hoveredNode === node.id;
          const Icon = node.icon;
          const isComplete = node.status === 'complete';
          const isWorking = node.status === 'working';

          return (
            <button
              key={node.id}
              type="button"
              onClick={() => onSelectStage && onSelectStage(node.id)}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              className={`group relative z-10 flex flex-1 flex-col items-center rounded-2xl border p-2 text-center transition-all duration-300 ${
                isActive
                  ? 'border-cyan-300/80 bg-cyan-400/20 shadow-[0_0_25px_rgba(56,189,248,0.3)] scale-105 ring-2 ring-cyan-400/50'
                  : isHovered
                  ? 'border-white/30 bg-white/10 scale-102'
                  : 'border-white/10 bg-black/40 hover:border-cyan-400/40'
              }`}
            >
              {/* Spinning Ring Glow for Active Node */}
              {isWorking && (
                <span className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-cyan-400 to-indigo-500 opacity-40 blur animate-pulse" />
              )}

              {/* Node Icon & Status Pill */}
              <div className="relative mb-1 flex items-center justify-center">
                <div className={`grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br ${node.color} text-white shadow-md transition group-hover:scale-110`}>
                  {isWorking ? (
                    <SpinnerGap size={16} className="animate-spin text-white" />
                  ) : (
                    <Icon size={16} />
                  )}
                </div>

                {isComplete && (
                  <span className="absolute -top-1 -right-1 rounded-full bg-emerald-400 text-black p-0.5 shadow-md">
                    <CheckCircle size={10} weight="fill" />
                  </span>
                )}
              </div>

              {/* Node Title & Live % Badge */}
              <span className="block font-mono text-[8px] font-bold text-slate-300 uppercase truncate max-w-full">
                {node.label}
              </span>

              {/* Animated Percent Pill */}
              <div className={`mt-1 flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[9px] font-extrabold tabular-nums border ${
                node.percent > 0
                  ? 'border-cyan-300/40 bg-cyan-400/15 text-cyan-200 shadow-[0_0_10px_rgba(56,189,248,0.2)]'
                  : 'border-white/5 bg-white/5 text-slate-500'
              }`}>
                <span>{node.percent}%</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
