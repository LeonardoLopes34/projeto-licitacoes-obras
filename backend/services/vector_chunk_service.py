"""Chunker versionado de texto de edital com offsets e limites explícitos."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.config import settings
from backend.services.document_text_indexing_service import ExtractedIndexPage


class ChunkLimitError(RuntimeError):
    """O orçamento de chunks foi excedido sem omitir conteúdo silenciosamente."""


@dataclass(frozen=True)
class ChunkDraft:
    ordem: int
    pagina_inicio: int
    pagina_fim: int
    inicio_caractere: int
    fim_caractere: int
    texto: str
    texto_hash: str
    origem_texto: str
    confianca_ocr: float | None
    token_count: int


def estimate_tokens(text: str) -> int:
    """Estimativa conservadora e determinística usada para os limites prévios."""

    return max(1, (len(text) + 3) // 4)


def _best_cut(text: str, start: int, limit: int) -> int:
    end = min(len(text), start + limit)
    if end == len(text):
        return end
    window = text[start:end]
    candidates = [
        window.rfind("\n\n"),
        window.rfind("\n"),
        window.rfind("; "),
        window.rfind(". "),
        window.rfind(" "),
    ]
    best = max(candidates)
    # Não corta um parágrafo no primeiro trecho curto só para obedecer uma
    # fronteira; ao menos metade do orçamento deve ter sido usada.
    if best >= max(1, limit // 2):
        return start + best + (2 if window[best : best + 2] == "\n\n" else 1)
    return end


def _page_chunks(page: ExtractedIndexPage, *, start_order: int) -> list[ChunkDraft]:
    text = page.texto
    maximum = settings.vector_chunk_max_characters
    overlap = min(settings.vector_chunk_overlap_characters, maximum // 2)
    start = 0
    order = start_order
    chunks: list[ChunkDraft] = []
    while start < len(text):
        while start < len(text) and text[start].isspace():
            start += 1
        if start >= len(text):
            break
        end = _best_cut(text, start, maximum)
        while end > start and text[end - 1].isspace():
            end -= 1
        if end <= start:
            end = min(len(text), start + maximum)
        original = text[start:end]
        if original:
            chunks.append(
                ChunkDraft(
                    ordem=order,
                    pagina_inicio=page.pagina,
                    pagina_fim=page.pagina,
                    inicio_caractere=start,
                    fim_caractere=end,
                    texto=original,
                    texto_hash=hashlib.sha256(original.encode("utf-8")).hexdigest(),
                    origem_texto=page.origem_texto,
                    confianca_ocr=page.confianca_ocr,
                    token_count=estimate_tokens(original),
                )
            )
            order += 1
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)
        # A sobreposição não pode introduzir uma sequência vazia ou instável.
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def chunk_pages(pages: tuple[ExtractedIndexPage, ...], *, max_chunks: int | None = None) -> list[ChunkDraft]:
    """Gera chunks somente dentro de cada página, preservando a proveniência."""

    limit = max_chunks or settings.vector_index_max_chunks_per_document
    chunks: list[ChunkDraft] = []
    for page in pages:
        if not page.texto.strip():
            continue
        page_chunks = _page_chunks(page, start_order=len(chunks) + 1)
        chunks.extend(page_chunks)
        if len(chunks) > limit:
            raise ChunkLimitError("O documento excede o limite de trechos para indexação.")
    return chunks


def combine_chunk_hashes(chunks: list[ChunkDraft]) -> str:
    joined = "".join(chunk.texto_hash for chunk in chunks)
    return hashlib.sha256(joined.encode("ascii")).hexdigest()
