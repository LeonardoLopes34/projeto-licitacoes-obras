from pydantic import TypeAdapter
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models.obra_model import ObraModel
from backend.schemas import ObraOut
from backend.services.db_service import upsert_obras
from backend.services.pncp_service import processar_itens_raw

RAW = {
    "numeroControlePNCP": "12345678901234-1-000001/2026",
    "orgaoEntidade": {"cnpj": "12345678901234", "razaoSocial": "Prefeitura"},
    "unidadeOrgao": {"ufSigla": "RS"},
    "anoCompra": 2026,
    "sequencialCompra": 1,
    "modalidadeId": 4,
    "objetoCompra": "Construção de escola municipal",
    "dataPublicacaoPncp": "2026-11-16T10:00:00",
    "dataAberturaProposta": "2026-11-17T08:00:00",
    "dataEncerramentoProposta": "2026-12-01T09:30:00",
}


def test_datas_da_proposta_saem_do_pncp_e_do_banco_local():
    [normalizado] = processar_itens_raw([RAW], data_inicial="20261116", data_final="20261116", modalidade=0)
    ao_vivo = TypeAdapter(ObraOut).validate_python(normalizado).model_dump(mode="json")
    assert ao_vivo["data_abertura_proposta"] == "2026-11-17T08:00:00"
    assert ao_vivo["data_encerramento_proposta"] == "2026-12-01T09:30:00"

    # Registro salvo antes do campo existir: as datas vêm do payload original guardado.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        assert upsert_obras(session, [normalizado]) == 1
        local = session.scalar(select(ObraModel)).to_dict()
    assert local["data_abertura_proposta"] == "2026-11-17T08:00:00"
    assert local["data_encerramento_proposta"] == "2026-12-01T09:30:00"


def test_sem_datas_no_pncp_fica_none():
    sem = {k: v for k, v in RAW.items() if not k.startswith("dataAbertura") and not k.startswith("dataEncerramento")}
    [normalizado] = processar_itens_raw([sem], data_inicial="20261116", data_final="20261116", modalidade=0)
    assert normalizado["data_abertura_proposta"] is None
    assert normalizado["data_encerramento_proposta"] is None
