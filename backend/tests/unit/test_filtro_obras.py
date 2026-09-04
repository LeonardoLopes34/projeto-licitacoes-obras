import json
from pathlib import Path

from backend.services.pncp_service import avaliar_filtro, classificar_obra


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
