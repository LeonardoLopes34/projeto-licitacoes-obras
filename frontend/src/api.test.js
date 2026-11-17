import { afterEach, describe, expect, it, vi } from "vitest";
import { buscarObrasProgressivamente, cancelarBuscaAtual } from "./api";

function streamFrom(text) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

describe("buscarObrasProgressivamente", () => {
  afterEach(() => {
    cancelarBuscaAtual();
    vi.unstubAllGlobals();
  });

  it("entrega os eventos de progresso antes do resultado final", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: streamFrom(
          'event: progresso\ndata: {"tipo":"progresso","dados":[{"id_pncp":"1"}]}\n\n' +
            'event: concluido\ndata: {"tipo":"concluido","status":"sucesso_real","dados":[{"id_pncp":"1"}]}\n\n',
        ),
      }),
    );
    const progress = [];
    const complete = vi.fn();

    await buscarObrasProgressivamente(
      { inicial_date: "20260801", final_date: "20260801" },
      { onProgress: (event) => progress.push(event), onComplete: complete },
    );

    expect(progress).toEqual([{ tipo: "progresso", dados: [{ id_pncp: "1" }] }]);
    expect(complete).toHaveBeenCalledWith({
      tipo: "concluido",
      status: "sucesso_real",
      dados: [{ id_pncp: "1" }],
    });
  });
});
