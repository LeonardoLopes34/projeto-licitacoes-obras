from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.vector_index_model import DocumentRequirementAnalysisModel, IndexedDocumentModel, utc_now
from backend.services import vector_index_repository as repository
from backend.services.document_text_indexing_service import IndexableDocumentSource
from backend.services.openai_edital_service import RequirementAnalysisResult, RequirementCandidate
from backend.services.vector_chunk_service import ChunkDraft, estimate_tokens


def _draft(text="Apresentar atestado de capacidade técnica."):
    return ChunkDraft(
        ordem=1,
        pagina_inicio=2,
        pagina_fim=2,
        inicio_caractere=0,
        fim_caractere=len(text),
        texto=text,
        texto_hash=("a" if text.startswith("Apresentar") else "b") * 64,
        origem_texto="pdf_texto",
        confianca_ocr=None,
        token_count=estimate_tokens(text),
    )


def _vector():
    return [0.0] * 1536


def _repository_with_sqlite(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", factory)
    return factory


def test_documentos_iguais_reutilizam_chunks_e_zip_ativa_conjunto_completo(monkeypatch):
    factory = _repository_with_sqlite(monkeypatch)
    source = IndexableDocumentSource(9, "Anexos do edital", "https://pncp.gov.br/anexos.zip")
    draft = _draft()

    first_id, first_chunks, reused = repository.persist_indexed_document(
        contratacao_chave="123:2026:8",
        source=source,
        uf="RS",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="1" * 64,
        chunks=[draft],
        embeddings=[_vector()],
    )
    same_id, same_chunks, reused_same = repository.persist_indexed_document(
        contratacao_chave="123:2026:8",
        source=source,
        uf="RS",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="1" * 64,
        chunks=[draft],
        embeddings=[_vector()],
    )
    second_id, _, _ = repository.persist_indexed_document(
        contratacao_chave="123:2026:8",
        source=source,
        uf="RS",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="2" * 64,
        chunks=[_draft("Segundo anexo técnico.")],
        embeddings=[_vector()],
    )
    repository.activate_document_source(contratacao_chave="123:2026:8", documento_id=9, source_hash="s" * 64)

    assert same_id == first_id
    assert reused is False and reused_same is True
    assert first_chunks[0].texto == same_chunks[0].texto
    with factory() as db:
        active = db.scalars(select(IndexedDocumentModel).where(IndexedDocumentModel.ativo.is_(True))).all()
    assert {document.id for document in active} == {first_id, second_id}


def test_analise_versionada_projeta_resultado_para_card(monkeypatch):
    _repository_with_sqlite(monkeypatch)
    source = IndexableDocumentSource(4, "Edital", "https://pncp.gov.br/edital.pdf")
    _, chunks, _ = repository.persist_indexed_document(
        contratacao_chave="123:2026:9",
        source=source,
        uf="PE",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="3" * 64,
        chunks=[_draft()],
        embeddings=[_vector()],
    )
    repository.activate_document_source(contratacao_chave="123:2026:9", documento_id=4, source_hash="s" * 64)
    result = RequirementAnalysisResult(
        accepted=[
            RequirementCandidate(
                categoria="qualificacao_tecnica",
                nome_documento="Atestado de capacidade técnica",
                resumo="Comprovação técnica.",
                chunk_id=chunks[0].id,
                documento_id=4,
                pagina=2,
                evidencia="Apresentar atestado de capacidade técnica.",
                confianca=0.9,
                estado="identificado",
            )
        ],
        rejected_count=0,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.001,
        latency_ms=30,
    )

    persisted = repository.persist_requirement_analysis(
        contratacao_chave="123:2026:9", manifesto_hash="m" * 64, chunks=chunks, result=result, status="sucesso"
    )

    assert persisted is not None
    assert persisted.analise_assistida is True
    assert persisted.documentos_exigidos[0].nome == "Atestado de capacidade técnica"
    assert persisted.exigencias[0].estado == "identificado"


def test_reprocessamento_com_sucesso_limpa_diagnostico_de_analise_indisponivel(monkeypatch):
    factory = _repository_with_sqlite(monkeypatch)
    contratacao_chave = "123:2026:11"
    manifesto_hash = "m" * 64
    source = IndexableDocumentSource(6, "Edital", "https://pncp.gov.br/edital.pdf")
    _, chunks, _ = repository.persist_indexed_document(
        contratacao_chave=contratacao_chave,
        source=source,
        uf="CE",
        manifesto_hash=manifesto_hash,
        source_hash="s" * 64,
        pdf_sha256="5" * 64,
        chunks=[_draft()],
        embeddings=[_vector()],
    )
    repository.record_requirement_failure(
        contratacao_chave=contratacao_chave,
        manifesto_hash=manifesto_hash,
        chunks=chunks,
        error_code="resposta_incompleta",
        error_message="A resposta da análise ficou incompleta.",
    )
    with factory() as db:
        unavailable = db.scalar(select(DocumentRequirementAnalysisModel))
        assert unavailable is not None
        assert unavailable.status == "indisponivel"
        assert unavailable.erro_codigo == "resposta_incompleta"
        assert unavailable.erro_mensagem_segura == "A resposta da análise ficou incompleta."

    result = RequirementAnalysisResult(
        accepted=[
            RequirementCandidate(
                categoria="qualificacao_tecnica",
                nome_documento="Atestado de capacidade técnica",
                resumo="Comprovação técnica.",
                chunk_id=chunks[0].id,
                documento_id=6,
                pagina=2,
                evidencia="Apresentar atestado de capacidade técnica.",
                confianca=0.9,
                estado="identificado",
            )
        ],
        rejected_count=0,
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.001,
        latency_ms=30,
    )

    persisted = repository.persist_requirement_analysis(
        contratacao_chave=contratacao_chave,
        manifesto_hash=manifesto_hash,
        chunks=chunks,
        result=result,
        status="sucesso",
    )

    assert persisted is not None
    with factory() as db:
        recovered = db.scalar(select(DocumentRequirementAnalysisModel))
        assert recovered is not None
        assert recovered.status == "sucesso"
        assert recovered.erro_codigo is None
        assert recovered.erro_mensagem_segura is None


def test_retencao_inativa_e_remove_derivados_expirados(monkeypatch):
    factory = _repository_with_sqlite(monkeypatch)
    source = IndexableDocumentSource(5, "Edital", "https://pncp.gov.br/edital.pdf")
    document_id, _, _ = repository.persist_indexed_document(
        contratacao_chave="123:2026:10",
        source=source,
        uf="BA",
        manifesto_hash="m" * 64,
        source_hash="s" * 64,
        pdf_sha256="4" * 64,
        chunks=[_draft()],
        embeddings=[_vector()],
    )
    repository.activate_document_source(contratacao_chave="123:2026:10", documento_id=5, source_hash="s" * 64)
    repository.inactivate_contract("123:2026:10")
    with factory() as db:
        document = db.get(IndexedDocumentModel, document_id)
        assert document is not None and document.ativo is False
        document.superseded_at = utc_now() - timedelta(days=2)
        db.commit()

    assert repository.purge_expired_inactive_derivatives(max_age_days=1) == 1
    with factory() as db:
        assert db.get(IndexedDocumentModel, document_id) is None
