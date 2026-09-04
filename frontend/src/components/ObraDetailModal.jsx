import React, { useEffect, useRef } from "react";
import {
  X,
  ExternalLink,
  MapPin,
  Tag,
  Calendar,
  FileText,
  DollarSign,
} from "lucide-react";
import { DocumentosSection, ExigenciasSection } from "./ObraDocumentAnalysisSections";

export default function ObraDetailModal({ obra, onClose, onAnalysisComplete }) {
  const modalRef = useRef(null);
  const previouslyFocused = useRef(null);

  // Gerenciar foco, Escape e scroll do body enquanto o modal está aberto.
  useEffect(() => {
    if (!obra) return;

    previouslyFocused.current = document.activeElement;
    const firstFocusable = modalRef.current?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    (firstFocusable || modalRef.current)?.focus();
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = "unset";
      previouslyFocused.current?.focus?.();
    };
  }, [obra]);

  if (!obra) return null;

  const handleModalKeyDown = (event) => {
    if (event.key === "Escape") {
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const focusables = Array.from(
      modalRef.current?.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) || [],
    );
    if (!focusables.length) {
      event.preventDefault();
      modalRef.current?.focus();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

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
    : "Valor não informado";

  const idPncp = obra.id_pncp || obra.numero_controle_pncp || "Não informado";
  const obraRequestKey = obra.id_pncp || obra.numero_controle_pncp || `${obra.cnpj}:${obra.ano}:${obra.sequencial}`;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-obra-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto"
    >
      {/* Backdrop com desfoque de fundo */}
      <div
        className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Container do Modal */}
      <div
        ref={modalRef}
        tabIndex={-1}
        onKeyDown={handleModalKeyDown}
        className="theme-card relative w-full max-w-2xl border rounded-2xl p-6 sm:p-7 shadow-2xl z-10 space-y-5 my-8 max-h-[90vh] flex flex-col justify-between animate-in fade-in zoom-in-95 duration-200"
      >
        {/* CABEÇALHO DO MODAL */}
        <div className="space-y-3 shrink-0">
          <div className="flex items-center justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
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
                  {obra.municipio ? `${obra.municipio} – ${obra.uf}` : obra.uf || "Nacional / Brasil"}
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

            {/* Botão Fechar (X) */}
            <button
              type="button"
              onClick={onClose}
              aria-label="Fechar detalhes da obra"
              className="p-2 rounded-xl transition cursor-pointer border hover:text-amber-500 focus-visible:outline-2 focus-visible:outline-amber-400"
              style={{
                backgroundColor: "var(--btn-pncp-bg)",
                borderColor: "var(--btn-pncp-border)",
                color: "var(--text-muted)",
              }}
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>

          <h2
            id="modal-obra-title"
            className="text-base sm:text-lg font-bold tracking-tight uppercase"
            style={{ color: "var(--text-primary)" }}
          >
            {obra.orgao || "Órgão Público não especificado"}
          </h2>
        </div>

        {/* CORPO DO MODAL COM SCROLL */}
        <div className="space-y-4 overflow-y-auto pr-1">
          {/* Grid de Informações Financeiras e Datas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div
              className="p-3.5 rounded-xl border transition-colors"
              style={{
                backgroundColor: "var(--badge-mod-bg)",
                borderColor: "var(--badge-mod-border)",
              }}
            >
              <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-amber-500">
                <DollarSign className="w-3.5 h-3.5" aria-hidden="true" />
                <span>Valor Estimado</span>
              </div>
              <div className="text-lg sm:text-xl font-bold font-mono text-amber-500 mt-1">
                {valorFormatado}
              </div>
            </div>

            <div
              className="p-3.5 rounded-xl border transition-colors"
              style={{
                backgroundColor: "var(--card-bg)",
                borderColor: "var(--border-subtle)",
              }}
            >
              <div
                className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider"
                style={{ color: "var(--text-dim)" }}
              >
                <Calendar className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
                <span>Data de Publicação</span>
              </div>
              <div className="text-sm sm:text-base font-semibold mt-1" style={{ color: "var(--text-primary)" }}>
                {formatDate(obra.data_publicacao)}
              </div>
            </div>
          </div>

          {/* Identificador / Controle PNCP */}
          {idPncp !== "Não informado" && (
            <div
              className="px-3.5 py-2.5 rounded-xl border text-xs flex flex-wrap items-center justify-between gap-2"
              style={{
                backgroundColor: "var(--card-bg)",
                borderColor: "var(--border-subtle)",
              }}
            >
              <span className="font-medium" style={{ color: "var(--text-dim)" }}>
                ID de Controle PNCP:
              </span>
              <span className="font-mono font-bold" style={{ color: "var(--text-secondary)" }}>
                {idPncp}
              </span>
            </div>
          )}

          {/* Objeto Completo na Íntegra */}
          <div className="space-y-1.5">
            <div
              className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider"
              style={{ color: "var(--text-dim)" }}
            >
              <FileText className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
              <span>Objeto da Licitação (Íntegra)</span>
            </div>
            <div
              className="p-4 rounded-xl border text-xs sm:text-sm leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto"
              style={{
                backgroundColor: "var(--bg-main)",
                borderColor: "var(--border-subtle)",
                color: "var(--text-primary)",
              }}
            >
              {obra.objeto || "Descrição do objeto não informada no edital."}
            </div>
          </div>

          <ExigenciasSection
            key={`exigencias:${obraRequestKey}`}
            obra={obra}
            onAnalysisComplete={onAnalysisComplete}
          />
          <DocumentosSection key={`documentos:${obraRequestKey}`} obra={obra} />
        </div>

        {/* FOOTER DO MODAL */}
        <div
          className="pt-4 border-t flex flex-col-reverse sm:flex-row items-center justify-between gap-3 shrink-0"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto px-5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-semibold transition border cursor-pointer hover:border-amber-500"
            style={{
              backgroundColor: "var(--btn-action-bg)",
              borderColor: "var(--btn-action-border)",
              color: "var(--btn-action-text)",
            }}
          >
            Fechar
          </button>

          {obra.link_pncp && (
            <a
              href={obra.link_pncp}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-bold transition bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-lg shadow-amber-500/20 cursor-pointer focus-visible:outline-2 focus-visible:outline-amber-400"
            >
              <span>Abrir no Portal PNCP</span>
              <ExternalLink className="w-4 h-4" aria-hidden="true" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
