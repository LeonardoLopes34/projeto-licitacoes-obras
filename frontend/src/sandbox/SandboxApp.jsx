import React, { useState, useMemo, useEffect } from "react";
import {
  Sliders,
  ArrowLeft,
  RefreshCw,
  Search,
  Building2,
  Tag,
  MapPin,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Database,
  SlidersHorizontal,
  X,
} from "lucide-react";
import "./sandbox.css";
import { DEFAULT_MOCK_OBRAS, MOCK_SCENARIOS } from "./mockData";
import DesignControls from "./DesignControls";
import ObrasSkeleton from "../components/ObrasSkeleton";

const DEFAULT_CONFIG = {
  theme: "theme-puredark",
  accentColor: "#d97706",
  accentGlow: "rgba(217, 119, 6, 0.25)",
  cardStyle: "glass",
  borderRadius: 16,
  gridCols: 2,
  density: "normal",
  fontScale: 1.0,
};

export default function SandboxApp() {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [isControlsOpen, setIsControlsOpen] = useState(false);
  const [currentScenarioKey, setCurrentScenarioKey] = useState("completo");

  // Fecha o drawer com a tecla Escape
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isControlsOpen) {
        setIsControlsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isControlsOpen]);

  // Dados mockados ativos
  const [obrasList, setObrasList] = useState(DEFAULT_MOCK_OBRAS);
  const [statusInfo, setStatusInfo] = useState(MOCK_SCENARIOS.completo.statusInfo);
  const [loading, setLoading] = useState(false);

  // Filtros locais do Sandbox
  const [searchTerm, setSearchTerm] = useState("");
  const [modalidadeFilter, setModalidadeFilter] = useState(0);
  const [ufFilter, setUfFilter] = useState("TODOS");

  // Troca de cenário
  const handleSelectScenario = (key) => {
    setCurrentScenarioKey(key);
    const scenario = MOCK_SCENARIOS[key];
    if (scenario) {
      setLoading(true);
      setTimeout(() => {
        setObrasList(scenario.dados);
        setStatusInfo(scenario.statusInfo);
        setLoading(false);
      }, 300);
    }
  };

  const handleSimulateRefresh = () => {
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
    }, 600);
  };

  const handleResetAll = () => {
    setConfig(DEFAULT_CONFIG);
    setCurrentScenarioKey("completo");
    setObrasList(DEFAULT_MOCK_OBRAS);
    setStatusInfo(MOCK_SCENARIOS.completo.statusInfo);
    setSearchTerm("");
    setModalidadeFilter(0);
    setUfFilter("TODOS");
  };

  // Filtragem em tempo real
  const filteredObras = useMemo(() => {
    return obrasList.filter((obra) => {
      if (modalidadeFilter !== 0) {
        if (modalidadeFilter === 4 && !obra.modalidade.includes("4")) return false;
        if (modalidadeFilter === 6 && !obra.modalidade.includes("6")) return false;
        if (modalidadeFilter === 8 && !obra.modalidade.includes("8")) return false;
      }
      if (ufFilter !== "TODOS" && obra.uf !== ufFilter) {
        return false;
      }
      if (!searchTerm.trim()) return true;
      const term = searchTerm.toLowerCase();
      return (
        (obra.municipio || "").toLowerCase().includes(term) ||
        (obra.uf || "").toLowerCase().includes(term) ||
        (obra.orgao || "").toLowerCase().includes(term) ||
        (obra.objeto || "").toLowerCase().includes(term) ||
        (obra.modalidade || "").toLowerCase().includes(term) ||
        (obra.categoria || "").toLowerCase().includes(term)
      );
    });
  }, [obrasList, searchTerm, modalidadeFilter, ufFilter]);

  // Lista única de UFs presentes
  const availableUfs = useMemo(() => {
    const ufs = new Set(obrasList.map((o) => o.uf).filter(Boolean));
    return ["TODOS", ...Array.from(ufs).sort()];
  }, [obrasList]);

  // Classes dinâmicas baseadas na configuração
  const cardStyleClass =
    config.cardStyle === "glass"
      ? "card-glass"
      : config.cardStyle === "elevated"
      ? "card-elevated"
      : "card-flat";

  const gridColsClass =
    config.gridCols === 1
      ? "grid-cols-1"
      : config.gridCols === 3
      ? "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
      : "grid-cols-1 md:grid-cols-2";

  return (
    <div
      className={`min-h-screen ${config.theme} density-${config.density} transition-colors duration-200`}
      style={{
        backgroundColor: "var(--sb-bg)",
        color: "var(--sb-text-main)",
        fontSize: `${config.fontScale}rem`,
      }}
    >
      {/* BARRA SUPERIOR FIXA DO SANDBOX */}
      <div className="sticky top-0 z-40 bg-slate-950/90 border-b border-slate-800 backdrop-blur-md px-4 py-2.5 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <a
            href="/"
            className="flex items-center gap-1.5 text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700 px-3 py-1.5 rounded-lg font-medium transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" aria-hidden="true" />
            <span>Voltar ao Projeto Principal</span>
          </a>

          <div className="hidden sm:flex items-center gap-2 text-slate-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-semibold text-white">Sandbox de Design Isolado</span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-400">
              Tema: <strong className="text-blue-400">{config.theme.replace("theme-", "")}</strong>
            </span>
          </div>
        </div>

        {/* BOTÃO PARA ABRIR CONTROLES */}
        <button
          type="button"
          onClick={() => setIsControlsOpen(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded-lg font-semibold shadow-lg shadow-blue-600/25 transition cursor-pointer"
          style={{ backgroundColor: config.accentColor }}
        >
          <Sliders className="w-4 h-4" aria-hidden="true" />
          <span>Personalizar Design & Mocks</span>
        </button>
      </div>

      {/* CONTEÚDO PRINCIPAL DO PROJETO NO SANDBOX */}
      <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {/* CABEÇALHO */}
        <header
          className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b"
          style={{ borderColor: "var(--sb-surface-border)" }}
        >
          <div>
            <div className="flex items-center gap-3">
              <div
                className="p-2.5 shadow-lg flex items-center justify-center text-white min-w-11 min-h-11"
                style={{
                  backgroundColor: config.accentColor,
                  borderRadius: `${config.borderRadius}px`,
                  boxShadow: `0 10px 15px -3px ${config.accentGlow}`,
                }}
              >
                <Building2 className="w-6 h-6" aria-hidden="true" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">
                Captação de Obras Públicas
              </h1>
            </div>
            <p className="text-sm mt-1" style={{ color: "var(--sb-text-muted)" }}>
              Filtro inteligente de licitações e engenharia via PNCP (Preview em Sandbox)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSimulateRefresh}
              disabled={loading}
              className="flex items-center justify-center gap-2 text-white px-5 py-2.5 min-h-11 font-medium transition cursor-pointer"
              style={{
                backgroundColor: config.accentColor,
                borderRadius: `${config.borderRadius}px`,
                boxShadow: `0 4px 12px ${config.accentGlow}`,
              }}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
              <span>{loading ? "Buscando Mocks..." : "Atualizar Dados"}</span>
            </button>
          </div>
        </header>

        {/* PAINEL DE FILTROS */}
        <section
          className="border p-5 space-y-4"
          style={{
            backgroundColor: "var(--sb-surface)",
            borderColor: "var(--sb-surface-border)",
            borderRadius: `${config.borderRadius}px`,
          }}
        >
          <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: "var(--sb-surface-border)" }}>
            <div className="flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4" style={{ color: config.accentColor }} aria-hidden="true" />
              <h2 className="text-sm font-semibold tracking-wide">Filtros de Licitações</h2>
            </div>
            <span className="text-xs font-mono" style={{ color: "var(--sb-text-muted)" }}>
              Cenário: <strong>{MOCK_SCENARIOS[currentScenarioKey]?.nome.split(" ")[0]}</strong>
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--sb-text-muted)" }}>
                Estado (UF)
              </label>
              <select
                value={ufFilter}
                onChange={(e) => setUfFilter(e.target.value)}
                className="w-full px-3 py-2.5 min-h-11 text-sm border focus:outline-none transition cursor-pointer"
                style={{
                  backgroundColor: "var(--sb-card-bg)",
                  borderColor: "var(--sb-surface-border)",
                  borderRadius: `${Math.min(config.borderRadius, 12)}px`,
                  color: "var(--sb-text-main)",
                }}
              >
                {availableUfs.map((uf) => (
                  <option key={uf} value={uf}>
                    {uf === "TODOS" ? "Todos os Estados" : `Estado: ${uf}`}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--sb-text-muted)" }}>
                Modalidade
              </label>
              <select
                value={modalidadeFilter}
                onChange={(e) => setModalidadeFilter(Number(e.target.value))}
                className="w-full px-3 py-2.5 min-h-11 text-sm border focus:outline-none transition cursor-pointer"
                style={{
                  backgroundColor: "var(--sb-card-bg)",
                  borderColor: "var(--sb-surface-border)",
                  borderRadius: `${Math.min(config.borderRadius, 12)}px`,
                  color: "var(--sb-text-main)",
                }}
              >
                <option value={0}>Todas as Modalidades</option>
                <option value={4}>Concorrência Eletrônica (4)</option>
                <option value={6}>Pregão Eletrônico (6)</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--sb-text-muted)" }}>
                Pesquisa Rápida
              </label>
              <div className="relative flex items-center">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2" style={{ color: "var(--sb-text-muted)" }} aria-hidden="true" />
                <input
                  type="text"
                  placeholder="Buscar por cidade, órgão, objeto ou categoria..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-10 py-2.5 min-h-11 text-sm border focus:outline-none transition"
                  style={{
                    backgroundColor: "var(--sb-card-bg)",
                    borderColor: "var(--sb-surface-border)",
                    borderRadius: `${Math.min(config.borderRadius, 12)}px`,
                    color: "var(--sb-text-main)",
                  }}
                />
                {searchTerm && (
                  <button
                    type="button"
                    onClick={() => setSearchTerm("")}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-slate-700 transition"
                  >
                    <X className="w-4 h-4" aria-hidden="true" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* BARRA DE STATUS */}
        {statusInfo && (
          <div
            className="border p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-sm"
            style={{
              borderRadius: `${config.borderRadius}px`,
              backgroundColor: "var(--sb-surface)",
              borderColor: "var(--sb-surface-border)",
            }}
          >
            <div className="flex items-center gap-3">
              {statusInfo.status?.includes("sucesso") ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" aria-hidden="true" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" aria-hidden="true" />
              )}
              <div>
                <span className="font-semibold">{statusInfo.mensagem}</span>
                <span className="block text-xs mt-0.5" style={{ color: "var(--sb-text-muted)" }}>
                  Status: {statusInfo.status} | Cenário ativo: {MOCK_SCENARIOS[currentScenarioKey]?.nome}
                </span>
              </div>
            </div>

            <div
              className="flex items-center gap-2 px-3 py-1.5 border font-mono text-xs"
              style={{
                backgroundColor: "var(--sb-card-bg)",
                borderColor: "var(--sb-surface-border)",
                borderRadius: `${Math.min(config.borderRadius, 8)}px`,
              }}
            >
              <Database className="w-4 h-4" style={{ color: config.accentColor }} aria-hidden="true" />
              <span>
                Exibindo: <strong>{filteredObras.length} de {obrasList.length}</strong>
              </span>
            </div>
          </div>
        )}

        {/* LISTAGEM DE CARDS DE OBRAS */}
        {loading ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-bold flex items-center gap-2">
                <span>Carregando dados simulados...</span>
                <span className="inline-block w-2 h-2 rounded-full bg-blue-400 animate-ping" />
              </h2>
            </div>
            <ObrasSkeleton count={4} />
          </div>
        ) : filteredObras.length === 0 ? (
          <div
            className="text-center py-16 border p-6"
            style={{
              backgroundColor: "var(--sb-surface)",
              borderColor: "var(--sb-surface-border)",
              borderRadius: `${config.borderRadius}px`,
            }}
          >
            <Search className="w-10 h-10 mx-auto mb-3" style={{ color: "var(--sb-text-muted)" }} aria-hidden="true" />
            <h3 className="text-lg font-bold">Nenhuma obra encontrada</h3>
            <p className="text-sm mt-1 max-w-md mx-auto" style={{ color: "var(--sb-text-muted)" }}>
              Tente ajustar os filtros ou selecionar outro cenário no painel de mocks.
            </p>
            <button
              type="button"
              onClick={() => {
                setSearchTerm("");
                setModalidadeFilter(0);
                setUfFilter("TODOS");
              }}
              className="mt-4 inline-flex items-center gap-2 text-white px-4 py-2 text-xs font-semibold transition cursor-pointer"
              style={{
                backgroundColor: config.accentColor,
                borderRadius: `${Math.min(config.borderRadius, 10)}px`,
              }}
            >
              Limpar Filtros
            </button>
          </div>
        ) : (
          <div className={`grid ${gridColsClass} gap-4`}>
            {filteredObras.map((obra) => {
              const valorFormatado = obra.valor_estimado
                ? `R$ ${obra.valor_estimado.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                : "Não informado";

              return (
                <article
                  key={obra.id_pncp}
                  className={`border p-5 flex flex-col justify-between transition duration-200 ${cardStyleClass}`}
                  style={{
                    backgroundColor: "var(--sb-card-bg)",
                    borderColor: "var(--sb-card-border)",
                    borderRadius: `${config.borderRadius}px`,
                  }}
                >
                  <div className="space-y-3">
                    {/* Badge de Localização + Modalidade + Categoria */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span
                        className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1"
                        style={{
                          backgroundColor: "var(--sb-surface)",
                          borderRadius: `${Math.min(config.borderRadius, 8)}px`,
                        }}
                      >
                        <MapPin className="w-3.5 h-3.5" style={{ color: config.accentColor }} aria-hidden="true" />
                        <span>{obra.municipio} - {obra.uf}</span>
                      </span>

                      <div className="flex items-center gap-2">
                        {obra.modalidade && (
                          <span
                            className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 border"
                            style={{
                              backgroundColor: "var(--sb-surface)",
                              borderColor: "var(--sb-surface-border)",
                              borderRadius: `${Math.min(config.borderRadius, 6)}px`,
                            }}
                          >
                            <Tag className="w-3 h-3" style={{ color: config.accentColor }} aria-hidden="true" />
                            <span>{obra.modalidade}</span>
                          </span>
                        )}

                        <span
                          className={`text-xs font-mono px-2 py-0.5 rounded border font-semibold ${
                            obra.fonte === "PNCP_REAL"
                              ? "bg-emerald-950/80 text-emerald-300 border-emerald-700"
                              : "bg-amber-950/80 text-amber-300 border-amber-700"
                          }`}
                        >
                          {obra.fonte}
                        </span>
                      </div>
                    </div>

                    {/* Órgão */}
                    <h3 className="text-base font-bold line-clamp-2">
                      {obra.orgao}
                    </h3>

                    {/* Categoria / Prazo */}
                    {obra.categoria && (
                      <div className="flex items-center gap-3 text-xs" style={{ color: "var(--sb-text-muted)" }}>
                        <span>Categoria: <strong style={{ color: "var(--sb-text-main)" }}>{obra.categoria}</strong></span>
                        {obra.prazo_meses && (
                          <span>Prazo: <strong style={{ color: "var(--sb-text-main)" }}>{obra.prazo_meses} meses</strong></span>
                        )}
                      </div>
                    )}

                    {/* Objeto */}
                    <p className="text-xs line-clamp-3 leading-relaxed" style={{ color: "var(--sb-text-muted)" }}>
                      {obra.objeto}
                    </p>
                  </div>

                  {/* FOOTER DO CARD */}
                  <div
                    className="mt-5 pt-4 border-t flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                    style={{ borderColor: "var(--sb-surface-border)" }}
                  >
                    <div>
                      <span className="block text-[11px] uppercase tracking-wider font-semibold" style={{ color: "var(--sb-text-muted)" }}>
                        Valor Estimado
                      </span>
                      <span className="font-bold text-sm text-emerald-400">
                        {valorFormatado}
                      </span>
                    </div>

                    {obra.link_pncp && (
                      <a
                        href={obra.link_pncp}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-semibold text-white transition cursor-pointer"
                        style={{
                          backgroundColor: config.accentColor,
                          borderRadius: `${Math.min(config.borderRadius, 8)}px`,
                        }}
                      >
                        <span>Ver no PNCP</span>
                        <ExternalLink className="w-3.5 h-3.5" aria-hidden="true" />
                      </a>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {/* RODAPÉ DO SANDBOX */}
        <footer
          className="mt-12 pt-6 border-t text-xs flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{
            borderColor: "var(--sb-surface-border)",
            color: "var(--sb-text-muted)",
          }}
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" aria-hidden="true" />
            <span>Sandbox Preview • Conformidade WCAG 2 Nível AA</span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsControlsOpen(true)}
              className="text-blue-400 hover:underline cursor-pointer"
            >
              Abrir Studio de Design
            </button>
            <span>•</span>
            <a href="/" className="hover:underline">
              Ir para App em Produção
            </a>
          </div>
        </footer>
      </div>

      {/* PAINEL LATERAL / DRAWER DE CONTROLES */}
      <DesignControls
        isOpen={isControlsOpen}
        onClose={() => setIsControlsOpen(false)}
        config={config}
        onChangeConfig={setConfig}
        currentScenario={currentScenarioKey}
        onSelectScenario={handleSelectScenario}
        onResetAll={handleResetAll}
      />
    </div>
  );
}
