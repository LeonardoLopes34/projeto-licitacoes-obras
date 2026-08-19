import React from "react";
import { CheckCircle2, AlertTriangle, Info, Box } from "lucide-react";

export default function StatusBar({ statusInfo, filteredTotal, volumeTotal }) {
  if (!statusInfo) return null;

  const isSuccess = statusInfo.status?.includes("sucesso_real");
  const isMock = statusInfo.status?.includes("mock");
  const hasFilter = filteredTotal !== undefined && filteredTotal !== statusInfo.total;

  // Formata o volume total para moeda brasileira R$ 000.000.000,00
  const formattedVolume =
    typeof volumeTotal === "number"
      ? `R$ ${volumeTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : null;

  // Formata mensagem destacando números em âmbar como no layout
  const renderHighlightedMessage = (msg) => {
    if (!msg) return null;
    const regex = /(\d+\s+itens\s+brutos|\d+\s+página\(s\)|\d+\s+itens|\d+\s+páginas?)/gi;
    const parts = msg.split(regex);
    return parts.map((part, index) => {
      if (regex.test(part)) {
        return (
          <span key={index} className="text-amber-500 font-bold">
            {part}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="border rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 text-xs sm:text-sm transition-colors"
      style={{
        backgroundColor: isSuccess
          ? "var(--status-success-bg)"
          : isMock
          ? "var(--status-mock-bg)"
          : "var(--status-mock-bg)",
        borderColor: isSuccess
          ? "var(--status-success-border)"
          : isMock
          ? "var(--status-mock-border)"
          : "var(--status-mock-border)",
        color: isSuccess
          ? "var(--status-success-text)"
          : isMock
          ? "var(--status-mock-text)"
          : "var(--status-mock-text)",
      }}
    >
      {/* LADO ESQUERDO: Ícone + Mensagem + Status */}
      <div className="flex items-center gap-3">
        {isSuccess ? (
          <CheckCircle2 className="w-6 h-6 text-emerald-500 shrink-0" aria-hidden="true" />
        ) : isMock ? (
          <AlertTriangle className="w-6 h-6 text-amber-500 shrink-0" aria-hidden="true" />
        ) : (
          <Info className="w-6 h-6 text-rose-500 shrink-0" aria-hidden="true" />
        )}
        <div>
          <div className="text-xs sm:text-sm font-medium">
            {renderHighlightedMessage(statusInfo.mensagem)}
          </div>
          <div className="text-[11px] mt-0.5 font-mono opacity-80">
            Status:{" "}
            <span
              className={`font-semibold ${
                isSuccess
                  ? "text-emerald-500"
                  : isMock
                  ? "text-amber-500"
                  : "text-rose-500"
              }`}
            >
              {statusInfo.status}
            </span>
          </div>
        </div>
      </div>

      {/* LADO DIREITO: Volume Total + Contador de Obras */}
      <div className="flex items-center gap-4 self-end md:self-center">
        {formattedVolume && (
          <div className="text-right">
            <span className="block text-[10px] font-bold uppercase tracking-wider opacity-75">
              Volume Total
            </span>
            <span className="text-sm sm:text-base font-bold text-amber-500 font-mono tracking-tight">
              {formattedVolume}
            </span>
          </div>
        )}

        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-mono text-xs font-bold shadow-sm border transition-colors"
          style={{
            backgroundColor: "var(--status-badge-bg)",
            borderColor: "var(--status-badge-border)",
            color: "var(--status-badge-text)",
          }}
        >
          <Box className="w-3.5 h-3.5 opacity-80 shrink-0" aria-hidden="true" />
          <span>
            Obras: {hasFilter ? `${filteredTotal} de ${statusInfo.total}` : statusInfo.total}
          </span>
        </div>
      </div>
    </div>
  );
}
