import pytest
from cachetools import TTLCache
from decimal import Decimal

from pydantic import TypeAdapter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models.obra_model import ObraModel
from backend.schemas import ObraOut
from backend.services.db_service import upsert_obras
from backend.services import pncp_service
from backend.services.tipo_contratacao import normalizar_campos_tipo_contratacao


def test_normaliza_tipo_composto_sem_duplicar_criterio_na_modalidade():
    result = normalizar_campos_tipo_contratacao(
        {
            "modalidadeNome": "Concorrência por Menor Preço",
            "modalidadeId": 4,
            "criterioJulgamentoNome": "Menor Preço",
            "tipoInstrumentoConvocatorioNome": "Edital",
        }
    )

    assert result == {
        "modalidade": "Concorrência por Menor Preço",
        "modalidade_codigo": 4,
        "criterio_julgamento": "Menor Preço",
        "tipo_instrumento": "Edital",
        "tipo_contratacao": "Concorrência por Menor Preço - Menor Preço",
        "tipo_contratacao_origem": {
            "modalidade": "modalidadeNome",
            "criterio_julgamento": "criterioJulgamentoNome",
            "tipo_instrumento": "tipoInstrumentoConvocatorioNome",
            "tipo_contratacao": "composto:modalidade,criterio_julgamento",
        },
    }


def test_normaliza_tipo_com_somente_modalidade():
    result = normalizar_campos_tipo_contratacao(
        {"modalidade": "Pregão - Eletrônico", "modalidade_codigo": "6"}
    )

    assert result["modalidade"] == "Pregão - Eletrônico"
    assert result["criterio_julgamento"] is None
    assert result["tipo_contratacao"] == "Pregão - Eletrônico"
    assert result["tipo_contratacao_origem"] == {
        "modalidade": "modalidade",
        "tipo_contratacao": "modalidade",
    }


def test_normaliza_modalidade_resumida_com_criterio_no_formato_do_portal():
    result = normalizar_campos_tipo_contratacao(
        {
            "modalidadeNome": "Concorrência - Eletrônica",
            "criterioJulgamentoNome": "Menor preço",
        }
    )

    assert result["tipo_contratacao"] == "Concorrência por Menor Preço - Menor Preço"


@pytest.mark.asyncio
async def test_busca_tipo_consulta_itens_sem_abrir_o_edital(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"criterioJulgamentoNome": "Menor preço"}]

    class FakeClient:
        async def get(self, url, **kwargs):
            captured["url"] = url
            captured["params"] = kwargs["params"]
            return FakeResponse()

    async def fake_client():
        return FakeClient()

    monkeypatch.setattr(pncp_service, "obter_cliente_pncp", fake_client)
    monkeypatch.setattr(pncp_service, "_TIPO_CONTRATACAO_CACHE", TTLCache(maxsize=4, ttl=60))
    monkeypatch.setattr(pncp_service, "_TIPO_CONTRATACAO_INFLIGHT", {})

    result = await pncp_service.buscar_tipo_contratacao_pncp(
        "87897740000150",
        2026,
        157,
        modalidade="Concorrência - Eletrônica",
        tipo_instrumento="Edital",
    )

    assert captured["url"].endswith("/compras/2026/157/itens")
    assert captured["params"] == {"pagina": 1, "tamanhoPagina": 50}
    assert result["tipo_contratacao"] == "Concorrência por Menor Preço - Menor Preço"


def test_normaliza_tipo_ausente_sem_inventar_valores():
    result = normalizar_campos_tipo_contratacao({"modalidadeId": 4})

    assert result == {
        "modalidade": None,
        "modalidade_codigo": 4,
        "criterio_julgamento": None,
        "tipo_instrumento": None,
        "tipo_contratacao": None,
        "tipo_contratacao_origem": None,
    }


def test_schema_e_persistencia_preservam_campos_de_tipo():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tipos = normalizar_campos_tipo_contratacao(
        {
            "modalidadeNome": "Concorrência por Menor Preço",
            "modalidadeId": 4,
            "criterioJulgamentoNome": "Menor Preço",
        }
    )
    item = {
        "id_pncp": "12345678901234-1-000001/2026",
        "orgao": "Órgão teste",
        "uf": "SP",
        "objeto": "Construção de escola",
        "valor_estimado": Decimal("10.00"),
        "data_publicacao": "2026-09-14T10:00:00+00:00",
        **tipos,
    }

    with Session(engine) as session:
        assert upsert_obras(session, [item]) == 1
        obra = session.scalar(select(ObraModel))
        payload = TypeAdapter(ObraOut).validate_python(obra.to_dict()).model_dump(mode="json")

    assert payload["tipo_contratacao"] == "Concorrência por Menor Preço - Menor Preço"
    assert payload["criterio_julgamento"] == "Menor Preço"
    assert payload["tipo_contratacao_origem"]["modalidade"] == "modalidadeNome"
