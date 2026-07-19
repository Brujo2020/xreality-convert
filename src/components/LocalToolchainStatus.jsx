import React, { useEffect, useRef, useState } from 'react';
import { summarizeTools } from '../lib/toolSummary.js';

const GROUPS = [
  { id: 'ready', label: 'Listas', dot: 'bg-cyan-300' },
  { id: 'missing', label: 'Faltantes', dot: 'bg-amber-300' },
  { id: 'blocked', label: 'Bloqueadas', dot: 'bg-rose-400' },
];

function capabilityLabel(capability) {
  return String(capability).replaceAll('_', ' ');
}

function ToolRow({ tool }) {
  const hint = tool.status === 'missing'
    ? tool.installHint || (tool.bundled
      ? 'Componente incluido no disponible; revisa el motor local.'
      : 'Instala esta herramienta para habilitar sus capacidades.')
    : tool.status === 'blocked'
    ? 'La comprobación local no pudo completarse.'
    : null;

  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 border-t border-sky-200/[0.07] py-2.5 first:border-t-0">
      <div className="min-w-0">
        <p className="truncate text-[11px] font-medium text-slate-100">{tool.label || tool.id || 'Herramienta local'}</p>
        <p className="mt-1 font-mono text-[8px] leading-relaxed text-slate-500">
          {(tool.capabilities || []).map(capabilityLabel).join(' · ') || 'sin capacidades declaradas'}
        </p>
        {hint && <p className="mt-1.5 text-[9px] leading-relaxed text-slate-400">{hint}</p>}
      </div>
      <span className={`mt-0.5 h-fit rounded border px-1.5 py-0.5 font-mono text-[7px] uppercase tracking-[0.14em] ${
        tool.bundled
          ? 'border-blue-300/20 bg-blue-400/10 text-blue-200'
          : 'border-slate-400/15 bg-white/[0.035] text-slate-400'
      }`}>
        {tool.bundled ? 'Incluida' : 'Opcional'}
      </span>
    </li>
  );
}

export default function LocalToolchainStatus({ snapshot, checking, onRefresh }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const tools = Array.isArray(snapshot?.tools) ? snapshot.tools : [];
  const summary = summarizeTools(tools);
  const displayTotal = summary.total || 8;

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    const handlePointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('pointerdown', handlePointerDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('pointerdown', handlePointerDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls="local-toolchain-status"
        onClick={() => setOpen((current) => !current)}
        className="group flex h-10 items-center gap-2 rounded-xl border border-sky-200/10 bg-[#020b1c]/55 px-2.5 transition hover:border-cyan-300/25 hover:bg-[#071a33]"
      >
        <span className="grid h-5 w-5 place-items-center rounded-md border border-cyan-300/15 bg-cyan-300/[0.06] font-mono text-[9px] text-cyan-200">
          {checking ? '··' : summary.ready}
        </span>
        <span className="text-left leading-none">
          <span className="block whitespace-nowrap font-mono text-[9px] font-medium text-slate-200">
            {summary.ready}/{displayTotal} tools listas
          </span>
          <span className="mt-1 block font-mono text-[7px] uppercase tracking-[0.16em] text-slate-500">
            {checking ? 'comprobando' : `${summary.bundledReady} incluidas`}
          </span>
        </span>
        <span aria-hidden="true" className={`text-[9px] text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`}>⌄</span>
      </button>

      {open && (
        <div
          id="local-toolchain-status"
          role="status"
          aria-live="polite"
          className="absolute right-0 top-[calc(100%+0.55rem)] z-50 w-[min(390px,calc(100vw-1.5rem))] select-text overflow-hidden rounded-2xl border border-sky-200/15 bg-[#061429]/[0.98] shadow-[0_24px_70px_rgba(0,4,16,0.72)] backdrop-blur-2xl"
        >
          <div className="flex items-center justify-between border-b border-sky-200/10 px-4 py-3">
            <div>
              <p className="font-mono text-[8px] uppercase tracking-[0.2em] text-cyan-300">Cadena 3D local</p>
              <p className="mt-1 text-[10px] text-slate-400">Capacidades detectadas en este Mac</p>
            </div>
            <button
              type="button"
              disabled={checking}
              onClick={() => onRefresh?.()}
              className="rounded-lg border border-sky-200/10 px-2.5 py-1.5 font-mono text-[8px] uppercase tracking-[0.12em] text-sky-200 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.06] disabled:cursor-wait disabled:opacity-45"
            >
              {checking ? 'Comprobando…' : 'Comprobar'}
            </button>
          </div>

          <div className="scroll-dark max-h-[min(460px,calc(100vh-6rem))] overflow-y-auto px-4 py-1">
            {!checking && !snapshot && (
              <p className="py-5 text-center text-[10px] text-slate-400">No fue posible comprobar las herramientas locales.</p>
            )}
            {GROUPS.map((group) => {
              const groupTools = tools.filter((tool) => (
                group.id === 'blocked'
                  ? tool.status !== 'ready' && tool.status !== 'missing'
                  : tool.status === group.id
              ));
              return (
                <section key={group.id} aria-labelledby={`tool-group-${group.id}`} className="py-2">
                  <div className="flex items-center justify-between py-1.5">
                    <h3 id={`tool-group-${group.id}`} className="flex items-center gap-2 font-mono text-[8px] uppercase tracking-[0.16em] text-slate-400">
                      <span className={`h-1.5 w-1.5 rounded-full ${group.dot}`} />
                      {group.label}
                    </h3>
                    <span className="font-mono text-[8px] tabular-nums text-slate-600">{groupTools.length}</span>
                  </div>
                  {groupTools.length > 0 && (
                    <ul>{groupTools.map((tool) => <ToolRow key={tool.id} tool={tool} />)}</ul>
                  )}
                </section>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
