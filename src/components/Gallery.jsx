import React, { useMemo, useState } from 'react';

export default function Gallery({ history, activeId, onSelect }) {
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const filteredHistory = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return history.filter((item) => {
      const typeOk = typeFilter === 'all' || item.type === typeFilter;
      const text = [item.assetName, item.prompt, item.model, item.profile, item.category, item.type].filter(Boolean).join(' ').toLowerCase();
      return typeOk && (!needle || text.includes(needle));
    });
  }, [history, query, typeFilter]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/5 px-4 py-4">
        <div className="flex items-center justify-between">
          <div><p className="font-mono text-[9px] uppercase tracking-[0.18em] text-sky-400/70">Assets</p><h2 className="mt-1 text-sm font-semibold text-white">Historial local</h2></div>
          <span className="grid h-7 min-w-7 place-items-center rounded-lg border border-sky-300/10 bg-sky-300/5 px-1.5 font-mono text-[9px] text-sky-200">{history.length}</span>
        </div>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar historial"
          className="field-modern mt-3 !py-2 text-xs"
        />
        <div className="mt-2 grid grid-cols-4 gap-1 rounded-xl border border-white/5 bg-black/15 p-1">
          {[
            ['all', 'Todo'],
            ['image', 'IMG'],
            ['glb', 'GLB'],
            ['stl', 'STL'],
          ].map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTypeFilter(id)}
              className={`rounded-lg px-2 py-1.5 font-mono text-[8px] uppercase tracking-wider transition ${typeFilter === id ? 'bg-cyan-300/12 text-cyan-100 ring-1 ring-cyan-300/25' : 'text-slate-500 hover:bg-white/5 hover:text-slate-200'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="scroll-dark flex-1 overflow-y-auto p-3">
        {!history.length ? (
          <div className="mt-8 rounded-2xl border border-dashed border-sky-300/10 bg-sky-300/[0.025] p-5 text-center">
            <span className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-sky-300/10 bg-sky-300/5 text-sky-300">◇</span>
            <p className="mt-3 text-[11px] font-medium text-slate-300">Tu primer activo aparecerá aquí</p>
            <p className="mt-1 text-[9px] leading-relaxed text-slate-500">Selecciona una referencia o escribe un prompt para crear el primer resultado local.</p>
          </div>
        ) : !filteredHistory.length ? (
          <div className="mt-8 rounded-2xl border border-dashed border-amber-300/10 bg-amber-300/[0.025] p-5 text-center">
            <span className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-amber-300/10 bg-amber-300/5 text-amber-200">⌕</span>
            <p className="mt-3 text-[11px] font-medium text-slate-300">Sin resultados para este filtro</p>
            <button onClick={() => { setQuery(''); setTypeFilter('all'); }} className="mt-3 rounded-lg border border-amber-200/15 px-3 py-1.5 text-[10px] font-semibold text-amber-100 hover:bg-amber-200/10">Limpiar filtros</button>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {filteredHistory.map((item) => {
              const active = item.id === activeId;
              return (
                <button key={item.id} onClick={() => onSelect(item)} title={item.assetName || item.prompt} className={`group relative aspect-square overflow-hidden rounded-2xl border transition-all duration-300 ${active ? 'border-cyan-300/60 shadow-[0_0_25px_rgba(82,215,255,0.16)]' : 'border-white/[0.07] hover:-translate-y-0.5 hover:border-sky-300/30'}`}>
                  {item.type === 'stl' || item.type === 'glb' ? (
                    <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-br from-sky-400/10 via-blue-900/20 to-black/20">
                      <span className="text-xl text-sky-300">{item.type === 'glb' ? '◈' : '◇'}</span>
                      <span className="mt-1 font-mono text-[7px] uppercase tracking-[0.16em] text-slate-500">{item.type === 'glb' ? 'GLB' : 'STL'}</span>
                    </div>
                  ) : (
                    <img src={item.image?.startsWith('data:') ? item.image : `data:image/png;base64,${item.image}`} alt={item.prompt} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" loading="lazy" />
                  )}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#020b1c] via-[#020b1c]/75 to-transparent px-2 pb-2 pt-5 text-left">
                    <span className="block truncate text-[8px] text-slate-300">{item.assetName || item.prompt}</span>
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
