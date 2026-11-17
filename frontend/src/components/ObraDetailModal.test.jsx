import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import ObraDetailModal from "./ObraDetailModal";

vi.mock("./ObraDocumentAnalysisSections", () => ({
  DocumentosSection: () => <div>Documentos preservados</div>,
  ExigenciasSection: () => <div>Exigências preservadas</div>,
}));

const obra = {
  id_pncp: "pncp-014",
  orgao: "Prefeitura de Exemplo",
  objeto: "Execução de pavimentação urbana.",
  modalidade: "Concorrência por Menor Preço",
  criterio_julgamento: "Menor Preço",
  tipo_instrumento: "Edital",
  tipo_contratacao: "Concorrência por Menor Preço - Menor Preço",
  tipo_contratacao_origem: ["modalidade", "criterio_julgamento"],
};

describe("ObraDetailModal", () => {
  afterEach(() => {
    document.body.style.overflow = "";
  });

  it("mostra os campos atômicos que explicam o tipo exibido no card", () => {
    render(<ObraDetailModal obra={obra} onClose={vi.fn()} onAnalysisComplete={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Tipo da contratação" })).toBeInTheDocument();
    expect(screen.getByText("Concorrência por Menor Preço - Menor Preço")).toBeInTheDocument();
    expect(screen.getByText("Critério de julgamento")).toBeInTheDocument();
    expect(screen.getByText("Menor Preço")).toBeInTheDocument();
    expect(screen.getByText("Tipo de instrumento")).toBeInTheDocument();
    expect(screen.getByText("Edital")).toBeInTheDocument();
    expect(screen.getByText("modalidade, criterio_julgamento")).toBeInTheDocument();
  });

  it("mantém fallbacks explícitos para campos de tipo ausentes", () => {
    render(
      <ObraDetailModal
        obra={{ id_pncp: "sem-tipo", orgao: "Órgão sem tipo", objeto: "Objeto" }}
        onClose={vi.fn()}
        onAnalysisComplete={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Não informado").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("Não informada").length).toBeGreaterThanOrEqual(1);
  });

  it("renderiza o container do modal ampliado mantendo atributos de acessibilidade", () => {
    render(<ObraDetailModal obra={obra} onClose={vi.fn()} onAnalysisComplete={vi.fn()} />);

    const dialog = screen.getByRole("dialog", { name: "Prefeitura de Exemplo" });
    expect(dialog).toHaveAttribute("aria-modal", "true");

    const modalCard = dialog.querySelector(".theme-card");
    expect(modalCard).not.toBeNull();
    expect(modalCard.className).toContain("max-w-5xl");
    expect(modalCard.className).toContain("xl:max-w-6xl");
    expect(modalCard.className).toContain("max-h-[92vh]");
  });
});
