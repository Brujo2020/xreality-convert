import React from 'react';

export default function Gallery({ history, activeId, onSelect }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/5 px-4 py-4">
        <div className="flex items-center justify-between">
          <div><p className="font-mono text-[9px] uppercase tracking-[0.18em] text-sky-400/70">Assets</p><h2 className="mt-1 text-sm font-semibold text-white">Historial local</h2></div>
          <span className="grid h-7 min-w-7 place-items-center rounded-lg border border-sky-300/10 bg-sky-300/5 px-1.5 font-mono text-[9px] text-sky-200">{history.length}</span>
        </div>
      </div>

      <div className="scroll-dark flex-1 overflow-y-auto p-3">
        {!history.length ? (
          <div className="mt-8 rounded-2xl border border-dashed border-sky-300/10 bg-sky-300/[0.025] p-5 text-center">
            <span className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-sky-300/10 bg-sky-300/5 text-sky-300">◇</span>
            <p className="mt-3 text-[11px] font-medium text-slate-300">Tu primer activo aparecerá aquí</p>
            <p className="mt-1 text-[9px] leading-relaxed text-slate-500">Todo se guarda localmente para volver a iterar.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {history.map((item) => {
              const active = item.id === activeId;
              return (
                <button key={item.id} onClick={() => onSelect(item)} title={item.prompt} className={`group relative aspect-square overflow-hidden rounded-2xl border transition-all duration-300 ${active ? 'border-cyan-300/60 shadow-[0_0_25px_rgba(82,215,255,0.16)]' : 'border-white/[0.07] hover:-translate-y-0.5 hover:border-sky-300/30'}`}>
                  {item.type === 'stl' || item.type === 'glb' ? (
                    <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-br from-sky-400/10 via-blue-900/20 to-black/20">
                      <span className="text-xl text-sky-300">{item.type === 'glb' ? '◈' : '◇'}</span>
                      <span className="mt-1 font-mono text-[7px] uppercase tracking-[0.16em] text-slate-500">{item.type === 'glb' ? 'GLB' : 'STL'}</span>
                    </div>
                  ) : (
                    <img src={`data:image/png;base64,${item.image}`} alt={item.prompt} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" loading="lazy" />
                  )}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#020b1c] via-[#020b1c]/75 to-transparent px-2 pb-2 pt-5 text-left">
                    <span className="block truncate text-[8px] text-slate-300">{item.prompt}</span>
                    <span className="mt-0.5 block font-mono text-[7px] uppercase text-sky-400/60">{item.profile || item.type}</span>
                  </div>
                  {active && <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_#52d7ff]" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
