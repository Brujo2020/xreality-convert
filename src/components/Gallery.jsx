import React from 'react';

export default function Gallery({ history, activeId, onSelect }) {
  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-border px-4 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-400">
          Gallery
        </h2>
        <p className="text-[10px] text-neutral-600">
          {history.length} recent
        </p>
      </div>

      <div className="scroll-dark flex-1 overflow-y-auto p-3">
        {history.length === 0 ? (
          <p className="mt-6 px-2 text-center text-xs text-neutral-600">
            No images yet.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {history.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item)}
                title={item.prompt}
                className={`group relative aspect-square overflow-hidden rounded-lg border transition ${
                  item.id === activeId
                    ? 'border-accent ring-1 ring-accent'
                    : 'border-border hover:border-neutral-600'
                }`}
              >
                {item.type === 'stl' ? (
                  // STL meshes aren't stored inline — show a 3D placeholder tile.
                  <div className="flex h-full w-full flex-col items-center justify-center bg-elevated text-neutral-400">
                    <span className="text-2xl">🧊</span>
                    <span className="mt-0.5 text-[8px] uppercase tracking-wide">
                      STL
                    </span>
                  </div>
                ) : (
                  <img
                    src={`data:image/png;base64,${item.image}`}
                    alt={item.prompt}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                )}
                <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-1.5 py-1 text-left text-[9px] leading-tight text-neutral-300 opacity-0 transition group-hover:opacity-100">
                  seed {item.seed}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
