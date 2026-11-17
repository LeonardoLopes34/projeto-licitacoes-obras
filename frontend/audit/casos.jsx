// Diagnóstico explícito: este caso deve falhar até a correção da navegação vazia.
import React from "react";
import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ObrasList from "../src/components/ObrasList";

it("preserva a navegação quando o filtro esvazia uma página remota", () => {
  render(
    <ObrasList
      obras={[]}
      loading={false}
      searchTerm="pavimentação"
      onSelectObra={vi.fn()}
      apiPagination={{ page: 2, hasPrevious: true, temMais: true, proximoCursor: "proxima" }}
      onLoadNextPage={vi.fn()}
      onLoadPreviousPage={vi.fn()}
    />,
  );

  expect(screen.queryByRole("button", { name: "Próxima" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Anterior" })).toBeInTheDocument();
});
