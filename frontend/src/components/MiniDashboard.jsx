import React, { useMemo } from "react";
import { TrendingUp, Award, MapPin, Tag, Layers } from "lucide-react";

export default function MiniDashboard({
  obras = [],
  onSelectUf,
  onSelectModalidade,
  activeUf = "TODOS",
  activeModalidade = 0,
}) {
  // Cálculo de todas as métricas em tempo real com useMemo
  const stats = useMemo(() => {
    if (!obras || obras.length === 0) {
      return null;
    }

    let volumeTotal = 0;
    let maiorObra = null;
    const ufMap = {};
    const modMap = {
      concorrencia: { count: 0, volume: 0, nome: "Concorrência Eletrônica", code: 4 },
      pregao: { count: 0, volume: 0, nome: "Pregão Eletrônico", code: 6 },
      outros: { count: 0, volume: 0, nome: "Outras Modalidades", code: 0 },
    };

    obras.forEach((obra) => {
      const val = Number(obra.valor_estimado) || 0;
      volumeTotal += val;

      // Maior Obra
      if (!maiorObra || val > (Number(maiorObra.valor_estimado) || 0)) {
        maiorObra = obra;
      }

      // Distribuição por UF
      const uf = (obra.uf || "OUTROS").toUpperCase().trim();
      if (!ufMap[uf]) {
        ufMap[uf] = { uf, volume: 0, count: 0 };
      }
      ufMap[uf].volume += val;
      ufMap[uf].count += 1;

      // Distribuição por Modalidade
      const modNome = (obra.modalidade || "").toLowerCase();
      if (modNome.includes("concorrência") || modNome.includes("concorrencia")) {
        modMap.concorrencia.count += 1;
        modMap.concorrencia.volume += val;
      } else if (modNome.includes("pregão") || modNome.includes("pregao")) {
        modMap.pregao.count += 1;
        modMap.pregao.volume += val;
      } else {
        modMap.outros.count += 1;
        modMap.outros.volume += val;
      }
    });

    // Top 5 Estados ordenados por volume financeiro
    const topUfs = Object.values(ufMap)
      .sort((a, b) => b.volume - a.volume)
      .slice(0, 5);

    const ticketMedio = obras.length > 0 ? volumeTotal / obras.length : 0;

    return {
      volumeTotal,
      totalObras: obras.length,
      ticketMedio,
      maiorObra,
      topUfs,
      modMap,
    };
  }, [obras]);

  if (!stats) return null;

  const formatCurrency = (val) =>
    `R$ ${(val || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const maxUfVolume = stats.topUfs[0]?.volume || 1;

  const totalModVolume = stats.volumeTotal || 1;
  const percConcorrencia = Math.round((stats.modMap.concorrencia.volume / totalModVolume) * 100) || 0;
  const percPregao = Math.round((stats.modMap.pregao.volume / totalModVolume) * 100) || 0;

  return (
    <section
      aria-label="Painel de Estatísticas e Análise das Licitações"
      className="theme-card border rounded-2xl p-5 sm:p-6 space-y-6 transition-all animate-in fade-in slide-in-from-top-3 duration-300"
    >
      {/* CABEÇALHO DO DASHBOARD */}
      <div className="flex items-center justify-between border-b pb-3" style={{ borderColor: "var(--border-subtle)" }}>
        <div className="flex items-center gap-2.5">
          <Layers className="w-4 h-4 text-amber-500" aria-hidden="true" />
          <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>
            Visão Geral e Indicadores do Período
          </h3>
        </div>
        <span className="text-[11px] font-mono opacity-70" style={{ color: "var(--text-muted)" }}>
          {stats.totalObras} licitações analisadas
        </span>
      </div>

      {/* LINHA 1: CARDS DE MÉTRICAS RÁPIDAS (TICKET MÉDIO & MAIOR OBRA) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Card: Ticket Médio por Obra */}
        <div
          className="p-4 rounded-xl border flex items-center gap-3.5 transition-colors"
          style={{
            backgroundColor: "var(--bg-main)",
            borderColor: "var(--border-subtle)",
          }}
        >
          <div
            className="p-3 rounded-xl flex items-center justify-center shrink-0 border"
            style={{
              backgroundColor: "var(--badge-mod-bg)",
              borderColor: "var(--badge-mod-border)",
              color: "var(--accent-amber)",
            }}
            aria-hidden="true"
          >
            <TrendingUp className="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
              Ticket Médio por Obra
            </span>
            <span className="text-base sm:text-lg font-bold font-mono text-amber-500 tracking-tight">
              {formatCurrency(stats.ticketMedio)}
            </span>
            <span className="block text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
              Média estimada por contratação
            </span>
          </div>
        </div>

        {/* Card: Maior Obra do Período */}
        {stats.maiorObra && (
          <div
            className="p-4 rounded-xl border flex items-center gap-3.5 transition-colors"
            style={{
              backgroundColor: "var(--bg-main)",
              borderColor: "var(--border-subtle)",
            }}
          >
            <div
              className="p-3 rounded-xl flex items-center justify-center shrink-0 border"
              style={{
                backgroundColor: "var(--badge-loc-bg)",
                borderColor: "var(--badge-loc-border)",
                color: "var(--badge-loc-text)",
              }}
              aria-hidden="true"
            >
              <Award className="w-5 h-5 opacity-90" />
            </div>
            <div className="min-w-0">
              <span className="block text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--text-dim)" }}>
                Maior Obra no Período
              </span>
              <span className="text-base sm:text-lg font-bold font-mono text-amber-500 tracking-tight truncate block">
                {formatCurrency(stats.maiorObra.valor_estimado)}
              </span>
              <span className="block text-[10px] truncate max-w-[260px] sm:max-w-xs" style={{ color: "var(--text-muted)" }}>
                {stats.maiorObra.orgao} ({stats.maiorObra.uf})
              </span>
            </div>
          </div>
        )}
      </div>

      {/* LINHA 2: GRÁFICOS (TOP 5 ESTADOS & DISTRIBUIÇÃO POR MODALIDADE) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
        {/* GRÁFICO 1: TOP 5 ESTADOS POR VOLUME FINANCEIRO */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5" style={{ color: "var(--text-secondary)" }}>
              <MapPin className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
              <span>Top Estados por Volume Financeiro</span>
            </h4>
            <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              Clique para filtrar
            </span>
          </div>

          <div className="space-y-2.5">
            {stats.topUfs.map((item) => {
              const perc = Math.round((item.volume / maxUfVolume) * 100);
              const isSelected = activeUf === item.uf;

              return (
                <button
                  key={item.uf}
                  type="button"
                  onClick={() => onSelectUf?.(isSelected ? "TODOS" : item.uf)}
                  title={`Filtrar obras do estado de ${item.uf}`}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer group ${
                    isSelected ? "ring-2 ring-amber-500" : "hover:border-amber-500/60"
                  }`}
                  style={{
                    backgroundColor: isSelected ? "var(--badge-mod-bg)" : "var(--bg-main)",
                    borderColor: isSelected ? "var(--accent-amber)" : "var(--border-subtle)",
                  }}
                >
                  <div className="flex items-center justify-between text-xs font-medium mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-bold px-2 py-0.5 rounded-md bg-amber-500/20 text-amber-500 font-mono text-[11px]">
                        {item.uf}
                      </span>
                      <span style={{ color: "var(--text-primary)" }}>
                        {item.count} {item.count === 1 ? "obra" : "obras"}
                      </span>
                    </div>
                    <span className="font-mono font-bold text-amber-500">
                      {formatCurrency(item.volume)}
                    </span>
                  </div>

                  {/* Barra de Progresso Proporcional */}
                  <div className="w-full bg-slate-800/40 dark:bg-slate-800/60 h-2 rounded-full overflow-hidden border border-slate-700/30">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-500 to-amber-400 transition-all duration-500"
                      style={{ width: `${Math.max(perc, 6)}%` }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* GRÁFICO 2: DISTRIBUIÇÃO POR MODALIDADE */}
        <div className="space-y-3 flex flex-col justify-between">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 mb-3" style={{ color: "var(--text-secondary)" }}>
              <Tag className="w-3.5 h-3.5 text-amber-500" aria-hidden="true" />
              <span>Distribuição por Modalidade</span>
            </h4>

            {/* Barra Bipartida de Proporção */}
            <div className="space-y-2">
              <div className="w-full h-3 rounded-full overflow-hidden flex border" style={{ borderColor: "var(--border-subtle)" }}>
                <div
                  className="h-full bg-amber-500 transition-all duration-500"
                  style={{ width: `${percConcorrencia}%` }}
                  title={`Concorrência Eletrônica: ${percConcorrencia}%`}
                />
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${percPregao}%` }}
                  title={`Pregão Eletrônico: ${percPregao}%`}
                />
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono pt-1" style={{ color: "var(--text-muted)" }}>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  Concorrência ({percConcorrencia}%)
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  Pregão ({percPregao}%)
                </span>
              </div>
            </div>
          </div>

          {/* Cards Interativos das Modalidades */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
            {/* Card Concorrência */}
            <button
              type="button"
              onClick={() => onSelectModalidade?.(activeModalidade === 4 ? 0 : 4)}
              className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                activeModalidade === 4 ? "ring-2 ring-amber-500" : "hover:border-amber-500/60"
              }`}
              style={{
                backgroundColor: activeModalidade === 4 ? "var(--badge-mod-bg)" : "var(--bg-main)",
                borderColor: activeModalidade === 4 ? "var(--accent-amber)" : "var(--border-subtle)",
              }}
            >
              <div className="flex items-center justify-between text-[11px] font-bold text-amber-500">
                <span>CONCORRÊNCIA</span>
                <span className="font-mono">{stats.modMap.concorrencia.count} obras</span>
              </div>
              <div className="text-sm font-bold font-mono mt-1" style={{ color: "var(--text-primary)" }}>
                {formatCurrency(stats.modMap.concorrencia.volume)}
              </div>
            </button>

            {/* Card Pregão */}
            <button
              type="button"
              onClick={() => onSelectModalidade?.(activeModalidade === 6 ? 0 : 6)}
              className={`p-3.5 rounded-xl border text-left transition-all cursor-pointer ${
                activeModalidade === 6 ? "ring-2 ring-emerald-500" : "hover:border-emerald-500/60"
              }`}
              style={{
                backgroundColor: activeModalidade === 6 ? "var(--status-success-bg)" : "var(--bg-main)",
                borderColor: activeModalidade === 6 ? "var(--status-success-border)" : "var(--border-subtle)",
              }}
            >
              <div className="flex items-center justify-between text-[11px] font-bold text-emerald-500">
                <span>PREGÃO ELETRÔNICO</span>
                <span className="font-mono">{stats.modMap.pregao.count} obras</span>
              </div>
              <div className="text-sm font-bold font-mono mt-1" style={{ color: "var(--text-primary)" }}>
                {formatCurrency(stats.modMap.pregao.volume)}
              </div>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
