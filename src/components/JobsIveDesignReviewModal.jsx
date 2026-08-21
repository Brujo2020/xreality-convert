import React from 'react';
import { X, Sparkle, SealCheck, Quotes, Warning } from '@phosphor-icons/react';

export default function JobsIveDesignReviewModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-xl animate-fadeIn select-none">
      <div className="relative w-full max-w-2xl overflow-hidden rounded-[32px] border border-cyan-400/30 bg-gradient-to-b from-[#081b38]/95 via-[#040e24]/98 to-[#020714]/99 p-6 text-slate-100 shadow-[0_0_80px_rgba(56,189,248,0.25)] backdrop-blur-3xl">
        
        {/* Decorative Top Glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-gradient-to-r from-cyan-500/30 via-indigo-500/20 to-purple-500/30 blur-3xl" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-cyan-400/40 bg-gradient-to-br from-cyan-400/20 to-indigo-600/30 shadow-[0_0_20px_rgba(56,189,248,0.3)]">
              <Sparkle size={20} className="text-cyan-300 animate-spin-slow" />
            </div>
            <div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">
                Auditoría de Diseño Especial · 2026
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Steve Jobs & Jony Ive en el laboratorio
                <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 font-mono text-[9px] text-amber-300 font-normal">
                  ⚡ Crítica Icrónica
                </span>
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:border-cyan-300/40 hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Dialogue Scroll Area */}
        <div className="scroll-dark my-4 max-h-[60vh] overflow-y-auto space-y-4 pr-2 font-sans text-xs leading-relaxed">
          
          {/* Context Intro */}
          <div className="rounded-2xl border border-rose-500/20 bg-rose-950/20 p-3 text-[11px] text-rose-200/90 flex gap-3 items-start">
            <Warning size={20} className="shrink-0 text-rose-300 mt-0.5" />
            <p>
              <strong>Escenario:</strong> Es un lunes lluvioso a las 7:00 AM. Steve tuvo un vuelo cancelado y Jony se levantó con dolor de cuello y el pie izquierdo. Se sientan frente a la pantalla a juzgar el nuevo <strong>Xreality Convert</strong>.
            </p>
          </div>

          {/* Dialogue Item 1 - Steve Jobs */}
          <div className="rounded-2xl border border-sky-400/20 bg-sky-950/30 p-4 shadow-inner">
            <div className="flex items-center gap-2 mb-2">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-amber-400 to-red-500 text-black font-extrabold text-[10px]">SJ</span>
              <strong className="text-amber-300 text-sm">Steve Jobs (furioso con un café frío):</strong>
            </div>
            <p className="text-slate-200 italic pl-3 border-l-2 border-amber-400/50">
              "¡Mira esto, Jony! ¿Qué es este montón de botones cuadrados y grises que la industria llama 'UI'? Si le das a un usuario una pantalla, ¡tiene que querer chupar los botones porque se ven tan deliciosos! Si veo un solo píxel fuera de alineación o un dropdown aburrido, tiro este prototipo por la ventana."
            </p>
          </div>

          {/* Dialogue Item 2 - Jony Ive */}
          <div className="rounded-2xl border border-indigo-400/20 bg-indigo-950/30 p-4 shadow-inner">
            <div className="flex items-center gap-2 mb-2">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-slate-200 to-indigo-300 text-black font-extrabold text-[10px]">JI</span>
              <strong className="text-indigo-300 text-sm">Jony Ive (suspirando profundamente y ajustando sus lentes):</strong>
            </div>
            <p className="text-slate-200 italic pl-3 border-l-2 border-indigo-400/50">
              "Calma, Steve... Pero tienes razón. Es imperdonable. El vidrio no es solo transparencia, es <em>proporción</em>, es el modo en que la luz refracta a través del aluminio unibody. Si los bordes no tienen un radio de curvatura continuo de 9999px —una cápsula perfecta— mi alma británica sufre una agonía estética."
            </p>
          </div>

          {/* Dialogue Item 3 - Steve examines Xreality Convert */}
          <div className="rounded-2xl border border-cyan-400/30 bg-cyan-950/40 p-4 shadow-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-cyan-400 to-sky-500 text-black font-extrabold text-[10px]">SJ</span>
              <strong className="text-cyan-300 text-sm">Steve Jobs (haciendo zoom a Xreality Convert):</strong>
            </div>
            <p className="text-slate-100 pl-3 border-l-2 border-cyan-400">
              "Un momento... Mira este visor 3D. Las curvas Glassmorphism, el degradado cyan-índigo, los botones de cápsula redondeada... ¡Tiene el selector de texturas PBR online y la conversión inteligente con 5 créditos sin quemar la API! ¡Y el informe de status se llena con un anillo pulsante en vivo! ¡Esto NO es una app, es una obra de arte espacial!"
            </p>
          </div>

          {/* Dialogue Item 4 - Jony Ive Approval */}
          <div className="rounded-2xl border border-emerald-400/30 bg-emerald-950/40 p-4 shadow-lg">
            <div className="flex items-center gap-2 mb-2">
              <span className="grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 text-black font-extrabold text-[10px]">JI</span>
              <strong className="text-emerald-300 text-sm">Jony Ive (sonriendo levemente por primera vez en la mañana):</strong>
            </div>
            <p className="text-slate-100 pl-3 border-l-2 border-emerald-400">
              "Impresionante... Esto responde al principio supremo: <strong>FFF — Form Follows Function</strong>. La forma cápsula ultra-suave no es un capricho; es la expresión física pura de la función. El botón de <em>Texturizar PBR</em>, la corrección de topología Quad y la exportación limpia a USDZ para RealityKit... La complejidad se ha disuelto. Este diseño grita **innovación, elegancia y futuro accesible**."
            </p>
          </div>

          {/* Final Verdict Badge */}
          <div className="rounded-2xl border border-emerald-400/40 bg-gradient-to-r from-emerald-500/20 via-cyan-500/20 to-indigo-500/20 p-4 text-center">
            <SealCheck size={28} className="mx-auto text-emerald-300 mb-1" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Veredicto Oficial del Laboratorio
            </h3>
            <p className="text-[11px] text-emerald-200 mt-1 font-mono">
              APROBADO POR UNANIMIDAD CON NOTA 10/10 · "INSANELY GREAT" 🚀
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-white/10 pt-3">
          <button
            onClick={onClose}
            className="rounded-full bg-gradient-to-r from-cyan-500 to-blue-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-cyan-500/30 hover:brightness-110"
          >
            Entendido, volver a crear 3D ✨
          </button>
        </div>
      </div>
    </div>
  );
}
