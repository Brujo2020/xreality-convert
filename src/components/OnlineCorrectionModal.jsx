import React, { useState } from 'react';
import { X, Sparkle, Polygon, ArrowRight, ShieldCheck } from '@phosphor-icons/react';

export default function OnlineCorrectionModal({ isOpen, onClose, onApplyCorrection, generating }) {
  const [targetTopology, setTargetTopology] = useState('quad');
  const [polycount, setPolycount] = useState(12000);
  const [autoRigging, setAutoRigging] = useState(false);
  const [repairNormals, setRepairNormals] = useState(true);

  if (!isOpen) return null;

  const handleApply = () => {
    onApplyCorrection({
      topology: targetTopology,
      target_polycount: polycount,
      autoRigging,
      repairNormals,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-2xl animate-fadeIn select-none">
      <div className="relative w-full max-w-xl overflow-hidden rounded-[32px] border border-indigo-400/30 bg-gradient-to-b from-[#100e28]/95 via-[#08061a]/98 to-[#03020d]/99 p-6 text-slate-100 shadow-[0_0_90px_rgba(99,102,241,0.25)] backdrop-blur-3xl">
        
        {/* Top Glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-gradient-to-r from-indigo-500/30 via-purple-500/20 to-pink-500/30 blur-3xl" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-indigo-400/40 bg-gradient-to-br from-indigo-400/20 to-purple-600/30 shadow-[0_0_20px_rgba(99,102,241,0.3)]">
              <Sparkle size={22} className="text-indigo-300" />
            </div>
            <div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-indigo-300">
                Optimización & Corrección de Geometría
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Corregir Modelo & Remesh Quad (Meshy 5cr)
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:border-indigo-300/40 hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="my-4 space-y-4 font-sans text-xs">
          
          {/* Topology Selector */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-indigo-300/80 mb-2">
              Tipo de Topología Destino
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setTargetTopology('quad')}
                className={`rounded-2xl border p-3 text-left transition-all ${
                  targetTopology === 'quad'
                    ? 'border-indigo-400/60 bg-indigo-500/20 text-white shadow-[0_0_20px_rgba(99,102,241,0.2)] ring-1 ring-indigo-400/50'
                    : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-indigo-300/30'
                }`}
              >
                <Polygon size={24} className="text-indigo-300 mb-1" />
                <strong className="block text-xs font-bold text-white">Quad (Malla Limpia Low Poly)</strong>
                <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                  Estructura cuadrilátera ideal para deformación y renderizado en tiempo real.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setTargetTopology('triangle')}
                className={`rounded-2xl border p-3 text-left transition-all ${
                  targetTopology === 'triangle'
                    ? 'border-indigo-400/60 bg-indigo-500/20 text-white shadow-[0_0_20px_rgba(99,102,241,0.2)] ring-1 ring-indigo-400/50'
                    : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-indigo-300/30'
                }`}
              >
                <Sparkle size={24} className="text-purple-300 mb-1" />
                <strong className="block text-xs font-bold text-white">Triangle Decimated</strong>
                <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                  Malla triangular optimizada para motor de físicas y STL directo.
                </p>
              </button>
            </div>
          </div>

          {/* Target Polycount Slider */}
          <div className="rounded-2xl border border-white/10 bg-black/40 p-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-medium text-slate-200">Presupuesto Poligonal (Polycount)</span>
              <strong className="font-mono text-xs text-indigo-300 font-bold">
                {(polycount / 1000).toFixed(1)}K Caras
              </strong>
            </div>
            <input
              type="range"
              min={3000}
              max={50000}
              step={1000}
              value={polycount}
              onChange={(e) => setPolycount(Number(e.target.value))}
              className="slider-accent w-full"
            />
            <div className="flex justify-between text-[8px] font-mono text-slate-500 mt-1 uppercase">
              <span>3K (VR Mobile)</span>
              <span>12K (Juegos Standard)</span>
              <span>50K (Hero Asset)</span>
            </div>
          </div>

          {/* Toggles */}
          <div className="space-y-2">
            <label className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.02] p-3 cursor-pointer">
              <span className="text-xs text-slate-200">Auto-Rigging de Esqueleto (ARDY)</span>
              <input
                type="checkbox"
                checked={autoRigging}
                onChange={(e) => setAutoRigging(e.target.checked)}
                className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-indigo-400"
              />
            </label>

            <label className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.02] p-3 cursor-pointer">
              <span className="text-xs text-slate-200">Reparar Normales Invertidas & Watertight STL</span>
              <input
                type="checkbox"
                checked={repairNormals}
                onChange={(e) => setRepairNormals(e.target.checked)}
                className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-indigo-500 focus:ring-indigo-400"
              />
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/10 pt-4">
          <span className="font-mono text-[9px] text-indigo-300/80 uppercase tracking-wider">
            Costo: 🛠️ 5 créditos Meshy API
          </span>
          <button
            onClick={handleApply}
            disabled={generating}
            className="flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-500/30 hover:brightness-110 disabled:opacity-50"
          >
            {generating ? 'Optimizando Geometría…' : 'Ejecutar Corrección de Modelo'}
            <ArrowRight size={16} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
}
