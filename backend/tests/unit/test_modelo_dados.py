from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models.obra_model import ObraModel, validar_modalidade
from backend.services.db_service import upsert_obras


def test_modalidade_invalida_e_rejeitada():
    with pytest.raises(ValueError):
        validar_modalidade(999, permitir_todas=False)


def test_cnpj_alfanumerico_e_precisao_decimal():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    item = {
        "id_pncp": "ABC123-1-000001/2026",
        "numero_controle_pncp": "ABC123-1-000001/2026",
        "cnpj": "A1B2C3D4E5F601",
        "ano": 2026,
        "sequencial": 1,
        "orgao": "Órgão teste",
        "uf": "SP",
        "objeto": "Construção de escola",
        "valor_estimado": "1234567.89",
        "data_publicacao": "2026-08-24T10:00:00+00:00",
        "modalidade": "Concorrência",
        "modalidade_codigo": 4,
        "fonte": "PNCP_REAL",
        "payload_original": {"cnpj": "A1B2C3D4E5F601"},
    }
    with Session(engine) as session:
        assert upsert_obras(session, [item]) == 1
        obra = session.scalar(select(ObraModel))

    assert obra.cnpj == "A1B2C3D4E5F601"
    assert obra.valor_estimado == Decimal("1234567.8900")
    assert obra.payload_original["cnpj"] == "A1B2C3D4E5F601"
