import React from 'react';

export default function Header({ status, onRefresh }) {
  const { connected, checking } = status;

  let dotColor = 'bg-yellow-500';
  let label = 'Checking Ollama…';
  if (!checking) {
    dotColor = connected ? 'bg-green-500' : 'bg-red-500';
    label = connected ? 'Ollama connected' : 'Ollama unavailable';
  }

  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-panel pl-20 pr-4 select-none">
      {/* pl-20 leaves room for the native macOS traffic lights */}
      <div className="flex items-center gap-2">
        <span className="text-[15px] font-semibold text-neutral-100">
          Ollama Image Studio
        </span>
      </div>

      <button
        onClick={onRefresh}
        title="Click to re-check connection"
        className="flex items-center gap-2 rounded-full border border-border bg-elevated px-3 py-1 text-xs text-neutral-300 transition hover:border-neutral-600"
      >
        <span
          className={`h-2 w-2 rounded-full ${dotColor} ${
            checking ? 'animate-pulse' : ''
          }`}
        />
        {label}
      </button>
    </header>
  );
}
