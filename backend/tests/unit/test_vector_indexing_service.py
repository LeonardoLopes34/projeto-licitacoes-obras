import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.config import settings
from backend.database import Base
from backend.models.vector_index_model import DocumentIndexJobModel
from backend.services import vector_index_repository as repository
from backend.services.openai_edital_service import OpenAIBudgetExceededError, OpenAIServiceError
from backend.services.vector_indexing_service import VectorIndexingService


def _claim_persisted_job(monkeypatch, *, contratacao_chave="123:2026:99"):
    """Monta uma fila SQLite compartilhada também pelas chamadas em thread do worker."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(repository, "SessionLocal", factory)
    job_id = repository.enqueue_job(contratacao_chave)
    claimed = repository.claim_next_job("worker-de-teste")
    assert claimed is not None and claimed.id == job_id
    return factory, claimed


@pytest.mark.asyncio
async def test_job_persistido_e_drenado_sem_prender_rota(monkeypatch):
    monkeypatch.setattr(settings, "vector_indexing_enabled", True)
    monkeypatch.setattr(settings, "vector_index_worker_concurrency", 1)
    service = VectorIndexingService()
    claimed = []
    completed = []

    monkeypatch.setattr(repository, "enqueue_job", lambda *args, **kwargs: 31)

    def claim(_worker):
        if claimed:
            return None
        claimed.append(True)
        return repository.ClaimedJob(31, "123:2026:7", "PE", 1, 1024, 10, 10)

    async def process(job):
        completed.append(job.id)

    monkeypatch.setattr(repository, "claim_next_job", claim)
    monkeypatch.setattr(service, "_process", process)

    await service.request_for_contract(contratacao_chave="123:2026:7", uf="PE")
    await service.wait_for_idle()

    assert completed == [31]
    assert service.metrics["jobs_enqueued"] == 1
    assert service.metrics["jobs_started"] == 1


@pytest.mark.asyncio
async def test_orcamento_esgotado_finaliza_job_sem_retentativa(monkeypatch):
    monkeypatch.setattr(settings, "vector_indexing_enabled", True)
    service = VectorIndexingService()
    job = repository.ClaimedJob(32, "123:2026:8", None, 1, 1024, 10, 10)
    finished = []

    async def process(_job):
        raise OpenAIBudgetExceededError()

    monkeypatch.setattr(repository, "claim_next_job", lambda _worker: job)
    monkeypatch.setattr(repository, "finish_job", lambda *args, **kwargs: finished.append((args, kwargs)))
    monkeypatch.setattr(service, "_process", process)

    assert await service._work_once() is True
    assert finished[0][1]["status"] == "esgotado"
    assert finished[0][1]["retryable"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["resposta_incompleta", "recusa_openai"])
async def test_erros_openai_terminais_registram_codigo_sem_retentativa(monkeypatch, error_code):
    monkeypatch.setattr(settings, "vector_indexing_enabled", True)
    factory, job = _claim_persisted_job(monkeypatch)
    service = VectorIndexingService()

    async def process(_job):
        raise OpenAIServiceError(error_code, "Diagnóstico seguro do provedor.")

    monkeypatch.setattr(repository, "claim_next_job", lambda _worker: job)
    monkeypatch.setattr(service, "_process", process)

    assert await service._work_once() is True

    with factory() as db:
        persisted = db.get(DocumentIndexJobModel, job.id)
        assert persisted is not None
        assert persisted.status == "falho_permanente"
        assert persisted.erro_codigo == error_code
        assert persisted.finished_at is not None
        assert persisted.lease_until is None
    assert service.metrics[f"openai_{error_code}"] == 1


@pytest.mark.asyncio
async def test_erro_openai_retryable_devolve_job_persistido_a_fila(monkeypatch):
    monkeypatch.setattr(settings, "vector_indexing_enabled", True)
    monkeypatch.setattr(settings, "vector_index_max_attempts", 3)
    factory, job = _claim_persisted_job(monkeypatch)
    service = VectorIndexingService()

    async def process(_job):
        raise OpenAIServiceError(
            "provedor_indisponivel",
            "O provedor está temporariamente indisponível.",
            retryable=True,
        )

    monkeypatch.setattr(repository, "claim_next_job", lambda _worker: job)
    monkeypatch.setattr(service, "_process", process)

    assert await service._work_once() is True

    with factory() as db:
        persisted = db.get(DocumentIndexJobModel, job.id)
        assert persisted is not None
        assert persisted.status == "pendente"
        assert persisted.erro_codigo == "provedor_indisponivel"
        assert persisted.finished_at is None
        assert persisted.lease_until is None
        assert persisted.worker_id is None
    assert service.metrics["openai_provedor_indisponivel"] == 1
