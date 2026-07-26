import React from 'react';

const STATUS = {
  preview: { label: 'Plan local', dot: 'bg-sky-300', card: 'border-sky-300/15 bg-sky-300/[0.04]' },
  ready: { label: 'Listo', dot: 'bg-sky-300', card: 'border-sky-300/15 bg-sky-300/[0.04]' },
  blocked: { label: 'En espera', dot: 'bg-slate-600', card: 'border-white/5 bg-black/15' },
  running: { label: 'Ejecutando', dot: 'bg-amber-300', card: 'border-amber-300/25 bg-amber-300/[0.07]' },
  done: { label: 'Validado', dot: 'bg-emerald-300', card: 'border-emerald-300/20 bg-emerald-300/[0.055]' },
  failed: { label: 'Falló', dot: 'bg-rose-400', card: 'border-rose-400/25 bg-rose-400/[0.07]' },
  cancelled: { label: 'Cancelado', dot: 'bg-slate-400', card: 'border-slate-400/20 bg-slate-400/[0.05]' },
};

function missionSummary(mission) {
  const completed = mission?.tasks?.filter((task) => task.status === 'done').length || 0;
  const total = mission?.tasks?.length || 0;
  if (mission?.status === 'done') return `${total}/${total} skills validadas`;
  if (mission?.status === 'failed') return `Bloqueada · ${completed}/${total}`;
  if (mission?.status === 'cancelled') return `Cancelada · ${completed}/${total}`;
  return `${completed}/${total} skills`;
}

export default function SuperagentMissionControl({ mission, skillCount = 0 }) {
  const tasks = mission?.tasks || [];
  const missionState = STATUS[mission?.status] || STATUS.preview;

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-sky-200/10 px-3.5 pb-3 pt-3.5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-mono text-[8px] uppercase tracking-[0.22em] text-cyan-300/75">
              Mission Control
            </p>
            <h2 className="mt-1 text-sm font-semibold tracking-tight text-white">Superagentes locales</h2>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/20 bg-emerald-300/[0.06] px-2 py-1 font-mono text-[7px] uppercase tracking-wider text-emerald-200">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_10px_#6ee7b7]" />
            Offline
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-1.5">
          <div className="rounded-xl border border-white/5 bg-black/15 px-2.5 py-2">
            <span className="block font-mono text-[7px] uppercase tracking-wider text-slate-500">Skill pack</span>
            <strong className="mt-1 block truncate text-[10px] text-slate-200">
              {mission?.pack?.label || 'Xreality Core'}
            </strong>
          </div>
          <div className="rounded-xl border border-white/5 bg-black/15 px-2.5 py-2">
            <span className="block font-mono text-[7px] uppercase tracking-wider text-slate-500">Registry</span>
            <strong className="mt-1 block text-[10px] text-slate-200">{skillCount || tasks.length} allowlisted</strong>
          </div>
        </div>
        <div
          role="status"
          aria-live="polite"
          className={`mt-2.5 flex items-center justify-between rounded-xl border px-2.5 py-2 ${missionState.card}`}
        >
          <span className="flex items-center gap-2 text-[9px] font-semibold text-slate-200">
            <span className={`h-1.5 w-1.5 rounded-full ${missionState.dot}`} />
            {mission?.status === 'running' ? 'Misión en ejecución' : missionState.label}
          </span>
          <span className="font-mono text-[8px] text-slate-400">{missionSummary(mission)}</span>
        </div>
      </div>

      <div className="scroll-dark min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2.5">
        {tasks.map((task, index) => {
          const state = STATUS[task.status] || STATUS.blocked;
          return (
            <article
              key={task.id}
              aria-current={task.status === 'running' ? 'step' : undefined}
              className={`rounded-xl border p-2.5 transition ${state.card}`}
            >
              <div className="flex items-start gap-2">
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-white/5 bg-black/20 font-mono text-[8px] text-slate-400">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="truncate text-[10px] text-slate-100">{task.agent}</strong>
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${state.dot} ${task.status === 'running' ? 'shadow-[0_0_12px_#fcd34d]' : ''}`} />
                  </div>
                  <p className="mt-0.5 truncate text-[8px] text-slate-500">{task.label}</p>
                  <div className="mt-1.5 flex items-center justify-between gap-2 font-mono text-[7px] uppercase tracking-wider">
                    <span className="text-slate-500">{task.resource === 'gpu' ? 'MLX · GPU' : 'Gate · CPU'}</span>
                    <span className={task.status === 'running' ? 'text-amber-200' : task.status === 'done' ? 'text-emerald-200' : 'text-slate-500'}>
                      {state.label}
                    </span>
                  </div>
                </div>
              </div>
              {task.error && <p className="mt-2 line-clamp-2 text-[8px] leading-relaxed text-rose-200">{task.error}</p>}
            </article>
          );
        })}
        {!tasks.length && (
          <div className="rounded-xl border border-dashed border-sky-300/15 p-4 text-center text-[9px] leading-relaxed text-slate-500">
            Preparando el plan local de skills.
          </div>
        )}
      </div>
      <div className="border-t border-sky-200/10 px-3 py-2 font-mono text-[7px] uppercase tracking-wider text-slate-600">
        Sin cloud · sin shell · DAG determinista
      </div>
    </section>
  );
}
