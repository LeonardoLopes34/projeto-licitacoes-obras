import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ObrasList from "./ObrasList";

vi.mock("./ObraCard", () => ({
  default: ({ obra }) => <article>{obra.orgao}</article>,
}));
vi.mock("./ObrasSkeleton", () => ({ default: () => <div>Carregando</div> }));

const obras = Array.from({ length: 16 }, (_, index) => ({
  id_pncp: `obra-${index + 1}`,
  orgao: `Órgão ${index + 1}`,
}));

describe("ObrasList", () => {
  beforeEach(() => {
    window.scrollTo.mockClear();
  });

  it("pagina localmente em blocos de quinze e retorna ao topo", () => {
    render(<ObrasList obras={obras} loading={false} searchTerm="" onSelectObra={vi.fn()} />);

    expect(screen.getByText("Órgão 15")).toBeInTheDocument();
    expect(screen.queryByText("Órgão 16")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));

    expect(screen.getByText("Órgão 16")).toBeInTheDocument();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });

  it("solicita a próxima página remota pelo cursor e retorna ao topo", () => {
    const onLoadNextPage = vi.fn();
    render(
      <ObrasList
        obras={obras.slice(0, 15)}
        loading={false}
        searchTerm=""
        onSelectObra={vi.fn()}
        apiPagination={{ page: 1, temMais: true, proximoCursor: "cursor-seguro" }}
        onLoadNextPage={onLoadNextPage}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));

    expect(onLoadNextPage).toHaveBeenCalledWith("cursor-seguro");
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
  });
});
