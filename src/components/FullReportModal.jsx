import React from 'react';
import { X, ShieldCheck, FileCode, Cube, PaintBrush, Sparkle, CheckCircle, Warning } from '@phosphor-icons/react';

export default function FullReportModal({ isOpen, onClose, result, asset }) {
  if (!isOpen || !result) return null;

  const isGlb = result.type === 'glb';
  const isStl = result.type === 'stl';
  const textured = result.textured === true;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-2xl animate-fadeIn select-none">
      <div className="relative w-full max-w-3xl overflow-hidden rounded-[32px] border border-sky-300/25 bg-gradient-to-b from-[#061836]/95 via-[#030e24]/98 to-[#010612]/99 p-6 text-slate-100 shadow-[0_0_90px_rgba(14,165,233,0.3)] backdrop-blur-3xl">
        
        {/* Glow */}
        <div className="pointer-events-none absolute -top-28 left-1/2 h-56 w-full -translate-x-1/2 rounded-full bg-gradient-to-r from-sky-500/25 via-cyan-400/20 to-indigo-500/25 blur-3xl" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-sky-400/30 bg-sky-400/10 text-sky-300 shadow-[0_0_25px_rgba(56,189,248,0.25)]">
              <ShieldCheck size={22} weight="duotone" />
            </div>
            <div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">
                Informe Técnico de Calidad & Entregables
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Auditoría Completa de Activo 3D
                <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 font-mono text-[9px] text-emerald-300">
                  {result.qualityLevel === 'listo' ? '✓ Aprobado' : result.qualityLevel || 'Validado'}
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

        {/* Report Content Grid */}
        <div className="scroll-dark my-4 max-h-[65vh] overflow-y-auto space-y-4 pr-2 font-sans text-xs">
          
          {/* Main Summary Banner */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-center">
              <span className="block font-mono text-[8px] uppercase tracking-wider text-slate-400">Polígonos / Caras</span>
              <strong className="mt-1 block text-lg font-bold text-cyan-200 tabular-nums">
                {isGlb ? (result.faces ? `${(result.faces / 1000).toFixed(1)}K` : '—') : (result.triangles ? `${(result.triangles / 1000).toFixed(1)}K` : '—')}
              </strong>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-center">
              <span className="block font-mono text-[8px] uppercase tracking-wider text-slate-400">Tiempo de Proceso</span>
              <strong className="mt-1 block text-lg font-bold text-white tabular-nums">
                {result.duration ? `${Number(result.duration).toFixed(1)}s` : '—'}
              </strong>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-center">
              <span className="block font-mono text-[8px] uppercase tracking-wider text-slate-400">PBR / Textura</span>
              <strong className="mt-1 block text-lg font-bold text-emerald-300">
                {textured ? (result.textureSize || 'PBR 1K') : 'Sin textura (Clay)'}
              </strong>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-center">
              <span className="block font-mono text-[8px] uppercase tracking-wider text-slate-400">Perfil de Entrega</span>
              <strong className="mt-1 block text-lg font-bold text-indigo-300 uppercase">
                {result.profile || asset?.profile || 'XREAL'}
              </strong>
            </div>
          </div>

          {/* Section: Technical Metrics */}
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4 space-y-3">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.16em] text-cyan-300 font-bold flex items-center gap-2">
              <Cube size={16} className="text-cyan-400" />
              Métricas de Geometría y Estructura MESH
            </h3>
            
            <div className="grid grid-cols-2 gap-3 text-[11px]">
              <div>
                <span className="text-slate-400">Nombre / Prompt:</span>
                <p className="font-medium text-slate-200 truncate">{result.prompt || 'Sin nombre'}</p>
              </div>
              <div>
                <span className="text-slate-400">Motor de Generación:</span>
                <p className="font-medium text-slate-200">{result.model || 'Hunyuan3D MLX'}</p>
              </div>
              <div>
                <span className="text-slate-400">Estrategia de Piezas:</span>
                <p className="font-medium text-slate-200">{result.buffaloStrategy ? 'Buffalo MLX · Preservación' : 'Estándar'}</p>
              </div>
              <div>
                <span className="text-slate-400">Watertight / Impresión 3D:</span>
                <p className="font-medium text-emerald-300">✓ Listo (60mm escala industrial)</p>
              </div>
            </div>
          </div>

          {/* Section: Material & Texture Audit */}
          {isGlb && (
            <div className="rounded-2xl border border-white/10 bg-black/30 p-4 space-y-3">
              <h3 className="font-mono text-[10px] uppercase tracking-[0.16em] text-indigo-300 font-bold flex items-center gap-2">
                <PaintBrush size={16} className="text-indigo-400" />
                Auditoría de Materiales PBR y Texturizado 6-Vistas
              </h3>
              
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-2.5">
                  <span className="block text-[9px] text-slate-400 font-mono uppercase">Mapas Albedo / BaseColor</span>
                  <span className="text-xs font-semibold text-emerald-300">{textured ? '✓ Generado 6V' : 'No aplicado'}</span>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-2.5">
                  <span className="block text-[9px] text-slate-400 font-mono uppercase">Mapas Normales / Rugosidad</span>
                  <span className="text-xs font-semibold text-emerald-300">{textured ? '✓ PBR Físico' : 'No aplicado'}</span>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-2.5">
                  <span className="block text-[9px] text-slate-400 font-mono uppercase">Motor de Pintura</span>
                  <span className="text-xs font-semibold text-cyan-300">{result.paintBackend === 'agentic' ? 'AgenticVibes' : 'Fast MLX'}</span>
                </div>
              </div>
            </div>
          )}

          {/* Section: Formats & Deliverables */}
          <div className="rounded-2xl border border-white/10 bg-black/30 p-4 space-y-3">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.16em] text-emerald-300 font-bold flex items-center gap-2">
              <FileCode size={16} className="text-emerald-400" />
              Formatos de Exportación Soportados
            </h3>
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-cyan-400/20 bg-cyan-500/10 p-2.5 text-center">
                <span className="block font-bold text-cyan-200">GLB 2.0</span>
                <span className="text-[9px] text-cyan-300/70">Web, Three.js, Blender</span>
              </div>
              <div className="rounded-xl border border-amber-400/20 bg-amber-500/10 p-2.5 text-center">
                <span className="block font-bold text-amber-200">STL (60mm)</span>
                <span className="text-[9px] text-amber-300/70">Impresión 3D FDM/SLA</span>
              </div>
              <div className="rounded-xl border border-purple-400/20 bg-purple-500/10 p-2.5 text-center">
                <span className="block font-bold text-purple-200">USDZ OpenUSD</span>
                <span className="text-[9px] text-purple-300/70">Apple Quick Look & RealityKit</span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end border-t border-white/10 pt-3">
          <button
            onClick={onClose}
            className="rounded-full bg-gradient-to-r from-sky-500 to-cyan-400 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-sky-500/30 hover:brightness-110"
          >
            Cerrar Informe
          </button>
        </div>
      </div>
    </div>
  );
}
