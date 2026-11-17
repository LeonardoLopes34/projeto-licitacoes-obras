import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FilterPanel from "./FilterPanel";

function renderFilterPanel(overrides = {}) {
  const props = {
    inicialDate: "2026-09-08",
    setInicialDate: vi.fn(),
    finalDate: "2026-09-08",
    setFinalDate: vi.fn(),
    ufFilter: "TODOS",
    setUfFilter: vi.fn(),
    modalidade: 0,
    setModalidade: vi.fn(),
    sortBy: "data_desc",
    setSortBy: vi.fn(),
    incluirPavimentacao: true,
    setIncluirPavimentacao: vi.fn(),
    searchTerm: "",
    setSearchTerm: vi.fn(),
    ...overrides,
  };
  render(<FilterPanel {...props} />);
  return props;
}

describe("FilterPanel", () => {
  it("permite excluir obras de pavimentação", () => {
    const props = renderFilterPanel();
    const checkbox = screen.getByRole("checkbox", { name: "Incluir obras de pavimentação" });

    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);

    expect(props.setIncluirPavimentacao).toHaveBeenCalledWith(false);
  });

  it("mostra os termos interpretados, permite removê-los e altera o escopo", () => {
    const onRemoveTerm = vi.fn();
    const props = renderFilterPanel({
      termosInclusao: ["pavimentação"],
      termosExclusao: ["drenagem", "registro de preços"],
      onRemoveTerm,
      escopoBusca: "objeto_itens",
      setEscopoBusca: vi.fn(),
    });

    expect(screen.getByText("Incluir")).toBeInTheDocument();
    expect(screen.getAllByText("Excluir")).toHaveLength(2);
    expect(screen.getByText("registro de preços")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remover Excluir: drenagem" }));
    expect(onRemoveTerm).toHaveBeenCalledWith({ termo: "drenagem", tipo: "exclusao", indice: 0 });

    fireEvent.change(screen.getByLabelText("Escopo da busca"), { target: { value: "todos_metadados" } });
    expect(props.setEscopoBusca).toHaveBeenCalledWith("todos_metadados");
  });

  it("orienta a sintaxe de inclusão, exclusão e frases", () => {
    renderFilterPanel();

    expect(screen.getByText(/Use/i)).toHaveTextContent("Use - para excluir termos e aspas para frases.");
    expect(screen.getByPlaceholderText('Ex.: pavimentação -drenagem ou -"registro de preços"')).toHaveAttribute(
      "aria-describedby",
      "filtro-busca-ajuda",
    );
  });
});
