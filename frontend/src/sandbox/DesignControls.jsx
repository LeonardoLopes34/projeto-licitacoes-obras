import React, { useState } from "react";
import {
  Palette,
  Layout,
  Database,
  Code2,
  X,
  RotateCcw,
  Copy,
  Check,
  Sliders,
  Sun,
  Moon,
} from "lucide-react";
import { MOCK_SCENARIOS } from "./mockData";
import { PRESET_THEMES, ACCENT_COLORS } from "./themeConstants";

export default function DesignControls({
  isOpen,
  onClose,
  config,
  onChangeConfig,
  currentScenario,
  onSelectScenario,
  onResetAll,
}) {
  const [activeTab, setActiveTab] = useState("theme");
  const [copied, setCopied] = useState(false);

  const handleCopyConfig = () => {
    const cssVars = `
/* Configuração exportada do Sandbox Studio */
:root {
  --theme-base: "${config.theme}";
  --primary-color: "${config.accentColor}";
  --card-style: "${config.cardStyle}";
  --border-radius: "${config.borderRadius}px";
  --grid-columns: ${config.gridCols};
  --layout-density: "${config.density}";
  --font-scale: ${config.fontScale};
}
    `.trim();

    navigator.clipboard.writeText(cssVars);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <aside
      role="dialog"
      aria-label="Painel de Personalização Visual e Mocks"
      className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 md:w-[420px] bg-slate-900/95 backdrop-blur-xl border-l border-slate-700/80 shadow-2xl flex flex-col text-slate-100 animate-in slide-in-from-right duration-200"
    >
      {/* HEADER DO PAINEL */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/30">
            <Sliders className="w-5 h-5" aria-hidden="true" />
          </div>
          <div>
            <h2 className="font-bold text-sm text-slate-100 flex items-center gap-1.5">
              Design & Mock Studio
              <span className="text-[10px] bg-blue-600 text-white font-mono px-1.5 py-0.5 rounded">
                SANDBOX
              </span>
            </h2>
            <p className="text-xs text-slate-400">Ajuste temas, cores e cenários ao vivo</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar painel de personalização"
          className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition cursor-pointer"
        >
          <X className="w-5 h-5" aria-hidden="true" />
        </button>
      </div>

      {/* ABAS DO PAINEL */}
      <div className="flex border-b border-slate-800 bg-slate-950/30 text-xs font-medium">
        <button
          type="button"
          onClick={() => setActiveTab("theme")}
          className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 transition border-b-2 ${
            activeTab === "theme"
              ? "border-blue-500 text-blue-400 bg-slate-800/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Palette className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Temas & Cores</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("layout")}
          className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 transition border-b-2 ${
            activeTab === "layout"
              ? "border-blue-500 text-blue-400 bg-slate-800/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Layout className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Layout</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("mocks")}
          className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 transition border-b-2 ${
            activeTab === "mocks"
              ? "border-blue-500 text-blue-400 bg-slate-800/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Database className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Mocks</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("export")}
          className={`flex-1 py-3 px-2 flex items-center justify-center gap-1.5 transition border-b-2 ${
            activeTab === "export"
              ? "border-blue-500 text-blue-400 bg-slate-800/40"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Code2 className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Exportar</span>
        </button>
      </div>

      {/* CONTEÚDO SCROLLÁVEL */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 text-sm">
        {/* ABA 1: TEMAS & CORES */}
        {activeTab === "theme" && (
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Temas Visuais Predefinidos
              </label>
              <div className="grid grid-cols-2 gap-2.5">
                {PRESET_THEMES.map((theme) => {
                  const isSelected = config.theme === theme.id;
                  return (
                    <button
                      key={theme.id}
                      type="button"
                      onClick={() => onChangeConfig({ ...config, theme: theme.id })}
                      className={`p-3 rounded-xl border text-left transition relative flex flex-col justify-between min-h-[78px] ${
                        isSelected
                          ? "border-blue-500 ring-2 ring-blue-500/30 bg-slate-800"
                          : "border-slate-700/80 hover:border-slate-600 bg-slate-800/50"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="font-semibold text-xs text-slate-200">
                          {theme.name}
                        </span>
                        {theme.isDark ? (
                          <Moon className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                        ) : (
                          <Sun className="w-3.5 h-3.5 text-amber-400" aria-hidden="true" />
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-2">
                        <span
                          className="w-4 h-4 rounded-full border border-slate-600 shadow-sm"
                          style={{ backgroundColor: theme.bg }}
                        />
                        <span
                          className="w-4 h-4 rounded-full border border-slate-600 shadow-sm"
                          style={{ backgroundColor: theme.surface }}
                        />
                        <span className="text-[10px] text-slate-400 ml-auto">
                          {theme.isDark ? "Dark" : "Light"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* PALETA DE COR PRIMÁRIA (ACCENT) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Cor de Destaque / Ação Primária
              </label>
              <div className="grid grid-cols-3 gap-2">
                {ACCENT_COLORS.map((color) => {
                  const isSelected = config.accentColor === color.hex;
                  return (
                    <button
                      key={color.id}
                      type="button"
                      onClick={() => onChangeConfig({ ...config, accentColor: color.hex, accentGlow: color.glow })}
                      className={`p-2.5 rounded-xl border flex items-center gap-2 transition ${
                        isSelected
                          ? "border-white ring-2 ring-blue-400/40 bg-slate-800"
                          : "border-slate-700 hover:border-slate-600 bg-slate-800/40"
                      }`}
                    >
                      <span
                        className="w-4 h-4 rounded-full shrink-0 shadow"
                        style={{ backgroundColor: color.hex }}
                      />
                      <span className="text-xs text-slate-200 font-medium truncate">
                        {color.name}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Seletor Customizado HEX */}
              <div className="mt-3 flex items-center gap-3 bg-slate-800/60 p-2.5 rounded-xl border border-slate-700">
                <input
                  type="color"
                  value={config.accentColor}
                  onChange={(e) => onChangeConfig({ ...config, accentColor: e.target.value, accentGlow: `${e.target.value}40` })}
                  className="w-8 h-8 rounded-lg cursor-pointer border-0 bg-transparent"
                />
                <div className="flex-1">
                  <span className="text-xs text-slate-400 block font-mono">HEX Personalizado</span>
                  <input
                    type="text"
                    value={config.accentColor}
                    onChange={(e) => onChangeConfig({ ...config, accentColor: e.target.value })}
                    className="bg-transparent text-xs font-mono font-bold text-white focus:outline-none uppercase"
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ABA 2: LAYOUT & CARDS */}
        {activeTab === "layout" && (
          <div className="space-y-5">
            {/* Estilo dos Cards */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Estilo Visual dos Cards de Obras
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: "glass", label: "Glassmorphism" },
                  { id: "elevated", label: "Elevado" },
                  { id: "flat", label: "Minimal Flat" },
                ].map((style) => (
                  <button
                    key={style.id}
                    type="button"
                    onClick={() => onChangeConfig({ ...config, cardStyle: style.id })}
                    className={`p-2.5 rounded-xl border text-center transition ${
                      config.cardStyle === style.id
                        ? "border-blue-500 bg-slate-800 text-white ring-1 ring-blue-500"
                        : "border-slate-700 bg-slate-800/40 text-slate-300 hover:border-slate-600"
                    }`}
                  >
                    <span className="text-xs font-semibold block">{style.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Arredondamento (Border Radius) */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Arredondamento de Bordas
                </label>
                <span className="text-xs font-mono text-blue-400 font-bold">
                  {config.borderRadius}px
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { val: 4, label: "Reto (4px)" },
                  { val: 12, label: "Médio (12px)" },
                  { val: 16, label: "Padrão (16px)" },
                  { val: 24, label: "Redondo (24px)" },
                ].map((item) => (
                  <button
                    key={item.val}
                    type="button"
                    onClick={() => onChangeConfig({ ...config, borderRadius: item.val })}
                    className={`py-2 px-1 text-center rounded-lg border text-xs transition font-medium ${
                      config.borderRadius === item.val
                        ? "border-blue-500 bg-blue-600/20 text-white"
                        : "border-slate-700 bg-slate-800/40 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Colunas do Grid */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Colunas da Listagem
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { cols: 1, label: "1 Coluna (Lista Única)" },
                  { cols: 2, label: "2 Colunas (Padrão)" },
                  { cols: 3, label: "3 Colunas (Expandido)" },
                ].map((item) => (
                  <button
                    key={item.cols}
                    type="button"
                    onClick={() => onChangeConfig({ ...config, gridCols: item.cols })}
                    className={`py-2 px-2 text-center rounded-lg border text-xs transition font-medium ${
                      config.gridCols === item.cols
                        ? "border-blue-500 bg-blue-600/20 text-white"
                        : "border-slate-700 bg-slate-800/40 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Densidade de Layout */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Densidade de Informação
              </label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { id: "compact", label: "Compacto" },
                  { id: "normal", label: "Normal" },
                  { id: "spacious", label: "Confortável" },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onChangeConfig({ ...config, density: item.id })}
                    className={`py-2 px-2 text-center rounded-lg border text-xs transition font-medium ${
                      config.density === item.id
                        ? "border-blue-500 bg-blue-600/20 text-white"
                        : "border-slate-700 bg-slate-800/40 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Escala de Fonte */}
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Escala de Texto
                </label>
                <span className="text-xs font-mono text-blue-400 font-bold">
                  {Math.round(config.fontScale * 100)}%
                </span>
              </div>
              <div className="flex gap-2">
                {[0.9, 1.0, 1.1, 1.2].map((scale) => (
                  <button
                    key={scale}
                    type="button"
                    onClick={() => onChangeConfig({ ...config, fontScale: scale })}
                    className={`flex-1 py-1.5 rounded-lg border text-xs font-mono transition ${
                      config.fontScale === scale
                        ? "border-blue-500 bg-blue-600/20 text-white font-bold"
                        : "border-slate-700 bg-slate-800/40 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    {Math.round(scale * 100)}%
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ABA 3: MOCKS & CENÁRIOS */}
        {activeTab === "mocks" && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2.5">
                Alternar Cenário de Dados Mockados
              </label>
              <div className="space-y-2.5">
                {Object.entries(MOCK_SCENARIOS).map(([key, scenario]) => {
                  const isSelected = currentScenario === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => onSelectScenario(key)}
                      className={`w-full p-3.5 rounded-xl border text-left transition flex flex-col gap-1 ${
                        isSelected
                          ? "border-blue-500 ring-2 ring-blue-500/30 bg-slate-800"
                          : "border-slate-700/80 bg-slate-800/40 hover:border-slate-600"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-slate-100">
                          {scenario.nome}
                        </span>
                        <span className="text-[10px] font-mono bg-slate-900 px-2 py-0.5 rounded text-blue-400 border border-slate-700">
                          {scenario.dados.length} obras
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2">
                        {scenario.descricao}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ABA 4: EXPORTAR CSS & CÓDIGO */}
        {activeTab === "export" && (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Tokens CSS Prontos para o Projeto
              </label>
              <p className="text-xs text-slate-400 mb-3">
                Copie o bloco de variáveis CSS abaixo para aplicar seu design customizado diretamente no arquivo <code className="text-blue-400">src/index.css</code>.
              </p>

              <pre className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 font-mono text-xs text-blue-300 overflow-x-auto leading-relaxed">
{`:root {
  --primary-color: ${config.accentColor};
  --border-radius: ${config.borderRadius}px;
  --theme-active: "${config.theme}";
  --card-style: "${config.cardStyle}";
  --grid-columns: ${config.gridCols};
  --density: "${config.density}";
}`}
              </pre>
            </div>

            <button
              type="button"
              onClick={handleCopyConfig}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white py-3 rounded-xl font-medium transition cursor-pointer shadow-lg shadow-blue-600/20"
            >
              {copied ? (
                <>
                  <Check className="w-4 h-4 text-emerald-300" aria-hidden="true" />
                  <span>Copiado para Área de Transferência!</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" aria-hidden="true" />
                  <span>Copiar Configuração CSS</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* FOOTER DO PAINEL COM RESET */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={onResetAll}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 py-2 px-3 rounded-lg hover:bg-slate-800 transition cursor-pointer"
        >
          <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
          <span>Restaurar Padrões</span>
        </button>

        <button
          type="button"
          onClick={onClose}
          className="bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold px-4 py-2 rounded-lg transition cursor-pointer"
        >
          Fechar Painel
        </button>
      </div>
    </aside>
  );
}
