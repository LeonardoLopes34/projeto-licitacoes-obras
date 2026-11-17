import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
  TrendingUp,
  Coins,
  HardHat,
  Search,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  ExternalLink,
  MapPin,
  Tag,
  X,
  ArrowLeft,
  Layers,
  Sun,
  Moon
} from "lucide-react";
import { buscarObras, cancelarBuscaAtual } from "../api";

// Lista de estados brasileiros para o filtro
const ESTADOS_BRASIL = [
  { sigla: "TODOS", nome: "Todos os Estados (UF)" },
  { sigla: "AC", nome: "Acre (AC)" },
  { sigla: "AL", nome: "Alagoas (AL)" },
  { sigla: "AP", nome: "Amapá (AP)" },
  { sigla: "AM", nome: "Amazonas (AM)" },
  { sigla: "BA", nome: "Bahia (BA)" },
  { sigla: "CE", nome: "Ceará (CE)" },
  { sigla: "DF", nome: "Distrito Federal (DF)" },
  { sigla: "ES", nome: "Espírito Santo (ES)" },
  { sigla: "GO", nome: "Goiás (GO)" },
  { sigla: "MA", nome: "Maranhão (MA)" },
  { sigla: "MT", nome: "Mato Grosso (MT)" },
  { sigla: "MS", nome: "Mato Grosso do Sul (MS)" },
  { sigla: "MG", nome: "Minas Gerais (MG)" },
  { sigla: "PA", nome: "Pará (PA)" },
  { sigla: "PB", nome: "Paraíba (PB)" },
  { sigla: "PR", nome: "Paraná (PR)" },
  { sigla: "PE", nome: "Pernambuco (PE)" },
  { sigla: "PI", nome: "Piauí (PI)" },
  { sigla: "RJ", nome: "Rio de Janeiro (RJ)" },
  { sigla: "RN", nome: "Rio Grande do Norte (RN)" },
  { sigla: "RS", nome: "Rio Grande do Sul (RS)" },
  { sigla: "RO", nome: "Rondônia (RO)" },
  { sigla: "RR", nome: "Roraima (RR)" },
  { sigla: "SC", nome: "Santa Catarina (SC)" },
  { sigla: "SP", nome: "São Paulo (SP)" },
  { sigla: "SE", nome: "Sergipe (SE)" },
  { sigla: "TO", nome: "Tocantins (TO)" },
];

const getFormattedDate = (offsetDays = 0) => {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export default function NeitImportsApp() {
  const [obras, setObras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusInfo, setStatusInfo] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState("todas");
  const [selectedUf, setSelectedUf] = useState("TODOS");
  const [selectedObra, setSelectedObra] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const requestIdRef = useRef(0);
  const itemsPerPage = 10;

  // Controle de Tema Claro / Escuro com persistência local
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("sandbox-theme") || "dark";
    } catch {
      return "dark";
    }
  });

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      try {
        localStorage.setItem("sandbox-theme", next);
      } catch {}
      return next;
    });
  };

  const isLight = theme === "light";

  // Filtros de Data
  const inicialDate = getFormattedDate(-2);
  const finalDate = getFormattedDate(0);

  // Busca dados reais da API
  const fetchObrasFromApi = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setCurrentPage(1);
    try {
      const initParam = inicialDate.replace(/-/g, "");
      const finalParam = finalDate.replace(/-/g, "");
      const modalidadeRemota =
        activeTab === "concorrencia" ? 4 : activeTab === "pregao" ? 6 : 0;
      const remoteParams = {
        inicial_date: initParam,
        final_date: finalParam,
        modalidade: modalidadeRemota,
        max_paginas: modalidadeRemota === 0 ? 1 : 5,
      };
      if (selectedUf !== "TODOS") {
        remoteParams.uf = selectedUf;
      }
      const data = await buscarObras({
        ...remoteParams,
      });
      if (requestId !== requestIdRef.current) return;
      setObras(data.dados || []);
      setStatusInfo({
        status: data.status,
        mensagem: data.mensagem,
        metadados: data.metadados,
      });
    } catch (err) {
      if (requestId !== requestIdRef.current || err.name === "AbortError") return;
      console.error("Erro ao buscar dados da API:", err);
      setStatusInfo({
        status: "erro",
        mensagem: "Não foi possível carregar os dados do PNCP.",
        metadados: { origem: "PNCP", parcial: false, paginas_com_erro: 0 },
      });
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  }, [inicialDate, finalDate, activeTab, selectedUf]);

  useEffect(() => {
    fetchObrasFromApi();
    return () => cancelarBuscaAtual();
  }, [fetchObrasFromApi]);

  // Formatação de Moeda
  const formatBRL = (val) => {
    if (val === null || val === undefined || isNaN(val)) return "—";
    return `R$ ${Number(val).toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  // Formatação de Data
  const formatDate = (rawDate) => {
    if (!rawDate) return "—";
    if (rawDate.includes("/")) return rawDate;
    try {
      const d = new Date(rawDate);
      if (isNaN(d.getTime())) return rawDate;
      const day = String(d.getDate()).padStart(2, "0");
      const month = String(d.getMonth() + 1).padStart(2, "0");
      const year = d.getFullYear();
      return `${day}/${month}/${year}`;
    } catch {
      return rawDate;
    }
  };

  // Cores de Avatar por UF
  const getUfAvatarColor = (uf) => {
    const code = (uf || "BR").charCodeAt(0) % 5;
    if (isLight) {
      switch (code) {
        case 0:
          return "bg-blue-100 text-blue-700 border border-blue-200";
        case 1:
          return "bg-emerald-100 text-emerald-700 border border-emerald-200";
        case 2:
          return "bg-amber-100 text-amber-800 border border-amber-200";
        case 3:
          return "bg-purple-100 text-purple-700 border border-purple-200";
        default:
          return "bg-slate-100 text-slate-700 border border-slate-200";
      }
    }

    switch (code) {
      case 0:
        return "bg-blue-600/30 text-blue-400 border border-blue-500/30";
      case 1:
        return "bg-emerald-600/30 text-emerald-400 border border-emerald-500/30";
      case 2:
        return "bg-amber-600/30 text-amber-400 border border-amber-500/30";
      case 3:
        return "bg-purple-600/30 text-purple-400 border border-purple-500/30";
      default:
        return "bg-slate-700/40 text-slate-300 border border-slate-600/40";
    }
  };

  // Badge da Modalidade
  const getModalidadeBadge = (modalidade) => {
    const mod = (modalidade || "").toLowerCase();
    if (mod.includes("concorrência") || mod.includes("concorrencia")) {
      return (
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
            isLight
              ? "bg-amber-50 text-amber-800 border border-amber-300 shadow-xs"
              : "bg-[#292218] text-[#fbbf24] border border-[#f59e0b]/30"
          }`}
        >
          Concorrência
        </span>
      );
    } else if (mod.includes("pregão") || mod.includes("pregao")) {
      return (
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
            isLight
              ? "bg-emerald-50 text-emerald-800 border border-emerald-300 shadow-xs"
              : "bg-[#132a22] text-[#34d399] border border-[#10b981]/30"
          }`}
        >
          Pregão
        </span>
      );
    }
    return (
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${
          isLight
            ? "bg-blue-50 text-blue-800 border border-blue-300"
            : "bg-[#1e293b] text-[#60a5fa] border border-[#3b82f6]/30"
        }`}
      >
        {modalidade || "Outros"}
      </span>
    );
  };

  // Métricas / KPIs calculadas em tempo real
  const kpis = useMemo(() => {
    let volumeTotal = 0;
    let concorrenciasCount = 0;
    let concorrenciasVolume = 0;
    let pregoesCount = 0;
    let pregoesVolume = 0;
    let maiorValor = 0;

    obras.forEach((obra) => {
      const val = Number(obra.valor_estimado) || 0;
      volumeTotal += val;
      if (val > maiorValor) maiorValor = val;

      const mod = (obra.modalidade || "").toLowerCase();
      if (mod.includes("concorrência") || mod.includes("concorrencia")) {
        concorrenciasCount += 1;
        concorrenciasVolume += val;
      } else if (mod.includes("pregão") || mod.includes("pregao")) {
        pregoesCount += 1;
        pregoesVolume += val;
      }
    });

    const ticketMedio = obras.length > 0 ? volumeTotal / obras.length : 0;

    return {
      volumeTotal,
      totalObras: obras.length,
      ticketMedio,
      maiorValor,
      concorrenciasCount,
      concorrenciasVolume,
      pregoesCount,
      pregoesVolume,
    };
  }, [obras]);

  // Filtragem de Obras
  const filteredObras = useMemo(() => {
    return obras.filter((obra) => {
      // Filtro por Estado (UF)
      if (selectedUf !== "TODOS" && (obra.uf || "").toUpperCase() !== selectedUf) {
        return false;
      }

      // Filtro por Abas
      const mod = (obra.modalidade || "").toLowerCase();
      const val = Number(obra.valor_estimado) || 0;

      if (activeTab === "concorrencia") {
        if (!mod.includes("concorrência") && !mod.includes("concorrencia")) return false;
      } else if (activeTab === "pregao") {
        if (!mod.includes("pregão") && !mod.includes("pregao")) return false;
      } else if (activeTab === "acima_1m") {
        if (val < 1000000) return false;
      }

      // Filtro por Busca Textual
      if (searchTerm.trim()) {
        const term = searchTerm.toLowerCase();
        const matchOrgao = (obra.orgao || "").toLowerCase().includes(term);
        const matchObjeto = (obra.objeto || "").toLowerCase().includes(term);
        const matchMunicipio = (obra.municipio || "").toLowerCase().includes(term);
        const matchUf = (obra.uf || "").toLowerCase().includes(term);
        const matchId = (obra.id_pncp || obra.numero_controle_pncp || "").toLowerCase().includes(term);

        if (!matchOrgao && !matchObjeto && !matchMunicipio && !matchUf && !matchId) {
          return false;
        }
      }

      return true;
    });
  }, [obras, selectedUf, activeTab, searchTerm]);

  // Paginação
  const totalPages = Math.ceil(filteredObras.length / itemsPerPage) || 1;
  const paginatedObras = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredObras.slice(start, start + itemsPerPage);
  }, [filteredObras, currentPage, itemsPerPage]);

  const metadata = statusInfo?.metadados || {};
  const hasPageErrors = Number(metadata.paginas_com_erro) > 0;
  const isOffline = metadata.origem === "banco_local";
  const showStatus = Boolean(statusInfo && (statusInfo.status === "erro" || isOffline || metadata.parcial));
  const statusMessage = isOffline
    ? "Exibindo dados salvos localmente; o PNCP não respondeu agora."
    : statusInfo?.status === "erro"
      ? statusInfo.mensagem
      : hasPageErrors
        ? statusInfo?.mensagem || "Algumas páginas não puderam ser consultadas."
        : "O limite de páginas foi atingido; refine o período ou selecione uma modalidade específica.";

  return (
    <div
      className={`min-h-screen font-sans antialiased transition-colors duration-200 ${
        isLight ? "bg-[#f8fafc] text-[#0f172a]" : "bg-[#0d0f12] text-[#f1f5f9]"
      }`}
    >
      {/* 1. TOP HEADER BAR */}
      <header
        className={`h-16 border-b px-6 lg:px-10 flex items-center justify-between backdrop-blur-md sticky top-0 z-20 transition-colors ${
          isLight
            ? "bg-white/90 border-[#e2e8f0] shadow-xs"
            : "bg-[#111317]/90 border-[#1e222b]"
        }`}
      >
        <div className="flex items-center gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-600 to-amber-400 text-slate-950 flex items-center justify-center font-bold shadow-md">
            <HardHat className="w-5 h-5 text-slate-950" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className={`font-bold text-sm sm:text-base tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>
                Captação de Obras Públicas
              </span>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  isLight
                    ? "bg-emerald-100 text-emerald-800 border-emerald-200"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                }`}
              >
                PNCP Live
              </span>
            </div>
            <span className={`block text-[11px] ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
              Monitoramento e Inteligência em Licitações de Engenharia
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Botão de Alternar Tema Claro / Escuro */}
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={isLight ? "Ativar Modo Escuro" : "Ativar Modo Claro"}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold border transition cursor-pointer shadow-xs ${
              isLight
                ? "bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-800"
                : "bg-[#181c24] hover:bg-[#202530] border-[#272d3b] text-[#f1f5f9]"
            }`}
          >
            {isLight ? (
              <>
                <Moon className="w-3.5 h-3.5 text-blue-600" />
                <span className="hidden sm:inline">Tema Escuro</span>
              </>
            ) : (
              <>
                <Sun className="w-3.5 h-3.5 text-amber-400" />
                <span className="hidden sm:inline">Tema Claro</span>
              </>
            )}
          </button>

          {/* Botão de Atualizar */}
          <button
            type="button"
            onClick={fetchObrasFromApi}
            disabled={loading}
            className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold border transition cursor-pointer disabled:opacity-50 ${
              isLight
                ? "bg-slate-100 hover:bg-slate-200 border-slate-300 text-slate-700"
                : "bg-[#181c24] hover:bg-[#202530] border-[#272d3b] text-[#94a3b8]"
            }`}
            title="Recarregar dados da API"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin text-amber-500" : ""}`} />
            <span className="hidden sm:inline">Atualizar</span>
          </button>

          {/* Link para voltar ao app principal */}
          <a
            href="/"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-[#2563eb] text-white hover:bg-[#1d4ed8] shadow-sm transition"
            title="Voltar para o app principal de Licitações"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Voltar ao Projeto</span>
          </a>
        </div>
      </header>

      {/* 2. ÁREA PRINCIPAL DO DASHBOARD (FULL WIDTH) */}
      <main className="p-6 md:p-8 lg:p-10 space-y-6 max-w-7xl mx-auto">
        {/* Título & Subtítulo */}
        <div className="space-y-0.5">
          <h1 className={`text-xl sm:text-2xl font-bold tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>
            Licitações de Obras
          </h1>
          <p className={`text-xs sm:text-sm ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
            Contratações públicas de engenharia, reformas e pavimentação via Portal Nacional de Contratações Públicas
          </p>
        </div>

        {/* 3. ROW DE 4 KPI METRIC CARDS */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Volume Total Estimado */}
          <div
            className={`border rounded-xl p-4 space-y-2 transition-colors ${
              isLight
                ? "bg-white border-slate-200 shadow-sm"
                : "bg-[#14171d] border-[#202530]"
            }`}
          >
            <div className={`flex items-center gap-2 text-xs ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
              <Coins className="w-3.5 h-3.5 text-amber-500" />
              <span>Volume Total Estimado</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-lg sm:text-xl font-bold text-amber-500 font-mono tracking-tight">
                {formatBRL(kpis.volumeTotal)}
              </span>
            </div>
            <span className={`block text-[10px] ${isLight ? "text-slate-400" : "text-[#64748b]"}`}>
              {kpis.totalObras} licitações no período
            </span>
          </div>

          {/* Card 2: Ticket Médio por Obra */}
          <div
            className={`border rounded-xl p-4 space-y-2 transition-colors ${
              isLight
                ? "bg-white border-slate-200 shadow-sm"
                : "bg-[#14171d] border-[#202530]"
            }`}
          >
            <div className={`flex items-center gap-2 text-xs ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
              <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
              <span>Ticket Médio por Obra</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-lg sm:text-xl font-bold font-mono tracking-tight ${isLight ? "text-emerald-600" : "text-[#34d399]"}`}>
                {formatBRL(kpis.ticketMedio)}
              </span>
            </div>
            <span className={`block text-[10px] font-medium ${isLight ? "text-emerald-600" : "text-[#34d399]/80"}`}>
              Média por contratação
            </span>
          </div>

          {/* Card 3: Concorrências Eletrônicas */}
          <div
            className={`border rounded-xl p-4 space-y-2 transition-colors ${
              isLight
                ? "bg-white border-slate-200 shadow-sm"
                : "bg-[#14171d] border-[#202530]"
            }`}
          >
            <div className={`flex items-center gap-2 text-xs ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
              <Tag className="w-3.5 h-3.5 text-amber-500" />
              <span>Concorrências Eletrônicas</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-lg sm:text-xl font-bold font-mono tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>
                {kpis.concorrenciasCount}
              </span>
              <span className={`text-xs font-mono ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
                ({formatBRL(kpis.concorrenciasVolume)})
              </span>
            </div>
            <span className={`block text-[10px] ${isLight ? "text-slate-400" : "text-[#64748b]"}`}>
              Modalidade Concorrência (04)
            </span>
          </div>

          {/* Card 4: Pregões Eletrônicos */}
          <div
            className={`border rounded-xl p-4 space-y-2 transition-colors ${
              isLight
                ? "bg-white border-slate-200 shadow-sm"
                : "bg-[#14171d] border-[#202530]"
            }`}
          >
            <div className={`flex items-center gap-2 text-xs ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
              <Layers className="w-3.5 h-3.5 text-blue-500" />
              <span>Pregões Eletrônicos</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={`text-lg sm:text-xl font-bold font-mono tracking-tight ${isLight ? "text-slate-900" : "text-white"}`}>
                {kpis.pregoesCount}
              </span>
              <span className={`text-xs font-mono ${isLight ? "text-slate-500" : "text-[#94a3b8]"}`}>
                ({formatBRL(kpis.pregoesVolume)})
              </span>
            </div>
            <span className={`block text-[10px] ${isLight ? "text-slate-400" : "text-[#64748b]"}`}>
              Modalidade Pregão (06)
            </span>
          </div>
        </div>

        {/* 4. BARRA DE BUSCA, ABAS DE STATUS E FILTRO DE UF */}
        <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
          {/* Input de Busca */}
          <div className="relative flex-1 max-w-lg">
            <Search className={`w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 ${isLight ? "text-slate-400" : "text-[#64748b]"}`} />
            <input
              type="text"
              placeholder="Buscar por órgão, cidade, UF, objeto ou número de controle..."
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              className={`w-full pl-9 pr-4 py-2.5 border rounded-lg text-xs transition ${
                isLight
                  ? "bg-white border-slate-300 text-slate-900 placeholder-slate-400 focus:border-blue-500 shadow-xs"
                  : "bg-[#14171d] border-[#202530] text-white placeholder-[#64748b] focus:border-[#3b82f6]"
              }`}
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className={`absolute right-3 top-1/2 -translate-y-1/2 ${isLight ? "text-slate-400 hover:text-slate-700" : "text-[#64748b] hover:text-white"}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Abas + Seletor de UF */}
          <div className="flex flex-wrap items-center gap-2.5">
            {/* Abas */}
            <div
              className={`inline-flex p-1 border rounded-lg text-xs font-medium ${
                isLight
                  ? "bg-slate-200/70 border-slate-300"
                  : "bg-[#14171d] border-[#202530]"
              }`}
            >
              <button
                type="button"
                onClick={() => {
                  setActiveTab("todas");
                  setCurrentPage(1);
                }}
                className={`px-3 py-1 rounded-md transition cursor-pointer ${
                  activeTab === "todas"
                    ? isLight
                      ? "bg-white text-slate-900 shadow-xs font-bold"
                      : "bg-[#1e2430] text-white shadow-sm font-semibold"
                    : isLight
                    ? "text-slate-600 hover:text-slate-900"
                    : "text-[#94a3b8] hover:text-white"
                }`}
              >
                Todas ({obras.length})
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("concorrencia");
                  setCurrentPage(1);
                }}
                className={`px-3 py-1 rounded-md transition cursor-pointer ${
                  activeTab === "concorrencia"
                    ? isLight
                      ? "bg-white text-slate-900 shadow-xs font-bold"
                      : "bg-[#1e2430] text-white shadow-sm font-semibold"
                    : isLight
                    ? "text-slate-600 hover:text-slate-900"
                    : "text-[#94a3b8] hover:text-white"
                }`}
              >
                Concorrência
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("pregao");
                  setCurrentPage(1);
                }}
                className={`px-3 py-1 rounded-md transition cursor-pointer ${
                  activeTab === "pregao"
                    ? isLight
                      ? "bg-white text-slate-900 shadow-xs font-bold"
                      : "bg-[#1e2430] text-white shadow-sm font-semibold"
                    : isLight
                    ? "text-slate-600 hover:text-slate-900"
                    : "text-[#94a3b8] hover:text-white"
                }`}
              >
                Pregão
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("acima_1m");
                  setCurrentPage(1);
                }}
                className={`px-3 py-1 rounded-md transition cursor-pointer ${
                  activeTab === "acima_1m"
                    ? isLight
                      ? "bg-white text-slate-900 shadow-xs font-bold"
                      : "bg-[#1e2430] text-white shadow-sm font-semibold"
                    : isLight
                    ? "text-slate-600 hover:text-slate-900"
                    : "text-[#94a3b8] hover:text-white"
                }`}
              >
                &gt; R$ 1 Milhão
              </button>
            </div>

            {/* Dropdown de UF */}
            <div className="relative">
              <select
                value={selectedUf}
                onChange={(e) => {
                  setSelectedUf(e.target.value);
                  setCurrentPage(1);
                }}
                className={`px-3 py-1.5 border rounded-lg text-xs font-medium cursor-pointer ${
                  isLight
                    ? "bg-white border-slate-300 text-slate-800 focus:border-blue-500 shadow-xs"
                    : "bg-[#14171d] border-[#202530] text-white focus:border-[#3b82f6]"
                }`}
              >
                {ESTADOS_BRASIL.map((uf) => (
                  <option
                    key={uf.sigla}
                    value={uf.sigla}
                    className={isLight ? "bg-white text-slate-800" : "bg-[#14171d] text-white"}
                  >
                    {uf.nome}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {showStatus && (
          <div
            role={statusInfo?.status === "erro" ? "alert" : "status"}
            aria-live="polite"
            className={`rounded-lg border px-4 py-3 text-xs ${
              statusInfo?.status === "erro"
                ? isLight
                  ? "border-red-200 bg-red-50 text-red-700"
                  : "border-red-500/30 bg-red-500/10 text-red-300"
                : isLight
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-amber-500/30 bg-amber-500/10 text-amber-200"
            }`}
          >
            <strong className="font-semibold">
              {statusInfo?.status === "erro" ? "Falha na busca" : isOffline ? "Modo offline" : hasPageErrors ? "Busca parcial" : "Limite de consulta"}
            </strong>{" "}
            <span>{statusMessage}</span>
          </div>
        )}

        {/* 5. TABELA DE LICITAÇÕES */}
        <div
          className={`border rounded-xl overflow-hidden shadow-sm transition-colors ${
            isLight ? "bg-white border-slate-200" : "bg-[#14171d] border-[#202530]"
          }`}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr
                  className={`border-b text-[10px] font-bold uppercase tracking-wider ${
                    isLight
                      ? "border-slate-200 text-slate-600 bg-slate-50"
                      : "border-[#202530] text-[#64748b] bg-[#111317]"
                  }`}
                >
                  <th className="py-3 px-4">Licitação / Órgão</th>
                  <th className="py-3 px-4 text-center">Modalidade</th>
                  <th className="py-3 px-4 text-left">Localização</th>
                  <th className="py-3 px-4 text-right">Valor Estimado</th>
                  <th className="py-3 px-4 text-right">Publicação</th>
                  <th className="py-3 px-3 text-center w-8"></th>
                </tr>
              </thead>
              <tbody className={`divide-y ${isLight ? "divide-slate-100" : "divide-[#1e222b]"}`}>
                {loading ? (
                  <tr>
                    <td colSpan={6} className={`py-12 text-center ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-amber-500" />
                      <span>Carregando dados da API PNCP...</span>
                    </td>
                  </tr>
                ) : paginatedObras.length === 0 ? (
                  <tr>
                    <td colSpan={6} className={`py-10 text-center ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                      Nenhuma licitação encontrada com os filtros selecionados.
                    </td>
                  </tr>
                ) : (
                  paginatedObras.map((obra, index) => (
                    <tr
                      key={obra.id_pncp || obra.numero_controle_pncp || `sandbox-${index}`}
                      onClick={() => setSelectedObra(obra)}
                      className={`transition-colors cursor-pointer group ${
                        isLight ? "hover:bg-slate-50" : "hover:bg-[#191d26]"
                      }`}
                    >
                      {/* Licitação / Órgão */}
                      <td className="py-3.5 px-4 max-w-sm">
                        <div className="flex items-start gap-3">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 ${getUfAvatarColor(
                              obra.uf
                            )}`}
                          >
                            {obra.uf || "BR"}
                          </div>
                          <div className="min-w-0">
                            <span
                              className={`block font-bold truncate transition-colors ${
                                isLight
                                  ? "text-slate-900 group-hover:text-blue-600"
                                  : "text-white group-hover:text-[#60a5fa]"
                              }`}
                            >
                              {obra.orgao}
                            </span>
                            <span
                              className={`block text-[11px] line-clamp-1 mt-0.5 ${
                                isLight ? "text-slate-500" : "text-[#94a3b8]"
                              }`}
                            >
                              {obra.objeto}
                            </span>
                            <span
                              className={`block text-[10px] font-mono mt-0.5 ${
                                isLight ? "text-slate-400" : "text-[#64748b]"
                              }`}
                            >
                              ID: {obra.numero_controle_pncp || obra.id_pncp}
                            </span>
                          </div>
                        </div>
                      </td>

                      {/* Modalidade */}
                      <td className="py-3.5 px-4 text-center whitespace-nowrap">
                        {getModalidadeBadge(obra.modalidade)}
                      </td>

                      {/* Localização */}
                      <td
                        className={`py-3.5 px-4 text-left whitespace-nowrap font-medium ${
                          isLight ? "text-slate-700" : "text-[#cbd5e1]"
                        }`}
                      >
                        <span className="flex items-center gap-1.5">
                          <MapPin className={`w-3.5 h-3.5 shrink-0 ${isLight ? "text-slate-400" : "text-[#64748b]"}`} />
                          <span>{obra.municipio ? `${obra.municipio} – ${obra.uf}` : obra.uf}</span>
                        </span>
                      </td>

                      {/* Valor Estimado */}
                      <td className="py-3.5 px-4 text-right font-mono font-bold text-amber-500 whitespace-nowrap">
                        {formatBRL(obra.valor_estimado)}
                      </td>

                      {/* Data Publicação */}
                      <td
                        className={`py-3.5 px-4 text-right font-mono text-[11px] whitespace-nowrap ${
                          isLight ? "text-slate-600" : "text-[#94a3b8]"
                        }`}
                      >
                        {formatDate(obra.data_publicacao)}
                      </td>

                      {/* Ação Chevron */}
                      <td
                        className={`py-3.5 px-3 text-center transition ${
                          isLight ? "text-slate-400 group-hover:text-slate-900" : "text-[#64748b] group-hover:text-white"
                        }`}
                      >
                        <ChevronRight className="w-4 h-4 opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-transform" />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Table Footer / Paginação */}
          <div
            className={`p-3 border-t flex items-center justify-between text-xs transition-colors ${
              isLight
                ? "border-slate-200 text-slate-600 bg-slate-50/50"
                : "border-[#202530] text-[#64748b]"
            }`}
          >
            <span>
              Mostrando {paginatedObras.length} de {filteredObras.length} licitação(ões)
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className={`p-1.5 rounded border transition disabled:opacity-40 disabled:cursor-not-allowed ${
                  isLight
                    ? "bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                    : "bg-[#181c24] border-[#272d3b] text-[#94a3b8] hover:text-white"
                }`}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className={`text-[11px] font-mono px-2 ${isLight ? "text-slate-700" : "text-[#94a3b8]"}`}>
                {currentPage} de {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className={`p-1.5 rounded border transition disabled:opacity-40 disabled:cursor-not-allowed ${
                  isLight
                    ? "bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                    : "bg-[#181c24] border-[#272d3b] text-[#94a3b8] hover:text-white"
                }`}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 6. NOTA DE RODAPÉ INFORMATIVA */}
        <div
          className={`p-3 rounded-lg border text-[11px] leading-relaxed flex items-center justify-between gap-4 transition-colors ${
            isLight
              ? "bg-white border-slate-200 text-slate-600 shadow-xs"
              : "bg-[#11141a] border-[#272f3d] text-[#94a3b8]"
          }`}
        >
          <div>
            <strong className={isLight ? "text-slate-900" : "text-white"}>Fonte Oficial:</strong> Dados capturados em tempo real diretamente do{" "}
            <strong className={isLight ? "text-slate-800" : "text-slate-300"}>PNCP (Portal Nacional de Contratações Públicas)</strong>, filtrando apenas licitações ativas de engenharia, construção civil e pavimentação.
          </div>
          <span className={`text-[10px] font-mono shrink-0 ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
            Período: {inicialDate} até {finalDate}
          </span>
        </div>
      </main>

      {/* 7. MODAL DE DETALHES DA OBRA (AO CLICAR NA LINHA) */}
      {selectedObra && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={() => setSelectedObra(null)}
        >
          <div
            className={`w-full max-w-2xl border rounded-2xl p-6 space-y-5 shadow-2xl transition-colors ${
              isLight ? "bg-white border-slate-200 text-slate-900" : "bg-[#14171d] border-[#272f3d] text-[#f1f5f9]"
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header Modal */}
            <div className={`flex items-start justify-between border-b pb-4 ${isLight ? "border-slate-200" : "border-[#202530]"}`}>
              <div className="flex items-start gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 ${getUfAvatarColor(
                    selectedObra.uf
                  )}`}
                >
                  {selectedObra.uf || "BR"}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                        isLight
                          ? "bg-blue-50 text-blue-700 border-blue-200"
                          : "bg-[#1e293b] text-[#93c5fd] border-[#3b82f6]/30"
                      }`}
                    >
                      <MapPin className="w-3 h-3 text-blue-500" />
                      {selectedObra.municipio ? `${selectedObra.municipio} – ${selectedObra.uf}` : selectedObra.uf}
                    </span>
                    {getModalidadeBadge(selectedObra.modalidade)}
                  </div>
                  <h3 className={`text-base font-bold ${isLight ? "text-slate-900" : "text-white"}`}>{selectedObra.orgao}</h3>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedObra(null)}
                className={`p-1.5 rounded-lg transition ${
                  isLight ? "text-slate-400 hover:text-slate-800 hover:bg-slate-100" : "text-[#64748b] hover:text-white hover:bg-[#1f242e]"
                }`}
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Grid Financeiro / Métricas do Modal */}
            <div
              className={`grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl border ${
                isLight ? "bg-slate-50 border-slate-200" : "bg-[#0f1217] border-[#202530]"
              }`}
            >
              <div>
                <span className={`text-[10px] uppercase font-bold block ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                  Valor Estimado
                </span>
                <span className="text-xl font-bold font-mono text-amber-500">
                  {formatBRL(selectedObra.valor_estimado)}
                </span>
              </div>
              <div>
                <span className={`text-[10px] uppercase font-bold block ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                  Data de Publicação
                </span>
                <span className={`text-sm font-bold font-mono mt-1 block ${isLight ? "text-slate-900" : "text-white"}`}>
                  {formatDate(selectedObra.data_publicacao)}
                </span>
              </div>
              <div className={`sm:col-span-2 pt-2 border-t ${isLight ? "border-slate-200" : "border-[#1e222b]"}`}>
                <span className={`text-[10px] uppercase font-bold block ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                  ID de Controle PNCP
                </span>
                <span className={`text-xs font-mono ${isLight ? "text-slate-700" : "text-[#94a3b8]"}`}>
                  {selectedObra.numero_controle_pncp || selectedObra.id_pncp}
                </span>
              </div>
            </div>

            {/* Objeto da Licitação na Íntegra */}
            <div className="space-y-1.5">
              <span className={`text-[10px] uppercase font-bold block ${isLight ? "text-slate-500" : "text-[#64748b]"}`}>
                Objeto da Licitação (Íntegra)
              </span>
              <div
                className={`p-3.5 rounded-xl border text-xs leading-relaxed max-h-48 overflow-y-auto font-sans ${
                  isLight ? "bg-slate-50 border-slate-200 text-slate-800" : "bg-[#0f1217] border-[#202530] text-[#cbd5e1]"
                }`}
              >
                {selectedObra.objeto}
              </div>
            </div>

            {/* Footer Modal */}
            <div className={`flex items-center justify-between pt-2 border-t ${isLight ? "border-slate-200" : "border-[#202530]"}`}>
              <button
                type="button"
                onClick={() => setSelectedObra(null)}
                className={`px-4 py-2 rounded-lg text-xs font-semibold transition ${
                  isLight
                    ? "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    : "bg-[#202530] text-white hover:bg-[#2a313e]"
                }`}
              >
                Fechar
              </button>

              {selectedObra.link_pncp && (
                <a
                  href={selectedObra.link_pncp}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 hover:brightness-110 shadow-md transition"
                >
                  <span>Abrir no Portal PNCP</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
