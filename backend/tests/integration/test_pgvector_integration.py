import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.services import vector_index_repository as repository
from backend.services.document_text_indexing_service import IndexableDocumentSource
from backend.services.vector_chunk_service import ChunkDraft, estimate_tokens


PGVECTOR_URL = os.getenv("PGVECTOR_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not PGVECTOR_URL, reason="Defina PGVECTOR_TEST_DATABASE_URL para validar pgvector")


def _draft(order, page, text):
    return ChunkDraft(
        ordem=order,
        pagina_inicio=page,
        pagina_fim=page,
        inicio_caractere=0,
        fim_caractere=len(text),
        texto=text,
        texto_hash=(str(order) * 64)[:64],
        origem_texto="pdf_texto",
        confianca_ocr=None,
        token_count=estimate_tokens(text),
    )


def _vector(first, second=0.0):
    return [first, second] + [0.0] * 1534


def test_pgvector_migracao_e_busca_interna_filtrada(monkeypatch):
    engine = create_engine(PGVECTOR_URL)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")) == "vector"
    monkeypatch.setattr(repository, "SessionLocal", sessionmaker(bind=engine))
    source = IndexableDocumentSource(21, "Edital", "https://pncp.gov.br/edital.pdf")
    _, _, _ = repository.persist_indexed_document(
        contratacao_chave="999:2026:1",
        source=source,
        uf="SP",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="1" * 64,
        chunks=[_draft(1, 3, "Atestado de capacidade técnica")],
        embeddings=[_vector(1.0)],
    )
    repository.activate_document_source(contratacao_chave="999:2026:1", documento_id=21, source_hash="s" * 64)
    other_source = IndexableDocumentSource(22, "Outro anexo", "https://pncp.gov.br/outro.pdf")
    repository.persist_indexed_document(
        contratacao_chave="999:2026:1",
        source=other_source,
        uf="SP",
        manifesto_hash="m" * 64,
        source_hash="o" * 64,
        pdf_sha256="2" * 64,
        chunks=[_draft(2, 5, "Balanço patrimonial")],
        embeddings=[_vector(0.0, 1.0)],
    )
    repository.activate_document_source(contratacao_chave="999:2026:1", documento_id=22, source_hash="o" * 64)

    rows = repository.search_similar_chunks(
        contratacao_chave="999:2026:1", embedding=_vector(1.0), documento_id=21, pagina=3, uf="SP"
    )

    assert len(rows) == 1
    assert rows[0]["texto"] == "Atestado de capacidade técnica"
    assert rows[0]["distancia"] == pytest.approx(0.0)
