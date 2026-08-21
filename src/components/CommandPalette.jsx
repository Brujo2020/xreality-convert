import React, { useState, useEffect, useRef } from 'react';
import {
  MagnifyingGlass,
  Cube,
  Camera,
  PaintBrush,
  Polygon,
  Lightbulb,
  Sun,
  Eye,
  FloppyDisk,
  SpeakerHigh,
  SpeakerSlash,
  Globe,
  ClockCounterClockwise,
  ArrowElbowDownLeft,
  X,
} from '@phosphor-icons/react';
import { sounds } from '../lib/soundEffects.js';

export default function CommandPalette({
  isOpen,
  onClose,
  mode,
  setMode,
  engineProvider,
  setEngineProvider,
  onTriggerAction,
  lang = 'es',
  setLang,
  soundMuted,
  onToggleSound,
}) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      sounds.playSwitch();
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const actions = [
    // Modes
    {
      id: 'mode_image',
      group: 'Modos de Generación',
      title: 'Modo: Crear Imagen (FLUX / Ollama)',
      icon: Camera,
      badge: '01',
      run: () => setMode('image'),
    },
    {
      id: 'mode_stl',
      group: 'Modos de Generación',
      title: 'Modo: Texto → 3D Paramétrico (STL)',
      icon: Polygon,
      badge: '02',
      run: () => setMode('stl'),
    },
    {
      id: 'mode_image3d',
      group: 'Modos de Generación',
      title: 'Modo: Imagen → 3D (MLX / Meshy)',
      icon: Cube,
      badge: '03',
      run: () => setMode('image3d'),
    },

    // Engine
    {
      id: 'engine_local',
      group: 'Motor de Procesamiento',
      title: 'Cambiar a Motor Local Apple Silicon MLX ($0)',
      icon: Cube,
      badge: 'Local',
      run: () => setEngineProvider('local'),
    },
    {
      id: 'engine_meshy',
      group: 'Motor de Procesamiento',
      title: 'Cambiar a Motor Meshy Cloud API v7',
      icon: Sun,
      badge: 'Cloud',
      run: () => setEngineProvider('meshy'),
    },

    // 3D View Inspection Modes
    {
      id: 'shade_lit',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: Lit PBR (Realista con reflejos HDRI)',
      icon: PaintBrush,
      badge: 'PBR',
      run: () => onTriggerAction && onTriggerAction('shading', 'lit'),
    },
    {
      id: 'shade_wire',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: Wireframe Pro (Topología poligonal)',
      icon: Polygon,
      badge: 'W',
      run: () => onTriggerAction && onTriggerAction('shading', 'wireframe'),
    },
    {
      id: 'shade_clay',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: Clay MatCap (Escultura de arcilla técnica)',
      icon: Eye,
      badge: 'C',
      run: () => onTriggerAction && onTriggerAction('shading', 'clay'),
    },
    {
      id: 'shade_uv',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: UV Distortion Checkerboard (Costuras y estiramiento)',
      icon: Eye,
      badge: 'UV',
      run: () => onTriggerAction && onTriggerAction('shading', 'uv_checker'),
    },
    {
      id: 'shade_norm',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: Normales de Superficie RGB',
      icon: Eye,
      badge: 'Norm',
      run: () => onTriggerAction && onTriggerAction('shading', 'normals'),
    },
    {
      id: 'shade_xray',
      group: 'Visor 3D · Sombreado',
      title: 'Sombreado: Holograma X-Ray (Visión espacial)',
      icon: Eye,
      badge: 'XRay',
      run: () => onTriggerAction && onTriggerAction('shading', 'xray'),
    },

    // Lighting Environments
    {
      id: 'light_studio',
      group: 'Visor 3D · Iluminación',
      title: 'Luz: Apple Studio High-Key Clean',
      icon: Lightbulb,
      badge: 'Studio',
      run: () => onTriggerAction && onTriggerAction('lighting', 'studio'),
    },
    {
      id: 'light_cyber',
      group: 'Visor 3D · Iluminación',
      title: 'Luz: Cyberpunk Neon Synth (Cian + Magenta)',
      icon: Lightbulb,
      badge: 'Neon',
      run: () => onTriggerAction && onTriggerAction('lighting', 'cyberpunk'),
    },
    {
      id: 'light_sunset',
      group: 'Visor 3D · Iluminación',
      title: 'Luz: Golden Hour Sunset Cálido',
      icon: Lightbulb,
      badge: 'Sunset',
      run: () => onTriggerAction && onTriggerAction('lighting', 'sunset'),
    },
    {
      id: 'light_scifi',
      group: 'Visor 3D · Iluminación',
      title: 'Luz: Deep Space Sci-Fi Lab',
      icon: Lightbulb,
      badge: 'Sci-Fi',
      run: () => onTriggerAction && onTriggerAction('lighting', 'scifi'),
    },

    // Camera Snaps
    {
      id: 'cam_front',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Frontal Canónica',
      icon: Eye,
      badge: '1',
      run: () => onTriggerAction && onTriggerAction('camera', 'front'),
    },
    {
      id: 'cam_right',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Derecha',
      icon: Eye,
      badge: '2',
      run: () => onTriggerAction && onTriggerAction('camera', 'right'),
    },
    {
      id: 'cam_back',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Trasera',
      icon: Eye,
      badge: '3',
      run: () => onTriggerAction && onTriggerAction('camera', 'back'),
    },
    {
      id: 'cam_left',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Izquierda',
      icon: Eye,
      badge: '4',
      run: () => onTriggerAction && onTriggerAction('camera', 'left'),
    },
    {
      id: 'cam_top',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Superior Cenital',
      icon: Eye,
      badge: '5',
      run: () => onTriggerAction && onTriggerAction('camera', 'top'),
    },
    {
      id: 'cam_bottom',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Inferior',
      icon: Eye,
      badge: '6',
      run: () => onTriggerAction && onTriggerAction('camera', 'bottom'),
    },
    {
      id: 'cam_iso',
      group: 'Visor 3D · Cámara',
      title: 'Cámara: Vista Isométrica 3/4',
      icon: Eye,
      badge: '0',
      run: () => onTriggerAction && onTriggerAction('camera', 'iso'),
    },
    {
      id: 'cam_turntable',
      group: 'Visor 3D · Cámara',
      title: 'Giro Turntable 360° Automático',
      icon: Eye,
      badge: 'Space',
      run: () => onTriggerAction && onTriggerAction('camera', 'toggle_turntable'),
    },
    {
      id: 'cam_snapshot',
      group: 'Visor 3D · Captura',
      title: 'Descargar Captura 4K PNG Transparente',
      icon: Camera,
      badge: 'PNG',
      run: () => onTriggerAction && onTriggerAction('camera', 'snapshot'),
    },

    // Global Actions
    {
      id: 'toggle_sound',
      group: 'Preferencias',
      title: soundMuted ? 'Activar Efectos de Sonido Espacial' : 'Silenciar Sonido Espacial',
      icon: soundMuted ? SpeakerHigh : SpeakerSlash,
      badge: soundMuted ? 'OFF' : 'ON',
      run: () => onToggleSound && onToggleSound(),
    },
    {
      id: 'toggle_lang',
      group: 'Preferencias',
      title: lang === 'es' ? 'Switch Language: English (EN)' : 'Cambiar Idioma: Español (ES)',
      icon: Globe,
      badge: lang.toUpperCase(),
      run: () => setLang && setLang(lang === 'es' ? 'en' : 'es'),
    },
  ];

  const filtered = actions.filter((action) =>
    action.title.toLowerCase().includes(query.toLowerCase()) ||
    action.group.toLowerCase().includes(query.toLowerCase()) ||
    action.badge.toLowerCase().includes(query.toLowerCase())
  );

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => (i + 1) % (filtered.length || 1));
      sounds.playClick();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => (i - 1 + filtered.length) % (filtered.length || 1));
      sounds.playClick();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) {
        sounds.playClick();
        filtered[selectedIndex].run();
        onClose();
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 backdrop-blur-md bg-black/65 transition-opacity duration-200 select-none"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-3xl border border-sky-400/30 bg-[#030d22]/95 shadow-[0_25px_90px_rgba(0,0,0,0.8)] backdrop-blur-3xl animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Header */}
        <div className="flex items-center gap-3 border-b border-white/10 px-5 py-4">
          <MagnifyingGlass size={22} weight="bold" className="text-cyan-300" />
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent text-base font-medium text-white placeholder-slate-400 outline-none font-sans"
            placeholder={lang === 'es' ? 'Escribe una acción, modo, cámara o sombreado…' : 'Type an action, mode, camera or shader…'}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
          />
          <span className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">
            ESC
          </span>
        </div>

        {/* Results List */}
        <div className="max-h-[380px] overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-sm text-slate-400">
              {lang === 'es' ? 'No se encontraron acciones coincidentes.' : 'No matching actions found.'}
            </div>
          ) : (
            filtered.map((action, index) => {
              const Icon = action.icon;
              const isSelected = index === selectedIndex;
              return (
                <button
                  key={action.id}
                  onClick={() => {
                    sounds.playClick();
                    action.run();
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`flex w-full items-center justify-between rounded-2xl px-3.5 py-2.5 text-left transition-all ${
                    isSelected
                      ? 'bg-gradient-to-r from-blue-600/40 via-sky-500/25 to-indigo-600/30 border border-sky-400/40 text-white shadow-lg'
                      : 'border border-transparent text-slate-300 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`grid h-8 w-8 place-items-center rounded-xl ${isSelected ? 'bg-sky-400 text-black shadow-md' : 'bg-white/5 text-sky-300'}`}>
                      <Icon size={16} weight="duotone" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-white font-sans">{action.title}</p>
                      <p className="text-[10px] text-slate-400">{action.group}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="rounded-lg border border-sky-400/20 bg-sky-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-cyan-200">
                      {action.badge}
                    </span>
                    {isSelected && (
                      <ArrowElbowDownLeft size={14} className="text-cyan-300 animate-pulse" />
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Footer info bar */}
        <div className="flex items-center justify-between border-t border-white/10 bg-black/40 px-4 py-2 font-mono text-[9px] text-slate-400">
          <div className="flex items-center gap-3">
            <span>↑↓ Navegar</span>
            <span>↵ Ejecutar</span>
            <span>ESC Cerrar</span>
          </div>
          <span className="text-cyan-300 font-bold">Xreality Spatial Command</span>
        </div>
      </div>
    </div>
  );
}
