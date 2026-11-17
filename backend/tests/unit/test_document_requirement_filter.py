from backend.services.document_requirement_filter import filtrar_exigencias_documentais


def _candidate(categoria: str, evidencia: str, pagina: int = 1) -> dict:
    return {
        "categoria": categoria,
        "evidencia": evidencia,
        "descricao_original": evidencia,
        "pagina": pagina,
        "status": "identificado_no_edital",
    }


def test_mantem_documentos_explicitamente_exigidos_por_categoria():
    candidates = [
        _candidate("habilitacao_juridica", "A licitante deverá apresentar contrato social atualizado."),
        _candidate("qualificacao_tecnica", "Deverá apresentar atestado de capacidade técnica."),
        _candidate("regularidade_fiscal_social_trabalhista", "Apresentar certidão de regularidade do FGTS."),
        _candidate("qualificacao_economico_financeira", "A empresa deverá juntar balanço patrimonial."),
        _candidate("declaracoes", "A licitante deverá apresentar declaração de inexistência de impedimento."),
    ]

    result = filtrar_exigencias_documentais(candidates)

    assert result.exigencias == candidates
    assert result.rejeitadas == []


def test_remove_contextos_de_execucao_que_so_mencionam_atestado_ou_entrega():
    candidates = [
        _candidate(
            "qualificacao_tecnica",
            "data do atestado de conformidade e entrega da(s) nota(s) fiscal(is).",
            pagina=39,
        ),
        _candidate(
            "qualificacao_tecnica",
            "períodos a serem definidos pela Unidade do DNIT sendo acompanhadas por um servidor da mesma unidade que certificará a visita, expedindo o atestado de conformidade.",
            pagina=26,
        ),
        _candidate(
            "qualificacao_tecnica",
            "A contratada deverá apresentar ART durante a execução contratual.",
            pagina=63,
        ),
    ]

    result = filtrar_exigencias_documentais(candidates)

    assert result.exigencias == []
    assert len(result.rejeitadas) == 3
    assert "nota fiscal" in result.rejeitadas[0]["motivo"]


def test_remove_categoria_sem_tipo_de_documento_e_mencao_sem_acao():
    candidates = [
        _candidate("qualificacao_tecnica", "Comprovação de qualificação técnica para executar o objeto."),
        _candidate("qualificacao_tecnica", "O atestado será conferido pela fiscalização."),
    ]

    result = filtrar_exigencias_documentais(candidates)

    assert result.exigencias == []
    assert {item["motivo"] for item in result.rejeitadas} == {
        "categoria mencionada sem tipo de documento identificável",
        "documento citado sem ação explícita de apresentação ou comprovação",
    }


def test_remove_duplicata_apenas_apos_normalizar_numeracao_e_pontuacao():
    candidates = [
        _candidate("qualificacao_tecnica", "8.4.1 A licitante deverá apresentar atestado de capacidade técnica."),
        _candidate("qualificacao_tecnica", "Item 8.4.2: A LICITANTE deverá apresentar atestado de capacidade técnica!", pagina=2),
        _candidate(
            "qualificacao_tecnica",
            "A licitante deverá apresentar atestado de capacidade técnica profissional.",
            pagina=3,
        ),
    ]

    result = filtrar_exigencias_documentais(candidates)

    assert len(result.exigencias) == 2
    assert result.exigencias[0]["pagina"] == 1
    assert result.exigencias[1]["pagina"] == 3
    assert result.rejeitadas[0]["motivo"] == "exigência duplicada após normalização do texto"

