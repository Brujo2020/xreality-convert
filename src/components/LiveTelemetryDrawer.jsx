import React, { useState } from 'react';
import { Terminal, Cpu, Clock, CheckCircle, SpinnerGap, CaretDown, CaretUp } from '@phosphor-icons/react';

export default function LiveTelemetryDrawer({ progress, logs = [] }) {
  const [expanded, setExpanded] = useState(false);

  const defaultLogs = [
    { time: '0.1s', message: '🟢 Inicialización de pipeline y comprobación de ADC/Metal', stage: 'init' },
    { time: '1.2s', message: '🔍 Análisis previo de la referencia visual (Ojo de Águila)', stage: 'analysis' },
    { time: '2.5s', message: '🖼️ Aislamiento de sujeto y eliminación de fondo (Auto-Cutout)', stage: 'preproc' },
    { time: '8.4s', message: '🧊 Reconstrucción de campo de volumen (Shape MLX Octree 128px)', stage: 'shape' },
    { time: '18.0s', message: '🎨 Despliegue UV y síntesis de 6 vistas PBR (Paint Service)', stage: 'paint' },
    { time: '32.1s', message: '🛡️ Evaluación de Gate de Calidad y sello de seguridad GLB/STL', stage: 'gate' },
  ];

  const displayLogs = logs.length ? logs : defaultLogs;

  return (
    <div className="w-full rounded-2xl border border-sky-300/20 bg-gradient-to-b from-[#061836]/90 to-[#020a1a]/95 p-3.5 backdrop-blur-xl text-slate-100 shadow-xl font-sans select-none">
      
      {/* Top Telemetry Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-xl border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            <Terminal size={17} weight="duotone" />
          </div>
          <div>
            <span className="block font-mono text-[8px] uppercase tracking-[0.18em] text-cyan-300/80">
              Consola de Telemetría en Vivo & Etapas MLX
            </span>
            <p className="text-xs font-semibold text-white flex items-center gap-2">
              {progress?.label || 'Procesando en tiempo real…'}
              <span className="font-mono text-[10px] text-amber-300 font-bold tabular-nums">
                {progress?.percent || 0}%
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-white/10 bg-black/40 px-3 py-1 font-mono text-[9px] text-slate-300">
            <Cpu size={13} className="text-emerald-300" />
            <span>GPU Metal: 94%</span>
          </div>
          
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 rounded-full border border-sky-300/30 bg-sky-300/10 px-3 py-1.5 text-[10px] font-semibold text-sky-200 hover:bg-sky-300/20 transition"
          >
            {expanded ? 'Ocultar Logs' : 'Ver Logs de Etapas'}
            {expanded ? <CaretUp size={12} /> : <CaretDown size={12} />}
          </button>
        </div>
      </div>

      {/* Progress Bar Beam */}
      <div className="progress-track mt-3 h-2 rounded-full overflow-hidden">
        <div
          className="progress-fill progress-beam h-full rounded-full transition-all duration-500 bg-gradient-to-r from-blue-500 via-sky-400 to-cyan-300"
          style={{ width: `${progress?.percent || 0}%` }}
        />
      </div>

      {/* Collapsible Logs Timeline */}
      {expanded && (
        <div className="mt-3.5 scroll-dark max-h-48 overflow-y-auto rounded-xl border border-white/10 bg-black/50 p-3 font-mono text-[10px] space-y-2 animate-fadeIn">
          {displayLogs.map((log, index) => {
            const isFinished = (progress?.percent || 0) >= ((index + 1) * 16);
            return (
              <div key={index} className="flex items-start justify-between gap-2 border-b border-white/5 pb-1.5 last:border-none">
                <div className="flex items-start gap-2 min-w-0">
                  {isFinished ? (
                    <CheckCircle size={14} className="text-emerald-300 shrink-0 mt-0.5" weight="fill" />
                  ) : (
                    <SpinnerGap size={14} className="text-amber-300 animate-spin shrink-0 mt-0.5" weight="bold" />
                  )}
                  <span className={isFinished ? 'text-slate-200' : 'text-amber-200 font-semibold'}>
                    {log.message}
                  </span>
                </div>
                <span className="text-[9px] text-slate-500 shrink-0">{log.time}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
