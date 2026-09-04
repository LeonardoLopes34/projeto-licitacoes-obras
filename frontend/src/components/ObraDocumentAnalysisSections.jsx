import React, { useEffect, useMemo, useState } from "react";
import { AlertCircle, ExternalLink, FileText, LoaderCircle, RefreshCw } from "lucide-react";
import { buscarDocumentos, buscarExigencias } from "../api";

const CATEGORY_LABELS = {
  habilitacao_juridica: "Habilitação jurídica",
  qualificacao_tecnica: "Qualificação técnica",
  regularidade_fiscal_social_trabalhista: "Regularidade fiscal, social e trabalhista",
  qualificacao_economico_financeira: "Qualificação econômico-financeira",
  declaracoes: "Declarações",
  documento_referenciado: "Documento referenciado",
  nao_classificado: "Revisão necessária",
};

const getObraKey = (obra) => obra.id_pncp || obra.numero_controle_pncp || `${obra.cnpj}:${obra.ano}:${obra.sequencial}`;

const isMockObra = (obra) => {
  const fonte = String(obra.fonte || "").toUpperCase();
  return fonte.includes("MOCK") || String(obra.id_pncp || "").toUpperCase().includes("MOCK");
};

const hasIdentifiers = (obra) => Boolean(obra.cnpj && obra.ano && obra.sequencial);

const formatDate = (dateStr) => {
  if (!dateStr) return "Não informada";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
};

const formatDateTime = (dateStr) => {
  if (!dateStr) return "data não informada";
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return dateStr;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const nonEmptyText = (value) => (typeof value === "string" ? value.trim() : "");

// New responses provide a human-readable summary. Older responses may not have
// it, so retain the classification label as a safe display fallback while
// keeping the source transcription exclusively in the evidence disclosure.
const getExigenciaSummary = (item) => (
  nonEmptyText(item.descricao_resumida)
  || nonEmptyText(item.rotulo)
  || "Exigência identificada no documento."
);

const getOriginalEvidence = (item) => (
  nonEmptyText(item.evidencia)
  || nonEmptyText(item.descricao_original)
  || "Trecho original não informado."
);

const extractSource = (data) => {
  const metadata = data?.metadados && typeof data.metadados === "object" ? data.metadados : data;
  return {
    origem: String(metadata?.origem || data?.origem || "").toLowerCase(),
    desatualizado: Boolean(metadata?.desatualizado ?? data?.desatualizado),
    atualizadoEm: metadata?.atualizado_em || data?.atualizado_em || null,
  };
};

function StoredResultNotice({ source }) {
  const isStoredResult = source?.origem === "cache_persistente" || source?.desatualizado;
  if (!isStoredResult) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="rounded-xl border p-3 text-xs leading-relaxed"
      style={{ backgroundColor: "var(--badge-mod-bg)", borderColor: "var(--badge-mod-border)", color: "var(--text-secondary)" }}
    >
      <div className="flex items-start gap-2">
        <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" aria-hidden="true" />
        <div className="space-y-1">
          <p className="font-semibold">Exibindo um resultado salvo anteriormente.</p>
          <p>
            O PNCP não respondeu na última tentativa. Atualizado em:{" "}
            <time dateTime={source.atualizadoEm || undefined}>{formatDateTime(source.atualizadoEm)}</time>.
          </p>
        </div>
      </div>
    </div>
  );
}

function SectionNotice({ children }) {
  return (
    <div
      className="rounded-xl border p-3 text-xs leading-relaxed"
      style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
    >
      {children}
    </div>
  );
}

function RetryButton({ children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold transition hover:border-amber-500"
      style={{ backgroundColor: "var(--btn-action-bg)", borderColor: "var(--btn-action-border)", color: "var(--btn-action-text)" }}
    >
      <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
      <span>{children}</span>
    </button>
  );
}

function DocumentFailureDetails({ documentos = [] }) {
  const failures = documentos.filter((documento) => documento.status === "erro" && documento.mensagem);
  if (!failures.length) return null;

  return (
    <ul className="space-y-1 border-t pt-2 text-[11px]" style={{ borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}>
      {failures.map((documento) => (
        <li key={documento.documento_id}>
          <span className="font-semibold" style={{ color: "var(--text-secondary)" }}>{documento.titulo}:</span>{" "}
          {documento.mensagem}
        </li>
      ))}
    </ul>
  );
}

export function ExigenciasSection({ obra, onAnalysisComplete }) {
  const [retryToken, setRetryToken] = useState(0);

  return (
    <div className="space-y-2" aria-live="polite">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        <FileText className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
        <span>Exigências identificadas no edital</span>
      </div>

      {isMockObra(obra) ? (
        <SectionNotice>A análise de documentos reais não está disponível no modo de demonstração.</SectionNotice>
      ) : !hasIdentifiers(obra) ? (
        <SectionNotice>Não há identificadores suficientes para analisar os documentos deste registro.</SectionNotice>
      ) : (
        <ExigenciasRequest
          key={`${getObraKey(obra)}:${retryToken}`}
          obra={obra}
          force={retryToken > 0}
          onAnalysisComplete={onAnalysisComplete}
          onRetry={() => setRetryToken((current) => current + 1)}
        />
      )}
    </div>
  );
}

function ExigenciasRequest({ obra, force, onAnalysisComplete, onRetry }) {
  const [result, setResult] = useState(() => ({ status: "loading", data: null, error: "", source: null }));

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    buscarExigencias({
      cnpj: obra.cnpj,
      ano: obra.ano,
      sequencial: obra.sequencial,
      signal: controller.signal,
      forcar: force,
    })
      .then((data) => {
        if (!active) return;
        const status = data?.status === "sucesso_parcial"
          ? "partial"
          : data?.status === "sucesso"
            ? "success"
            : data?.status === "sem_documento_analisavel"
              ? "empty"
              : "error";
        setResult({ status, data, error: "", source: extractSource(data) });
        onAnalysisComplete?.(data);
      })
      .catch((error) => {
        if (!active || error.name === "AbortError") return;
        setResult({
          status: "error",
          data: null,
          error: error.message || "Não foi possível analisar os documentos agora.",
          source: null,
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [force, obra, onAnalysisComplete]);

  const exigenciasPorCategoria = useMemo(() => (result.data?.exigencias || []).reduce((groups, item) => {
    const category = item.categoria || "nao_classificado";
    groups[category] = [...(groups[category] || []), item];
    return groups;
  }, {}), [result.data]);

  if (result.status === "loading") {
    return (
      <div className="flex items-center gap-2 rounded-xl border p-3 text-xs" style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}>
        <LoaderCircle className="w-4 h-4 animate-spin" aria-hidden="true" />
        <span>Analisando documentos de habilitação. Os detalhes da obra continuam disponíveis.</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <StoredResultNotice source={result.source} />

      {result.status === "empty" && (
        <SectionNotice>{result.data?.mensagem || "Não há documento analisável disponível para esta contratação."}</SectionNotice>
      )}

      {result.status === "error" && (
        <SectionNotice>
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" aria-hidden="true" />
              <span>{result.data?.mensagem || result.error || "Não foi possível analisar os documentos agora."}</span>
            </div>
            <DocumentFailureDetails documentos={result.data?.documentos_analisados} />
            <RetryButton onClick={onRetry}>Tentar novamente</RetryButton>
          </div>
        </SectionNotice>
      )}

      {(result.status === "success" || result.status === "partial") && (
        <>
          <div className="rounded-xl border p-3 text-xs leading-relaxed" style={{ backgroundColor: "var(--badge-mod-bg)", borderColor: "var(--badge-mod-border)", color: "var(--text-secondary)" }}>
            {result.data?.mensagem}
            <span className="block mt-1" style={{ color: "var(--text-muted)" }}>
              A análise identifica trechos do edital e não confirma habilitação, regularidade ou suficiência jurídica da empresa.
            </span>
          </div>
          <DocumentFailureDetails documentos={result.data?.documentos_analisados} />
          {Object.entries(exigenciasPorCategoria).map(([category, items]) => (
            <section key={category} className="space-y-2" aria-label={CATEGORY_LABELS[category] || "Exigências"}>
              <h3 className="text-xs font-bold" style={{ color: "var(--text-primary)" }}>
                {CATEGORY_LABELS[category] || "Exigências para revisão"}
              </h3>
              {items.map((item, index) => (
                <article key={`${item.documento_id}-${item.pagina}-${index}`} className="rounded-xl border p-3 space-y-2" style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)" }}>
                  <p className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{item.rotulo}</p>
                  <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>{getExigenciaSummary(item)}</p>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]" style={{ color: "var(--text-dim)" }}>
                    <span>{item.titulo_documento}, página {item.pagina}</span>
                    <span>· confiança da extração: {Math.round((item.confianca || 0) * 100)}%</span>
                    {item.status === "referenciado_em_outro_documento" && <span>· referência a outro documento</span>}
                  </div>
                  <details className="text-xs" style={{ color: "var(--text-muted)" }}>
                    <summary className="cursor-pointer font-semibold">Ver trecho original</summary>
                    <p className="mt-2 rounded-lg p-2 leading-relaxed" style={{ backgroundColor: "var(--bg-main)" }}>{getOriginalEvidence(item)}</p>
                  </details>
                  {item.url_documento && (
                    <a href={item.url_documento} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs font-semibold hover:text-amber-500" style={{ color: "var(--btn-pncp-text)" }}>
                      <span>Abrir fonte original</span>
                      <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                    </a>
                  )}
                </article>
              ))}
            </section>
          ))}
          <RetryButton onClick={onRetry}>Reprocessar análise</RetryButton>
        </>
      )}
    </div>
  );
}

export function DocumentosSection({ obra }) {
  const [retryToken, setRetryToken] = useState(0);

  return (
    <div className="space-y-1.5" aria-live="polite">
      <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
        <FileText className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
        <span>Documentos publicados no PNCP</span>
      </div>

      {isMockObra(obra) ? (
        <SectionNotice>Documentos reais não estão disponíveis no modo de demonstração.</SectionNotice>
      ) : !hasIdentifiers(obra) ? (
        <SectionNotice>Documentos indisponíveis para este registro.</SectionNotice>
      ) : (
        <DocumentosRequest
          key={`${getObraKey(obra)}:${retryToken}`}
          obra={obra}
          onRetry={() => setRetryToken((current) => current + 1)}
        />
      )}
    </div>
  );
}

function DocumentosRequest({ obra, onRetry }) {
  const [result, setResult] = useState(() => ({ status: "loading", documentos: [], error: "", source: null }));

  useEffect(() => {
    const controller = new AbortController();
    let active = true;

    buscarDocumentos({
      cnpj: obra.cnpj,
      ano: obra.ano,
      sequencial: obra.sequencial,
      signal: controller.signal,
    })
      .then((data) => {
        if (!active) return;
        const documentos = Array.isArray(data?.documentos) ? data.documentos : [];
        setResult({
          status: documentos.length > 0 ? "success" : "empty",
          documentos,
          error: "",
          source: extractSource(data),
        });
      })
      .catch((error) => {
        if (!active || error.name === "AbortError") return;
        setResult({
          status: "error",
          documentos: [],
          error: error.message || "Não foi possível carregar os documentos agora.",
          source: null,
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [obra]);

  if (result.status === "loading") {
    return (
      <div className="flex items-center gap-2 rounded-xl border p-3 text-xs" style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}>
        <LoaderCircle className="w-4 h-4 animate-spin" aria-hidden="true" />
        <span>Carregando documentos...</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <StoredResultNotice source={result.source} />

      {result.status === "empty" && <SectionNotice>Nenhum documento foi disponibilizado para esta contratação no PNCP.</SectionNotice>}

      {result.status === "error" && (
        <SectionNotice>
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" aria-hidden="true" />
              <span>{result.error || "Não foi possível carregar os documentos agora."}</span>
            </div>
            <RetryButton onClick={onRetry}>Tentar novamente</RetryButton>
          </div>
        </SectionNotice>
      )}

      {result.status === "success" && result.documentos.map((documento, index) => {
        const titulo = documento.titulo || documento.tipo_documento_nome || `Documento ${documento.sequencial_documento}`;
        return (
          <div
            key={documento.sequencial_documento || documento.url || `${titulo}-${index}`}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border p-3"
            style={{ backgroundColor: "var(--card-bg)", borderColor: "var(--border-subtle)" }}
          >
            <div className="min-w-0 space-y-1">
              <p className="text-xs sm:text-sm font-semibold break-words" style={{ color: "var(--text-primary)" }}>{titulo}</p>
              <p className="text-[11px] leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {documento.tipo_documento_nome ? `Tipo: ${documento.tipo_documento_nome}` : "Tipo não informado"}
                {" · "}
                Publicado em: {formatDate(documento.data_publicacao_pncp)}
              </p>
            </div>
            {documento.url ? (
              <a href={documento.url} target="_blank" rel="noopener noreferrer" className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-semibold transition hover:border-amber-500" style={{ backgroundColor: "var(--btn-pncp-bg)", borderColor: "var(--btn-pncp-border)", color: "var(--btn-pncp-text)" }}>
                <span>Abrir documento</span>
                <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
              </a>
            ) : (
              <span className="shrink-0 text-[11px]" style={{ color: "var(--text-dim)" }}>Link indisponível</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
