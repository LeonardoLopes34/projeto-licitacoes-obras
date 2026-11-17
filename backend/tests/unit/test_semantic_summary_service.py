import pytest

from backend.services.semantic_summary_service import gerar_descricao_resumida


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        (
            "Declaração de atendimento e cumprimento de legislação e normas vigentes.",
            "Comprovação de conformidade com a legislação e as normas vigentes.",
        ),
        (
            "Prestar declaração sobre a veracidade das informações apresentadas.",
            "Declaração de veracidade das informações e dos documentos apresentados.",
        ),
        (
            "Declaração de inidoneidade enquanto perdurarem os motivos.",
            "Declaração de que a empresa não está declarada inidônea para contratar.",
        ),
        (
            "Preenchimento em campo próprio do sistema eletrônico da licitação.",
            "Preenchimento das declarações obrigatórias no sistema eletrônico da licitação.",
        ),
    ],
)
def test_gera_descricao_semantica_para_declaracoes(texto, esperado):
    assert gerar_descricao_resumida("declaracoes", texto) == esperado


def test_fallback_por_categoria_nao_copia_o_texto_original():
    original = "Apresentar documento complementar específico conforme exigência do edital."

    resumo = gerar_descricao_resumida("qualificacao_tecnica", original)

    assert resumo == "Comprovação da capacidade técnica para executar o objeto."
    assert resumo != original


def test_fallback_para_categoria_desconhecida_e_seguro():
    assert gerar_descricao_resumida("categoria_nova", "Texto não classificado.") == (
        "Exigência identificada no edital para análise do licitante."
    )


def test_localizador_preserva_evidencia_e_adiciona_resumo():
    from backend.services.edital_analysis_service import SelectedDocument, localizar_exigencias
    from backend.services.pdf_text_service import PageText

    evidencia = "A licitante deverá apresentar declaração de inexistência de impedimento."
    entries = localizar_exigencias(
        documento=SelectedDocument(1, "Edital", "https://pncp.gov.br/edital.pdf", 0, True),
        paginas=[(PageText(1, evidencia, len(evidencia), 1.0, "texto_suficiente"), "pdf_texto", None)],
    )

    assert len(entries) == 1
    assert entries[0]["descricao_resumida"] == (
        "Declaração de que a empresa não possui impedimento para participar ou contratar."
    )
    assert entries[0]["descricao_original"] == evidencia
    assert entries[0]["evidencia"] == evidencia
