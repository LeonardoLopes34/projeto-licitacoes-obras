import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { buscarDocumentos } from "../api";
import { DocumentosSection, ExigenciasSection } from "./ObraDocumentAnalysisSections";

vi.mock("../api", () => ({
  buscarDocumentos: vi.fn(),
  buscarExigencias: vi.fn(),
}));

describe("DocumentosSection", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("sinaliza claramente quando os documentos vieram do cache persistente", async () => {
    buscarDocumentos.mockResolvedValue({
      status: "sucesso",
      origem: "cache_persistente",
      desatualizado: true,
      atualizado_em: "2026-09-03T12:00:00+00:00",
      documentos: [{ titulo: "Edital salvo", sequencial_documento: 1 }],
    });

    render(<DocumentosSection obra={{ cnpj: "123", ano: 2026, sequencial: 1 }} />);

    expect(await screen.findByText("Exibindo um resultado salvo anteriormente.")).toBeInTheDocument();
    expect(screen.getByText("Edital salvo")).toBeInTheDocument();
    expect(screen.getByText(/Atualizado em:/)).toBeInTheDocument();
  });

  it("mostra o motivo de falha informado para cada documento selecionado", async () => {
    const { buscarExigencias } = await import("../api");
    buscarExigencias.mockResolvedValue({
      status: "erro",
      mensagem: "Não foi possível analisar os documentos selecionados do edital.",
      documentos_analisados: [
        {
          documento_id: 1,
          titulo: "Edital compactado.zip",
          status: "erro",
          mensagem: "O pacote ZIP não possui PDF analisável.",
        },
      ],
    });

    render(<ExigenciasSection obra={{ cnpj: "123", ano: 2026, sequencial: 1 }} />);

    expect(await screen.findByText("O pacote ZIP não possui PDF analisável.")).toBeInTheDocument();
    expect(screen.getByText(/Edital compactado.zip:/)).toBeInTheDocument();
  });
});

describe("ExigenciasSection", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  const baseExigencia = {
    categoria: "declaracoes",
    rotulo: "Declaração exigida",
    documento_id: 1,
    titulo_documento: "Edital.pdf",
    url_documento: "https://pncp.gov.br/edital.pdf",
    pagina: 39,
    confianca: 0.85,
    origem_texto: "pdf_texto",
    status: "identificado_no_edital",
  };

  it("exibe a descrição resumida no card e mantém o texto original dentro da evidência", async () => {
    const { buscarExigencias } = await import("../api");
    buscarExigencias.mockResolvedValue({
      status: "sucesso",
      mensagem: "Exigências identificadas no edital.",
      exigencias: [{
        ...baseExigencia,
        descricao_resumida: "Comprovar o cumprimento das normas aplicáveis.",
        descricao_original: "d) Declaração de Atendimento e Cumprimento de Legislação e Normas Vigentes Relativas às",
        evidencia: "4.2.1 d) Declaração de Atendimento e Cumprimento de Legislação e Normas Vigentes Relativas às obras.",
      }],
    });

    render(<ExigenciasSection obra={{ cnpj: "123", ano: 2026, sequencial: 1 }} />);

    const article = await screen.findByRole("article");
    expect(within(article).getByText("Comprovar o cumprimento das normas aplicáveis.")).toBeInTheDocument();
    expect(within(article).getByText("4.2.1 d) Declaração de Atendimento e Cumprimento de Legislação e Normas Vigentes Relativas às obras.")).toBeInTheDocument();
    expect(within(article).getByText("Ver trecho original")).toBeInTheDocument();

    const evidence = article.querySelector("details");
    expect(evidence).not.toBeNull();
    expect(evidence).toContainElement(within(article).getByText("4.2.1 d) Declaração de Atendimento e Cumprimento de Legislação e Normas Vigentes Relativas às obras."));
  });

  it("mantém compatibilidade com respostas antigas sem descricao_resumida", async () => {
    const { buscarExigencias } = await import("../api");
    buscarExigencias.mockResolvedValue({
      status: "sucesso",
      mensagem: "Exigências identificadas no edital.",
      exigencias: [{
        ...baseExigencia,
        descricao_original: "Apresentar declaração de inexistência de fatos impeditivos.",
        evidencia: "7.3 Apresentar declaração de inexistência de fatos impeditivos.",
      }],
    });

    render(<ExigenciasSection obra={{ cnpj: "123", ano: 2026, sequencial: 1 }} />);

    const article = await screen.findByRole("article");
    expect(article.querySelector("p.text-xs.leading-relaxed")).toHaveTextContent("Declaração exigida");
    expect(within(article).getByText("Ver trecho original")).toBeInTheDocument();
    const evidence = article.querySelector("details");
    expect(evidence).not.toBeNull();
    expect(evidence).toContainElement(within(article).getByText("7.3 Apresentar declaração de inexistência de fatos impeditivos."));
  });

  it("permite filtrar as exigências clicando nas categorias do OCR no topo", async () => {
    const { buscarExigencias } = await import("../api");
    buscarExigencias.mockResolvedValue({
      status: "sucesso",
      mensagem: "Exigências identificadas no edital.",
      exigencias: [
        {
          ...baseExigencia,
          categoria: "declaracoes",
          rotulo: "Declaração de visita técnica",
          descricao_resumida: "Apresentar declaração de conhecimento do local da obra.",
          evidencia: "Item 8.1 Declaração de visita técnica.",
        },
        {
          ...baseExigencia,
          categoria: "qualificacao_tecnica",
          rotulo: "Registro no CREA/CAU",
          descricao_resumida: "Comprovar registro da empresa e do responsável técnico.",
          pagina: 14,
          evidencia: "Item 6.2 Registro ou inscrição na entidade profissional competente.",
        },
        {
          ...baseExigencia,
          categoria: "qualificacao_tecnica",
          rotulo: "Atestado de capacidade técnica",
          descricao_resumida: "Apresentar CAT compatível com pavimentação.",
          pagina: 15,
          evidencia: "Item 6.3 Atestado de capacidade técnico-profissional.",
        },
      ],
    });

    render(<ExigenciasSection obra={{ cnpj: "123", ano: 2026, sequencial: 1 }} />);

    const filterGroup = await screen.findByRole("group", { name: "Filtrar exigências por categoria" });
    const btnTodas = within(filterGroup).getByRole("button", { name: /Todas/i });
    const btnTecnica = within(filterGroup).getByRole("button", { name: /Qualificação técnica/i });
    const btnDeclaracoes = within(filterGroup).getByRole("button", { name: /Declarações/i });

    expect(btnTodas).toHaveAttribute("aria-pressed", "true");
    expect(btnTodas).toHaveTextContent("3");
    expect(btnTecnica).toHaveAttribute("aria-pressed", "false");
    expect(btnTecnica).toHaveTextContent("2");
    expect(btnDeclaracoes).toHaveAttribute("aria-pressed", "false");
    expect(btnDeclaracoes).toHaveTextContent("1");
    expect(screen.getAllByRole("article")).toHaveLength(3);

    fireEvent.click(btnTecnica);

    expect(btnTecnica).toHaveAttribute("aria-pressed", "true");
    expect(btnTodas).toHaveAttribute("aria-pressed", "false");
    expect(screen.getAllByRole("article")).toHaveLength(2);
    expect(screen.getByText("Registro no CREA/CAU")).toBeInTheDocument();
    expect(screen.getByText("Atestado de capacidade técnica")).toBeInTheDocument();
    expect(screen.queryByText("Declaração de visita técnica")).not.toBeInTheDocument();

    fireEvent.click(btnDeclaracoes);

    expect(btnDeclaracoes).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(screen.getByText("Declaração de visita técnica")).toBeInTheDocument();
    expect(screen.queryByText("Registro no CREA/CAU")).not.toBeInTheDocument();

    // Clicar novamente na categoria ativa restaura todas as categorias
    fireEvent.click(btnDeclaracoes);

    expect(btnTodas).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("article")).toHaveLength(3);
  });
});
