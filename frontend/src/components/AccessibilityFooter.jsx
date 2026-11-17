import React from "react";
import { ShieldCheck, Keyboard, ExternalLink } from "lucide-react";

export default function AccessibilityFooter() {
  return (
    <footer
      role="contentinfo"
      aria-label="Informações de Acessibilidade e Rodapé"
      className="mt-12 pt-8 border-t text-xs space-y-6 transition-colors"
      style={{ borderColor: "var(--border-subtle)", color: "var(--text-muted)" }}
    >
      <div className="theme-card border p-5 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 transition-colors">
        {/* Bloco de compromisso com acessibilidade */}
        <div className="space-y-2 max-w-xl">
          <div className="flex items-center gap-2 text-sm font-bold" style={{ color: "var(--text-primary)" }}>
            <ShieldCheck className="w-5 h-5 text-amber-500" aria-hidden="true" />
            <span>Compromisso com acessibilidade digital</span>
          </div>
          <p className="leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Esta interface foi desenvolvida seguindo os padrões internacionais do{" "}
            <strong className="font-medium" style={{ color: "var(--text-secondary)" }}>
              W3C Web Accessibility Initiative (WAI)
            </strong>
            . A conformidade formal depende de auditoria automatizada e revisão manual contínuas.
          </p>
        </div>

        {/* Badge e Link Oficial da W3C */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <a
            href="https://www.w3.org/WAI/WCAG2AA-Conformance"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Consultar a referência WCAG no site oficial do W3C WAI (abre em nova aba)"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl font-medium transition border focus-visible:outline-2 focus-visible:outline-amber-400 focus-visible:outline-offset-2"
            style={{
              backgroundColor: "var(--btn-action-bg)",
              borderColor: "var(--btn-action-border)",
              color: "var(--btn-action-text)",
            }}
          >
            <span
              className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider"
              style={{
                backgroundColor: "var(--accent-amber)",
                color: "var(--accent-amber-text)",
              }}
            >
              Acessibilidade em evolução
            </span>
            <span>Referência W3C WAI</span>
            <ExternalLink className="w-3.5 h-3.5 opacity-70" aria-hidden="true" />
          </a>
        </div>
      </div>

      {/* Guia de Navegação por Teclado */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-1" style={{ color: "var(--text-dim)" }}>
        <div className="flex items-center gap-2">
          <Keyboard className="w-4 h-4 opacity-70" aria-hidden="true" />
          <span>
            Navegação por Teclado: Use{" "}
            <kbd
              className="px-1.5 py-0.5 rounded font-mono text-[11px] border"
              style={{
                backgroundColor: "var(--kbd-bg)",
                borderColor: "var(--kbd-border)",
                color: "var(--kbd-text)",
              }}
            >
              Tab
            </kbd>{" "}
            para avançar,{" "}
            <kbd
              className="px-1.5 py-0.5 rounded font-mono text-[11px] border"
              style={{
                backgroundColor: "var(--kbd-bg)",
                borderColor: "var(--kbd-border)",
                color: "var(--kbd-text)",
              }}
            >
              Shift + Tab
            </kbd>{" "}
            para retroceder e{" "}
            <kbd
              className="px-1.5 py-0.5 rounded font-mono text-[11px] border"
              style={{
                backgroundColor: "var(--kbd-bg)",
                borderColor: "var(--kbd-border)",
                color: "var(--kbd-text)",
              }}
            >
              Enter
            </kbd>{" "}
            ou{" "}
            <kbd
              className="px-1.5 py-0.5 rounded font-mono text-[11px] border"
              style={{
                backgroundColor: "var(--kbd-bg)",
                borderColor: "var(--kbd-border)",
                color: "var(--kbd-text)",
              }}
            >
              Espaço
            </kbd>{" "}
            para acionar.
          </span>
        </div>
        <div>
          <span>© {new Date().getFullYear()} Captação de Obras Públicas – PNCP</span>
        </div>
      </div>
    </footer>
  );
}
