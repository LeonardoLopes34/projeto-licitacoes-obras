"""Validação conservadora de candidatos a documentos exigidos.

O OCR encontra palavras e frases; este módulo decide se a ocorrência parece
uma obrigação documental do licitante. A decisão é local e explicável para
evitar que uma classificação generativa invente requisitos ou transforme uma
menção operacional em documento exigido.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


DOCUMENT_TERMS: tuple[str, ...] = (
    "contrato social",
    "ato constitutivo",
    "estatuto",
    "registro comercial",
    "certidao",
    "cnd",
    "fgts",
    "atestado",
    "acervo tecnico",
    "registro profissional",
    "crea",
    "cau",
    "balanco patrimonial",
    "patrimonio liquido",
    "indice de liquidez",
    "indices de liquidez",
    "regularidade fiscal",
    "regularidade trabalhista",
    "declaracao",
    "declaracoes",
)

_ACTION_RE = re.compile(
    r"\b(?:dever(?:a|ao)?\s+)?(?:apresent(?:ar|acao)|anex(?:ar|o)|junt(?:ar|ada)|"
    r"entreg(?:ar|a)|encaminh(?:ar|ado)|comprov(?:ar|acao)|disponibiliz(?:ar|acao)|"
    r"declar(?:ar|acao)|preench(?:er|imento))\b"
)
_SUBJECT_TERMS = ("licitante", "empresa", "proponente", "participante", "interessado")
_DECLARATION_INTENT_TERMS = (
    "atendimento",
    "cumprimento",
    "legislacao",
    "normas",
    "veracidade",
    "inidoneidade",
    "impedimento",
    "trabalho",
    "menor",
    "sancao",
)
_CONTEXT_TERMS = (
    "nota fiscal",
    "notas fiscais",
    "fiscalizacao",
    "visita tecnica",
    "servidor",
    "periodo",
    "periodos",
    "acompanhad",
    "medicao",
    "execucao contratual",
    "durante a execucao",
    "contratada",
)


@dataclass(frozen=True)
class DocumentRequirementDecision:
    aceito: bool
    confianca: float
    motivo: str


@dataclass(frozen=True)
class DocumentRequirementFilterResult:
    exigencias: list[dict]
    rejeitadas: list[dict]
    total_candidatas: int


def normalizar_candidato(texto: str | None) -> str:
    normalized = unicodedata.normalize("NFD", texto or "")
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    without_parenthetical = re.sub(r"\([^)]*\)", "", without_accents)
    return re.sub(r"\s+", " ", without_parenthetical).strip().lower()


def _tem_termo_documental(texto: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", texto) for term in DOCUMENT_TERMS)


def _tem_acao_documental(texto: str) -> bool:
    return _ACTION_RE.search(texto) is not None


def _tem_contexto_operacional(texto: str) -> bool:
    if any(term in texto for term in _CONTEXT_TERMS):
        return True
    return re.search(r"\bnotas?\W*(?:s)?\W+fiscais?\b", texto) is not None


def avaliar_candidato_documental(texto: str, categoria: str | None = None) -> DocumentRequirementDecision:
    """Decide se um trecho contém uma obrigação documental verificável."""

    normalized = normalizar_candidato(texto)
    if len(normalized) < 18:
        return DocumentRequirementDecision(False, 0.0, "trecho curto ou cabeçalho")
    if not _tem_termo_documental(normalized):
        return DocumentRequirementDecision(False, 0.0, "não há tipo documental identificável")

    has_action = _tem_acao_documental(normalized)
    is_declaration_title = (
        "declaracao" in normalized
        and any(term in normalized for term in _DECLARATION_INTENT_TERMS)
        and len(normalized) >= 35
    )
    if not has_action and not is_declaration_title:
        return DocumentRequirementDecision(False, 0.0, "menção sem ação de apresentação ou comprovação")

    # Essas ocorrências descrevem procedimento, validade ou execução; não são
    # documentos de habilitação mesmo quando contêm a palavra "atestado".
    if _tem_contexto_operacional(normalized):
        return DocumentRequirementDecision(False, 0.0, "menção contextual ou operacional")

    has_subject = any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in _SUBJECT_TERMS)
    # A ação explícita é a evidência mais forte. Sujeito explícito aumenta a
    # confiança, mas não é obrigatório porque muitos editais usam listas.
    confidence = 0.92 if has_action and has_subject else 0.84 if has_action else 0.72
    return DocumentRequirementDecision(True, confidence, "obrigação documental identificada")


def chave_requisito_documental(categoria: str, texto: str) -> str:
    """Gera uma chave conceitual para deduplicar pequenas variações de OCR."""

    normalized = normalizar_candidato(texto)
    concepts = (
        ("atestado_tecnico_profissional", ("atestado", "profissional")),
        ("atestado_tecnico_operacional", ("atestado", "operacional")),
        ("atestado_capacidade_tecnica", ("atestado",)),
        ("contrato_social", ("contrato social", "ato constitutivo", "estatuto")),
        ("regularidade_fiscal", ("regularidade fiscal", "certidao")),
        ("regularidade_trabalhista", ("regularidade trabalhista", "fgts")),
        ("balanco_patrimonial", ("balanco patrimonial", "patrimonio liquido")),
        ("declaracao_legislacao", ("declaracao", "legislacao")),
        ("declaracao_veracidade", ("declaracao", "veracidade", "falsa")),
        ("declaracao_inidoneidade", ("declaracao", "inidoneidade")),
        ("declaracao_impedimento", ("declaracao", "impedimento")),
        ("declaracao_sistema", ("declaracao", "sistema")),
    )
    for key, terms in concepts:
        if all(term in normalized for term in terms):
            return key
    # Para itens não cobertos, usa a categoria e a forma normalizada. Isso
    # mantém exigências diferentes separadas e ainda colapsa repetições exatas.
    compact = re.sub(r"\b(?:devera|deverao|apresentar|anexar|juntar|entregar)\b", "", normalized)
    compact = re.sub(r"\s+", " ", compact).strip()
    return f"{categoria}:{compact[:180]}"


def candidatos_semelhantes(primeiro: str, segundo: str, *, limite: float = 0.9) -> bool:
    """Compara variações pequenas de OCR sem misturar conceitos diferentes."""

    return SequenceMatcher(None, normalizar_candidato(primeiro), normalizar_candidato(segundo)).ratio() >= limite


def filtrar_exigencias_documentais(candidatas: list[dict]) -> DocumentRequirementFilterResult:
    """Filtra candidatos e elimina repetições conceituais do OCR."""

    exigencias: list[dict] = []
    rejeitadas: list[dict] = []
    chaves: set[tuple[str, str]] = set()
    for candidata in candidatas:
        categoria = str(candidata.get("categoria") or "nao_classificado")
        evidencia = str(candidata.get("evidencia") or candidata.get("descricao_original") or "")
        decisao = avaliar_candidato_documental(evidencia, categoria)
        if not decisao.aceito:
            normalized = normalizar_candidato(evidencia)
            if "nota fiscal" in normalized or "notas fiscais" in normalized or re.search(
                r"\bnotas?\W*(?:s)?\W+fiscais?\b", normalized
            ):
                motivo = "menção contextual a nota fiscal"
            elif "categoria técnica" in normalized or "qualificacao tecnica" in normalized:
                motivo = "categoria mencionada sem tipo de documento identificável"
            elif "ação" in decisao.motivo or "acao" in decisao.motivo or "sem ação" in decisao.motivo:
                motivo = "documento citado sem ação explícita de apresentação ou comprovação"
            else:
                motivo = decisao.motivo
            rejeitadas.append({**candidata, "motivo": motivo})
            continue

        chave = (categoria, str(candidata.get("chave_documental") or chave_requisito_documental(categoria, evidencia)))
        if chave in chaves:
            rejeitadas.append(
                {**candidata, "motivo": "exigência duplicada após normalização do texto"}
            )
            continue
        chaves.add(chave)
        exigencias.append({key: value for key, value in candidata.items() if key != "chave_documental"})

    return DocumentRequirementFilterResult(
        exigencias=exigencias,
        rejeitadas=rejeitadas,
        total_candidatas=len(candidatas),
    )
