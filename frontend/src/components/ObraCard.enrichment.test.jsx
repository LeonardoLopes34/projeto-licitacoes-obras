import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { buscarTipoContratacao } from "../api";
import ObraCard from "./ObraCard";

vi.mock("../api", () => ({
  buscarTipoContratacao: vi.fn(),
}));

describe("ObraCard - tipo publicado nos itens", () => {
  it("substitui a modalidade resumida pelo tipo composto do PNCP", async () => {
    buscarTipoContratacao.mockResolvedValue({
      criterio_julgamento: "Menor preço",
      tipo_contratacao: "Concorrência por Menor Preço - Menor Preço",
    });

    render(
      <ObraCard
        obra={{
          id_pncp: "87897740000150-1-000157/2026",
          cnpj: "87897740000150",
          ano: 2026,
          sequencial: 157,
          orgao: "Município de Santiago",
          municipio: "Santiago",
          uf: "RS",
          modalidade: "Concorrência - Eletrônica",
          tipo_instrumento: "Edital",
          tipo_contratacao: "Concorrência - Eletrônica",
        }}
        onSelect={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(
        screen.getByLabelText("Tipo: Concorrência por Menor Preço - Menor Preço"),
      ).toBeInTheDocument();
    });
    expect(buscarTipoContratacao).toHaveBeenCalledWith(
      expect.objectContaining({
        cnpj: "87897740000150",
        ano: 2026,
        sequencial: 157,
        modalidade: "Concorrência - Eletrônica",
      }),
    );
  });
});
