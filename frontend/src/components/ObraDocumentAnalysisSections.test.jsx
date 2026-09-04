import React from "react";
import { render, screen, within } from "@testing-library/react";
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
});
