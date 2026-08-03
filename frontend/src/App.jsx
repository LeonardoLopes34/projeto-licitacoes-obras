import React, { useState, useEffect } from "react";
import {
  Building2,
  Search,
  RefreshCw,
  ExternalLink,
  MapPin,
  Calendar,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  Database,
} from "lucide-react";

export default function App() {
  const [obras, setObras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusInfo, setStatusInfo] = useState(null);

  // Filtros
  const [inicialDate, setInicialDate] = useState("2026-08-01");
  const [finalDate, setFinalDate] = useState("2026-08-03");
  const [modalidade, setModalidade] = useState(8);
  const [maxPaginas, setMaxPaginas] = useState(3);
  const [forceMock, setForceMock] = useState(false);

  // Formata data YYYY-MM-DD para YYYYMMDD exigido pela API
  const formatDateForApi = (dateStr) => dateStr.replaceAll("-", "");

  const fetchObras = async () => {
    setLoading(true);
    try {
      const pInicial = formatDateForApi(inicialDate);
      const pFinal = formatDateForApi(finalDate);

      const url = `http://127.0.0.1:8000/api/v1/obras?inicial_date=${pInicial}&final_date=${pFinal}&modalidade=${modalidade}&max_paginas=${maxPaginas}&force_mock=${forceMock}`;

      const res = await fetch(url);
      const data = await res.json();

      setObras(data.dados || []);
      setStatusInfo({
        status: data.status,
        mensagem: data.mensagem,
        total: data.total_encontradas,
      });
    } catch (err) {
      console.error("Erro ao conectar no backend:", err);
      setStatusInfo({
        status: "erro",
        mensagem:
          "Erro ao conectar com a API FastAPI. Verifique se o backend está rodando.",
        total: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchObras();
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 font-sans p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* HEADER */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="bg-blue-600 p-2.5 rounded-xl shadow-lg shadow-blue-500/20">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold tracking-tight">
                Captação de Obras Publicas
              </h1>
            </div>
            <p className="text-slate-400 text-sm mt-1">
              Filtro inteligente de licitações e engenharia via PNCP
            </p>
          </div>

          <button
            onClick={fetchObras}
            disabled={loading}
            className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium transition duration-200 disabled:opacity-50 cursor-pointer shadow-lg shadow-blue-600/20"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            {loading ? "Buscando..." : "Atualizar Dados"}
          </button>
        </header>

        {/* PAINEL DE FILTROS */}
        <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-5 backdrop-blur-md">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Data Inicial
              </label>
              <input
                type="date"
                value={inicialDate}
                onChange={(e) => setInicialDate(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Data Final
              </label>
              <input
                type="date"
                value={finalDate}
                onChange={(e) => setFinalDate(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Modalidade
              </label>
              <select
                value={modalidade}
                onChange={(e) => setModalidade(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value={8}>Concorrência Eletrônica (8)</option>
                <option value={6}>Pregão (6)</option>
                <option value={4}>Dispensa (4)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                Profundidade (Páginas)
              </label>
              <select
                value={maxPaginas}
                onChange={(e) => setMaxPaginas(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500"
              >
                <option value={1}>1 Página (50 itens)</option>
                <option value={3}>3 Páginas (150 itens)</option>
                <option value={5}>5 Páginas (250 itens)</option>
              </select>
            </div>

            <div className="flex items-end">
              <label className="flex items-center gap-2 cursor-pointer bg-slate-900 border border-slate-700 w-full px-3 py-2.5 rounded-xl text-sm hover:border-slate-600 transition">
                <input
                  type="checkbox"
                  checked={forceMock}
                  onChange={(e) => setForceMock(e.target.checked)}
                  className="rounded text-blue-600 focus:ring-0 bg-slate-800 border-slate-700"
                />
                <span className="text-slate-300 font-medium">
                  Forçar Mock (Dev)
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* BARRA DE STATUS DA API */}
        {statusInfo && (
          <div
            className={`border rounded-xl p-4 flex items-center justify-between text-sm ${
              statusInfo.status.includes("sucesso_real")
                ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
                : statusInfo.status.includes("mock")
                  ? "bg-amber-950/40 border-amber-800/60 text-amber-300"
                  : "bg-rose-950/40 border-rose-800/60 text-rose-300"
            }`}
          >
            <div className="flex items-center gap-3">
              {statusInfo.status.includes("sucesso_real") ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-400" />
              )}
              <div>
                <span className="font-semibold">{statusInfo.mensagem}</span>
                <span className="opacity-75 block text-xs mt-0.5">
                  Status: {statusInfo.status}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800 font-mono text-xs">
              <Database className="w-4 h-4" />
              <span>
                Obras encontradas: <strong>{statusInfo.total}</strong>
              </span>
            </div>
          </div>
        )}

        {/* LISTA / CARDS DE OBRAS */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-400">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            <p className="text-sm">
              Varrendo a API do PNCP e aplicando filtros de engenharia...
            </p>
          </div>
        ) : obras.length === 0 ? (
          <div className="text-center py-16 bg-slate-800/30 border border-slate-800 rounded-2xl">
            <Search className="w-10 h-10 text-slate-500 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-slate-300">
              Nenhuma obra encontrada
            </h3>
            <p className="text-slate-500 text-sm mt-1">
              Tente aumentar a quantidade de páginas ou ajustar o intervalo de
              datas.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {obras.map((obra, idx) => (
              <div
                key={obra.id_pncp || idx}
                className="bg-slate-800/40 border border-slate-700/50 hover:border-blue-500/50 rounded-2xl p-5 flex flex-col justify-between transition duration-200 hover:shadow-xl hover:shadow-blue-500/5 group"
              >
                <div className="space-y-3">
                  {/* Badge da Fonte + UF/Município */}
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-xs font-semibold bg-slate-700/60 text-slate-300 px-2.5 py-1 rounded-lg">
                      <MapPin className="w-3.5 h-3.5 text-blue-400" />
                      {obra.municipio
                        ? `${obra.municipio} - ${obra.uf}`
                        : obra.uf || "Brasil"}
                    </span>

                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                        obra.fonte === "PNCP_REAL"
                          ? "bg-emerald-950 text-emerald-400 border-emerald-800/50"
                          : "bg-amber-950 text-amber-400 border-amber-800/50"
                      }`}
                    >
                      {obra.fonte}
                    </span>
                  </div>

                  {/* Órgão */}
                  <h2 className="text-sm font-bold text-slate-200 line-clamp-1 group-hover:text-blue-400 transition">
                    {obra.orgao}
                  </h2>

                  {/* Objeto */}
                  <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed">
                    {obra.objeto}
                  </p>
                </div>

                {/* FOOTER DO CARD */}
                <div className="mt-5 pt-4 border-t border-slate-700/40 flex items-center justify-between gap-2 text-xs">
                  <div>
                    <span className="text-slate-500 block text-[10px] uppercase tracking-wider font-medium">
                      Valor Estimado
                    </span>
                    <span className="font-bold text-emerald-400 text-sm flex items-center gap-0.5">
                      {obra.valor_estimado
                        ? `R$ ${obra.valor_estimado.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                        : "Não informado"}
                    </span>
                  </div>

                  {obra.link_pncp && (
                    <a
                      href={obra.link_pncp}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 bg-slate-700/50 hover:bg-blue-600 text-slate-300 hover:text-white px-3 py-1.5 rounded-lg font-medium transition duration-150"
                    >
                      Ver no PNCP
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
