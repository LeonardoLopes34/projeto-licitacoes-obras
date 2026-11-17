import { describe, expect, it } from "vitest";
import { evaluateSearch, parseSearchExpression } from "./searchExpression";

describe("expressão de busca local", () => {
  it("inclui pavimentação e exclui drenagem por palavra normalizada", () => {
    const expression = parseSearchExpression('pavimentacao -"registro de preços" -drenagem');
    expect(evaluateSearch({ objeto: "Pavimentação de vias" }, expression).aprovado).toBe(true);
    expect(evaluateSearch({ objeto: "Pavimentação com drenagem" }, expression).motivo).toBe("excluido_por_termo");
    expect(evaluateSearch({ objeto: "Registro de preços para pavimentação" }, expression).aprovado).toBe(false);
  });

  it("não usa órgão no escopo padrão", () => {
    const expression = parseSearchExpression("engenharia");
    const obra = { objeto: "Aquisição de uniformes", orgao: "Secretaria de Engenharia" };
    expect(evaluateSearch(obra, expression).aprovado).toBe(false);
    expect(evaluateSearch(obra, expression, "objeto_itens_orgao").aprovado).toBe(true);
  });
});
