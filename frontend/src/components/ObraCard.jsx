import React from "react";
import { MapPin, ExternalLink, Calendar, Tag, ChevronRight } from "lucide-react";

export default function ObraCard({ obra, onSelect }) {
  const cardId = obra.id_pncp || obra.numero_controle_pncp || Math.random().toString(36).substring(2, 9);

  const formatDate = (dateStr) => {
    if (!dateStr) return "Não informada";
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const valorFormatado = obra.valor_estimado
    ? `R$ ${obra.valor_estimado.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : "Não informado";

  const handleCardClick = () => {
    onSelect?.(obra);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect?.(obra);
    }
  };

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      aria-labelledby={`obra-title-${cardId}`}
      aria-haspopup="dialog"
      title="Clique para ver os detalhes completos da obra"
      className="theme-card theme-card-hover border rounded-2xl p-5 flex flex-col justify-between transition-all duration-200 group cursor-pointer focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 select-none"
    >
      <div className="space-y-3">
        {/* Badge de Localização + Modalidade */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span
            className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-lg border transition-colors"
            style={{
              backgroundColor: "var(--badge-loc-bg)",
              borderColor: "var(--badge-loc-border)",
              color: "var(--badge-loc-text)",
            }}
          >
            <MapPin className="w-3.5 h-3.5 opacity-70 shrink-0" aria-hidden="true" />
            <span>
              {obra.municipio
                ? `${obra.municipio} – ${obra.uf}`
                : obra.uf || "Nacional / Brasil"}
            </span>
          </span>

          {obra.modalidade && (
            <span
              className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-md border transition-colors"
              style={{
                backgroundColor: "var(--badge-mod-bg)",
                borderColor: "var(--badge-mod-border)",
                color: "var(--badge-mod-text)",
              }}
            >
              <Tag className="w-3 h-3 opacity-80 shrink-0" aria-hidden="true" />
              <span>{obra.modalidade.replace(/\s*\(\d+\)$/, "")}</span>
            </span>
          )}
        </div>

        {/* Órgão / Título do Card */}
        <h3
          id={`obra-title-${cardId}`}
          className="text-sm sm:text-base font-bold tracking-wide uppercase line-clamp-2 transition-colors group-hover:text-amber-500"
          style={{ color: "var(--text-primary)" }}
        >
          {obra.orgao || "Órgão Público não especificado"}
        </h3>

        {/* Data de Publicação */}
        <div className="flex items-center gap-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
          <Calendar className="w-3.5 h-3.5 opacity-70 shrink-0" aria-hidden="true" />
          <span>
            Publicado em:{" "}
            <strong className="font-semibold" style={{ color: "var(--text-secondary)" }}>
              {formatDate(obra.data_publicacao)}
            </strong>
          </span>
        </div>

        {/* Objeto */}
        <p className="text-xs line-clamp-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          {obra.objeto}
        </p>
      </div>

      {/* FOOTER DO CARD */}
      <div
        className="mt-5 pt-4 border-t flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <div>
          <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
            Valor Estimado
          </span>
          <span
            className="font-bold text-base sm:text-lg font-mono flex items-center gap-0.5 mt-0.5 tracking-tight text-amber-500"
            aria-label={`Valor estimado: ${valorFormatado}`}
          >
            {valorFormatado}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {obra.link_pncp && (
            <a
              href={obra.link_pncp}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              aria-label={`Ver detalhes da licitação de ${obra.orgao || 'órgão'} no portal PNCP (abre em nova aba)`}
              className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 min-h-10 rounded-xl font-bold transition duration-150 border focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 cursor-pointer shadow-sm text-xs hover:border-amber-500"
              style={{
                backgroundColor: "var(--btn-pncp-bg)",
                borderColor: "var(--btn-pncp-border)",
                color: "var(--btn-pncp-text)",
              }}
            >
              <span>Ver no PNCP</span>
              <ExternalLink className="w-3.5 h-3.5 opacity-70 group-hover:opacity-100" aria-hidden="true" />
              <span className="sr-only"> (abre em nova aba)</span>
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
