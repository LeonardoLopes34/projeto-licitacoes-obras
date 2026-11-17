import json
from pathlib import Path

import pytest

from backend.services.search_filter_service import (
    DEFAULT_SEARCH_SCOPE,
    MAX_SEARCH_TERM_LENGTH,
    SEARCH_PARSER_VERSION,
    SearchExpressionError,
    aplicar_busca,
    avaliar_busca,
    normalizar_texto_busca,
    parse_search_expression,
    parse_search_request,
    termo_corresponde,
)


FIXTURE = Path(__file__).parents[3] / "tests" / "fixtures" / "casos_busca_014.json"


def test_fixture_anotada_cobre_casos_de_busca_e_auditoria():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))

    for case in cases:
        expression = parse_search_expression(
            case["expressao"], escopo_busca=case.get("escopo_busca", DEFAULT_SEARCH_SCOPE)
        )
        result = avaliar_busca(case["registro"], expression)
        expected = case["esperado"]

        assert result.aprovado is expected["aprovado"], case["id"]
        assert result.motivo_filtro == expected["motivo_filtro"], case["id"]
        if "termo" in expected:
            found_terms = result.termos_excluidos or result.termos_correspondentes
            found_fields = result.campos_excluidos or result.campos_correspondentes
            assert expected["termo"] in found_terms, case["id"]
            assert expected["campo"] in found_fields, case["id"]


def test_parser_separa_inclusao_exclusao_frase_e_hifen_interno():
    expression = parse_search_expression(
        'pavimentação obra-de-arte -drenagem -"registro de preços"'
    )

    assert [term.normalizado for term in expression.inclusoes] == [
        "pavimentacao",
        "obra de arte",
    ]
    assert [term.normalizado for term in expression.exclusoes] == [
        "drenagem",
        "registro de precos",
    ]
    assert expression.exclusoes[1].frase is True
    assert expression.versao_parser == SEARCH_PARSER_VERSION


@pytest.mark.parametrize(
    "expression",
    ['"sem fim', "-", "- pavimentação", 'pavi"mentação', "x" * 1_001],
)
def test_parser_rejeita_expressoes_ambiguas_ou_abusivas(expression):
    with pytest.raises(SearchExpressionError):
        parse_search_expression(expression)


def test_parser_aceita_vazio_e_listas_estruturadas_sem_ambiguidade():
    empty = parse_search_expression("   ")
    structured = parse_search_request(
        termos_inclusao=["pavimentação"],
        termos_exclusao=["drenagem", '"registro de preços"'],
        escopo_busca="todos_metadados",
        modo_inclusao="todos",
    )

    assert empty.possui_termos is False
    assert [term.normalizado for term in structured.inclusoes] == ["pavimentacao"]
    assert [term.normalizado for term in structured.exclusoes] == [
        "drenagem",
        "registro de precos",
    ]
    assert structured.escopo == "todos_metadados"
    assert structured.modo_inclusao == "todos"

    with pytest.raises(SearchExpressionError, match="não ambos"):
        parse_search_request("pavimentação", termos_exclusao=["drenagem"])


def test_parser_valida_tamanho_individual_e_opcoes():
    with pytest.raises(SearchExpressionError, match="cada termo"):
        parse_search_expression("a" * (MAX_SEARCH_TERM_LENGTH + 1))
    with pytest.raises(SearchExpressionError, match="escopo_busca"):
        parse_search_expression("obra", escopo_busca="orgao")
    with pytest.raises(SearchExpressionError, match="modo_inclusao"):
        parse_search_expression("obra", modo_inclusao="nenhum")


def test_normalizacao_limites_de_palavra_e_frases_contiguas():
    assert normalizar_texto_busca("  PAVIMENTAÇÃO: das-vias  ") == "pavimentacao das vias"
    assert termo_corresponde("Pavimentação de vias", "pavimentacao") is True
    assert termo_corresponde("Repavimentacao de vias", "pavimentacao") is False
    assert termo_corresponde("Registro de preços para obra", "registro de precos") is True
    assert termo_corresponde("Registro municipal de novos preços", "registro de precos") is False


def test_modo_todos_exige_cada_termo_em_algum_campo_do_escopo():
    expression = parse_search_request(
        termos_inclusao=["pavimentação", "metálica"], modo_inclusao="todos"
    )
    only_one = avaliar_busca(
        {"objeto": "Pavimentação de vias", "status_classificacao": "aprovado"}, expression
    )
    split_between_object_and_item = avaliar_busca(
        {
            "objeto": "Pavimentação de vias",
            "itens": [{"descricao": "Estrutura metálica para abrigo"}],
            "status_classificacao": "aprovado",
        },
        expression,
    )

    assert only_one.motivo_filtro == "nao_corresponde_termo"
    assert split_between_object_and_item.aprovado is True


@pytest.mark.parametrize(
    ("term", "field", "value"),
    [
        ("curitiba", "municipio", "Curitiba"),
        ("pregao", "modalidade", "Pregão eletrônico"),
        ("dados abertos", "fonte", "Dados abertos do PNCP"),
    ],
)
def test_todos_metadados_habilita_campos_extras(term, field, value):
    record = {"objeto": "Reforma de escola", field: value, "status_classificacao": "aprovado"}
    default = avaliar_busca(record, parse_search_expression(term))
    expanded = avaliar_busca(
        record, parse_search_expression(term, escopo_busca="todos_metadados")
    )

    assert default.motivo_filtro == "nao_corresponde_termo"
    assert expanded.aprovado is True
    assert expanded.campos_correspondentes == (field,)


def test_exclusao_do_usuario_nao_depende_dos_pesos_do_classificador():
    expression = parse_search_expression("pavimentação -drenagem")
    approved = avaliar_busca(
        {
            "objeto": "Pavimentação com drenagem pluvial",
            "status_classificacao": "aprovado",
            "score_classificacao": 99,
        },
        expression,
    )
    review = avaliar_busca(
        {
            "objeto": "Pavimentação com drenagem pluvial",
            "status_classificacao": "revisao_pendente",
            "score_classificacao": -99,
        },
        expression,
    )

    assert approved.motivo_filtro == review.motivo_filtro == "excluido_por_termo"


def test_aplicar_busca_nao_expoe_registros_excluidos_e_retorna_auditoria():
    expression = parse_search_expression("pavimentação -drenagem")
    result = aplicar_busca(
        [
            {"id_pncp": "entra", "objeto": "Pavimentação de vias", "status_classificacao": "aprovado"},
            {"id_pncp": "sai", "objeto": "Pavimentação com drenagem", "status_classificacao": "aprovado"},
            {"id_pncp": "rejeita", "objeto": "Pavimentação", "status_classificacao": "rejeitado"},
        ],
        expression,
        anexar_metadados=True,
    )
    metadata = result.metadados(expression)

    assert [record["id_pncp"] for record in result.registros] == ["entra"]
    assert result.registros[0]["metadados_busca"]["motivo_filtro"] == "incluido_por_termo"
    assert metadata["contagens_busca"] == {
        "total_avaliado": 3,
        "total_incluido": 1,
        "total_excluido_por_termo": 1,
        "total_sem_correspondencia": 0,
        "total_rejeitado_classificacao": 1,
        "total_revisao_pendente": 0,
    }
    assert metadata["campos_correspondentes"] == {"objeto": 1}
