import React from 'react';
import { Camera, CheckCircle, Clock } from '@phosphor-icons/react';

export default function MultiViewGrid({ views, mainImage, inputDataUrl }) {
  const fallbackImg = mainImage || inputDataUrl;
  const defaultViews = [
    { id: 'front', label: 'Frontal (0°)', image: views?.front || fallbackImg },
    { id: 'right', label: 'Derecha (90°)', image: views?.right || fallbackImg },
    { id: 'back', label: 'Trasera (180°)', image: views?.back || fallbackImg },
    { id: 'left', label: 'Izquierda (270°)', image: views?.left || fallbackImg },
    { id: 'top', label: 'Superior (+90°)', image: views?.top || fallbackImg },
    { id: 'bottom', label: 'Inferior (-90°)', image: views?.bottom || fallbackImg },
  ];

  return (
    <div className="flex h-full w-full flex-col gap-4 p-4 overflow-y-auto select-none font-sans">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div>
          <span className="font-mono text-[9px] font-bold uppercase tracking-[0.2em] text-cyan-300">
            Evidencia & Cobertura Multi-Vista 3D
          </span>
          <h2 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
            Matriz de Proyección 6 Vistas PBR
          </h2>
        </div>
        <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 font-mono text-[9px] font-semibold text-cyan-200">
          6 Vistas Sincronizadas
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 flex-1">
        {defaultViews.map((item) => {
          const hasImage = Boolean(item.image);
          const formatSrc = (img) => {
            if (!img) return '';
            if (img.startsWith('data:') || img.startsWith('http') || img.startsWith('blob:')) return img;
            return `data:image/png;base64,${img}`;
          };

          return (
            <div
              key={item.id}
              className={`relative overflow-hidden rounded-2xl border transition-all ${
                hasImage
                  ? 'border-cyan-300/30 bg-black/40 shadow-[0_0_20px_rgba(56,189,248,0.1)]'
                  : 'border-dashed border-white/10 bg-white/[0.02]'
              }`}
            >
              <div className="absolute top-2 left-2 z-10 flex items-center gap-1.5 rounded-full border border-white/10 bg-black/60 px-2.5 py-1 backdrop-blur-md">
                <Camera size={12} className={hasImage ? 'text-cyan-300' : 'text-slate-500'} />
                <span className="font-mono text-[8px] font-bold uppercase text-slate-200">
                  {item.label}
                </span>
              </div>

              {hasImage ? (
                <div className="group relative flex h-full min-h-[140px] items-center justify-center p-3">
                  <img
                    src={formatSrc(item.image)}
                    alt={item.label}
                    className="max-h-36 w-full rounded-xl object-contain transition duration-300 group-hover:scale-105"
                  />
                  <span className="absolute bottom-2 right-2 rounded-full border border-emerald-400/30 bg-emerald-400/20 p-1 text-emerald-300">
                    <CheckCircle size={14} weight="fill" />
                  </span>
                </div>
              ) : (
                <div className="flex h-full min-h-[140px] flex-col items-center justify-center p-4 text-center">
                  <Clock size={24} className="text-slate-600 mb-1" />
                  <span className="text-[10px] text-slate-500 font-medium">Sintetizando vista...</span>
                  <span className="text-[8px] font-mono text-slate-600 mt-0.5">Sintetizada por Paint</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
