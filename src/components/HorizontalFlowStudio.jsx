import React from 'react';
import {
  Camera,
  Cube,
  PaintBrush,
  ShieldCheck,
  CheckCircle,
  Lightning,
  SpinnerGap,
  Scan
} from '@phosphor-icons/react';

export default function HorizontalFlowStudio({ percent = 45, mode = 'image3d', isMeshy = false, label = '', textureEnabled = true }) {
  const steps = isMeshy ? [
    {
      id: 1,
      name: '01. Previa 5cr',
      subtitle: 'Smart Topology',
      pctThreshold: 25,
      icon: Camera,
      color: 'from-blue-500 to-indigo-500',
    },
    {
      id: 2,
      name: '02. Malla Quad',
      subtitle: 'Geometría Low-Poly',
      pctThreshold: 50,
      icon: Cube,
      color: 'from-indigo-500 to-sky-400',
    },
    {
      id: 3,
      name: '03. 6-Vistas 360°',
      subtitle: 'Sincronización Multivista',
      pctThreshold: 75,
      icon: Scan,
      color: 'from-sky-400 to-teal-400',
    },
    {
      id: 4,
      name: '04. Mapas PBR',
      subtitle: 'Albedo / Normal / Rough',
      pctThreshold: 90,
      icon: PaintBrush,
      color: 'from-teal-400 to-emerald-400',
    },
    {
      id: 5,
      name: '05. USDZ Apple',
      subtitle: 'Sello Quick Look',
      pctThreshold: 100,
      icon: ShieldCheck,
      color: 'from-emerald-400 to-blue-500',
    }
  ] : mode === 'image' ? [
    {
      id: 1,
      name: '01. Dirección',
      subtitle: 'Prompt & Contexto',
      pctThreshold: 20,
      icon: Camera,
      color: 'from-blue-500 to-cyan-400',
    },
    {
      id: 2,
      name: '02. Modelo FLUX',
      subtitle: 'Carga Pesos IA',
      pctThreshold: 45,
      icon: Cube,
      color: 'from-cyan-400 to-teal-400',
    },
    {
      id: 3,
      name: '03. Difusión',
      subtitle: 'Muestreo Latente',
      pctThreshold: 70,
      icon: Scan,
      color: 'from-teal-400 to-indigo-500',
    },
    {
      id: 4,
      name: '04. VAE Decode',
      subtitle: 'Matriz Píxeles 2D',
      pctThreshold: 90,
      icon: PaintBrush,
      color: 'from-indigo-500 to-purple-500',
    },
    {
      id: 5,
      name: '05. Referencia 2D',
      subtitle: 'Imagen Lista',
      pctThreshold: 100,
      icon: ShieldCheck,
      color: 'from-purple-500 to-pink-500',
    }
  ] : mode === 'stl' ? [
    {
      id: 1,
      name: '01. Requerimiento',
      subtitle: 'Prompt Técnico',
      pctThreshold: 20,
      icon: Camera,
      color: 'from-blue-500 to-cyan-400',
    },
    {
      id: 2,
      name: '02. LLM Code',
      subtitle: 'Inferencia JSCAD',
      pctThreshold: 45,
      icon: Cube,
      color: 'from-cyan-400 to-teal-400',
    },
    {
      id: 3,
      name: '03. Compilación',
      subtitle: 'Evaluación V8 Engine',
      pctThreshold: 70,
      icon: Scan,
      color: 'from-teal-400 to-indigo-500',
    },
    {
      id: 4,
      name: '04. Triangulación',
      subtitle: 'Malla Poligonal CSG',
      pctThreshold: 90,
      icon: PaintBrush,
      color: 'from-indigo-500 to-purple-500',
    },
    {
      id: 5,
      name: '05. Malla STL',
      subtitle: 'Exportación 3D Lista',
      pctThreshold: 100,
      icon: ShieldCheck,
      color: 'from-purple-500 to-pink-500',
    }
  ] : [
    {
      id: 1,
      name: '01. Ingesta & Sujeto',
      subtitle: 'Contrato Alpha & P0',
      pctThreshold: 20,
      icon: Camera,
      color: 'from-blue-500 to-cyan-400',
    },
    {
      id: 2,
      name: '02. Shape & FlexiCubes',
      subtitle: 'Vóxel MLX + Aristas Vivas',
      pctThreshold: 50,
      icon: Cube,
      color: 'from-cyan-400 to-teal-400',
    },
    {
      id: 3,
      name: '03. Partes & SmartUV',
      subtitle: 'PartDecomposer + Islas UV',
      pctThreshold: 75,
      icon: Scan,
      color: 'from-teal-400 to-indigo-500',
    },
    {
      id: 4,
      name: textureEnabled ? '04. Pintado Regional' : '04. Sin Textura',
      subtitle: textureEnabled ? 'PBR Multi-Material 2K' : 'Malla limpia sin shader',
      pctThreshold: 90,
      icon: textureEnabled ? PaintBrush : Cube,
      color: 'from-indigo-500 to-purple-500',
    },
    {
      id: 5,
      name: '05. USDZ & AssetGraph',
      subtitle: 'Sello RealityKit + LODs',
      pctThreshold: 100,
      icon: ShieldCheck,
      color: 'from-purple-500 to-pink-500',
    }
  ];

  return (
    <div className="w-full rounded-3xl border border-sky-500/20 bg-gradient-to-b from-[#061838]/90 to-[#020b1c]/95 p-4.5 backdrop-blur-2xl shadow-xl font-sans select-none">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-2.5 mb-3">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-sky-500/20 text-cyan-300 shadow-[0_0_15px_rgba(56,189,248,0.3)]">
            <Lightning size={17} weight="fill" />
          </div>
          <div>
            <span className="font-mono text-[8px] font-extrabold uppercase tracking-[0.2em] text-cyan-300">
              Flujo de Procesamiento Horizontal
            </span>
            <h3 className="text-xs font-bold text-white flex items-center gap-2 font-outfit">
              {isMeshy
                ? 'Meshy Cloud API v7 Engine'
                : mode === 'image'
                ? 'Ollama FLUX Latent Diffusion Engine'
                : mode === 'stl'
                ? 'Ollama LLM + JSCAD CSG Engine'
                : 'Apple Silicon MLX Local Engine'}
            </h3>
            <p className="mt-0.5 font-mono text-[9px] font-bold text-cyan-300/90 flex items-center gap-1.5">
              {percent < 100 && <SpinnerGap size={12} className="animate-spin text-cyan-300 shrink-0" />}
              <span className="truncate">{label || (percent >= 100 ? '✓ Proceso completado con éxito' : '⚡ Ejecutando orquestación 3D en tiempo real…')}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-[10px] font-extrabold text-cyan-300 bg-sky-500/15 border border-sky-400/30 px-3.5 py-1 rounded-full shadow-sm">
          <span>{percent}% COMPLETADO</span>
        </div>
      </div>

      {/* 5 Step Horizontal Flow Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        {steps.map((step) => {
          const StepIcon = step.icon;
          const isDone = percent >= step.pctThreshold;
          const isCurrent = percent >= (step.pctThreshold - 20) && percent < step.pctThreshold;

          return (
            <div
              key={step.id}
              className={`relative flex flex-col justify-between rounded-2xl border p-3 transition-all duration-300 ${
                isDone
                  ? 'border-emerald-400/40 bg-emerald-950/25'
                  : isCurrent
                  ? 'border-amber-400/[0.14] bg-amber-950/[0.14] shadow-[0_0_12px_rgba(245,158,11,0.06)]'
                  : 'border-white/10 bg-black/40'
              }`}
            >
              {/* Header Icon & Status Badge */}
              <div className="flex items-center justify-between mb-2">
                <div className={`grid h-7 w-7 place-items-center rounded-full bg-gradient-to-br ${step.color} text-black font-extrabold shadow-sm`}>
                  <StepIcon size={15} weight="bold" />
                </div>

                {isDone ? (
                  <span className="flex items-center gap-1 rounded-full bg-emerald-400/20 border border-emerald-400/40 px-2 py-0.5 text-[9px] font-mono font-extrabold text-emerald-300">
                    <CheckCircle size={11} weight="fill" /> OK
                  </span>
                ) : isCurrent ? (
                  <span className="flex items-center gap-1 rounded-full bg-amber-400/[0.08] border border-amber-400/[0.14] px-2 py-0.5 text-[9px] font-mono font-bold text-amber-200/80">
                    <SpinnerGap size={11} className="animate-spin" /> RUN
                  </span>
                ) : (
                  <span className="font-mono text-[9px] font-bold text-slate-500">Wait</span>
                )}
              </div>

              {/* Title & Subtitle */}
              <div>
                <h4 className="text-[11px] font-bold text-white tracking-tight truncate">{step.name}</h4>
                <p className="text-[9px] text-slate-300 mt-0.5 truncate">{step.subtitle}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
