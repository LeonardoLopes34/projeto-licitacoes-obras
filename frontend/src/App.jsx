import React, { useState, useEffect, useCallback, useMemo } from "react";
import Header from "./components/Header";
import FilterPanel from "./components/FilterPanel";
import StatusBar from "./components/StatusBar";
import MiniDashboard from "./components/MiniDashboard";
import ObrasList from "./components/ObrasList";
import ObraDetailModal from "./components/ObraDetailModal";
import AccessibilityFooter from "./components/AccessibilityFooter";

// Retorna a data no formato YYYY-MM-DD com deslocamento de dias
const getFormattedDate = (offsetDays = 0) => {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const DEFAULT_INITIAL_DATE = getFormattedDate(-2);
const DEFAULT_FINAL_DATE = getFormattedDate(0);
const DEFAULT_UF = "TODOS";
const DEFAULT_MODALIDADE = 0;
const DEFAULT_SORT_BY = "data_desc";

export default function App() {
  const [obras, setObras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState(null);
  const [selectedObra, setSelectedObra] = useState(null);
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

  // Filtros de Requisição da API e Frontend
  const [inicialDate, setInicialDate] = useState(() => DEFAULT_INITIAL_DATE);
  const [finalDate, setFinalDate] = useState(() => DEFAULT_FINAL_DATE);
  const [ufFilter, setUfFilter] = useState(DEFAULT_UF);
  const [modalidade, setModalidade] = useState(DEFAULT_MODALIDADE);
  const [sortBy, setSortBy] = useState(DEFAULT_SORT_BY);

  // Filtro de Pesquisa em Tempo Real no Frontend
  const [searchTerm, setSearchTerm] = useState("");

  // Formata data YYYY-MM-DD para YYYYMMDD exigido pela API
  const formatDateForApi = (dateStr) => (dateStr ? dateStr.replaceAll("-", "") : "");

  const fetchObras = useCallback(async (customSignal) => {
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

    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => timeoutController.abort(), 18000);

    const onCustomAbort = () => timeoutController.abort();
    if (customSignal instanceof AbortSignal) {
      if (customSignal.aborted) {
        clearTimeout(timeoutId);
        setLoading(false);
        return;
      }
      customSignal.addEventListener("abort", onCustomAbort);
    }

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1/obras";
      const url = `${apiBaseUrl}?inicial_date=${pInicial}&final_date=${pFinal}&modalidade=${modalidade}`;

      const res = await fetch(url, { signal: timeoutController.signal });
      const data = await res.json();

      setObras(data.dados || []);
      setStatusInfo({
        status: data.status,
        mensagem: data.mensagem,
        total: data.total_encontradas,
      });
    } catch (err) {
      if (customSignal?.aborted) {
        return;
      }
      console.error("Erro ao conectar no backend:", err);
      setStatusInfo({
        status: "erro",
        mensagem:
          err.name === "AbortError"
            ? "Tempo limite esgotado (Timeout). O servidor do PNCP demorou muito para responder."
            : "Erro ao conectar com a API FastAPI. Verifique se o backend está rodando.",
        total: 0,
      });
    } finally {
      clearTimeout(timeoutId);
      if (customSignal instanceof AbortSignal) {
        customSignal.removeEventListener("abort", onCustomAbort);
      }
      setLoading(false);
    }
  }, [inicialDate, finalDate, modalidade]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      fetchObras(controller.signal);
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
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

  // Filtra e ordena as obras retornadas em tempo real com useMemo para máxima performance
  const filteredObras = useMemo(() => {
    let result = obras;

    // Filtro por Estado (UF) em tempo real no frontend
    if (ufFilter && ufFilter !== "TODOS") {
      result = result.filter((obra) => {
        const uf = (obra.uf || "").toUpperCase().trim();
        return uf === ufFilter.toUpperCase().trim();
      });
    }

    // Filtro por termo de pesquisa
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      result = result.filter((obra) => {
        const municipio = (obra.municipio || "").toLowerCase();
        const uf = (obra.uf || "").toLowerCase();
        const orgao = (obra.orgao || "").toLowerCase();
        const objeto = (obra.objeto || "").toLowerCase();
        const modalidadeNome = (obra.modalidade || "").toLowerCase();
        const fonte = (obra.fonte || "").toLowerCase();
        const dataPub = (obra.data_publicacao || "").toLowerCase();

        return (
          municipio.includes(term) ||
          uf.includes(term) ||
          orgao.includes(term) ||
          objeto.includes(term) ||
          modalidadeNome.includes(term) ||
          fonte.includes(term) ||
          dataPub.includes(term)
        );
      });
    }

    // Aplicação da Ordenação
    return [...result].sort((a, b) => {
      if (sortBy === "valor_desc") {
        return (Number(b.valor_estimado) || 0) - (Number(a.valor_estimado) || 0);
      }
      if (sortBy === "valor_asc") {
        return (Number(a.valor_estimado) || 0) - (Number(b.valor_estimado) || 0);
      }
      if (sortBy === "orgao") {
        return (a.orgao || "").localeCompare(b.orgao || "");
      }
      if (sortBy === "data_asc") {
        return new Date(a.data_publicacao || 0) - new Date(b.data_publicacao || 0);
      }
      // Padrão: data_desc (mais recente primeiro)
      return new Date(b.data_publicacao || 0) - new Date(a.data_publicacao || 0);
    });
  }, [obras, ufFilter, searchTerm, sortBy]);

  // Volume total estimado somado de todas as obras filtradas
  const volumeTotal = useMemo(() => {
    return filteredObras.reduce((acc, curr) => acc + (Number(curr.valor_estimado) || 0), 0);
  }, [filteredObras]);

  // Contagem de filtros ativos desviando do padrão
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (inicialDate !== DEFAULT_INITIAL_DATE) count++;
    if (finalDate !== DEFAULT_FINAL_DATE) count++;
    if (ufFilter !== DEFAULT_UF) count++;
    if (modalidade !== DEFAULT_MODALIDADE) count++;
    if (sortBy !== DEFAULT_SORT_BY) count++;
    if (searchTerm.trim() !== "") count++;
    return count;
  }, [inicialDate, finalDate, ufFilter, modalidade, sortBy, searchTerm]);

  // Restaura todos os filtros para os valores padrão
  const handleResetFilters = useCallback(() => {
    setInicialDate(DEFAULT_INITIAL_DATE);
    setFinalDate(DEFAULT_FINAL_DATE);
    setUfFilter(DEFAULT_UF);
    setModalidade(DEFAULT_MODALIDADE);
    setSortBy(DEFAULT_SORT_BY);
    setSearchTerm("");
  }, []);

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
          onRefresh={() => fetchObras()}
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
            searchTerm={searchTerm}
            setSearchTerm={setSearchTerm}
            activeFiltersCount={activeFiltersCount}
            onResetFilters={handleResetFilters}
          />

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
              obras={obras}
              onSelectUf={setUfFilter}
              onSelectModalidade={setModalidade}
              activeUf={ufFilter}
              activeModalidade={modalidade}
            />
          )}

          <ObrasList
            obras={filteredObras}
            loading={loading}
            searchTerm={searchTerm}
            onClearSearch={() => setSearchTerm("")}
            onSelectObra={setSelectedObra}
          />
        </main>

        {/* Modal de Detalhes da Obra */}
        <ObraDetailModal
          obra={selectedObra}
          onClose={() => setSelectedObra(null)}
        />

        <AccessibilityFooter />
      </div>
    </div>
  );
}
