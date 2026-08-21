import React, { useState } from 'react';
import { TEXTURE_PRESETS } from '../lib/texturePresets.js';
import { PaintBrush, CaretDown, CaretUp, Sparkle } from '@phosphor-icons/react';

export default function TextureLibraryPicker({ onSelectTexture, disabled = false }) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCat, setSelectedCat] = useState('Todas');

  const categories = ['Todas', ...new Set(TEXTURE_PRESETS.map((p) => p.category))];

  const filteredPresets = selectedCat === 'Todas'
    ? TEXTURE_PRESETS
    : TEXTURE_PRESETS.filter((p) => p.category === selectedCat);

  return (
    <div className="w-full rounded-2xl border border-sky-400/20 bg-sky-950/20 p-3 backdrop-blur-xl shadow-lg font-sans">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <div className="grid h-6 w-6 place-items-center rounded-lg bg-sky-400/20 text-sky-300">
            <PaintBrush size={14} weight="duotone" />
          </div>
          <div>
            <span className="block text-[11px] font-bold text-white">
              🎨 Catálogo de 50 Texturas PBR Recomendadas
            </span>
            <span className="block font-mono text-[8px] text-sky-300">
              Vehículos, Piel, Plantas, Arquitectura, Electrónica y más
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 font-mono text-[9px] font-bold text-amber-300 bg-amber-400/10 border border-amber-400/30 px-2.5 py-1 rounded-full">
          <span>50 PRESETS</span>
          {isOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </div>
      </button>

      {isOpen && (
        <div className="mt-3 border-t border-white/10 pt-3">
          {/* Category Filter Pills */}
          <div className="flex flex-wrap gap-1 mb-2.5 max-h-24 overflow-y-auto pr-1">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCat(cat)}
                className={`rounded-full px-2.5 py-0.5 font-mono text-[8px] transition ${
                  selectedCat === cat
                    ? 'bg-sky-400/30 border border-sky-400/60 text-white font-bold'
                    : 'bg-white/5 border border-white/10 text-slate-400 hover:text-white'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* 50 Presets Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-52 overflow-y-auto pr-1">
            {filteredPresets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                disabled={disabled}
                onClick={() => onSelectTexture(preset.suffix)}
                className="group flex flex-col justify-between rounded-xl border border-white/5 bg-black/30 p-2 text-left transition hover:border-sky-400/40 hover:bg-sky-400/10 disabled:opacity-40"
              >
                <span className="font-mono text-[7px] text-sky-300/70 uppercase font-semibold">{preset.category}</span>
                <span className="text-[10px] font-bold text-slate-200 group-hover:text-white mt-0.5">{preset.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
