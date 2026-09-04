from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.document_snapshot_model import DocumentSnapshotModel
from backend.services import document_snapshot_repository as repository


def test_snapshot_normaliza_hash_estavel_e_recupera_ultima_versao(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", session_factory)

    primeira_resposta = [
        {
            "sequencialDocumento": "2",
            "url": " https://pncp.gov.br/anexo.pdf ",
            "tipoDocumentoId": "9",
            "tipoDocumentoNome": " Anexo ",
            "titulo": " Habilitação ",
            "dataPublicacaoPncp": " 2026-09-03 ",
            "campo_transitorio": "ignorar",
        },
        {
            "sequencial_documento": 1,
            "url": "https://pncp.gov.br/edital.pdf",
            "titulo": "Edital",
        },
    ]
    mesma_resposta_em_outra_ordem = list(reversed(primeira_resposta))

    first = repository.salvar_snapshot_documentos("123:2026:1", primeira_resposta)
    repeated = repository.salvar_snapshot_documentos("123:2026:1", mesma_resposta_em_outra_ordem)
    latest = repository.obter_snapshot_documentos("123:2026:1")

    assert first is not None
    assert repeated is not None
    assert latest is not None
    assert first.documentos_hash == repeated.documentos_hash == latest.documentos_hash
    assert latest.documentos == [
        {
            "sequencial_documento": 1,
            "url": "https://pncp.gov.br/edital.pdf",
            "tipo_documento_id": None,
            "tipo_documento_nome": None,
            "titulo": "Edital",
            "data_publicacao_pncp": None,
        },
        {
            "sequencial_documento": 2,
            "url": "https://pncp.gov.br/anexo.pdf",
            "tipo_documento_id": 9,
            "tipo_documento_nome": "Anexo",
            "titulo": "Habilitação",
            "data_publicacao_pncp": "2026-09-03",
        },
    ]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DocumentSnapshotModel)) == 1


def test_snapshot_preserva_historico_por_hash_e_prioriza_o_mais_recente(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", session_factory)

    repository.salvar_snapshot_documentos(
        "123:2026:2",
        [{"sequencial_documento": 1, "titulo": "Edital versão 1"}],
    )
    newer = repository.salvar_snapshot_documentos(
        "123:2026:2",
        [{"sequencial_documento": 1, "titulo": "Edital versão 2"}],
    )
    latest = repository.obter_snapshot_documentos("123:2026:2")

    assert newer is not None
    assert latest is not None
    assert latest.documentos_hash == newer.documentos_hash
    assert latest.documentos[0]["titulo"] == "Edital versão 2"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DocumentSnapshotModel)) == 2
