import pytest

from backend.config import settings
from backend.services.document_text_indexing_service import ExtractedIndexPage
from backend.services.vector_chunk_service import ChunkLimitError, chunk_pages


def test_chunker_preserva_pagina_offsets_sobreposicao_e_hash(monkeypatch):
    monkeypatch.setattr(settings, "vector_chunk_max_characters", 42)
    monkeypatch.setattr(settings, "vector_chunk_overlap_characters", 8)
    page = ExtractedIndexPage(
        pagina=3,
        texto="Primeiro requisito documental. Segundo requisito com atestado técnico. Terceiro requisito final.",
        origem_texto="pdf_texto",
        confianca_ocr=None,
    )

    chunks = chunk_pages((page,))

    assert len(chunks) >= 2
    assert [chunk.ordem for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert all(chunk.pagina_inicio == 3 and chunk.pagina_fim == 3 for chunk in chunks)
    assert all(chunk.texto_hash and len(chunk.texto_hash) == 64 for chunk in chunks)
    assert all(chunk.inicio_caractere < chunk.fim_caractere for chunk in chunks)
    assert chunks[1].inicio_caractere < chunks[0].fim_caractere


def test_chunker_rejeita_documento_acima_do_limite_sem_omitir(monkeypatch):
    monkeypatch.setattr(settings, "vector_chunk_max_characters", 20)
    page = ExtractedIndexPage(1, "texto " * 30, "ocr", 0.74)

    with pytest.raises(ChunkLimitError, match="limite de trechos"):
        chunk_pages((page,), max_chunks=1)
