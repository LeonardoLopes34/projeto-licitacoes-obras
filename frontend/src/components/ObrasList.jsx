import React from "react";
import { Search } from "lucide-react";
import ObraCard from "./ObraCard";
import ObrasSkeleton from "./ObrasSkeleton";

export default function ObrasList({ obras, loading, searchTerm, onClearSearch }) {
  if (loading) {
    return (
      <section
        role="region"
        aria-labelledby="obras-heading-loading"
        aria-busy="true"
        className="space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2
            id="obras-heading-loading"
            className="text-sm sm:text-base font-bold flex items-center gap-2"
            style={{ color: "var(--text-primary)" }}
          >
            <span>Buscando Licitações no PNCP...</span>
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping" />
          </h2>
          <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
            Aplicando filtros de engenharia
          </span>
        </div>
        <ObrasSkeleton count={4} />
      </section>
    );
  }

  if (obras.length === 0) {
    return (
      <section
        role="region"
        aria-labelledby="obras-heading-empty"
        className="theme-card text-center py-16 border rounded-2xl p-6 transition-colors"
      >
        <Search className="w-10 h-10 opacity-40 mx-auto mb-3" aria-hidden="true" />
        <h2 id="obras-heading-empty" className="text-base sm:text-lg font-bold" style={{ color: "var(--text-primary)" }}>
          {searchTerm
            ? `Nenhuma obra encontrada para "${searchTerm}"`
            : "Nenhuma obra encontrada"}
        </h2>
        <p className="text-sm mt-1 max-w-md mx-auto" style={{ color: "var(--text-muted)" }}>
          {searchTerm
            ? "Tente buscar por outro termo, cidade, UF ou órgão público."
            : "Tente aumentar a quantidade de páginas ou ajustar o intervalo de datas."}
        </p>
        {searchTerm && onClearSearch && (
          <button
            type="button"
            onClick={onClearSearch}
            aria-label="Limpar termo e restaurar todos os resultados"
            className="mt-5 inline-flex items-center gap-2 px-5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-bold transition cursor-pointer border shadow-sm hover:border-amber-500"
            style={{
              backgroundColor: "var(--btn-pncp-bg)",
              borderColor: "var(--btn-pncp-border)",
              color: "var(--btn-pncp-text)",
            }}
          >
            Limpar filtro de pesquisa
          </button>
        )}
      </section>
    );
  }

  return (
    <section role="region" aria-labelledby="obras-heading-list" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 id="obras-heading-list" className="text-sm sm:text-base font-bold" style={{ color: "var(--text-primary)" }}>
          Obras e Licitações Encontradas{" "}
          <span className="text-xs font-normal" style={{ color: "var(--text-muted)" }}>
            ({obras.length} {obras.length === 1 ? "resultado" : "resultados"})
          </span>
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {obras.map((obra, idx) => (
          <ObraCard key={obra.id_pncp || obra.numero_controle_pncp || idx} obra={obra} />
        ))}
      </div>
    </section>
  );
}
