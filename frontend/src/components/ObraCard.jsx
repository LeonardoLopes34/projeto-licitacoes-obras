import React, { useEffect, useState } from "react";
import { MapPin, ExternalLink, Calendar } from "lucide-react";
import { buscarTipoContratacao } from "../api";

export default function ObraCard({ obra, analiseExigencias, onSelect, itemKey = "obra-sem-id" }) {
  const cardId = obra.id_pncp || obra.numero_controle_pncp || itemKey;
  const [tipoEnriquecido, setTipoEnriquecido] = useState(null);

  useEffect(() => {
    const { cnpj, ano, sequencial } = obra;
    if (!cnpj || !ano || !sequencial || obra.criterio_julgamento) {
      setTipoEnriquecido(null);
      return undefined;
    }

    const controller = new AbortController();
    buscarTipoContratacao({
      cnpj,
      ano,
      sequencial,
      modalidade: obra.modalidade,
      tipoInstrumento: obra.tipo_instrumento,
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted && data?.tipo_contratacao) {
          setTipoEnriquecido(data);
        }
      })
      .catch(() => {
        // O card mantém o texto já publicado na listagem quando o PNCP
        // estiver indisponível para a consulta complementar.
      });

    return () => controller.abort();
  }, [obra.ano, obra.cnpj, obra.criterio_julgamento, obra.modalidade, obra.sequencial, obra.tipo_instrumento]);

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

  const valorNumerico = Number(obra.valor_estimado);
  const valorFormatado = Number.isFinite(valorNumerico)
    ? `R$ ${valorNumerico.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : "Não informado";
  const tipoContratacao = String(
    tipoEnriquecido?.tipo_contratacao || obra.tipo_contratacao || obra.modalidade || "",
  ).trim() || "Tipo não informado";

  return (
    <article
      aria-labelledby={`obra-title-${cardId}`}
      className="theme-card theme-card-hover border rounded-2xl p-5 flex flex-col justify-between transition-all duration-200 group"
    >
      <div className="space-y-3">
        {/* Localização e tipo: o tipo substitui o antigo selo amarelo. */}
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

          <div className="min-w-0 max-w-full text-right">
            <span
              className="block text-[10px] font-bold uppercase tracking-wider"
              style={{ color: "var(--text-dim)" }}
            >
              Tipo
            </span>
            <p
              className="max-w-[18rem] whitespace-normal break-words text-xs font-semibold leading-snug"
              style={{ color: "var(--text-secondary)" }}
              title={tipoContratacao}
              aria-label={`Tipo: ${tipoContratacao}`}
            >
              {tipoContratacao}
            </p>
          </div>
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
          {obra.objeto || "Objeto não informado"}
        </p>

        <div
          className="rounded-xl border px-3 py-2 text-xs leading-relaxed"
          style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
          aria-label="Resumo de exigências identificadas no edital"
        >
          <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
            Exigências do edital
          </span>
          {!analiseExigencias && <span>Ainda não analisado — a análise começa ao abrir os detalhes.</span>}
          {analiseExigencias?.status === "sucesso" && (
            <span>
              {analiseExigencias.total_exigencias} {analiseExigencias.total_exigencias === 1 ? "item identificado" : "itens identificados"}
              {Object.keys(analiseExigencias.categorias || {}).length > 0
                ? ` · ${Object.keys(analiseExigencias.categorias).length} categorias`
                : ""}
            </span>
          )}
          {analiseExigencias?.status === "sucesso_parcial" && <span>Análise parcial — confira as fontes no detalhe.</span>}
          {analiseExigencias?.status === "sem_documento_analisavel" && <span>Não há documento analisável disponível.</span>}
          {analiseExigencias?.status === "erro" && <span>Não foi possível analisar os anexos.</span>}
          {!analiseExigencias?.analise_assistida && analiseExigencias?.analise_assistida_status === "indisponivel" && (
            <span className="block mt-1">Análise assistida indisponível — o resultado local permanece disponível.</span>
          )}
          {analiseExigencias?.analise_assistida && (
            <div className="mt-2 space-y-1">
              <span className="block font-semibold" style={{ color: "var(--text-secondary)" }}>
                Análise assistida · confira as fontes no detalhe
              </span>
              {Array.isArray(analiseExigencias.documentos_exigidos) && analiseExigencias.documentos_exigidos.length > 0 && (
                <ul className="list-disc space-y-0.5 pl-4" aria-label="Documentos exigidos identificados">
                  {analiseExigencias.documentos_exigidos.slice(0, 3).map((documento, index) => (
                    <li key={`${documento.nome}-${index}`}>
                      {documento.nome}{documento.estado === "incerto" ? " (revisar)" : ""}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
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
          <button
            type="button"
            onClick={() => onSelect?.(obra)}
            aria-label={`Ver detalhes de ${obra.orgao || "órgão público"}`}
            className="inline-flex items-center justify-center px-3.5 py-2 min-h-10 rounded-xl font-bold transition duration-150 border focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 cursor-pointer shadow-sm text-xs hover:border-amber-500"
            style={{
              backgroundColor: "var(--btn-action-bg)",
              borderColor: "var(--btn-action-border)",
              color: "var(--btn-action-text)",
            }}
          >
            Ver detalhes
          </button>
          {obra.link_pncp && (
            <a
              href={obra.link_pncp}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Ver detalhes da licitação de ${obra.orgao || "órgão"} no portal PNCP (abre em nova aba)`}
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
