from fastapi.testclient import TestClient

import backend.main as main_module
from backend.services.ocr_service import TesseractAvailability


def result_fixture(status="sucesso"):
    return {
        "status": status,
        "mensagem": "Exigências identificadas no edital.",
        "total_exigencias": 1,
        "categorias": {"qualificacao_tecnica": 1},
        "documentos_analisados": [
            {
                "documento_id": 1,
                "titulo": "Edital",
                "url": "https://pncp.gov.br/edital.pdf",
                "paginas": 10,
                "paginas_com_ocr": 0,
                "status": "analisado",
            }
        ],
        "exigencias": [
            {
                "categoria": "qualificacao_tecnica",
                "rotulo": "Atestado de capacidade técnica",
                "descricao_original": "Apresentar atestado de capacidade técnica.",
                "documento_id": 1,
                "titulo_documento": "Edital",
                "url_documento": "https://pncp.gov.br/edital.pdf",
                "pagina": 4,
                "evidencia": "Apresentar atestado de capacidade técnica.",
                "confianca": 0.85,
                "origem_texto": "pdf_texto",
                "status": "identificado_no_edital",
            }
        ],
        "analisador_versao": "ocr-edital-v1",
        "origem": "PNCP",
    }


def test_endpoint_exigencias_retorna_contrato_e_reprocessamento(monkeypatch):
    calls = []

    async def fake_analyze(cnpj, ano, sequencial, *, forcar=False):
        calls.append((cnpj, ano, sequencial, forcar))
        return result_fixture()

    monkeypatch.setattr(main_module.edital_analysis_service, "analisar_contratacao", fake_analyze)
    response = TestClient(main_module.app).get(
        "/api/v1/obras/12345678901234/2026/7/exigencias?forcar=true"
    )

    assert response.status_code == 200
    assert response.json()["exigencias"][0]["pagina"] == 4
    assert calls == [("12345678901234", 2026, 7, True)]


def test_endpoint_exigencias_rejeita_identificador_inseguro():
    response = TestClient(main_module.app).get(
        "/api/v1/obras/123-45678901234/2026/7/exigencias"
    )

    assert response.status_code == 422


def test_health_informa_ocr_degradado_sem_expor_detalhes_do_ambiente(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "verificar_disponibilidade_tesseract",
        lambda: TesseractAvailability("binario_ausente", "por", None, (), "Tesseract não está instalado."),
    )

    response = TestClient(main_module.app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degradado"
    assert response.json()["ocr"] == {
        "status": "binario_ausente",
        "idioma": "por",
        "versao": None,
        "erro": "Tesseract não está instalado.",
    }
