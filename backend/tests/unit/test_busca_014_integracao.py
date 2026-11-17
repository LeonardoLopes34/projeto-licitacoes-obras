import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.services import pncp_service
from backend.services.search_filter_service import parse_search_request


class _DummyClient:
    pass


def test_busca_do_usuario_e_aplicada_antes_dos_totais_e_com_auditoria():
    expression = parse_search_request("pavimentação -drenagem")
    ordered, summary = pncp_service._ordenar_e_resumir_consulta(
        [
            {
                "id_pncp": "entra",
                "objeto": "Pavimentação de vias urbanas",
                "data_publicacao": "2026-09-02",
                "status_classificacao": "aprovado",
            },
            {
                "id_pncp": "sai",
                "objeto": "Pavimentação com drenagem pluvial",
                "data_publicacao": "2026-09-03",
                "status_classificacao": "aprovado",
            },
        ],
        termo="pavimentação -drenagem",
        ordenacao="data_desc",
        expressao_busca=expression,
    )

    assert [item["id_pncp"] for item in ordered] == ["entra"]
    assert ordered[0]["motivo_filtro"] == "incluido_por_termo"
    assert ordered[0]["campos_correspondentes"] == ["objeto"]
    assert summary["total_coletado"] == 2
    assert summary["total_filtrado"] == 1
    assert summary["contagens_busca"]["total_excluido_por_termo"] == 1
    assert summary["termos_exclusao"] == ["drenagem"]


def test_cursor_muda_quando_muda_escopo_exclusao_ou_parser():
    common = {
        "data_inicial": "20260901",
        "data_final": "20260903",
        "modalidade": 0,
        "tamanho_pagina": 50,
        "max_paginas": 2,
        "uf": None,
        "tamanho_resultado": 15,
    }
    default = pncp_service._pagination_fingerprint(
        **common, termos_inclusao=["pavimentacao"], termos_exclusao=["drenagem"]
    )
    changed_scope = pncp_service._pagination_fingerprint(
        **common,
        termos_inclusao=["pavimentacao"],
        termos_exclusao=["drenagem"],
        escopo_busca="todos_metadados",
    )
    changed_exclusion = pncp_service._pagination_fingerprint(
        **common, termos_inclusao=["pavimentacao"], termos_exclusao=["registro de precos"]
    )

    assert default != changed_scope != changed_exclusion


def test_deduplicacao_pncp_preserva_campos_e_vinculos_da_versao_mais_completa():
    first = {
        "numeroControlePNCP": "PNCP-1",
        "objetoCompra": "Pavimentação de vias",
        "documentos": [{"titulo": "Edital"}],
        "link_pncp": "https://pncp.gov.br/edital",
    }
    duplicate = {
        "numeroControlePNCP": "PNCP-1",
        "objetoCompra": "Pavimentação de vias urbanas",
        "atas": [{"id": "ata-1"}],
        "contratos": [{"id": "contrato-1"}],
    }

    merged = pncp_service._merge_duplicate_pncp_item(first, duplicate)

    assert pncp_service._raw_pncp_identifier(merged) == "PNCP-1"
    assert merged["link_pncp"] == "https://pncp.gov.br/edital"
    assert merged["documentos"] == [{"titulo": "Edital"}]
    assert merged["atas"] == [{"id": "ata-1"}]
    assert merged["contratos"] == [{"id": "contrato-1"}]


@pytest.mark.asyncio
async def test_stream_aplica_busca_antes_de_exibir_paginas_posteriores(monkeypatch):
    def item(identifier, objeto):
        return {
            "numeroControlePNCP": identifier,
            "orgaoEntidade": {"razaoSocial": "Prefeitura", "cnpj": "12345678000199"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Porto Alegre"},
            "objetoCompra": objeto,
            "dataPublicacaoPncp": "2026-08-01",
            "modalidadeId": 4,
            "modalidadeNome": "Concorrência",
            "anoCompra": "2026",
            "sequencialCompra": identifier,
        }

    async def fake_fetch(_client, _semaphore, _url, params, _headers, **_kwargs):
        page = params["pagina"]
        return pncp_service.PageFetchResult(
            page=page,
            items={1: [item("primeiro", "Reforma de escola")], 2: [item("segundo", "Pavimentação de vias")]}[page],
            total_registros=2,
        )

    async def no_local(**_kwargs):
        return None

    async def fake_client():
        return _DummyClient()

    monkeypatch.setattr(pncp_service, "fetch_pagina", fake_fetch)
    monkeypatch.setattr(pncp_service, "_resultado_local_disponivel", no_local)
    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", fake_client)
    monkeypatch.setattr(pncp_service, "_persistir_obras_consulta", lambda _dados: None)

    events = [
        event
        async for event in pncp_service.stream_licitacoes_construction(
            "20260801", "20260801", modalidade=4, max_paginas=2, termo="pavimentação"
        )
    ]

    assert events[0]["total_encontradas"] == 0
    assert [obra["id_pncp"] for obra in events[1]["dados"]] == ["segundo"]
    assert events[-1]["metadados"]["total_filtrado"] == 1


@pytest.mark.asyncio
async def test_snapshot_serializa_agregados_decimais_antes_de_emitir_cursor(monkeypatch):
    captured = {}
    now = datetime.now(timezone.utc)

    def save_snapshot(**kwargs):
        captured.update(kwargs)
        return pncp_service.QuerySnapshot(
            id="snapshot-json",
            fingerprint=kwargs["fingerprint"],
            dados=kwargs["dados"],
            resultado=kwargs["resultado"],
            created_at=now,
            expires_at=now + timedelta(minutes=5),
        )

    monkeypatch.setattr(pncp_service, "salvar_snapshot_consulta", save_snapshot)
    result = await pncp_service._snapshot_and_paginate(
        {
            "status": "sucesso_local",
            "mensagem": "ok",
            "total_encontradas": 16,
            "dados": [{"id_pncp": str(index)} for index in range(16)],
            "metadados": {"volume_estimado": Decimal("12.50")},
        },
        fingerprint="filtro",
        tamanho_resultado=15,
    )

    assert captured["resultado"]["metadados"]["volume_estimado"] == "12.50"
    assert result["paginacao"]["tem_mais"] is True
