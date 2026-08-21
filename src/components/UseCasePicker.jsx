import React, { useState } from 'react';
import { Armchair, ArrowRight, Boat, Buildings, Bus, Car, CaretDown, Crane, DeviceMobile, Drone, Factory, Lightning, Medal, Motorcycle, Package, PawPrint, Printer, SolarPanel, Tractor, Tree, Truck, Wrench } from '@phosphor-icons/react';
import { USE_CASES } from '../lib/useCases.js';

const USE_CASE_ICONS = {
  industrial: Factory,
  vehicles: Car,
  cargo: Truck,
  trucks: Truck,
  cranes: Crane,
  electrical: Lightning,
  vegetation: Tree,
  buildings: Buildings,
  tools: Wrench,
  forklifts: Tractor,
  excavators: Tractor,
  motorcycles: Motorcycle,
  buses: Bus,
  drones: Drone,
  boats: Boat,
  furniture: Armchair,
  solar: SolarPanel,
  product: Package,
  organic: PawPrint,
  mobilexr: DeviceMobile,
  print3d: Printer,
  master: Medal,
};

export default function UseCasePicker({ value, onChange, disabled }) {
  const [open, setOpen] = useState(false);
  const current = USE_CASES[value];
  const CurrentIcon = USE_CASE_ICONS[value] || Package;
  return (
    <section className="relative">
      <button disabled={disabled} onClick={() => setOpen((state) => !state)} className="glass-card flex w-full items-center gap-3 rounded-2xl p-3 text-left transition hover:border-sky-300/25">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-cyan-300/15 bg-gradient-to-br from-sky-400/15 to-blue-900/10 text-cyan-200"><CurrentIcon size={22} weight="duotone" aria-hidden="true" /></span>
        <span className="min-w-0 flex-1"><span className="block font-mono text-[8px] uppercase tracking-[0.18em] text-sky-400/70">Caso de uso · {current.tag}</span><span className="mt-1 block truncate text-xs font-semibold text-white">{current.label}</span></span>
        <CaretDown size={16} weight="bold" className={`text-sky-400 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open && (
        <div className="mt-2 grid max-h-[420px] grid-cols-2 gap-2 overflow-y-auto rounded-2xl border border-sky-200/10 bg-[#06162c]/95 p-2.5 shadow-[0_25px_70px_rgba(0,5,20,0.55)] backdrop-blur-2xl">
          {Object.entries(USE_CASES).map(([id, item]) => (
            <button key={id} onClick={() => { onChange(id); setOpen(false); }} className={`rounded-xl border p-2.5 text-left transition ${value === id ? 'border-cyan-300/35 bg-cyan-300/10' : 'border-white/5 bg-black/10 hover:border-sky-300/20 hover:bg-white/[0.04]'}`}>
              {React.createElement(USE_CASE_ICONS[id] || Package, { size: 19, weight: 'duotone', className: 'text-sky-300', 'aria-hidden': true })}
              <span className="mt-1 block text-[10px] font-semibold text-slate-100">{item.label}</span>
              <span className="mt-0.5 block text-[8px] text-slate-500">{item.tag}</span>
            </button>
          ))}
        </div>
      )}
      <div className="mt-2 flex items-center gap-1.5 px-1">
        {current.route.map((step, index) => <React.Fragment key={step}><span className="font-mono text-[8px] uppercase tracking-wider text-slate-500">{step}</span>{index < current.route.length - 1 && <ArrowRight size={10} weight="bold" className="text-sky-500" aria-hidden="true" />}</React.Fragment>)}
      </div>
    </section>
  );
}
