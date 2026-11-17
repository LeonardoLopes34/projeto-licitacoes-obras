"""Normalização dos dados de tipo publicados pelo PNCP.

O PNCP usa nomes de campos diferentes entre seus recursos e versões. Este
módulo concentra essas variações sem substituir os campos atômicos: o texto
composto é somente uma representação para o card, enquanto modalidade,
critério e instrumento continuam disponíveis para auditoria e filtros.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any


_MODALIDADE_FIELDS = (
    "modalidadeNome",
    "modalidade",
    "modalidadeContratacaoNome",
    "nomeModalidade",
)
_MODALIDADE_CODE_FIELDS = (
    "modalidadeId",
    "modalidade_codigo",
    "codigoModalidadeContratacao",
    "modalidadeContratacaoId",
)
_CRITERIO_FIELDS = (
    "criterioJulgamentoNome",
    "criterioJulgamento",
    "criterio_julgamento",
    "nomeCriterioJulgamento",
)
_INSTRUMENTO_FIELDS = (
    "tipoInstrumentoConvocatorioNome",
    "tipoInstrumentoConvocatorio",
    "tipo_instrumento",
    "nomeTipoInstrumentoConvocatorio",
)
# Este grupo não inclui ``tipoInstrumentoConvocatorioNome``. Um instrumento
# (por exemplo, edital) é um campo atômico diferente de um texto de tipo de
# contratação já composto e não deve sobrescrever modalidade + critério.
_TIPO_ESPECIFICO_FIELDS = (
    "tipoContratacaoNome",
    "tipoContratacao",
    "tipo_contratacao",
    "nomeTipoContratacao",
)

# A modalidade exibida pela consulta resumida do PNCP combina a modalidade
# jurídica com a forma de disputa (por exemplo, ``Concorrência - Eletrônica``).
# A tela de detalhes do portal, porém, usa a modalidade jurídica como base do
# tipo e deixa a forma eletrônica/presencial como informação separada.
_FORMA_DISPUTA_SUFFIX_RE = re.compile(
    r"\s+-\s+(?:eletr(?:ô|o)nic[oa]|presencial)\s*$",
    flags=re.IGNORECASE,
)


def _texto_publicado(value: Any) -> str | None:
    """Converte texto publicado sem fabricar valor a partir de identificador."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _extract_text(item: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[str | None, str | None]:
    for field in fields:
        value = _texto_publicado(item.get(field))
        if value:
            return value, field
    return None, None


def _extract_int(item: Mapping[str, Any], fields: tuple[str, ...]) -> int | None:
    for field in fields:
        value = item.get(field)
        if value is None or isinstance(value, bool) or str(value).strip() == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _comparavel(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[\w]+", without_accents))


def _contem_criterio(modalidade: str, criterio: str) -> bool:
    """Compara por palavras para não confundir uma substring com o critério."""
    comparable_modalidade = f" {_comparavel(modalidade)} "
    comparable_criterio = _comparavel(criterio)
    return bool(comparable_criterio and f" {comparable_criterio} " in comparable_modalidade)


def _modalidade_para_tipo(modalidade: str) -> str:
    """Retorna a modalidade jurídica usada na composição do tipo.

    ``modalidadeNome`` da consulta de publicações traz a forma de disputa no
    mesmo texto. Removê-la somente quando existe critério evita o resultado
    incorreto ``Concorrência - Eletrônica por Menor preço`` e reproduz o
    formato usado pelo PNCP no detalhe da contratação.
    """

    return _FORMA_DISPUTA_SUFFIX_RE.sub("", modalidade).strip() or modalidade


def _criterio_para_tipo(criterio: str) -> str:
    """Uniformiza a capitalização do rótulo composto sem alterar o atômico."""

    palavras_minusculas = {"a", "as", "e", "o", "os", "de", "da", "das", "do", "dos"}
    palavras = criterio.split()
    return " ".join(
        palavra.casefold()
        if index > 0 and palavra.casefold() in palavras_minusculas
        else palavra[:1].upper() + palavra[1:]
        for index, palavra in enumerate(palavras)
    )


def compor_tipo_contratacao(
    modalidade: str | None,
    criterio_julgamento: str | None,
    tipo_instrumento: str | None = None,
    *,
    tipo_especifico: str | None = None,
) -> str | None:
    """Monta o texto do card com regra estável e sem repetição acidental.

    Um texto específico da origem sempre vence. Na ausência dele, a convenção
    já publicada pelo PNCP é preservada: se a modalidade já traz o critério,
    acrescenta-se apenas o critério após o separador; se ela for genérica,
    forma-se ``modalidade por critério - critério``. O instrumento não é
    anexado a uma modalidade sem uma convenção confirmada; ele é um fallback
    quando é o único texto de tipo disponível.
    """
    if tipo_especifico:
        return tipo_especifico
    if modalidade and criterio_julgamento:
        modalidade_tipo = _modalidade_para_tipo(modalidade)
        criterio_tipo = _criterio_para_tipo(criterio_julgamento)
        if _comparavel(modalidade_tipo) == _comparavel(criterio_julgamento):
            return modalidade_tipo
        if _contem_criterio(modalidade_tipo, criterio_julgamento):
            return f"{modalidade_tipo} - {criterio_tipo}"
        return f"{modalidade_tipo} por {criterio_tipo} - {criterio_tipo}"
    return modalidade or criterio_julgamento or tipo_instrumento


def normalizar_campos_tipo_contratacao(item: Mapping[str, Any]) -> dict[str, Any]:
    """Extrai e compõe campos de tipo de um objeto PNCP.

    A chave ``tipo_contratacao_origem`` registra os nomes dos campos que
    contribuíram para o texto final. Ela permite auditar a composição sem
    duplicar o payload bruto no contrato de resposta.
    """
    modalidade, modalidade_field = _extract_text(item, _MODALIDADE_FIELDS)
    criterio, criterio_field = _extract_text(item, _CRITERIO_FIELDS)
    instrumento, instrumento_field = _extract_text(item, _INSTRUMENTO_FIELDS)
    tipo_especifico, tipo_especifico_field = _extract_text(item, _TIPO_ESPECIFICO_FIELDS)
    modalidade_codigo = _extract_int(item, _MODALIDADE_CODE_FIELDS)

    tipo_contratacao = compor_tipo_contratacao(
        modalidade,
        criterio,
        instrumento,
        tipo_especifico=tipo_especifico,
    )
    origem = {
        name: field
        for name, field in (
            ("modalidade", modalidade_field),
            ("criterio_julgamento", criterio_field),
            ("tipo_instrumento", instrumento_field),
            ("tipo_contratacao", tipo_especifico_field),
        )
        if field
    }
    if tipo_contratacao and not tipo_especifico_field:
        if modalidade_field and criterio_field:
            origem["tipo_contratacao"] = "composto:modalidade,criterio_julgamento"
        elif modalidade_field:
            origem["tipo_contratacao"] = "modalidade"
        elif criterio_field:
            origem["tipo_contratacao"] = "criterio_julgamento"
        elif instrumento_field:
            origem["tipo_contratacao"] = "tipo_instrumento"

    return {
        "modalidade": modalidade,
        "modalidade_codigo": modalidade_codigo,
        "criterio_julgamento": criterio,
        "tipo_instrumento": instrumento,
        "tipo_contratacao": tipo_contratacao,
        "tipo_contratacao_origem": origem or None,
    }
