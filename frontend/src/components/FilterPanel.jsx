import React, { useRef } from "react";
import { Search, X, SlidersHorizontal, RotateCcw } from "lucide-react";

export const ESTADOS_BRASIL = [
  { sigla: "TODOS", nome: "Todos os Estados (UF)" },
  { sigla: "AC", nome: "Acre (AC)" },
  { sigla: "AL", nome: "Alagoas (AL)" },
  { sigla: "AP", nome: "Amapá (AP)" },
  { sigla: "AM", nome: "Amazonas (AM)" },
  { sigla: "BA", nome: "Bahia (BA)" },
  { sigla: "CE", nome: "Ceará (CE)" },
  { sigla: "DF", nome: "Distrito Federal (DF)" },
  { sigla: "ES", nome: "Espírito Santo (ES)" },
  { sigla: "GO", nome: "Goiás (GO)" },
  { sigla: "MA", nome: "Maranhão (MA)" },
  { sigla: "MT", nome: "Mato Grosso (MT)" },
  { sigla: "MS", nome: "Mato Grosso do Sul (MS)" },
  { sigla: "MG", nome: "Minas Gerais (MG)" },
  { sigla: "PA", nome: "Pará (PA)" },
  { sigla: "PB", nome: "Paraíba (PB)" },
  { sigla: "PR", nome: "Paraná (PR)" },
  { sigla: "PE", nome: "Pernambuco (PE)" },
  { sigla: "PI", nome: "Piauí (PI)" },
  { sigla: "RJ", nome: "Rio de Janeiro (RJ)" },
  { sigla: "RN", nome: "Rio Grande do Norte (RN)" },
  { sigla: "RS", nome: "Rio Grande do Sul (RS)" },
  { sigla: "RO", nome: "Rondônia (RO)" },
  { sigla: "RR", nome: "Roraima (RR)" },
  { sigla: "SC", nome: "Santa Catarina (SC)" },
  { sigla: "SP", nome: "São Paulo (SP)" },
  { sigla: "SE", nome: "Sergipe (SE)" },
  { sigla: "TO", nome: "Tocantins (TO)" },
];

export default function FilterPanel({
  inicialDate,
  setInicialDate,
  finalDate,
  setFinalDate,
  ufFilter = "TODOS",
  setUfFilter,
  modalidade,
  setModalidade,
  sortBy = "data_desc",
  setSortBy,
  maxPaginas,
  setMaxPaginas,
  forceMock,
  setForceMock,
  searchTerm,
  setSearchTerm,
  onResetFilters,
  activeFiltersCount = 0,
}) {
  const searchInputRef = useRef(null);

  return (
    <section
      role="search"
      aria-labelledby="filter-panel-heading"
      className="theme-card border rounded-2xl p-5 transition-colors space-y-4"
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-b pb-3"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2.5">
          <SlidersHorizontal className="w-4 h-4 text-amber-500" aria-hidden="true" />
          <h2
            id="filter-panel-heading"
            className="text-xs sm:text-sm font-bold tracking-wider uppercase"
            style={{ color: "var(--text-secondary)" }}
          >
            Filtros de Licitações e Busca
          </h2>
          {activeFiltersCount > 0 && (
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border"
              style={{
                backgroundColor: "var(--badge-mod-bg)",
                borderColor: "var(--badge-mod-border)",
                color: "var(--badge-mod-text)",
              }}
            >
              {activeFiltersCount} {activeFiltersCount === 1 ? "filtro ativo" : "filtros ativos"}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {setMaxPaginas && (
            <div className="hidden sm:flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
              <label htmlFor="filtro-max-paginas" className="font-medium" style={{ color: "var(--text-muted)" }}>
                Páginas:
              </label>
              <select
                id="filtro-max-paginas"
                value={maxPaginas}
                onChange={(e) => setMaxPaginas(Number(e.target.value))}
                className="theme-input border rounded-lg px-2 py-1 text-xs focus-visible:outline-2 focus-visible:outline-amber-400 transition cursor-pointer"
              >
                <option value={1}>1 pág (50)</option>
                <option value={3}>3 págs (150)</option>
                <option value={5}>5 págs (250)</option>
              </select>
            </div>
          )}

          {setForceMock && (
            <label
              htmlFor="filtro-force-mock"
              className="hidden lg:flex items-center gap-1.5 cursor-pointer text-xs transition-colors"
              style={{ color: "var(--text-muted)" }}
            >
              <input
                id="filtro-force-mock"
                type="checkbox"
                checked={forceMock}
                onChange={(e) => setForceMock(e.target.checked)}
                className="w-3.5 h-3.5 rounded accent-amber-500 cursor-pointer"
              />
              <span>Mock Dev</span>
            </label>
          )}

          {onResetFilters && activeFiltersCount > 0 && (
            <button
              type="button"
              onClick={onResetFilters}
              className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition cursor-pointer hover:text-amber-500"
              style={{ color: "var(--text-muted)" }}
            >
              <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Restaurar Padrão</span>
            </button>
          )}
        </div>
      </div>

      {/* SEÇÃO 1: FILTROS PRINCIPAIS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
        <div>
          <label
            htmlFor="filtro-data-inicial"
            className="block text-[11px] font-bold uppercase tracking-wider mb-2"
            style={{ color: "var(--text-dim)" }}
          >
            Data Inicial
          </label>
          <input
            id="filtro-data-inicial"
            type="date"
            value={inicialDate}
            onChange={(e) => setInicialDate(e.target.value)}
            className="theme-input w-full border rounded-xl px-3.5 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition"
          />
        </div>

        <div>
          <label
            htmlFor="filtro-data-final"
            className="block text-[11px] font-bold uppercase tracking-wider mb-2"
            style={{ color: "var(--text-dim)" }}
          >
            Data Final
          </label>
          <input
            id="filtro-data-final"
            type="date"
            value={finalDate}
            onChange={(e) => setFinalDate(e.target.value)}
            className="theme-input w-full border rounded-xl px-3.5 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition"
          />
        </div>

        <div>
          <label
            htmlFor="filtro-uf"
            className="block text-[11px] font-bold uppercase tracking-wider mb-2"
            style={{ color: "var(--text-dim)" }}
          >
            Estado (UF)
          </label>
          <select
            id="filtro-uf"
            value={ufFilter}
            onChange={(e) => setUfFilter?.(e.target.value)}
            className="theme-input w-full border rounded-xl px-3.5 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition cursor-pointer"
          >
            {ESTADOS_BRASIL.map((uf) => (
              <option key={uf.sigla} value={uf.sigla}>
                {uf.nome}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filtro-modalidade"
            className="block text-[11px] font-bold uppercase tracking-wider mb-2"
            style={{ color: "var(--text-dim)" }}
          >
            Modalidade
          </label>
          <select
            id="filtro-modalidade"
            value={modalidade}
            onChange={(e) => setModalidade(Number(e.target.value))}
            className="theme-input w-full border rounded-xl px-3.5 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition cursor-pointer"
          >
            <option value={0}>Todas (Concorrência + Pregão)</option>
            <option value={4}>Concorrência Eletrônica (4)</option>
            <option value={6}>Pregão Eletrônico (6)</option>
          </select>
        </div>

        <div>
          <label
            htmlFor="filtro-ordenar-por"
            className="block text-[11px] font-bold uppercase tracking-wider mb-2"
            style={{ color: "var(--text-dim)" }}
          >
            Ordenar Por
          </label>
          <select
            id="filtro-ordenar-por"
            value={sortBy}
            onChange={(e) => setSortBy?.(e.target.value)}
            className="theme-input w-full border rounded-xl px-3.5 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition cursor-pointer"
          >
            <option value="data_desc">Data de Publicação</option>
            <option value="valor_desc">Maior Valor Estimado</option>
            <option value="valor_asc">Menor Valor Estimado</option>
            <option value="orgao">Órgão / Município A-Z</option>
          </select>
        </div>
      </div>

      {/* SEÇÃO 2: CAIXA DE PESQUISA EM TEMPO REAL */}
      <div className="pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
        <label htmlFor="filtro-busca-texto" className="sr-only">
          Filtrar resultados por cidade, UF, órgão, objeto ou modalidade
        </label>
        <div className="relative flex items-center">
          <Search
            className="w-4 h-4 opacity-50 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
            aria-hidden="true"
          />
          <input
            ref={searchInputRef}
            id="filtro-busca-texto"
            type="text"
            placeholder="Filtrar por cidade, UF, órgão, objeto ou modalidade... (Pressione '/' ou 'Ctrl+K' para buscar)"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="theme-input w-full border rounded-xl pl-10 pr-24 py-2.5 min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 transition"
          />

          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
            {searchTerm ? (
              <button
                type="button"
                onClick={() => {
                  setSearchTerm("");
                  searchInputRef.current?.focus();
                }}
                aria-label="Limpar termo de pesquisa"
                title="Limpar pesquisa"
                className="opacity-70 hover:opacity-100 p-1.5 rounded-lg transition focus-visible:outline-2 focus-visible:outline-amber-400 cursor-pointer"
              >
                <X className="w-4 h-4" aria-hidden="true" />
              </button>
            ) : (
              <kbd
                className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono select-none border"
                style={{
                  backgroundColor: "var(--kbd-bg)",
                  borderColor: "var(--kbd-border)",
                  color: "var(--kbd-text)",
                }}
              >
                Ctrl K
              </kbd>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
