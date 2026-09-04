import pytest
from fastapi.testclient import TestClient

import backend.main as main_module


@pytest.mark.asyncio
async def test_endpoint_de_obras_preserva_metadados(monkeypatch):
    async def fake_search(**kwargs):
        return {
            "status": "sucesso_parcial",
            "mensagem": "Resultado parcial",
            "total_encontradas": 0,
            "dados": [],
            "metadados": {
                "parcial": True,
                "paginas_consultadas": 2,
                "paginas_com_erro": 1,
                "origem": "PNCP",
            },
        }

    monkeypatch.setattr(main_module, "search_licitacoes_construction", fake_search)
    result = await main_module.list_jobs(main_module._default_date(0), main_module._default_date(0), 4, 2, 50, None)
    assert result["metadados"]["parcial"] is True
    assert result["metadados"]["paginas_com_erro"] == 1


@pytest.mark.asyncio
async def test_endpoint_de_obras_padrao_consulta_somente_o_dia_atual(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {
            "status": "sucesso_vazio",
            "mensagem": "Nenhuma licitação encontrada.",
            "total_encontradas": 0,
            "dados": [],
            "metadados": {"origem": "PNCP", "parcial": False, "paginas_consultadas": 1, "paginas_com_erro": 0},
        }

    monkeypatch.setattr(main_module, "search_licitacoes_construction", fake_search)
    await main_module.list_jobs(main_module._default_date(0), main_module._default_date(0), 0, 1, 50, None)

    assert captured["data_inicial"] == main_module._default_date(0)
    assert captured["data_final"] == main_module._default_date(0)


@pytest.mark.asyncio
async def test_endpoint_de_obras_permite_alterar_periodo(monkeypatch):
    captured = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {
            "status": "sucesso_vazio",
            "mensagem": "Nenhuma licitação encontrada.",
            "total_encontradas": 0,
            "dados": [],
            "metadados": {"origem": "PNCP", "parcial": False, "paginas_consultadas": 1, "paginas_com_erro": 0},
        }

    monkeypatch.setattr(main_module, "search_licitacoes_construction", fake_search)
    await main_module.list_jobs("20200101", "20200131", 0, 1, 50, None)

    assert captured["data_inicial"] == "20200101"
    assert captured["data_final"] == "20200131"


def test_endpoint_rejeita_tamanho_de_pagina_abaixo_do_limite_do_pncp():
    response = TestClient(main_module.app).get(
        "/api/v1/obras?inicial_date=20260801&final_date=20260803&tamanho_pagina=1"
    )

    assert response.status_code == 422
    assert "greater than or equal to 10" in response.text


def test_endpoint_rejeita_tamanho_de_pagina_acima_do_limite_do_pncp():
    response = TestClient(main_module.app).get(
        "/api/v1/obras?inicial_date=20260801&final_date=20260803&tamanho_pagina=51"
    )

    assert response.status_code == 422
    assert "less than or equal to 50" in response.text


@pytest.mark.asyncio
async def test_endpoint_rejeita_data_de_calendario_invalida():
    with pytest.raises(main_module.HTTPException) as caught:
        await main_module.list_jobs("20261399", "20261399", 4, 1, 50, None)

    assert caught.value.status_code == 422
    assert "data válida" in str(caught.value.detail)


def test_endpoint_de_documentos_normaliza_resposta(monkeypatch):
    async def fake_documents(cnpj, ano, sequencial):
        assert (cnpj, ano, sequencial) == ("12345678901234", 2026, 7)
        return {
            "status": "sucesso_real",
            "mensagem": "Documentos carregados",
            "total": 1,
            "documentos": [
                {
                    "sequencial_documento": 1,
                    "url": "https://pncp.gov.br/arquivo.pdf",
                    "tipo_documento_id": 10,
                    "tipo_documento_nome": "Edital",
                    "titulo": "Edital principal",
                    "data_publicacao_pncp": "2026-09-02",
                }
            ],
            "origem": "PNCP",
        }

    monkeypatch.setattr(main_module, "buscar_documentos_pncp", fake_documents)
    response = TestClient(main_module.app).get(
        "/api/v1/obras/12345678901234/2026/7/documentos"
    )

    assert response.status_code == 200
    assert response.json()["documentos"][0]["titulo"] == "Edital principal"


def test_endpoint_de_documentos_rejeita_cnpj_invalido():
    response = TestClient(main_module.app).get(
        "/api/v1/obras/123-45678901234/2026/7/documentos"
    )

    assert response.status_code == 422
