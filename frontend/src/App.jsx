import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import Header from "./components/Header";
import FilterPanel from "./components/FilterPanel";
import StatusBar from "./components/StatusBar";
import MiniDashboard from "./components/MiniDashboard";
import ObrasList from "./components/ObrasList";
import ObraDetailModal from "./components/ObraDetailModal";
import AccessibilityFooter from "./components/AccessibilityFooter";
import StatusBanner from "./components/StatusBanner";
import { buscarObrasProgressivamente, cancelarBuscaAtual } from "./api";
import {
  DEFAULT_SEARCH_SCOPE,
  evaluateSearch,
  normalizeSearchText,
  parseSearchExpression,
  removeSearchTerm,
} from "./searchExpression";

// Retorna a data no formato YYYY-MM-DD com deslocamento de dias
const getFormattedDate = (offsetDays = 0) => {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const DEFAULT_UF = "TODOS";
const DEFAULT_MODALIDADE = 0;
const DEFAULT_SORT_BY = "data_desc";
const PROGRESSIVE_MAX_PAGES = 5;

const normalizeText = normalizeSearchText;

const isPavementWork = (obra) =>
  /paviment|recape|calcamento|asfalt|pavimento/.test(normalizeText(obra.objeto));

export default function App() {
  const [obras, setObras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState(null);
  const [apiPagination, setApiPagination] = useState(null);
  const [selectedObra, setSelectedObra] = useState(null);
  const [analisesExigencias, setAnalisesExigencias] = useState({});
  const [showDashboard, setShowDashboard] = useState(false);

  // Controle de Tema: 'dark' (Deep Midnight Navy) ou 'light' (Light Pro) com persistência local
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("app-theme") || "dark";
    } catch {
      return "dark";
    }
  });

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const nextTheme = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("app-theme", nextTheme);
      } catch {}
      return nextTheme;
    });
  }, []);

  // Os filtros são aplicados ao último snapshot carregado. Só uma mudança de
  // período ou o botão Atualizar Dados pode iniciar uma coleta no PNCP.
  const [inicialDate, setInicialDate] = useState(() => getFormattedDate(0));
  const [finalDate, setFinalDate] = useState(() => getFormattedDate(0));
  const [ufFilter, setUfFilter] = useState(DEFAULT_UF);
  const [modalidade, setModalidade] = useState(DEFAULT_MODALIDADE);
  const [sortBy, setSortBy] = useState(DEFAULT_SORT_BY);
  const [incluirPavimentacao, setIncluirPavimentacao] = useState(true);

  // Filtro de Pesquisa em Tempo Real no Frontend
  const [searchTerm, setSearchTerm] = useState("");
  const [escopoBusca, setEscopoBusca] = useState(DEFAULT_SEARCH_SCOPE);
  const requestIdRef = useRef(0);

  // Formata data YYYY-MM-DD para YYYYMMDD exigido pela API
  const formatDateForApi = (dateStr) => (dateStr ? dateStr.replaceAll("-", "") : "");

  const fetchObras = useCallback(async ({ forcarAtualizacao = false } = {}) => {
    const requestId = ++requestIdRef.current;
    const pInicial = formatDateForApi(inicialDate);
    const pFinal = formatDateForApi(finalDate);

    if (!pInicial || !pFinal || pInicial.length !== 8 || pFinal.length !== 8) {
      setStatusInfo({
        status: "aviso",
        mensagem: "Por favor, selecione datas válidas.",
        total: 0,
      });
      return;
    }

    if (pInicial > pFinal) {
      setStatusInfo({
        status: "aviso",
        mensagem: "A data inicial não pode ser maior que a data final.",
        total: 0,
      });
      return;
    }

    setLoading(true);
    setObras([]);
    setApiPagination(null);

    try {
      const remoteParams = {
        inicial_date: pInicial,
        final_date: pFinal,
        // Traz o conjunto-base do período. As mudanças de UF, modalidade,
        // termo, ordenação e pavimentação são locais e não voltam ao PNCP.
        modalidade: DEFAULT_MODALIDADE,
        // Os cards chegam página a página. Assim, a tela começa a preencher
        // imediatamente e continua coletando resultados para evitar cortes na
        // primeira página do PNCP.
        max_paginas: PROGRESSIVE_MAX_PAGES,
        incluir_pavimentacao: true,
      };
      if (forcarAtualizacao) remoteParams.forcar_atualizacao = true;

      const aplicarResultadoConcluido = (data) => {
        if (requestId !== requestIdRef.current) return;
        setObras(Array.isArray(data.dados) ? data.dados : []);
        setApiPagination(null);
        setStatusInfo({
          status: data.status,
          mensagem: data.mensagem,
          total: data.total_encontradas,
          metadados: data.metadados,
        });
      };

      await buscarObrasProgressivamente(remoteParams, {
        onProgress: (data) => {
          if (requestId !== requestIdRef.current) return;
          setObras(Array.isArray(data.dados) ? data.dados : []);
          setStatusInfo({
            status: data.status,
            mensagem: data.mensagem,
            total: data.total_encontradas,
            metadados: data.metadados,
          });
        },
        onComplete: aplicarResultadoConcluido,
      });
    } catch (err) {
      if (err.name === "AbortError" || requestId !== requestIdRef.current) {
        return;
      }
      console.error("Erro ao conectar no backend:", err);
      setStatusInfo({
        status: "erro",
        mensagem:
          err.status === 410 || err.code === "consulta_expirada"
            ? "A consulta expirou. Atualize para reiniciar mantendo os filtros selecionados."
            : err.name === "AbortError"
            ? "Tempo limite esgotado (Timeout). O servidor do PNCP demorou muito para responder."
            : "Erro ao conectar com a API FastAPI. Verifique se o backend está rodando.",
        total: 0,
      });
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [inicialDate, finalDate]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchObras();
    }, 400);
    return () => {
      clearTimeout(timer);
      cancelarBuscaAtual();
    };
  }, [fetchObras]);

  // Atalhos de teclado globais: '/' ou 'Ctrl+K' / 'Cmd+K' para focar a barra de pesquisa
  useEffect(() => {
    const handleKeyDown = (e) => {
      const isSearchShortcut =
        (e.key === "k" && (e.ctrlKey || e.metaKey)) ||
        (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName));

      if (isSearchShortcut) {
        e.preventDefault();
        const searchInput = document.getElementById("filtro-busca-texto");
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const obrasAposFiltrosEstruturais = useMemo(() => {
    let result = obras;

    if (ufFilter !== DEFAULT_UF) {
      result = result.filter((obra) => normalizeText(obra.uf) === normalizeText(ufFilter));
    }
    if (modalidade !== DEFAULT_MODALIDADE) {
      result = result.filter((obra) => Number(obra.modalidade_codigo) === modalidade);
    }
    if (!incluirPavimentacao) {
      result = result.filter((obra) => !isPavementWork(obra));
    }
    return result;
  }, [obras, ufFilter, modalidade, incluirPavimentacao]);

  const expressaoBusca = useMemo(() => parseSearchExpression(searchTerm), [searchTerm]);

  const avaliacoesBusca = useMemo(
    () => obrasAposFiltrosEstruturais.map((obra) => ({
      obra,
      ...evaluateSearch(obra, expressaoBusca, escopoBusca),
    })),
    [obrasAposFiltrosEstruturais, expressaoBusca, escopoBusca],
  );

  const resumoBusca = useMemo(() => {
    const excluidos = avaliacoesBusca.filter((item) => item.motivo === "excluido_por_termo").length;
    const semCorrespondencia = avaliacoesBusca.filter((item) => item.motivo === "nao_corresponde").length;
    return {
      termosInclusao: expressaoBusca.inclusoes.map((term) => term.original),
      termosExclusao: expressaoBusca.exclusoes.map((term) => term.original),
      escopoBusca,
      totalAntesBusca: avaliacoesBusca.length,
      totalExcluidos: excluidos,
      totalSemCorrespondencia: semCorrespondencia,
      todosExcluidos: avaliacoesBusca.length > 0
        && excluidos === avaliacoesBusca.length
        && expressaoBusca.exclusoes.length > 0,
    };
  }, [avaliacoesBusca, escopoBusca, expressaoBusca]);

  const filteredObras = useMemo(() => {
    const result = avaliacoesBusca.filter((item) => item.aprovado).map((item) => item.obra);

    return [...result].sort((a, b) => {
      if (sortBy === "valor_desc") return (Number(b.valor_estimado) || 0) - (Number(a.valor_estimado) || 0);
      if (sortBy === "valor_asc") return (Number(a.valor_estimado) || 0) - (Number(b.valor_estimado) || 0);
      if (sortBy === "orgao") return String(a.orgao || "").localeCompare(String(b.orgao || ""));
      if (sortBy === "data_asc") return String(a.data_publicacao || "").localeCompare(String(b.data_publicacao || ""));
      return String(b.data_publicacao || "").localeCompare(String(a.data_publicacao || ""));
    });
  }, [avaliacoesBusca, sortBy]);

  const volumeTotal = useMemo(
    () => filteredObras.reduce((total, obra) => total + (Number(obra.valor_estimado) || 0), 0),
    [filteredObras],
  );

  // Contagem de filtros ativos desviando do padrão
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    const hoje = getFormattedDate(0);
    if (inicialDate !== hoje) count++;
    if (finalDate !== hoje) count++;
    if (ufFilter !== DEFAULT_UF) count++;
    if (modalidade !== DEFAULT_MODALIDADE) count++;
    if (!incluirPavimentacao) count++;
    if (searchTerm.trim() !== "") count++;
    if (escopoBusca !== DEFAULT_SEARCH_SCOPE) count++;
    return count;
  }, [inicialDate, finalDate, ufFilter, modalidade, incluirPavimentacao, searchTerm, escopoBusca]);

  // Restaura todos os filtros para os valores padrão
  const handleResetFilters = useCallback(() => {
    const hoje = getFormattedDate(0);
    setInicialDate(hoje);
    setFinalDate(hoje);
    setUfFilter(DEFAULT_UF);
    setModalidade(DEFAULT_MODALIDADE);
    setSortBy(DEFAULT_SORT_BY);
    setIncluirPavimentacao(true);
    setSearchTerm("");
    setEscopoBusca(DEFAULT_SEARCH_SCOPE);
  }, []);

  const handleAnalysisComplete = useCallback((analysis) => {
    if (!selectedObra) return;
    const key = selectedObra.id_pncp || `${selectedObra.cnpj}:${selectedObra.ano}:${selectedObra.sequencial}`;
    setAnalisesExigencias((current) => ({ ...current, [key]: analysis }));
  }, [selectedObra]);

  return (
    <div className={`min-h-screen app-bg theme-${theme} font-sans p-4 sm:p-6 lg:p-8 selection:bg-amber-500 selection:text-slate-950 transition-colors duration-200`}>
      {/* Skip Link para navegabilidade por teclado (WCAG 2.4.1) */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-3 focus:bg-amber-500 focus:text-slate-950 focus:font-bold focus:rounded-xl focus:shadow-2xl focus:outline-2 focus:outline-amber-300 transition"
      >
        Pular para o conteúdo principal
      </a>

      <div className="max-w-7xl mx-auto space-y-6">
        <Header
          onRefresh={() => fetchObras({ forcarAtualizacao: true })}
          loading={loading}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />

        <main id="main-content" tabIndex="-1" className="space-y-6 focus:outline-none">
          <FilterPanel
            inicialDate={inicialDate}
            setInicialDate={setInicialDate}
            finalDate={finalDate}
            setFinalDate={setFinalDate}
            ufFilter={ufFilter}
            setUfFilter={setUfFilter}
            modalidade={modalidade}
            setModalidade={setModalidade}
            sortBy={sortBy}
            setSortBy={setSortBy}
            incluirPavimentacao={incluirPavimentacao}
            setIncluirPavimentacao={setIncluirPavimentacao}
            searchTerm={searchTerm}
            setSearchTerm={setSearchTerm}
            termosInclusao={expressaoBusca.inclusoes.map((term) => term.original)}
            termosExclusao={expressaoBusca.exclusoes.map((term) => term.original)}
            escopoBusca={escopoBusca}
            setEscopoBusca={setEscopoBusca}
            onRemoveTerm={(chip) => setSearchTerm((current) => removeSearchTerm(current, chip))}
            activeFiltersCount={activeFiltersCount}
            onResetFilters={handleResetFilters}
          />

          <StatusBanner statusInfo={statusInfo} />

          <StatusBar
            statusInfo={statusInfo}
            filteredTotal={filteredObras.length}
            volumeTotal={volumeTotal}
            showDashboard={showDashboard}
            onToggleDashboard={() => setShowDashboard((prev) => !prev)}
          />

          {/* Mini Dashboard Expansível de Estatísticas e Análise */}
          {showDashboard && (
            <MiniDashboard
              obras={filteredObras}
              resumo={statusInfo?.metadados}
              onSelectUf={setUfFilter}
              onSelectModalidade={setModalidade}
              activeUf={ufFilter}
              activeModalidade={modalidade}
            />
          )}

          <ObrasList
            key={`${inicialDate}:${finalDate}:${ufFilter}:${modalidade}:${sortBy}:${incluirPavimentacao}:${searchTerm}:${escopoBusca}`}
            obras={filteredObras}
            loading={loading}
            searchTerm={searchTerm}
            onClearSearch={() => setSearchTerm("")}
            onSelectObra={setSelectedObra}
            analisesExigencias={analisesExigencias}
            apiPagination={apiPagination}
            resumoBusca={resumoBusca}
          />
        </main>

        {/* Modal de Detalhes da Obra */}
        <ObraDetailModal
          obra={selectedObra}
          onClose={() => setSelectedObra(null)}
          onAnalysisComplete={handleAnalysisComplete}
        />

        <AccessibilityFooter />
      </div>
    </div>
  );
}
