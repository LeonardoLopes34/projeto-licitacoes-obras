import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { buscarObrasProgressivamente } = vi.hoisted(() => ({
  buscarObrasProgressivamente: vi.fn(),
}));

vi.mock("./api", () => ({
  buscarObrasProgressivamente,
  cancelarBuscaAtual: vi.fn(),
}));

vi.mock("./components/Header", () => ({
  default: ({ onRefresh }) => <button type="button" onClick={onRefresh}>Atualizar Dados</button>,
}));
vi.mock("./components/FilterPanel", () => ({
  default: ({ setUfFilter, setSearchTerm }) => (
    <div>
      <button type="button" onClick={() => setUfFilter("RS")}>Filtrar UF</button>
      <button type="button" onClick={() => setSearchTerm("escola")}>Filtrar termo</button>
    </div>
  ),
}));
vi.mock("./components/StatusBar", () => ({ default: () => null }));
vi.mock("./components/MiniDashboard", () => ({ default: () => null }));
vi.mock("./components/ObrasList", () => ({ default: () => null }));
vi.mock("./components/ObraDetailModal", () => ({ default: () => null }));
vi.mock("./components/AccessibilityFooter", () => ({ default: () => null }));
vi.mock("./components/StatusBanner", () => ({ default: () => null }));

import App from "./App";

describe("App", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    buscarObrasProgressivamente.mockImplementation(async (_params, { onComplete }) => {
      onComplete({
        status: "sucesso_local",
        mensagem: "Dados locais",
        total_encontradas: 1,
        dados: [],
        metadados: { origem: "banco_local" },
      });
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("não consulta novamente ao mudar filtros e força PNCP apenas ao atualizar", async () => {
    render(<App />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });

    expect(buscarObrasProgressivamente).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Filtrar UF" }));
    fireEvent.click(screen.getByRole("button", { name: "Filtrar termo" }));
    expect(buscarObrasProgressivamente).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Atualizar Dados" }));
    expect(buscarObrasProgressivamente).toHaveBeenCalledTimes(2);
    expect(buscarObrasProgressivamente.mock.calls[1][0]).toMatchObject({
      forcar_atualizacao: true,
    });
  });
});
