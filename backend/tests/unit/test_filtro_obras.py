import json
from pathlib import Path

from backend.services.pncp_service import (
    _ordenar_e_resumir_consulta,
    avaliar_filtro,
    classificar_obra,
    eh_obra_pavimentacao,
)


FIXTURE = Path(__file__).parents[3] / "tests" / "fixtures" / "casos_filtro.json"


def test_fixture_de_filtro_mantem_casos_conhecidos():
    casos = json.loads(FIXTURE.read_text(encoding="utf-8"))
    metricas = avaliar_filtro(casos)

    assert metricas["acuracia"] == 1.0
    assert metricas["precisao"] == 1.0
    assert metricas["cobertura"] == 1.0


def test_contexto_hospitalar_e_cabo_eletrico():
    assert classificar_obra("Reforma de ala hospitalar") == "aprovado"
    assert classificar_obra("Aquisição de cabo elétrico") == "rejeitado"


def test_registro_de_precos_para_contratacao_futura_eh_excluido():
    descricao = (
        "Registro de Preços destinado à futura e eventual contratação de empresa "
        "para execução de obras de pavimentação asfáltica."
    )

    assert classificar_obra(descricao) == "rejeitado"


def test_filtro_de_pavimentacao_reconhece_variacoes_do_objeto():
    assert eh_obra_pavimentacao("Pavimentação asfáltica com drenagem") is True
    assert eh_obra_pavimentacao("Recapeamento de vias urbanas") is True
    assert eh_obra_pavimentacao("Reforma de escola municipal") is False


def test_filtro_opcional_pode_excluir_obras_de_pavimentacao():
    dados, resumo = _ordenar_e_resumir_consulta(
        [
            {"id_pncp": "1", "objeto": "Reforma de escola", "data_publicacao": "2026-09-01"},
            {"id_pncp": "2", "objeto": "Pavimentação asfáltica", "data_publicacao": "2026-09-02"},
            {"id_pncp": "3", "objeto": "Recapeamento de vias", "data_publicacao": "2026-09-03"},
        ],
        termo=None,
        ordenacao="data_desc",
        incluir_pavimentacao=False,
    )

    assert [obra["id_pncp"] for obra in dados] == ["1"]
    assert resumo["total_coletado"] == 3
    assert resumo["total_filtrado"] == 1
