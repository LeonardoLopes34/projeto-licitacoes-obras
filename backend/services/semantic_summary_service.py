"""Descrições curtas e explicativas para exibição das exigências.

As descrições deste módulo são geradas por regras locais e previsíveis. Elas
não substituem o trecho extraído: o texto original e a evidência continuam
armazenados no resultado para conferência pelo usuário.
"""

from __future__ import annotations

import re
import unicodedata


def _normalizar_texto(texto: str | None) -> str:
    normalized = unicodedata.normalize("NFD", texto or "")
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _contém_todos(texto: str, termos: tuple[str, ...]) -> bool:
    return all(termo in texto for termo in termos)


# A ordem é importante: regras mais específicas devem ser avaliadas primeiro.
# Os textos são intencionalmente descritivos, em vez de reproduzirem a redação
# que foi encontrada no edital.
_REGRAS_SEMANTICAS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("legislacao", "normas"),
        "Comprovação de conformidade com a legislação e as normas vigentes.",
    ),
    (
        ("veracidade",),
        "Declaração de veracidade das informações e dos documentos apresentados.",
    ),
    (
        ("documentacao falsa",),
        "Declaração de veracidade das informações e dos documentos apresentados.",
    ),
    (
        ("declaracao falsa",),
        "Declaração de veracidade das informações e dos documentos apresentados.",
    ),
    (
        ("inidoneidade",),
        "Declaração de que a empresa não está declarada inidônea para contratar.",
    ),
    (
        ("impedimento",),
        "Declaração de que a empresa não possui impedimento para participar ou contratar.",
    ),
    (
        ("sistema eletronico",),
        "Preenchimento das declarações obrigatórias no sistema eletrônico da licitação.",
    ),
    (
        ("campo proprio", "sistema"),
        "Preenchimento das declarações obrigatórias no sistema eletrônico da licitação.",
    ),
    (
        ("plataforma eletronica",),
        "Preenchimento das declarações obrigatórias na plataforma eletrônica da licitação.",
    ),
)

_RESUMOS_POR_CATEGORIA: dict[str, str] = {
    "habilitacao_juridica": "Comprovação da habilitação jurídica da empresa.",
    "qualificacao_tecnica": "Comprovação da capacidade técnica para executar o objeto.",
    "regularidade_fiscal_social_trabalhista": "Comprovação da regularidade fiscal, social e trabalhista.",
    "qualificacao_economico_financeira": "Comprovação da capacidade econômico-financeira da empresa.",
    "declaracoes": "Apresentação de declaração exigida no edital.",
    "documento_referenciado": "Apresentação do documento referenciado no edital.",
    "nao_classificado": "Exigência identificada no edital para análise do licitante.",
}


def gerar_descricao_resumida(categoria: str | None, texto: str | None) -> str:
    """Gera uma descrição curta sem expor literalmente o trecho do edital.

    A função é deliberadamente conservadora: quando não reconhece uma
    intenção conhecida, devolve um resumo genérico por categoria. Isso mantém
    a interface útil sem inventar requisitos que não estejam sustentados pela
    evidência original.
    """

    normalized = _normalizar_texto(texto)
    for termos, resumo in _REGRAS_SEMANTICAS:
        if _contém_todos(normalized, termos):
            return resumo
    return _RESUMOS_POR_CATEGORIA.get(categoria or "", _RESUMOS_POR_CATEGORIA["nao_classificado"])
