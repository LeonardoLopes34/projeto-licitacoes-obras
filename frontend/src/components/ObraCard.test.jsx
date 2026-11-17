import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ObraCard from "./ObraCard";

const obraBase = {
  id_pncp: "pncp-014",
  orgao: "Prefeitura de Exemplo",
  municipio: "Recife",
  uf: "PE",
  objeto: "Execução de pavimentação urbana.",
  modalidade: "Concorrência por Menor Preço",
  valor_estimado: 1500000,
  data_publicacao: "2026-09-14",
};

describe("ObraCard", () => {
  it("exibe o tipo no topo, no lugar do antigo selo de modalidade", () => {
    render(
      <ObraCard
        obra={{ ...obraBase, tipo_contratacao: "Concorrência por Menor Preço - Menor Preço" }}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Tipo")).toBeInTheDocument();
    expect(screen.getByLabelText("Tipo: Concorrência por Menor Preço - Menor Preço")).toBeInTheDocument();
  });

  it("usa a modalidade e depois um fallback quando o tipo não foi publicado", () => {
    const { rerender } = render(<ObraCard obra={obraBase} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("Tipo: Concorrência por Menor Preço")).toBeInTheDocument();

    rerender(<ObraCard obra={{ ...obraBase, modalidade: null, objeto: null }} onSelect={vi.fn()} />);
    expect(screen.getByLabelText("Tipo: Tipo não informado")).toBeInTheDocument();
    expect(screen.getByText("Objeto não informado")).toBeInTheDocument();
  });

  it("mostra documentos compactos e o aviso de análise assistida", () => {
    render(
      <ObraCard
        obra={obraBase}
        onSelect={vi.fn()}
        analiseExigencias={{
          status: "sucesso",
          total_exigencias: 2,
          categorias: { qualificacao_tecnica: 2 },
          analise_assistida: true,
          documentos_exigidos: [
            { nome: "Atestado de capacidade técnica", estado: "identificado" },
            { nome: "Declaração técnica", estado: "incerto" },
          ],
        }}
      />,
    );

    expect(screen.getByText("Análise assistida · confira as fontes no detalhe")).toBeInTheDocument();
    expect(screen.getByText("Atestado de capacidade técnica")).toBeInTheDocument();
    expect(screen.getByText("Declaração técnica (revisar)")).toBeInTheDocument();
  });
});
