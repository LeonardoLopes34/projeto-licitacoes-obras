import React from "react";

export default function ObrasSkeleton({ count = 4 }) {
  return (
    <div
      role="status"
      aria-label="Carregando lista de licitações de obras públicas..."
      aria-live="polite"
      className="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <span className="sr-only">Carregando licitações de obras do PNCP...</span>
      {Array.from({ length: count }).map((_, idx) => (
        <div
          key={idx}
          className="theme-card border rounded-2xl p-5 flex flex-col justify-between space-y-4 animate-pulse"
        >
          <div className="space-y-3.5">
            {/* Top Badges Skeleton */}
            <div className="flex items-center justify-between gap-2">
              <div className="h-6 w-32 rounded-lg opacity-40" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="flex items-center gap-2">
                <div className="h-5 w-24 rounded-md opacity-30" style={{ backgroundColor: "var(--border-card-hover)" }} />
              </div>
            </div>

            {/* Órgão / Título Skeleton */}
            <div className="space-y-1.5 pt-1">
              <div className="h-5 w-4/5 rounded opacity-50" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="h-4 w-1/2 rounded opacity-30" style={{ backgroundColor: "var(--border-card-hover)" }} />
            </div>

            {/* Data de Publicação Skeleton */}
            <div className="flex items-center gap-2">
              <div className="h-3.5 w-3.5 rounded-full opacity-40" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="h-3.5 w-36 rounded opacity-40" style={{ backgroundColor: "var(--border-card-hover)" }} />
            </div>

            {/* Objeto / Descrição Skeleton */}
            <div className="space-y-2 pt-1">
              <div className="h-3.5 w-full rounded opacity-25" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="h-3.5 w-11/12 rounded opacity-25" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="h-3.5 w-3/4 rounded opacity-25" style={{ backgroundColor: "var(--border-card-hover)" }} />
            </div>
          </div>

          {/* Footer do Card Skeleton */}
          <div className="mt-4 pt-4 border-t flex items-center justify-between gap-3" style={{ borderColor: "var(--border-subtle)" }}>
            <div className="space-y-1">
              <div className="h-2.5 w-20 rounded opacity-30" style={{ backgroundColor: "var(--border-card-hover)" }} />
              <div className="h-5 w-28 rounded opacity-50" style={{ backgroundColor: "var(--border-card-hover)" }} />
            </div>
            <div className="h-9 w-28 rounded-xl opacity-40" style={{ backgroundColor: "var(--border-card-hover)" }} />
          </div>
        </div>
      ))}
    </div>
  );
}
