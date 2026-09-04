import React, { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import ObraCard from "./ObraCard";
import ObrasSkeleton from "./ObrasSkeleton";

const CARDS_PER_PAGE = 15;

export default function ObrasList({
  obras,
  loading,
  searchTerm,
  onClearSearch,
  onSelectObra,
  analisesExigencias = {},
  apiPagination = null,
  onLoadNextPage,
  onLoadPreviousPage,
}) {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(obras.length / CARDS_PER_PAGE));
  const page = Math.min(currentPage, totalPages);
  const firstCardIndex = (page - 1) * CARDS_PER_PAGE;
  const apiFirstCardIndex = ((apiPagination?.page || 1) - 1) * CARDS_PER_PAGE;
  const currentObras = useMemo(
    () => obras.slice(firstCardIndex, firstCardIndex + CARDS_PER_PAGE),
    [obras, firstCardIndex],
  );
  const canLoadNextFromApi = Boolean(
    (apiPagination?.temMais || apiPagination?.proximoCursor) && typeof onLoadNextPage === "function",
  );
  const usesApiPagination = Boolean(apiPagination && typeof onLoadNextPage === "function");
  const canLoadPreviousFromApi = Boolean(apiPagination?.hasPrevious && typeof onLoadPreviousPage === "function");
  const changePage = (nextPage) => {
    if (usesApiPagination && nextPage > page && canLoadNextFromApi) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      onLoadNextPage(apiPagination.proximoCursor);
      return;
    }
    setCurrentPage(nextPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

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
            : "Tente aumentar o intervalo de datas ou selecionar outra modalidade."}
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
        {(obras.length > CARDS_PER_PAGE || usesApiPagination) && (
          <span className="text-xs" style={{ color: "var(--text-muted)" }} aria-live="polite">
            Exibindo {usesApiPagination ? apiFirstCardIndex + 1 : firstCardIndex + 1}–{usesApiPagination ? apiFirstCardIndex + obras.length : Math.min(firstCardIndex + CARDS_PER_PAGE, obras.length)}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {currentObras.map((obra, idx) => (
          <ObraCard
            key={obra.id_pncp || obra.numero_controle_pncp || idx}
            itemKey={`obra-${firstCardIndex + idx}`}
            obra={obra}
            analiseExigencias={analisesExigencias[obra.id_pncp || `${obra.cnpj}:${obra.ano}:${obra.sequencial}`] || obra.resumo_exigencias}
            onSelect={onSelectObra}
          />
        ))}
      </div>

      {(totalPages > 1 || usesApiPagination) && (
        <nav className="flex flex-wrap items-center justify-center gap-3 pt-2" aria-label="Paginação das licitações">
          <button
            type="button"
            onClick={() => {
              if (usesApiPagination) {
                window.scrollTo({ top: 0, behavior: "smooth" });
                onLoadPreviousPage?.();
                return;
              }
              changePage(Math.max(1, page - 1));
            }}
            disabled={usesApiPagination ? !canLoadPreviousFromApi : page === 1}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
            style={{ backgroundColor: "var(--btn-action-bg)", borderColor: "var(--btn-action-border)", color: "var(--btn-action-text)" }}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            Anterior
          </button>

          <span className="text-xs font-semibold" style={{ color: "var(--text-muted)" }} aria-current="page">
            {usesApiPagination ? `Página ${apiPagination.page || 1}` : `Página ${page} de ${totalPages}`}
          </span>

          <button
            type="button"
            onClick={() => changePage(page + 1)}
            disabled={usesApiPagination ? !canLoadNextFromApi : page === totalPages}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-50"
            style={{ backgroundColor: "var(--btn-action-bg)", borderColor: "var(--btn-action-border)", color: "var(--btn-action-text)" }}
          >
            Próxima
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </nav>
      )}
    </section>
  );
}
