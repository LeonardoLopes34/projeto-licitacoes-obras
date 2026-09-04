from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.schemas import ResultadoExigencias
from backend.services import edital_analysis_repository as repository


def test_cache_persistente_e_indexado_por_hash_e_versao(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", session_factory)
    result = ResultadoExigencias(
        status="sucesso",
        mensagem="Exigências identificadas no edital.",
        analisador_versao="ocr-edital-v1",
    )

    repository.salvar_analise("123:2026:1", "a" * 64, result)

    cached = repository.obter_analise("123:2026:1", "a" * 64, "ocr-edital-v1")
    wrong_hash = repository.obter_analise("123:2026:1", "b" * 64, "ocr-edital-v1")
    wrong_version = repository.obter_analise("123:2026:1", "a" * 64, "ocr-edital-v2")

    assert cached is not None
    assert cached.status == "sucesso"
    assert wrong_hash is None
    assert wrong_version is None


def test_resumo_para_card_nao_processa_novos_documentos(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", session_factory)
    result = ResultadoExigencias(
        status="sucesso_parcial",
        mensagem="Resultado parcial.",
        total_exigencias=2,
        categorias={"qualificacao_tecnica": 2},
        analisador_versao="ocr-edital-v1",
    )
    repository.salvar_analise("123:2026:2", "c" * 64, result)

    summaries = repository.obter_resumos_contratacoes({"123:2026:2", "sem:resultado"})

    assert summaries["123:2026:2"]["total_exigencias"] == 2
    assert summaries["123:2026:2"]["status"] == "sucesso_parcial"


def test_ultima_analise_compativel_retorna_resultado_e_timestamp(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", session_factory)

    successful = ResultadoExigencias(
        status="sucesso",
        mensagem="Análise concluída.",
        total_exigencias=1,
        analisador_versao="ocr-edital-v1",
    )
    failed = ResultadoExigencias(
        status="erro",
        mensagem="Falha transitória.",
        analisador_versao="ocr-edital-v1",
    )
    repository.salvar_analise("123:2026:3", "a" * 64, successful)
    repository.salvar_analise("123:2026:3", "b" * 64, failed)

    persisted = repository.obter_ultima_analise_com_atualizacao("123:2026:3", "ocr-edital-v1")
    result = repository.obter_ultima_analise_compativel("123:2026:3", "ocr-edital-v1")

    assert persisted is not None
    assert persisted.resultado.status == "sucesso"
    assert persisted.updated_at is not None
    assert result is not None
    assert result.status == "sucesso"
    assert repository.obter_ultima_analise_compativel("123:2026:3", "ocr-edital-v2") is None
