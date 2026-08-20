import React from "react";
import { Coins, HardHat, BarChart2, ChevronDown, ChevronUp } from "lucide-react";

export default function StatusBar({
  statusInfo,
  filteredTotal,
  volumeTotal,
  showDashboard = false,
  onToggleDashboard,
}) {
  if (!statusInfo && typeof volumeTotal !== "number") return null;

  const totalObras = statusInfo?.total || filteredTotal || 0;
  const hasFilter = filteredTotal !== undefined && filteredTotal !== totalObras;

  // Formata o volume total para moeda brasileira R$ 000.000.000,00
  const formattedVolume =
    typeof volumeTotal === "number"
      ? `R$ ${volumeTotal.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
      : "R$ 0,00";

  return (
    <div
      role="region"
      aria-label="Resumo de Volume Total e Obras Encontradas"
      className="theme-card border rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4 transition-colors"
    >
      {/* Métrica 1: Volume Total Estimado */}
      <div className="flex items-center gap-3.5">
        <div
          className="p-3 rounded-xl flex items-center justify-center shrink-0 border transition-colors"
          style={{
            backgroundColor: "var(--badge-mod-bg)",
            borderColor: "var(--badge-mod-border)",
            color: "var(--accent-amber)",
          }}
          aria-hidden="true"
        >
          <Coins className="w-5 h-5 text-amber-500" />
        </div>
        <div>
          <span
            className="block text-[11px] font-bold uppercase tracking-wider"
            style={{ color: "var(--text-dim)" }}
          >
            Volume Total Estimado
          </span>
          <span
            className="text-lg sm:text-2xl font-bold font-mono tracking-tight text-amber-500"
            aria-label={`Volume total estimado: ${formattedVolume}`}
          >
            {formattedVolume}
          </span>
        </div>
      </div>

      {/* Métrica 2: Total de Obras & Botão de Estatísticas perfeitamente alinhados */}
      <div
        className="flex flex-wrap items-center gap-3 justify-between md:justify-end border-t md:border-t-0 pt-3 md:pt-0"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        {/* Badge Total de Obras */}
        <div
          className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl font-mono text-xs sm:text-sm font-bold border shadow-sm transition-colors min-h-11"
          style={{
            backgroundColor: "var(--status-badge-bg)",
            borderColor: "var(--status-badge-border)",
            color: "var(--status-badge-text)",
          }}
        >
          <HardHat className="w-4 h-4 opacity-80 shrink-0" aria-hidden="true" />
          <span>
            {hasFilter ? `${filteredTotal} de ${totalObras} obras` : `${totalObras} obras encontradas`}
          </span>
        </div>

        {/* Botão para Expandir / Ocultar Dashboard de Estatísticas */}
        {onToggleDashboard && (
          <button
            type="button"
            onClick={onToggleDashboard}
            aria-expanded={showDashboard}
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold border transition cursor-pointer shadow-sm focus-visible:outline-2 focus-visible:outline-amber-400 hover:border-amber-500 min-h-11"
            style={{
              backgroundColor: showDashboard ? "var(--badge-mod-bg)" : "var(--btn-pncp-bg)",
              borderColor: showDashboard ? "var(--accent-amber)" : "var(--btn-pncp-border)",
              color: showDashboard ? "var(--accent-amber)" : "var(--btn-pncp-text)",
            }}
          >
            <BarChart2 className="w-4 h-4 text-amber-500 shrink-0" aria-hidden="true" />
            <span>{showDashboard ? "Ocultar Estatísticas" : "Ver Estatísticas"}</span>
            {showDashboard ? (
              <ChevronUp className="w-3.5 h-3.5 opacity-80 shrink-0" aria-hidden="true" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5 opacity-80 shrink-0" aria-hidden="true" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}
