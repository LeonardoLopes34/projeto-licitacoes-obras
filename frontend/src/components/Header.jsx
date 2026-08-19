import React from "react";
import { Building2, RefreshCw, Sun, Moon } from "lucide-react";

export default function Header({ onRefresh, loading, theme = "dark", onToggleTheme }) {
  const isDark = theme === "dark";

  return (
    <header
      role="banner"
      aria-label="Cabeçalho do Portal"
      className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-6 transition-colors"
      style={{ borderColor: "var(--border-subtle)" }}
    >
      <div>
        <div className="flex items-center gap-3">
          <div
            className="bg-amber-500 p-2.5 rounded-xl shadow-lg shadow-amber-500/20 flex items-center justify-center min-w-11 min-h-11 text-slate-950"
            aria-hidden="true"
          >
            <Building2 className="w-6 h-6 text-slate-950 stroke-[2.5]" aria-hidden="true" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Captação de Obras Públicas
          </h1>
        </div>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          Filtro inteligente de licitações e engenharia via PNCP
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
        {/* Botão de Alternância de Tema (Dark / Light Pro) */}
        {onToggleTheme && (
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={isDark ? "Mudar para o Tema Claro (Light Pro)" : "Mudar para o Tema Escuro (Midnight Navy)"}
            title={isDark ? "Ativar Modo Claro" : "Ativar Modo Escuro"}
            className="flex items-center justify-center gap-2 px-3.5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-medium transition duration-200 border cursor-pointer focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 shadow-sm"
            style={{
              backgroundColor: "var(--btn-action-bg)",
              borderColor: "var(--btn-action-border)",
              color: "var(--btn-action-text)",
            }}
          >
            {isDark ? (
              <>
                <Sun className="w-4 h-4 text-amber-400" aria-hidden="true" />
                <span className="hidden sm:inline">Tema Claro</span>
              </>
            ) : (
              <>
                <Moon className="w-4 h-4 text-slate-700" aria-hidden="true" />
                <span className="hidden sm:inline">Tema Escuro</span>
              </>
            )}
          </button>
        )}

        <a
          href="/sandbox.html"
          aria-label="Abrir Sandbox de Design e Mocks em página isolada"
          className="flex items-center justify-center gap-2 px-3.5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-medium transition duration-200 border focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2 shadow-sm"
          style={{
            backgroundColor: "var(--btn-action-bg)",
            borderColor: "var(--btn-action-border)",
            color: "var(--btn-action-text)",
          }}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.8)]" aria-hidden="true" />
          <span className="hidden sm:inline">Sandbox de Design</span>
          <span className="sm:hidden">Sandbox</span>
        </a>

        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          aria-label={loading ? "Buscando licitações no portal PNCP..." : "Atualizar dados de licitações"}
          aria-busy={loading}
          className="flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 active:bg-amber-600 text-slate-950 px-4 sm:px-5 py-2.5 min-h-11 rounded-xl text-xs sm:text-sm font-bold transition duration-200 disabled:opacity-50 cursor-pointer shadow-lg shadow-amber-500/20 focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2"
        >
          <RefreshCw
            className={`w-4 h-4 text-slate-950 ${loading ? "animate-spin" : ""}`}
            aria-hidden="true"
          />
          <span>{loading ? "Buscando..." : "Atualizar Dados"}</span>
        </button>
      </div>
    </header>
  );
}
