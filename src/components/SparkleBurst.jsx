import React, { useEffect, useState } from 'react';
import { Sparkle, SealCheck } from '@phosphor-icons/react';

export default function SparkleBurst({ show }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (show) {
      setVisible(true);
      const timer = setTimeout(() => setVisible(false), 3500);
      return () => clearTimeout(timer);
    }
  }, [show]);

  if (!visible) return null;

  const particles = Array.from({ length: 18 });

  return (
    <div className="pointer-events-none absolute inset-0 z-40 flex items-center justify-center overflow-hidden select-none">
      
      {/* Central Glowing Shield Badge */}
      <div className="animate-bounce-short flex flex-col items-center rounded-3xl border border-cyan-300/50 bg-gradient-to-b from-cyan-500/30 via-indigo-600/30 to-purple-600/40 p-5 shadow-[0_0_80px_rgba(56,189,248,0.5)] backdrop-blur-2xl">
        <SealCheck size={48} className="text-cyan-200 animate-pulse" weight="fill" />
        <span className="mt-2 font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-200">
          ¡Entrega 3D Validada!
        </span>
        <span className="text-xs text-white font-semibold">Listo para Inspeccionar & Exportar</span>
      </div>

      {/* Floating Sparkle Particles */}
      {particles.map((_, i) => {
        const randomX = (Math.sin(i * 37) * 220).toFixed(0);
        const randomY = (Math.cos(i * 29) * 180).toFixed(0);
        const delay = (i * 0.1).toFixed(1);
        const size = 12 + (i % 3) * 6;

        return (
          <div
            key={i}
            className="absolute text-cyan-300 animate-ping opacity-80"
            style={{
              transform: `translate(${randomX}px, ${randomY}px)`,
              animationDelay: `${delay}s`,
              animationDuration: '2s',
            }}
          >
            <Sparkle size={size} weight="fill" />
          </div>
        );
      })}
    </div>
  );
}
