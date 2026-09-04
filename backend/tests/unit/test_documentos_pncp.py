import asyncio
from datetime import datetime, timezone

import httpx
import pytest
from cachetools import TTLCache

from backend.config import settings
from backend.services import pncp_service
from backend.services.document_snapshot_repository import SnapshotDocumentosPersistidos


@pytest.fixture(autouse=True)
def no_persistent_snapshot_in_unit_tests(monkeypatch):
    monkeypatch.setattr(pncp_service, "salvar_snapshot_documentos", lambda *args, **kwargs: None)
    monkeypatch.setattr(pncp_service, "obter_snapshot_documentos", lambda *args, **kwargs: None)


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://pncp.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("erro simulado", request=request, response=response)

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url, **kwargs):
        self.url = url
        return self.response


def test_normaliza_documentos_preserva_ordem_deduplica_e_filtra_url():
    payload = {
        "documentos": [
            {
                "sequencialDocumento": 2,
                "url": "https://pncp.gov.br/arquivo-2.pdf",
                "tipoDocumentoId": 10,
                "tipoDocumentoNome": "Edital",
                "titulo": "Edital principal",
                "dataPublicacaoPncp": "2026-09-02",
            },
            {
                "sequencialDocumento": 1,
                "url": "javascript:alert(1)",
                "tipoDocumentoNome": "Anexo",
            },
            {"sequencialDocumento": 2, "url": "https://pncp.gov.br/duplicado.pdf"},
            {"sequencialDocumento": "invalido"},
        ]
    }

    result = pncp_service.normalizar_documentos_pncp(payload)

    assert [item["sequencial_documento"] for item in result] == [2, 1]
    assert result[0]["tipo_documento_nome"] == "Edital"
    assert result[1]["url"] is None


@pytest.mark.asyncio
async def test_busca_documentos_monta_url_normaliza_e_faz_cache(monkeypatch):
    cache = TTLCache(maxsize=4, ttl=60)
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", cache)
    fake_client = FakeClient(
        FakeResponse(
            200,
            {
                "documentos": [
                    {
                        "sequencialDocumento": 1,
                        "url": "https://pncp.gov.br/arquivo.pdf",
                        "titulo": "Edital",
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: fake_client)

    result = await pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7)

    assert result["status"] == "sucesso_real"
    assert result["total"] == 1
    assert fake_client.url.endswith("/orgaos/12345678901234/compras/2026/7/arquivos")

    async def unexpected_client(**kwargs):
        raise AssertionError("a segunda consulta deveria usar o cache")

    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", unexpected_client)
    cached = await pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7)
    assert cached["documentos"] == result["documentos"]
    assert cached["origem"] == "cache_memoria"


@pytest.mark.asyncio
async def test_cliente_http_do_pncp_e_reutilizado_no_mesmo_loop(monkeypatch):
    criado = []

    class ReusableClient:
        is_closed = False

    def factory(**kwargs):
        client = ReusableClient()
        criado.append(client)
        return client

    monkeypatch.setattr(pncp_service, "_PNCP_HTTP_CLIENT", None)
    monkeypatch.setattr(pncp_service, "_PNCP_HTTP_CLIENT_LOOP", None)
    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", factory)

    primeiro = await pncp_service.obter_cliente_pncp()
    segundo = await pncp_service.obter_cliente_pncp()

    assert primeiro is segundo
    assert len(criado) == 1


@pytest.mark.asyncio
async def test_consultas_simultaneas_de_documentos_compartilham_chamada_ao_pncp(monkeypatch):
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", TTLCache(maxsize=4, ttl=60))
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_INFLIGHT", {})
    started = asyncio.Event()
    release = asyncio.Event()
    calls = {"total": 0}

    class SlowClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            calls["total"] += 1
            started.set()
            await release.wait()
            return FakeResponse(
                200,
                {"documentos": [{"sequencialDocumento": 1, "titulo": "Edital"}]},
            )

    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: SlowClient())

    first = asyncio.create_task(pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7))
    await started.wait()
    second = asyncio.create_task(pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7))
    await asyncio.sleep(0)
    release.set()
    first_result, second_result = await asyncio.gather(first, second)

    assert calls["total"] == 1
    assert first_result == second_result
    assert first_result["total"] == 1


@pytest.mark.asyncio
async def test_timeout_do_consumidor_nao_cancela_consulta_compartilhada(monkeypatch):
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", TTLCache(maxsize=4, ttl=60))
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_INFLIGHT", {})
    started = asyncio.Event()
    release = asyncio.Event()
    calls = {"total": 0}

    class SlowClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            calls["total"] += 1
            started.set()
            await release.wait()
            return FakeResponse(
                200,
                {"documentos": [{"sequencialDocumento": 1, "titulo": "Edital"}]},
            )

    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: SlowClient())

    first = asyncio.create_task(pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7))
    await started.wait()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first

    second = asyncio.create_task(pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7))
    await asyncio.sleep(0)
    release.set()
    result = await second

    assert calls["total"] == 1
    assert result["total"] == 1


def test_timeout_do_endpoint_documentos_comporta_retry(monkeypatch):
    monkeypatch.setattr(settings, "pncp_timeout_seconds", 3.0)

    assert pncp_service.documentos_request_timeout_seconds() == 7.5


@pytest.mark.asyncio
async def test_falha_do_pncp_retorna_snapshot_persistente_marcado_como_desatualizado(monkeypatch):
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", TTLCache(maxsize=4, ttl=60))
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_INFLIGHT", {})

    class FailedClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, **kwargs):
            raise httpx.ReadTimeout("timeout simulado")

    snapshot_time = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: FailedClient())
    monkeypatch.setattr(
        pncp_service,
        "obter_snapshot_documentos",
        lambda key: SnapshotDocumentosPersistidos(
            documentos=[{"sequencial_documento": 1, "titulo": "Edital anterior"}],
            documentos_hash="a" * 64,
            created_at=snapshot_time,
            updated_at=snapshot_time,
        ),
    )

    result = await pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7)

    assert result["status"] == "sucesso_real"
    assert result["origem"] == "cache_persistente"
    assert result["desatualizado"] is True
    assert result["atualizado_em"] == "2026-09-03T12:00:00+00:00"
    assert result["documentos"][0]["titulo"] == "Edital anterior"


@pytest.mark.asyncio
async def test_busca_documentos_trata_204_como_lista_vazia(monkeypatch):
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", TTLCache(maxsize=4, ttl=60))
    fake_client = FakeClient(FakeResponse(204))
    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: fake_client)

    result = await pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7)

    assert result["status"] == "sucesso_vazio"
    assert result["documentos"] == []


@pytest.mark.asyncio
async def test_falha_ao_salvar_snapshot_nao_descarta_resposta_real_do_pncp(monkeypatch):
    monkeypatch.setattr(pncp_service, "_DOCUMENTOS_CACHE", TTLCache(maxsize=4, ttl=60))
    monkeypatch.setattr(
        pncp_service,
        "salvar_snapshot_documentos",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("banco indisponível")),
    )
    fake_client = FakeClient(FakeResponse(200, {"documentos": [{"sequencialDocumento": 1}]}))
    monkeypatch.setattr(pncp_service.httpx, "AsyncClient", lambda **kwargs: fake_client)

    result = await pncp_service.buscar_documentos_pncp("12345678901234", 2026, 7)

    assert result["status"] == "sucesso_real"
    assert result["total"] == 1


def test_validacao_rejeita_cnpj_com_formato_inseguro():
    with pytest.raises(ValueError, match="14 caracteres alfanuméricos"):
        asyncio.run(pncp_service.buscar_documentos_pncp("123/45678901234", 2026, 1))
