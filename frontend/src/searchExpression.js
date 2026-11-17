// Espelho leve da semântica do backend para filtrar o snapshot já carregado.
// Alterar filtros na tela não inicia uma nova coleta PNCP; a API continua
// sendo a fonte autoritativa para consultas diretas e paginação por cursor.
export const DEFAULT_SEARCH_SCOPE = "objeto_itens";

export const normalizeSearchText = (value) => String(value || "")
  .normalize("NFKD")
  .replace(/[\u0300-\u036f]/g, "")
  .toLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, " ")
  .replace(/\s+/g, " ")
  .trim();

export function parseSearchExpression(value) {
  const raw = String(value || "");
  const inclusoes = [];
  const exclusoes = [];
  let index = 0;

  while (index < raw.length) {
    while (index < raw.length && /\s/.test(raw[index])) index += 1;
    if (index >= raw.length) break;
    const negative = raw[index] === "-" && index + 1 < raw.length && !/\s/.test(raw[index + 1]);
    if (negative) index += 1;
    const quoted = raw[index] === '"';
    let original = "";
    if (quoted) {
      const end = raw.indexOf('"', index + 1);
      if (end < 0) break;
      original = raw.slice(index + 1, end).trim();
      index = end + 1;
    } else {
      const start = index;
      while (index < raw.length && !/\s/.test(raw[index])) index += 1;
      original = raw.slice(start, index).trim();
    }
    const normalizado = normalizeSearchText(original);
    if (!normalizado) continue;
    const term = { original, normalizado, quoted };
    (negative ? exclusoes : inclusoes).push(term);
  }
  return { inclusoes, exclusoes };
}

const stringValues = (value) => {
  if (typeof value === "string" || typeof value === "number") return [String(value)];
  if (Array.isArray(value)) return value.flatMap(stringValues);
  if (value && typeof value === "object") return Object.values(value).flatMap(stringValues);
  return [];
};

const matchesTerm = (value, term) => {
  const text = normalizeSearchText(value);
  return Boolean(text && ` ${text} `.includes(` ${term.normalizado} `));
};

function fieldValues(obra, scope) {
  const fields = {
    objeto: stringValues(obra.objeto),
    itens: stringValues(obra.itens || obra.descricao_itens),
  };
  if (scope === "objeto_itens_orgao" || scope === "todos_metadados") {
    fields.orgao = stringValues(obra.orgao);
  }
  if (scope === "todos_metadados") {
    fields.municipio = stringValues(obra.municipio);
    fields.modalidade = stringValues(obra.modalidade);
    fields.fonte = stringValues(obra.fonte);
    fields.documentos = stringValues(obra.documentos);
  }
  return fields;
}

export function evaluateSearch(obra, expression, scope = DEFAULT_SEARCH_SCOPE, mode = "qualquer") {
  const fields = fieldValues(obra, scope);
  const matches = (term) => Object.values(fields).some((values) => values.some((value) => matchesTerm(value, term)));
  const inclusoesEncontradas = expression.inclusoes.filter(matches);
  const exclusoesEncontradas = expression.exclusoes.filter(matches);
  const positivo = expression.inclusoes.length === 0
    || (mode === "todos"
      ? inclusoesEncontradas.length === expression.inclusoes.length
      : inclusoesEncontradas.length > 0);
  return {
    aprovado: positivo && exclusoesEncontradas.length === 0,
    motivo: exclusoesEncontradas.length ? "excluido_por_termo" : positivo ? "incluido" : "nao_corresponde",
    exclusoesEncontradas,
  };
}

export function removeSearchTerm(expression, chip) {
  const parsed = parseSearchExpression(expression);
  const terms = chip.tipo === "exclusao" ? parsed.exclusoes : parsed.inclusoes;
  terms.splice(chip.indice, 1);
  const serialize = (term, negative = false) => `${negative ? "-" : ""}${term.quoted || term.original.includes(" ") ? `"${term.original}"` : term.original}`;
  return [
    ...parsed.inclusoes.map((term) => serialize(term)),
    ...parsed.exclusoes.map((term) => serialize(term, true)),
  ].join(" ");
}
