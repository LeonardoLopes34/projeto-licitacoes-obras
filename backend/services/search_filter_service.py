"""Parser e avaliador determinístico da busca textual de obras.

O classificador de obras decide se um registro parece uma oportunidade de
construção. Este módulo é deliberadamente independente dele: interpreta os
termos digitados pela pessoa usuária e os aplica *depois* daquela decisão.
Assim, pesos internos de classificação nunca passam a ter a semântica de uma
exclusão explícita da busca.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal


SEARCH_PARSER_VERSION = "014.1"
"""Versão incluída na assinatura de consultas/snapshots pela integração."""

DEFAULT_SEARCH_SCOPE = "objeto_itens"
SEARCH_SCOPES = frozenset(
    {"objeto_itens", "objeto_itens_orgao", "todos_metadados"}
)
INCLUSION_MODES = frozenset({"qualquer", "todos"})

MAX_SEARCH_EXPRESSION_LENGTH = 1_000
MAX_SEARCH_TERMS = 20
MAX_SEARCH_TERM_LENGTH = 120

SearchScope = Literal["objeto_itens", "objeto_itens_orgao", "todos_metadados"]
InclusionMode = Literal["qualquer", "todos"]


class SearchExpressionError(ValueError):
    """Expressão de busca inválida e segura para transformar em erro 422."""

    code = "expressao_busca_invalida"


@dataclass(frozen=True)
class SearchTerm:
    """Um termo preservando a escrita recebida e sua forma de comparação."""

    original: str
    normalizado: str
    frase: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "normalizado": self.normalizado,
            "frase": self.frase,
        }


@dataclass(frozen=True)
class SearchExpression:
    """Consulta textual já validada, pronta para ser aplicada a registros."""

    inclusoes: tuple[SearchTerm, ...] = ()
    exclusoes: tuple[SearchTerm, ...] = ()
    escopo: SearchScope = DEFAULT_SEARCH_SCOPE
    modo_inclusao: InclusionMode = "qualquer"
    versao_parser: str = SEARCH_PARSER_VERSION

    @property
    def possui_termos(self) -> bool:
        return bool(self.inclusoes or self.exclusoes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "termos_inclusao": [term.normalizado for term in self.inclusoes],
            "termos_exclusao": [term.normalizado for term in self.exclusoes],
            "escopo_busca": self.escopo,
            "modo_inclusao": self.modo_inclusao,
            "versao_parser": self.versao_parser,
        }


@dataclass(frozen=True)
class SearchMatch:
    """Evidência de que um termo foi encontrado em um campo pesquisável."""

    termo: str
    campo: str
    trecho: str
    tipo: Literal["inclusao", "exclusao"]

    def as_dict(self) -> dict[str, str]:
        return {
            "termo": self.termo,
            "campo": self.campo,
            "trecho": self.trecho,
            "tipo": self.tipo,
        }


@dataclass(frozen=True)
class SearchEvaluation:
    """Decisão auditável de busca para um único registro normalizado."""

    aprovado: bool
    motivo_filtro: str
    termos_correspondentes: tuple[str, ...] = ()
    campos_correspondentes: tuple[str, ...] = ()
    termos_excluidos: tuple[str, ...] = ()
    campos_excluidos: tuple[str, ...] = ()
    correspondencias: tuple[SearchMatch, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "termos_correspondentes": list(self.termos_correspondentes),
            "campos_correspondentes": list(self.campos_correspondentes),
            "termos_excluidos": list(self.termos_excluidos),
            "campos_excluidos": list(self.campos_excluidos),
            "motivo_filtro": self.motivo_filtro,
            "correspondencias": [match.as_dict() for match in self.correspondencias],
        }


@dataclass(frozen=True)
class SearchAudit:
    """Contagens agregadas; não carrega os registros que foram excluídos."""

    total_avaliado: int = 0
    total_incluido: int = 0
    total_excluido_por_termo: int = 0
    total_sem_correspondencia: int = 0
    total_rejeitado_classificacao: int = 0
    total_revisao_pendente: int = 0
    campos_correspondentes: dict[str, int] = field(default_factory=dict)

    def as_dict(self, expression: SearchExpression) -> dict[str, Any]:
        return {
            **expression.as_dict(),
            "contagens_busca": {
                "total_avaliado": self.total_avaliado,
                "total_incluido": self.total_incluido,
                "total_excluido_por_termo": self.total_excluido_por_termo,
                "total_sem_correspondencia": self.total_sem_correspondencia,
                "total_rejeitado_classificacao": self.total_rejeitado_classificacao,
                "total_revisao_pendente": self.total_revisao_pendente,
            },
            "campos_correspondentes": dict(self.campos_correspondentes),
        }


@dataclass(frozen=True)
class SearchFilterResult:
    """Registros aprovados e metadados para a resposta, sem itens excluídos."""

    registros: tuple[dict[str, Any], ...]
    auditoria: SearchAudit

    def metadados(self, expression: SearchExpression) -> dict[str, Any]:
        return self.auditoria.as_dict(expression)


def normalizar_texto_busca(texto: object) -> str:
    """Normaliza Unicode, acentos, pontuação e espaços para comparação.

    O texto de origem não é alterado. A forma normalizada usa espaços entre
    palavras para permitir limites de palavra e frases contíguas previsíveis.
    """

    decomposed = unicodedata.normalize("NFKD", str(texto or ""))
    sem_acentos = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", re.sub(r"[\W_]+", " ", sem_acentos.lower())).strip()


def termo_corresponde(texto: object, termo: SearchTerm | str) -> bool:
    """Compara por palavra inteira ou frase inteira, nunca por substring."""

    term_normalized = (
        termo.normalizado if isinstance(termo, SearchTerm) else normalizar_texto_busca(termo)
    )
    text_normalized = normalizar_texto_busca(texto)
    if not term_normalized or not text_normalized:
        return False
    return re.search(
        rf"(?:^|\s){re.escape(term_normalized)}(?=\s|$)", text_normalized
    ) is not None


def parse_search_expression(
    termo: str | None,
    *,
    escopo_busca: str = DEFAULT_SEARCH_SCOPE,
    modo_inclusao: str = "qualquer",
) -> SearchExpression:
    """Interpreta a expressão legada ``termo`` com aspas e prefixo ``-``.

    O hífen só tem significado no início de um token. Em ``obra-de-arte`` ele
    é pontuação interna e o termo continua sendo de inclusão.
    """

    _validate_options(escopo_busca, modo_inclusao)
    raw_expression = str(termo or "")
    _validate_expression_length(raw_expression)
    inclusoes: list[SearchTerm] = []
    exclusoes: list[SearchTerm] = []
    index = 0

    while index < len(raw_expression):
        while index < len(raw_expression) and raw_expression[index].isspace():
            index += 1
        if index >= len(raw_expression):
            break

        negative = raw_expression[index] == "-"
        if negative:
            index += 1
            if index >= len(raw_expression) or raw_expression[index].isspace():
                raise SearchExpressionError("termo de exclusão vazio")

        quoted = index < len(raw_expression) and raw_expression[index] == '"'
        if quoted:
            index += 1
            end = raw_expression.find('"', index)
            if end == -1:
                raise SearchExpressionError("aspas sem fechamento na expressão de busca")
            token = raw_expression[index:end]
            index = end + 1
            if index < len(raw_expression) and not raw_expression[index].isspace():
                raise SearchExpressionError("após aspas deve haver um espaço entre termos")
        else:
            start = index
            while index < len(raw_expression) and not raw_expression[index].isspace():
                if raw_expression[index] == '"':
                    raise SearchExpressionError("aspas só podem delimitar uma frase completa")
                index += 1
            token = raw_expression[start:index]

        term = _create_term(token, frase=quoted)
        (exclusoes if negative else inclusoes).append(term)

    return _build_expression(inclusoes, exclusoes, escopo_busca, modo_inclusao)


def parse_search_request(
    termo: str | None = None,
    *,
    termos_inclusao: Sequence[str] | None = None,
    termos_exclusao: Sequence[str] | None = None,
    escopo_busca: str = DEFAULT_SEARCH_SCOPE,
    modo_inclusao: str = "qualquer",
) -> SearchExpression:
    """Aceita a expressão legada ou as listas estruturadas, sem ambiguidade.

    Quando ``termo`` e qualquer lista estruturada possuem conteúdo, a chamada
    é rejeitada. Isso impede duplicar ou mudar silenciosamente a consulta.
    """

    _validate_options(escopo_busca, modo_inclusao)
    has_legacy_term = bool(str(termo or "").strip())
    has_structured_terms = bool(termos_inclusao or termos_exclusao)
    if has_legacy_term and has_structured_terms:
        raise SearchExpressionError(
            "use termo ou listas estruturadas de inclusão/exclusão, não ambos"
        )
    if has_legacy_term:
        return parse_search_expression(
            termo,
            escopo_busca=escopo_busca,
            modo_inclusao=modo_inclusao,
        )

    inclusoes = _parse_structured_terms(termos_inclusao, "inclusão")
    exclusoes = _parse_structured_terms(termos_exclusao, "exclusão")
    return _build_expression(inclusoes, exclusoes, escopo_busca, modo_inclusao)


def avaliar_busca(
    registro: Mapping[str, Any],
    expressao: SearchExpression,
    *,
    status_classificacao: str | None = None,
) -> SearchEvaluation:
    """Aplica inclusão/exclusão ao registro já normalizado.

    ``rejeitado`` pela classificação encerra a avaliação antes da expressão.
    ``revisao_pendente`` continua elegível, mas fica explícito no motivo caso
    não seja removido por uma exclusão textual do usuário.
    """

    status = str(
        status_classificacao if status_classificacao is not None else registro.get("status_classificacao") or "aprovado"
    ).strip().lower()
    if status == "rejeitado":
        return SearchEvaluation(aprovado=False, motivo_filtro="rejeitado")

    fields = extrair_campos_busca(registro, expressao.escopo)
    inclusion_matches = _matches_for_terms(
        fields, expressao.inclusoes, tipo="inclusao"
    )
    exclusion_matches = _matches_for_terms(
        fields, expressao.exclusoes, tipo="exclusao"
    )
    positive_terms = _unique(match.termo for match in inclusion_matches)
    positive_fields = _unique(match.campo for match in inclusion_matches)
    negative_terms = _unique(match.termo for match in exclusion_matches)
    negative_fields = _unique(match.campo for match in exclusion_matches)

    if exclusion_matches:
        return SearchEvaluation(
            aprovado=False,
            motivo_filtro="excluido_por_termo",
            termos_correspondentes=positive_terms,
            campos_correspondentes=positive_fields,
            termos_excluidos=negative_terms,
            campos_excluidos=negative_fields,
            correspondencias=tuple(inclusion_matches + exclusion_matches),
        )

    matched_inclusions = {match.termo for match in inclusion_matches}
    has_required_inclusions = not expressao.inclusoes or (
        bool(matched_inclusions)
        if expressao.modo_inclusao == "qualquer"
        else len(matched_inclusions) == len(expressao.inclusoes)
    )
    if not has_required_inclusions:
        return SearchEvaluation(
            aprovado=False,
            motivo_filtro="nao_corresponde_termo",
            termos_correspondentes=positive_terms,
            campos_correspondentes=positive_fields,
            correspondencias=tuple(inclusion_matches),
        )

    if status == "revisao_pendente":
        motivo = "revisao_pendente"
    elif expressao.inclusoes:
        motivo = "incluido_por_termo"
    elif expressao.exclusoes:
        motivo = "incluido_apos_exclusao"
    else:
        motivo = "sem_filtro"
    return SearchEvaluation(
        aprovado=True,
        motivo_filtro=motivo,
        termos_correspondentes=positive_terms,
        campos_correspondentes=positive_fields,
        correspondencias=tuple(inclusion_matches),
    )


def aplicar_busca(
    registros: Sequence[Mapping[str, Any]],
    expressao: SearchExpression,
    *,
    anexar_metadados: bool = False,
) -> SearchFilterResult:
    """Retorna somente aprovados e as contagens para os metadados da consulta.

    Com ``anexar_metadados=True``, cada cópia aprovada recebe
    ``metadados_busca``. Os registros excluídos nunca são incluídos no retorno.
    """

    aprovados: list[dict[str, Any]] = []
    fields_counter: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    for registro in registros:
        evaluation = avaliar_busca(registro, expressao)
        counts["total_avaliado"] += 1
        if evaluation.motivo_filtro == "rejeitado":
            counts["total_rejeitado_classificacao"] += 1
        elif evaluation.motivo_filtro == "revisao_pendente":
            counts["total_revisao_pendente"] += 1
        elif evaluation.motivo_filtro == "excluido_por_termo":
            counts["total_excluido_por_termo"] += 1
        elif evaluation.motivo_filtro == "nao_corresponde_termo":
            counts["total_sem_correspondencia"] += 1

        if not evaluation.aprovado:
            continue
        counts["total_incluido"] += 1
        fields_counter.update(evaluation.campos_correspondentes)
        normalized_record = dict(registro)
        if anexar_metadados:
            metadata = evaluation.as_dict()
            # Os campos explícitos são serializados no contrato ObraOut; a
            # cópia agrupada é útil a consumidores que preferem o bloco de
            # auditoria completo.
            normalized_record.update(metadata)
            normalized_record["metadados_busca"] = metadata
        aprovados.append(normalized_record)

    return SearchFilterResult(
        registros=tuple(aprovados),
        auditoria=SearchAudit(
            total_avaliado=counts["total_avaliado"],
            total_incluido=counts["total_incluido"],
            total_excluido_por_termo=counts["total_excluido_por_termo"],
            total_sem_correspondencia=counts["total_sem_correspondencia"],
            total_rejeitado_classificacao=counts["total_rejeitado_classificacao"],
            total_revisao_pendente=counts["total_revisao_pendente"],
            campos_correspondentes=dict(fields_counter),
        ),
    )


def extrair_campos_busca(
    registro: Mapping[str, Any], escopo: SearchScope = DEFAULT_SEARCH_SCOPE
) -> dict[str, tuple[str, ...]]:
    """Extrai textos dos nomes normalizados e das formas publicadas pelo PNCP."""

    if escopo not in SEARCH_SCOPES:
        raise SearchExpressionError(f"escopo_busca inválido: {escopo}")

    # Registros do banco preservam o payload PNCP para que a busca local ainda
    # alcance descrições de itens e documentos, sem expor esse payload na API.
    raw_payload = registro.get("payload_original")
    searchable_record: Mapping[str, Any] = (
        {**raw_payload, **registro} if isinstance(raw_payload, Mapping) else registro
    )

    fields: dict[str, tuple[str, ...]] = {
        "objeto": _values_for_aliases(searchable_record, ("objeto", "objetoCompra", "descricao_objeto")),
        "itens": _values_for_aliases(
            searchable_record,
            ("itens", "items", "descricao_itens", "descricaoItens", "itensCompra"),
        ),
    }
    if escopo in {"objeto_itens_orgao", "todos_metadados"}:
        fields["orgao"] = _values_for_aliases(
            searchable_record, ("orgao", "razao_social", "razaoSocial")
        ) + _nested_values(
            searchable_record, "orgaoEntidade", ("razaoSocial", "razao_social", "nome")
        )
    if escopo == "todos_metadados":
        fields.update(
            {
                "municipio": _values_for_aliases(searchable_record, ("municipio", "municipioNome"))
                + _nested_values(searchable_record, "unidadeOrgao", ("municipioNome", "municipio")),
                "modalidade": _values_for_aliases(
                    searchable_record, ("modalidade", "modalidadeNome")
                ),
                "fonte": _values_for_aliases(searchable_record, ("fonte",)),
                "documentos": _values_for_aliases(
                    searchable_record,
                    ("documentos", "documents", "documentos_texto", "descricao_documentos"),
                ),
            }
        )
    return {field: values for field, values in fields.items() if values}


def _validate_options(escopo_busca: str, modo_inclusao: str) -> None:
    if escopo_busca not in SEARCH_SCOPES:
        raise SearchExpressionError(f"escopo_busca inválido: {escopo_busca}")
    if modo_inclusao not in INCLUSION_MODES:
        raise SearchExpressionError(f"modo_inclusao inválido: {modo_inclusao}")


def _validate_expression_length(value: str) -> None:
    if len(value) > MAX_SEARCH_EXPRESSION_LENGTH:
        raise SearchExpressionError(
            f"a expressão de busca aceita no máximo {MAX_SEARCH_EXPRESSION_LENGTH} caracteres"
        )
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise SearchExpressionError("a expressão de busca contém caracteres de controle")


def _create_term(value: str, *, frase: bool) -> SearchTerm:
    original = str(value or "").strip()
    if not original:
        raise SearchExpressionError("termo de busca vazio")
    if len(original) > MAX_SEARCH_TERM_LENGTH:
        raise SearchExpressionError(
            f"cada termo aceita no máximo {MAX_SEARCH_TERM_LENGTH} caracteres"
        )
    if any(unicodedata.category(char).startswith("C") for char in original):
        raise SearchExpressionError("termo de busca contém caracteres de controle")
    normalized = normalizar_texto_busca(original)
    if not normalized:
        raise SearchExpressionError("termo de busca não contém letras ou números")
    return SearchTerm(original=original, normalizado=normalized, frase=frase or " " in normalized)


def _parse_structured_terms(
    values: Sequence[str] | None, kind: str
) -> list[SearchTerm]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise SearchExpressionError(f"termos de {kind} devem ser enviados como lista")
    terms: list[SearchTerm] = []
    for value in values:
        if not isinstance(value, str):
            raise SearchExpressionError(f"cada termo de {kind} deve ser texto")
        cleaned = value.strip()
        if cleaned.startswith("-"):
            raise SearchExpressionError(
                f"termos estruturados de {kind} não usam o prefixo '- '"
            )
        quoted = len(cleaned) >= 2 and cleaned.startswith('"') and cleaned.endswith('"')
        if '"' in cleaned and not quoted:
            raise SearchExpressionError("aspas só podem delimitar uma frase completa")
        terms.append(_create_term(cleaned[1:-1] if quoted else cleaned, frase=quoted))
    return terms


def _build_expression(
    inclusoes: Sequence[SearchTerm],
    exclusoes: Sequence[SearchTerm],
    escopo_busca: str,
    modo_inclusao: str,
) -> SearchExpression:
    _validate_options(escopo_busca, modo_inclusao)
    total = len(inclusoes) + len(exclusoes)
    if total > MAX_SEARCH_TERMS:
        raise SearchExpressionError(
            f"a busca aceita no máximo {MAX_SEARCH_TERMS} termos"
        )
    return SearchExpression(
        inclusoes=_deduplicate_terms(inclusoes),
        exclusoes=_deduplicate_terms(exclusoes),
        escopo=escopo_busca,  # type: ignore[arg-type]
        modo_inclusao=modo_inclusao,  # type: ignore[arg-type]
    )


def _deduplicate_terms(terms: Sequence[SearchTerm]) -> tuple[SearchTerm, ...]:
    seen: set[str] = set()
    return tuple(
        term
        for term in terms
        if not (term.normalizado in seen or seen.add(term.normalizado))
    )


def _matches_for_terms(
    fields: Mapping[str, Sequence[str]],
    terms: Sequence[SearchTerm],
    *,
    tipo: Literal["inclusao", "exclusao"],
) -> list[SearchMatch]:
    matches: list[SearchMatch] = []
    for term in terms:
        for field_name, values in fields.items():
            for value in values:
                if termo_corresponde(value, term):
                    matches.append(
                        SearchMatch(
                            termo=term.normalizado,
                            campo=field_name,
                            trecho=_excerpt(value, term),
                            tipo=tipo,
                        )
                    )
                    break
    return matches


def _excerpt(value: str, term: SearchTerm, limit: int = 180) -> str:
    """Preserva um trecho original legível para auditoria, sem normalizá-lo."""

    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    normalized_words = term.normalizado.split()
    first_word = normalized_words[0] if normalized_words else ""
    words = text.split()
    position = next(
        (
            index
            for index, word in enumerate(words)
            if normalizar_texto_busca(word) == first_word
        ),
        0,
    )
    before = " ".join(words[max(0, position - 8) : position])
    after = " ".join(words[position : position + 20])
    excerpt = f"{before} {after}".strip()
    return f"…{excerpt[: limit - 1]}" if position else excerpt[:limit]


def _values_for_aliases(record: Mapping[str, Any], aliases: Sequence[str]) -> tuple[str, ...]:
    values: list[str] = []
    for alias in aliases:
        if alias not in record:
            continue
        values.extend(_string_values(record[alias]))
    return tuple(_unique(values))


def _nested_values(
    record: Mapping[str, Any], parent: str, aliases: Sequence[str]
) -> tuple[str, ...]:
    value = record.get(parent)
    if not isinstance(value, Mapping):
        return ()
    values: list[str] = []
    for alias in aliases:
        if alias in value:
            values.extend(_string_values(value[alias]))
    return tuple(_unique(values))


def _string_values(value: object) -> list[str]:
    if isinstance(value, str):
        cleaned = " ".join(value.split())
        return [cleaned] if cleaned else []
    if isinstance(value, Mapping):
        values: list[str] = []
        for nested in value.values():
            values.extend(_string_values(nested))
        return values
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        values: list[str] = []
        for nested in value:
            values.extend(_string_values(nested))
        return values
    return []


def _unique(values: Any) -> tuple[Any, ...]:
    return tuple(dict.fromkeys(values))
