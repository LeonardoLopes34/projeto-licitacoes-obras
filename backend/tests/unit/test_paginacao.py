import asyncio

import pytest
import httpx

from backend.exceptions import PNCPResponseError
from backend.services import pncp_service


def test_paginacao_de_resultado_limita_15_itens_e_emite_cursor():
    fingerprint = pncp_service._pagination_fingerprint(
        data_inicial="20260901",
        data_final="20260903",
        modalidade=0,
        tamanho_pagina=50,
        max_paginas=1,
        uf="RS",
        tamanho_resultado=15,
    )
    result = {"dados": [{"id_pncp": str(index)} for index in range(23)]}

    first = pncp_service._paginate_result(
        result,
        cursor=None,
        tamanho_resultado=15,
        fingerprint=fingerprint,
    )
    second = pncp_service._paginate_result(
        result,
        cursor=first["paginacao"]["proximo_cursor"],
        tamanho_resultado=15,
        fingerprint=fingerprint,
    )

    assert [item["id_pncp"] for item in first["dados"]] == [str(index) for index in range(15)]
    assert first["paginacao"] == {
        "tamanho": 15,
        "total_carregado": 23,
        "tem_mais": True,
        "proximo_cursor": first["paginacao"]["proximo_cursor"],
    }
    assert [item["id_pncp"] for item in second["dados"]] == [str(index) for index in range(15, 23)]
    assert second["paginacao"]["tem_mais"] is False
    assert second["paginacao"]["proximo_cursor"] is None


def test_cursor_de_paginacao_rejeita_consulta_diferente():
    original = pncp_service._pagination_fingerprint(
        data_inicial="20260901",
        data_final="20260903",
        modalidade=0,
        tamanho_pagina=50,
        max_paginas=1,
        uf="RS",
        tamanho_resultado=15,
    )
    changed = pncp_service._pagination_fingerprint(
        data_inicial="20260901",
        data_final="20260903",
        modalidade=4,
        tamanho_pagina=50,
        max_paginas=1,
        uf="RS",
        tamanho_resultado=15,
    )

    with pytest.raises(ValueError, match="cursor de paginação inválido"):
        pncp_service._decode_page_cursor(pncp_service._encode_page_cursor(15, original), changed)


def test_cursor_de_paginacao_rejeita_codificacao_malformada():
    with pytest.raises(ValueError, match="cursor de paginação inválido"):
        pncp_service._decode_page_cursor("%", "fingerprint")


class DummyClient:
    pass


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://pncp.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("erro simulado", request=request, response=response)

    def json(self):
        return self._payload


class ResponseClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def get(self, *args, **kwargs):
        return next(self.responses)


def page_result(page, items, total=5, error=None, rate_limited=False):
    return pncp_service.PageFetchResult(
        page=page,
        items=items,
        total_registros=total,
        error=error,
        rate_limited=rate_limited,
    )


@pytest.mark.asyncio
async def test_resposta_204_eh_fim_normal_da_paginacao():
    result = await pncp_service.fetch_pagina(
        ResponseClient([FakeResponse(204)]),
        asyncio.Semaphore(1),
        "url",
        {"pagina": 3},
        {},
    )

    assert result.error is None
    assert result.items == []
    assert result.total_registros == 0


@pytest.mark.asyncio
async def test_204_interrompe_a_paginacao_sem_marcar_falha(monkeypatch):
    calls = []

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        calls.append(params["pagina"])
        return page_result(params["pagina"], [], total=0)

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 4, 50, 5
    )

    assert calls == [1]
    assert raw == []
    assert metadata.parcial is False
    assert metadata.paginas_com_erro == 0


@pytest.mark.asyncio
async def test_rate_limit_tem_retry_controlado(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(pncp_service.asyncio, "sleep", fake_sleep)
    result = await pncp_service.fetch_pagina(
        ResponseClient(
            [
                FakeResponse(429),
                FakeResponse(200, {"data": [{"numeroControlePNCP": "1"}], "totalRegistros": 1}),
            ]
        ),
        asyncio.Semaphore(1),
        "url",
        {"pagina": 1},
        {},
    )

    assert result.error is None
    assert result.items == [{"numeroControlePNCP": "1"}]
    assert waits == [5.0]


@pytest.mark.asyncio
async def test_consulta_paginada_respeita_intervalo_entre_chamadas(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(pncp_service.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(pncp_service.settings, "pncp_request_interval_seconds", 2.0)
    result = await pncp_service.fetch_pagina(
        ResponseClient([FakeResponse(200, {"data": [], "totalRegistros": 0})]),
        asyncio.Semaphore(1),
        "url",
        {"pagina": 1},
        {},
        pace_requests=True,
    )

    assert result.error is None
    assert waits == [2.0]


@pytest.mark.asyncio
async def test_erro_500_tem_retry_controlado(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(pncp_service.asyncio, "sleep", fake_sleep)
    result = await pncp_service.fetch_pagina(
        ResponseClient(
            [
                FakeResponse(500),
                FakeResponse(200, {"data": [{"numeroControlePNCP": "1"}], "totalRegistros": 1}),
            ]
        ),
        asyncio.Semaphore(1),
        "url",
        {"pagina": 1},
        {},
    )

    assert result.error is None
    assert result.items == [{"numeroControlePNCP": "1"}]
    assert waits == [0.5]


@pytest.mark.asyncio
async def test_rate_limit_esgotado_eh_reportado_como_erro(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(pncp_service.asyncio, "sleep", fake_sleep)
    result = await pncp_service.fetch_pagina(
        ResponseClient([FakeResponse(429), FakeResponse(429, headers={"Retry-After": "10"})]),
        asyncio.Semaphore(1),
        "url",
        {"pagina": 2},
        {},
    )

    assert isinstance(result.error, PNCPResponseError)
    assert result.rate_limited is True
    assert waits == [5.0]


@pytest.mark.asyncio
async def test_erro_de_uma_modalidade_nao_interrompe_as_demais(monkeypatch):
    calls = []

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        calls.append(params["codigoModalidadeContratacao"])
        if params["codigoModalidadeContratacao"] == 4:
            return page_result(
                1,
                [],
                error=pncp_service.PNCPResponseError("falha simulada"),
            )
        if params["codigoModalidadeContratacao"] == 6:
            return page_result(
                1,
                [{"numeroControlePNCP": "pregao-1"}],
                total=1,
            )
        return page_result(1, [], total=0)

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 0, 50, 1
    )

    assert calls == [4, 6, 8]
    assert raw == [{"numeroControlePNCP": "pregao-1"}]
    assert metadata.parcial is True
    assert metadata.paginas_com_erro == 1


@pytest.mark.asyncio
async def test_primeira_pagina_de_todas_as_modalidades_respeita_limite_global(monkeypatch):
    active = 0
    max_active = 0

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        nonlocal active, max_active
        async with semaphore:
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)
            active -= 1
            mode = params["codigoModalidadeContratacao"]
            return page_result(1, [{"numeroControlePNCP": f"modo-{mode}"}], total=1)

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 0, 50, 1
    )

    assert max_active == 1
    assert len(raw) == 3
    assert metadata.parcial is False
    assert metadata.paginas_consultadas == 3


@pytest.mark.asyncio
async def test_busca_todas_as_paginas_ate_total(monkeypatch):
    calls = []

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        calls.append(params["pagina"])
        data = {
            1: [{"numeroControlePNCP": "1"}, {"numeroControlePNCP": "2"}],
            2: [{"numeroControlePNCP": "3"}, {"numeroControlePNCP": "4"}],
            3: [{"numeroControlePNCP": "5"}],
        }
        return page_result(params["pagina"], data[params["pagina"]])

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 4, 2, 5
    )

    assert calls == [1, 2, 3]
    assert len(raw) == 5
    assert metadata.parcial is False
    assert metadata.paginas_com_erro == 0


@pytest.mark.asyncio
async def test_limite_de_paginas_marca_resultado_parcial(monkeypatch):
    async def fake_fetch(client, semaphore, url, params, headers, **_):
        return page_result(params["pagina"], [{"numeroControlePNCP": str(params["pagina"])}])

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 4, 1, 2
    )

    assert len(raw) == 2
    assert metadata.parcial is True


@pytest.mark.asyncio
async def test_falha_de_pagina_e_contabilizada(monkeypatch):
    async def fake_fetch(client, semaphore, url, params, headers, **_):
        if params["pagina"] == 2:
            return page_result(2, [], error=PNCPResponseError("falha simulada"))
        return page_result(params["pagina"], [{"numeroControlePNCP": str(params["pagina"])}])

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    _, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 4, 1, 3
    )

    assert metadata.paginas_com_erro == 1
    assert metadata.parcial is True


@pytest.mark.asyncio
async def test_rate_limit_interrompe_demais_paginas(monkeypatch):
    calls = []

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        calls.append(params["pagina"])
        if params["pagina"] == 2:
            return page_result(
                2,
                [],
                error=PNCPResponseError("rate limit"),
                rate_limited=True,
            )
        return page_result(params["pagina"], [{"numeroControlePNCP": "1"}])

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    raw, metadata = await pncp_service._execute_search(
        DummyClient(), "url", {}, "20260801", "20260803", 0, 1, 10
    )

    assert calls == [1, 2]
    assert len(raw) == 1
    assert metadata.paginas_com_erro == 1
    assert metadata.parcial is True


@pytest.mark.asyncio
async def test_busca_progressiva_entrega_dados_a_cada_pagina(monkeypatch):
    def item(identifier, objeto):
        return {
            "numeroControlePNCP": identifier,
            "orgaoEntidade": {"razaoSocial": "Prefeitura de Teste", "cnpj": "12345678000199"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Porto Alegre"},
            "objetoCompra": objeto,
            "valorTotalEstimado": 1000,
            "dataPublicacaoPncp": "2026-08-01",
            "modalidadeId": 4,
            "modalidadeNome": "Concorrência",
            "anoCompra": "2026",
            "sequencialCompra": identifier,
        }

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        page = params["pagina"]
        data = {1: [item("1", "Reforma de escola")], 2: [item("2", "Pavimentação asfáltica")]}
        return page_result(page, data[page], total=2)

    async def fake_client():
        return DummyClient()

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", fake_client)
    monkeypatch.setattr(pncp_service, "_persistir_obras_consulta", lambda dados: None)

    events = [
        event
        async for event in pncp_service.stream_licitacoes_construction(
            "20260801", "20260801", modalidade=4, max_paginas=2
        )
    ]

    assert [event["tipo"] for event in events] == ["progresso", "progresso", "concluido"]
    assert [obra["id_pncp"] for obra in events[0]["dados"]] == ["1"]
    assert [obra["id_pncp"] for obra in events[1]["dados"]] == ["1", "2"]
    assert events[-1]["status"] == "sucesso_real"
    assert events[-1]["metadados"]["paginas_consultadas"] == 2


@pytest.mark.asyncio
async def test_busca_progressiva_usa_snapshot_local_sem_chamar_pncp(monkeypatch):
    calls = 0

    async def local_snapshot(**_):
        return {
            "status": "sucesso_local",
            "mensagem": "Dados locais",
            "total_encontradas": 1,
            "dados": [
                {
                    "id_pncp": "LOCAL-1",
                    "objeto": "Reforma de escola",
                    "valor_estimado": 1000,
                    "data_publicacao": "2026-08-01T00:00:00+00:00",
                }
            ],
            "metadados": {"origem": "banco_local", "parcial": False},
        }

    async def unexpected_client():
        nonlocal calls
        calls += 1
        return DummyClient()

    monkeypatch.setattr(pncp_service, "_resultado_local_disponivel", local_snapshot)
    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", unexpected_client)

    events = [
        event
        async for event in pncp_service.stream_licitacoes_construction(
            "20260801", "20260801", modalidade=4
        )
    ]

    assert [event["tipo"] for event in events] == ["concluido"]
    assert events[0]["status"] == "sucesso_local"
    assert events[0]["total_encontradas"] == 1
    assert calls == 0


@pytest.mark.asyncio
async def test_busca_progressiva_usa_cache_quando_uma_pagina_falha(monkeypatch):
    raw_item = {
        "numeroControlePNCP": "1",
        "orgaoEntidade": {"razaoSocial": "Prefeitura de Teste", "cnpj": "12345678000199"},
        "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Porto Alegre"},
        "objetoCompra": "Reforma de escola",
        "valorTotalEstimado": 1000,
        "dataPublicacaoPncp": "2026-08-01",
        "modalidadeId": 4,
        "modalidadeNome": "Concorrência",
        "anoCompra": "2026",
        "sequencialCompra": "1",
    }
    fallback_calls = []

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        if params["pagina"] == 1:
            return page_result(1, [raw_item], total=2)
        return page_result(2, [], error=PNCPResponseError("falha simulada"))

    async def fake_client():
        return DummyClient()

    async def fake_fallback(**kwargs):
        fallback_calls.append(kwargs)
        return {
            "status": "sucesso_offline_cache",
            "mensagem": "Resultado em cache",
            "total_encontradas": 1,
            "dados": [{"id_pncp": "CACHE-1", "objeto": "Obra em cache", "valor_estimado": 10}],
            "metadados": {"origem": "cache", "parcial": True},
        }

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", fake_client)
    monkeypatch.setattr(pncp_service, "_fallback_cache_or_local", fake_fallback)

    events = [
        event
        async for event in pncp_service.stream_licitacoes_construction(
            "20260801", "20260801", modalidade=4, max_paginas=2
        )
    ]

    assert [event["tipo"] for event in events] == ["progresso", "concluido"]
    assert events[-1]["status"] == "sucesso_offline_cache"
    assert [obra["id_pncp"] for obra in events[-1]["dados"]] == ["CACHE-1"]
    assert fallback_calls[0]["paginas_consultadas"] == 2
    assert fallback_calls[0]["paginas_com_erro"] == 1


@pytest.mark.asyncio
async def test_busca_progressiva_salva_snapshot_no_cache(monkeypatch):
    raw_item = {
        "numeroControlePNCP": "1",
        "orgaoEntidade": {"razaoSocial": "Prefeitura de Teste", "cnpj": "12345678000199"},
        "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Porto Alegre"},
        "objetoCompra": "Reforma de escola",
        "valorTotalEstimado": 1000,
        "dataPublicacaoPncp": "2026-08-01",
        "modalidadeId": 4,
        "modalidadeNome": "Concorrência",
        "anoCompra": "2026",
        "sequencialCompra": "1",
    }

    async def fake_fetch(client, semaphore, url, params, headers, **_):
        return page_result(1, [raw_item], total=1)

    async def fake_client():
        return DummyClient()

    cache = {}
    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", fake_client)
    monkeypatch.setattr(pncp_service, "_persistir_obras_consulta", lambda dados: None)
    monkeypatch.setattr(pncp_service, "_CACHE", cache)

    events = [
        event
        async for event in pncp_service.stream_licitacoes_construction(
            "20260801", "20260801", modalidade=4, max_paginas=1
        )
    ]

    cache_key = "20260801:20260801:4:50:1:TODOS"
    assert events[-1]["status"] == "sucesso_real"
    assert cache[cache_key]["status"] == "sucesso_real"
    assert [obra["id_pncp"] for obra in cache[cache_key]["dados"]] == ["1"]
