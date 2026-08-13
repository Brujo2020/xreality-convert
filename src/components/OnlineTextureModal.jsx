import React, { useState } from 'react';
import { X, PaintBrush, Sparkle, ArrowRight } from '@phosphor-icons/react';

const PRESET_TEXTURES = [
  { id: 'chrome', name: 'Metal Cromado Pulido', prompt: 'Polished mirror chrome metallic surface, reflective PBR', icon: '🪙' },
  { id: 'wood', name: 'Madera de Nogal', prompt: 'Dark walnut wood grain texture, satin finish PBR', icon: '🪵' },
  { id: 'carbon', name: 'Fibra de Carbono', prompt: 'Woven carbon fiber composite material, matte finish PBR', icon: '🏁' },
  { id: 'neon', name: 'Neón Cyberpunk', prompt: 'Glowing cyan and violet neon metallic accents, glowing PBR', icon: '🌌' },
  { id: 'marble', name: 'Mármol Blanco', prompt: 'White Carrara marble stone texture with light grey veins', icon: '🏛️' },
  { id: 'titanium', name: 'Titanio Anodizado', prompt: 'Brushed blue anodized titanium metal finish PBR', icon: '🦾' },
];

export default function OnlineTextureModal({ isOpen, onClose, onApplyTexture, generating }) {
  const [selectedPreset, setSelectedPreset] = useState('chrome');
  const [customPrompt, setCustomPrompt] = useState('');
  const [resolution, setResolution] = useState('2K');

  if (!isOpen) return null;

  const handleApply = () => {
    const presetObj = PRESET_TEXTURES.find((p) => p.id === selectedPreset);
    const finalPrompt = customPrompt.trim() || presetObj?.prompt || 'Realistic PBR material';
    onApplyTexture({ prompt: finalPrompt, resolution, presetId: selectedPreset });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-2xl animate-fadeIn select-none">
      <div className="relative w-full max-w-xl overflow-hidden rounded-[32px] border border-amber-400/30 bg-gradient-to-b from-[#170e04]/95 via-[#0c0803]/98 to-[#050301]/99 p-6 text-slate-100 shadow-[0_0_90px_rgba(245,158,11,0.25)] backdrop-blur-3xl">
        
        {/* Top Glow */}
        <div className="pointer-events-none absolute -top-24 left-1/2 h-48 w-96 -translate-x-1/2 rounded-full bg-gradient-to-r from-amber-500/30 via-orange-500/20 to-yellow-500/30 blur-3xl" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-amber-400/40 bg-gradient-to-br from-amber-400/20 to-orange-600/30 shadow-[0_0_20px_rgba(245,158,11,0.3)]">
              <PaintBrush size={22} className="text-amber-300" />
            </div>
            <div>
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-amber-300">
                Texturizado & Swapping de Materiales Online
              </span>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                Cambiar Textura del Modelo (Meshy 10cr)
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-slate-400 hover:border-amber-300/40 hover:bg-white/10 hover:text-white"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="my-4 space-y-4 font-sans text-xs">
          
          {/* Preset Buttons */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-amber-300/80 mb-2">
              Estilos de Materiales Predefinidos
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {PRESET_TEXTURES.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => { setSelectedPreset(preset.id); setCustomPrompt(''); }}
                  className={`rounded-2xl border p-3 text-left transition-all ${
                    selectedPreset === preset.id
                      ? 'border-amber-400/60 bg-amber-500/20 text-white shadow-[0_0_20px_rgba(245,158,11,0.2)] ring-1 ring-amber-400/50'
                      : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-amber-300/30'
                  }`}
                >
                  <span className="text-lg block mb-1">{preset.icon}</span>
                  <strong className="block text-[11px] leading-tight font-semibold">{preset.name}</strong>
                </button>
              ))}
            </div>
          </div>

          {/* Custom Prompt */}
          <div>
            <label className="block text-[10px] font-mono uppercase tracking-wider text-slate-300 mb-1">
              O escribe una dirección creativa de textura personalizada:
            </label>
            <input
              type="text"
              placeholder="Ej: Pintura de coche roja con purpurina dorada y acabado cerámico..."
              value={customPrompt}
              onChange={(e) => setCustomPrompt(e.target.value)}
              className="field-modern w-full text-xs font-sans"
            />
          </div>

          {/* Resolution Selector */}
          <div className="flex items-center justify-between rounded-2xl border border-white/10 bg-black/40 p-3">
            <span className="text-xs font-medium text-slate-200">Resolución de Textura PBR</span>
            <div className="flex gap-1.5">
              {['1K', '2K', '4K'].map((res) => (
                <button
                  key={res}
                  type="button"
                  onClick={() => setResolution(res)}
                  className={`rounded-full px-3 py-1 text-[10px] font-mono font-bold transition ${
                    resolution === res
                      ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md'
                      : 'bg-white/5 text-slate-400 hover:text-white'
                  }`}
                >
                  {res}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-white/10 pt-4">
          <span className="font-mono text-[9px] text-amber-300/80 uppercase tracking-wider">
            Costo: 🎨 10 créditos Meshy API
          </span>
          <button
            onClick={handleApply}
            disabled={generating}
            className="flex items-center gap-2 rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-yellow-500 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-amber-500/30 hover:brightness-110 disabled:opacity-50"
          >
            {generating ? 'Enviando a Meshy Cloud…' : 'Aplicar Textura Online'}
            <ArrowRight size={16} weight="bold" />
          </button>
        </div>
      </div>
    </div>
  );
}
