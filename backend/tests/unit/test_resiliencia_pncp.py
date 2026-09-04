import asyncio

import pytest
from cachetools import TTLCache

from backend.config import settings
from backend.schemas import ExecucaoBusca
from backend.services import pncp_service
from backend.services.circuit_breaker import CircuitBreaker


def _offline_result(**kwargs):
    return {
        "status": "sucesso_offline_db",
        "mensagem": kwargs["mensagem"],
        "total_encontradas": 1,
        "dados": [{"id_pncp": "LOCAL-1"}],
        "metadados": {
            "parcial": True,
            "paginas_consultadas": kwargs.get("paginas_consultadas", 0),
            "paginas_com_erro": kwargs.get("paginas_com_erro", 0),
            "origem": "banco_local",
        },
    }


def test_configuracao_padrao_falha_rapido_e_abre_circuito():
    assert settings.pncp_timeout_seconds == 3.0
    assert settings.pncp_circuit_failure_threshold == 3


def test_timeout_global_considera_quantidade_de_paginas():
    assert pncp_service._search_timeout_seconds(0, 1) == 3.0
    assert pncp_service._search_timeout_seconds(4, 5) == 15.0
    assert pncp_service._search_timeout_seconds(0, 5) == 45.0


@pytest.fixture
def isolated_pncp_state(monkeypatch):
    monkeypatch.setattr(pncp_service, "_CACHE", TTLCache(maxsize=16, ttl=60))
    circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
    monkeypatch.setattr(pncp_service, "_PNCP_CIRCUIT", circuit)
    monkeypatch.setattr(pncp_service, "_fallback_local", _offline_result)
    return circuit


def test_circuit_breaker_abre_e_permite_uma_sonda_de_recuperacao():
    now = [0.0]
    circuit = CircuitBreaker(failure_threshold=2, recovery_timeout=10, clock=lambda: now[0])

    assert circuit.allow_request() is True
    circuit.record_failure()
    assert circuit.allow_request() is True
    circuit.record_failure()
    assert circuit.is_open is True
    assert circuit.allow_request() is False

    now[0] = 11.0
    assert circuit.allow_request() is True
    assert circuit.allow_request() is False
    circuit.record_success()
    assert circuit.is_open is False
    assert circuit.consecutive_failures == 0
    assert circuit.allow_request() is True


def test_circuit_breaker_nao_abre_com_uma_falha_lenta():
    circuit = CircuitBreaker(failure_threshold=3, recovery_timeout=10)

    circuit.record_failure(response_time=3.0)

    assert circuit.is_open is False
    assert circuit.consecutive_failures == 1
    assert circuit.last_response_time == 3.0
    assert circuit.allow_request() is True


@pytest.mark.asyncio
async def test_cache_nao_e_usado_enquanto_o_pncp_responde(monkeypatch, isolated_pncp_state):
    calls = 0

    async def successful_search(*args):
        nonlocal calls
        calls += 1
        return [], ExecucaoBusca(origem="PNCP")

    monkeypatch.setattr(pncp_service, "_execute_search", successful_search)

    result = await pncp_service.search_licitacoes_construction("20260801", "20260803", modalidade=4, max_paginas=1)

    assert result["status"] == "sucesso_vazio"
    assert calls == 1
    assert isolated_pncp_state.consecutive_failures == 0


@pytest.mark.asyncio
async def test_falha_do_pncp_prefere_cache_ao_banco(monkeypatch, isolated_pncp_state):
    cache_key = "20260801:20260803:4:50:1:TODOS"
    pncp_service._CACHE[cache_key] = {
        "status": "sucesso_real",
        "mensagem": "Resultado salvo",
        "total_encontradas": 1,
        "dados": [{"id_pncp": "CACHE-1"}],
        "metadados": {"origem": "PNCP", "parcial": False, "paginas_consultadas": 1, "paginas_com_erro": 0},
    }
    calls = 0

    async def failed_search(*args):
        nonlocal calls
        calls += 1
        raise pncp_service.PNCPConnectionError("indisponível")

    monkeypatch.setattr(pncp_service, "_execute_search", failed_search)

    result = await pncp_service.search_licitacoes_construction("20260801", "20260803", modalidade=4, max_paginas=1)

    assert calls == 1
    assert result["status"] == "sucesso_offline_cache"
    assert result["metadados"]["origem"] == "cache"
    assert result["dados"] == [{"id_pncp": "CACHE-1"}]


@pytest.mark.asyncio
async def test_timeout_total_retorna_fallback_e_registra_falha(monkeypatch, isolated_pncp_state):
    async def slow_search(*args):
        await asyncio.sleep(0.05)

    monkeypatch.setattr(pncp_service, "_execute_search", slow_search)
    monkeypatch.setattr(settings, "pncp_timeout_seconds", 0.01)

    result = await pncp_service.search_licitacoes_construction("20260801", "20260803", modalidade=4, max_paginas=1)

    assert result["status"] == "sucesso_offline_db"
    assert result["metadados"]["origem"] == "banco_local"
    assert result["metadados"]["paginas_com_erro"] == 1
    assert "excedeu 0.01 segundos" in result["mensagem"]
    assert isolated_pncp_state.consecutive_failures == 1


@pytest.mark.asyncio
async def test_circuito_aberto_usa_banco_sem_chamar_pncp(monkeypatch, isolated_pncp_state):
    isolated_pncp_state.record_failure()
    isolated_pncp_state.record_failure()
    isolated_pncp_state.record_failure()
    calls = 0

    async def unexpected_search(*args):
        nonlocal calls
        calls += 1
        return [], ExecucaoBusca()

    monkeypatch.setattr(pncp_service, "_execute_search", unexpected_search)

    result = await pncp_service.search_licitacoes_construction("20260801", "20260803", modalidade=4, max_paginas=1)

    assert calls == 0
    assert result["metadados"]["origem"] == "banco_local"
    assert "temporariamente indisponível" in result["mensagem"]


@pytest.mark.asyncio
async def test_busca_com_sucesso_fecha_circuito(monkeypatch, isolated_pncp_state):
    isolated_pncp_state.record_failure()

    async def successful_search(*args):
        return [], ExecucaoBusca(origem="PNCP")

    monkeypatch.setattr(pncp_service, "_execute_search", successful_search)

    result = await pncp_service.search_licitacoes_construction("20260801", "20260803", modalidade=4, max_paginas=1)

    assert result["status"] == "sucesso_vazio"
    assert isolated_pncp_state.consecutive_failures == 0
    assert isolated_pncp_state.is_open is False
