import pytest
from pydantic import ValidationError

from backend.schemas import ExigenciaOut, ResultadoExigencias


def test_resultado_de_exigencias_preserva_evidencia_rastreavel():
    result = ResultadoExigencias(
        status="sucesso",
        mensagem="Exigências identificadas no edital.",
        total_exigencias=1,
        categorias={"qualificacao_tecnica": 1},
        exigencias=[
            ExigenciaOut(
                categoria="qualificacao_tecnica",
                rotulo="Atestado de capacidade técnica",
                descricao_original="Apresentar atestado de capacidade técnica.",
                documento_id=1,
                titulo_documento="Edital",
                pagina=18,
                evidencia="8.4.1 Apresentar atestado de capacidade técnica.",
                confianca=0.86,
                origem_texto="pdf_texto",
                status="identificado_no_edital",
            )
        ],
        analisador_versao="ocr-edital-v1",
    )

    assert result.exigencias[0].pagina == 18
    assert result.categorias["qualificacao_tecnica"] == 1


def test_exigencia_rejeita_pagina_ou_evidencia_invalida():
    with pytest.raises(ValidationError):
        ExigenciaOut(
            categoria="qualificacao_tecnica",
            rotulo="Atestado",
            descricao_original="Apresentar atestado.",
            documento_id=1,
            titulo_documento="Edital",
            pagina=0,
            evidencia="",
            confianca=0.8,
            origem_texto="pdf_texto",
            status="identificado_no_edital",
        )
