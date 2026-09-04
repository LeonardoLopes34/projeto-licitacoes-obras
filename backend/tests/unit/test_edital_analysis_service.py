import asyncio
import hashlib
from datetime import datetime, timezone

import pytest

from backend.services import edital_analysis_service
from backend.schemas import ResultadoExigencias
from backend.services.edital_analysis_repository import AnalisePersistida
from backend.services.edital_analysis_service import (
    EditalAnalysisService,
    SelectedDocument,
    localizar_exigencias,
    selecionar_documentos_para_analise,
)
from backend.services.pdf_download_service import DownloadedPdf, DownloadedZip
from backend.services.pdf_download_service import PdfDownloadError
from backend.services.pdf_text_service import PageText, PdfTextResult


@pytest.fixture(autouse=True)
def no_persistent_cache_in_unit_tests(monkeypatch):
    monkeypatch.setattr(edital_analysis_service, "obter_analise", lambda *args, **kwargs: None)
    monkeypatch.setattr(edital_analysis_service, "salvar_analise", lambda *args, **kwargs: None)


def test_selecao_prioriza_edital_sem_ocultar_outros_documentos():
    selected = selecionar_documentos_para_analise(
        [
            {"sequencial_documento": 3, "titulo": "Minuta de contrato", "url": "https://pncp.gov.br/minuta.pdf"},
            {"sequencial_documento": 2, "tipo_documento_nome": "Anexo", "titulo": "Anexo de habilitação"},
            {"sequencial_documento": 1, "titulo": "Edital de concorrência"},
        ]
    )

    assert [item.documento_id for item in selected] == [1, 2, 3]
    assert [item.selecionado for item in selected] == [True, True, False]


def test_termo_de_referencia_fica_visivel_mas_nao_e_habilitacao_automatica():
    selected = selecionar_documentos_para_analise(
        [{"sequencial_documento": 1, "titulo": "Termo de referência", "url": "https://pncp.gov.br/tr.pdf"}]
    )

    assert selected[0].prioridade == 3
    assert selected[0].selecionado is False


def test_localizador_classifica_com_evidencia_e_exclui_execucao():
    document = SelectedDocument(1, "Edital", "https://pncp.gov.br/edital.pdf", 0, True)
    page = PageText(
        pagina=8,
        texto=(
            "A licitante deverá apresentar contrato social atualizado.\n"
            "Deverá apresentar atestado de capacidade técnica.\n"
            "Apresentar certidão de regularidade do FGTS e CND trabalhista.\n"
            "Apresentar balanço patrimonial e declaração de inexistência de impedimento.\n"
            "A contratada deverá apresentar ART durante a execução contratual."
        ),
        caracteres=300,
        proporcao_imprimivel=1.0,
        status="texto_suficiente",
    )

    entries = localizar_exigencias(documento=document, paginas=[(page, "pdf_texto", None)])

    categories = {entry["categoria"] for entry in entries}
    assert categories == {
        "habilitacao_juridica",
        "qualificacao_tecnica",
        "regularidade_fiscal_social_trabalhista",
        "qualificacao_economico_financeira",
        "declaracoes",
    }
    assert all(entry["pagina"] == 8 and entry["evidencia"] for entry in entries)
    assert all("ART" not in entry["evidencia"] for entry in entries)


@pytest.mark.asyncio
async def test_analise_usa_cache_por_hash_sem_reextrair(monkeypatch):
    content = b"%PDF-1.7 edit"
    downloaded = DownloadedPdf(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        url_final="https://pncp.gov.br/edital.pdf",
        content_type="application/pdf",
    )
    download_calls = 0
    extraction_calls = 0

    async def fake_download(url):
        nonlocal download_calls
        download_calls += 1
        return downloaded

    def fake_extract(content):
        nonlocal extraction_calls
        extraction_calls += 1
        return PdfTextResult(
            paginas=[
                PageText(
                    pagina=1,
                    texto="A licitante deverá apresentar atestado de capacidade técnica.",
                    caracteres=64,
                    proporcao_imprimivel=1,
                    status="texto_suficiente",
                )
            ],
            parser="fixture",
        )

    monkeypatch.setattr(edital_analysis_service, "extrair_texto_pdf", fake_extract)
    service = EditalAnalysisService(downloader=fake_download)
    documents = [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}]

    first = await service.analisar_documentos(documents, contratacao_key="123:2026:1")
    second = await service.analisar_documentos(documents, contratacao_key="123:2026:1")

    assert first.status == "sucesso"
    assert first.total_exigencias == 1
    assert second.total_exigencias == 1
    assert download_calls == 2
    assert extraction_calls == 1
    assert service.metrics["cache_hits"] == 1


@pytest.mark.asyncio
async def test_analise_retorna_ultima_versao_quando_documentos_estao_desatualizados(monkeypatch):
    updated_at = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    previous = ResultadoExigencias(
        status="sucesso",
        mensagem="Análise anterior.",
        total_exigencias=1,
        analisador_versao="ocr-edital-v1",
    )

    async def stale_documents(*args, **kwargs):
        return {"documentos": [], "desatualizado": True}

    monkeypatch.setattr(edital_analysis_service, "buscar_documentos_pncp", stale_documents)
    monkeypatch.setattr(
        edital_analysis_service,
        "obter_ultima_analise_com_atualizacao",
        lambda *args, **kwargs: AnalisePersistida(previous, updated_at),
    )

    result = await EditalAnalysisService().analisar_contratacao("12345678901234", 2026, 7)

    assert result.status == "sucesso"
    assert result.origem == "cache_persistente"
    assert result.desatualizado is True
    assert result.atualizado_em == "2026-09-03T12:00:00+00:00"
    assert "última análise" in result.mensagem


@pytest.mark.asyncio
async def test_falha_de_download_nao_quebra_metricas_de_paginacao():
    async def failed_download(url):
        raise PdfDownloadError("Não foi possível baixar o PDF.")

    service = EditalAnalysisService(downloader=failed_download)

    result = await service.analisar_documentos(
        [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}],
        contratacao_key="123:2026:download-falhou",
    )

    assert result.status == "erro"
    assert result.documentos_analisados[0].status == "erro"
    assert result.documentos_analisados[0].paginas == 0
    assert result.documentos_analisados[0].paginas_com_ocr == 0
    assert service.metrics["pages_ocr"] == 0


@pytest.mark.asyncio
async def test_falha_de_ocr_devolve_resultado_parcial_sem_inventar_item(monkeypatch):
    content = b"%PDF-1.7 image"
    downloaded = DownloadedPdf(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        url_final="https://pncp.gov.br/anexo.pdf",
        content_type="application/pdf",
    )

    async def fake_download(url):
        return downloaded

    monkeypatch.setattr(
        edital_analysis_service,
        "extrair_texto_pdf",
        lambda content: PdfTextResult(
            paginas=[PageText(1, "", 0, 0.0, "sem_texto")],
            parser="fixture",
        ),
    )
    monkeypatch.setattr(edital_analysis_service, "renderizar_pagina_para_ocr", lambda content, page: object())

    class FailedOcr:
        def reconhecer(self, image, pagina):
            from backend.services.ocr_service import OcrPageResult

            return OcrPageResult(pagina, "", None, "por", 1, "erro", "indisponível")

    result = await EditalAnalysisService(downloader=fake_download, ocr_service=FailedOcr()).analisar_documentos(
        [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/anexo.pdf"}],
        contratacao_key="123:2026:2",
    )

    assert result.status == "sucesso_parcial"
    assert result.total_exigencias == 0
    assert result.documentos_analisados[0].status == "analise_parcial"


@pytest.mark.asyncio
async def test_requisicoes_concorrentes_compartilham_o_mesmo_processamento(monkeypatch):
    content = b"%PDF-1.7 concurrent"
    downloaded = DownloadedPdf(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        url_final="https://pncp.gov.br/edital.pdf",
        content_type="application/pdf",
    )
    download_calls = 0

    async def fake_download(url):
        nonlocal download_calls
        download_calls += 1
        await asyncio.sleep(0.02)
        return downloaded

    monkeypatch.setattr(
        edital_analysis_service,
        "extrair_texto_pdf",
        lambda content: PdfTextResult(
            paginas=[PageText(1, "Apresentar atestado técnico.", 29, 1.0, "texto_suficiente")],
            parser="fixture",
        ),
    )
    service = EditalAnalysisService(downloader=fake_download)
    documents = [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}]

    first, second = await asyncio.gather(
        service.analisar_documentos(documents, contratacao_key="123:2026:3"),
        service.analisar_documentos(documents, contratacao_key="123:2026:3"),
    )

    assert first.total_exigencias == second.total_exigencias == 1
    assert download_calls == 1


@pytest.mark.asyncio
async def test_analisa_todos_os_pdfs_extraidos_de_um_zip(monkeypatch):
    first_content = b"%PDF-1.7 edital"
    second_content = b"%PDF-1.7 anexo"
    archive_content = b"arquivo zip de teste"
    archive = DownloadedZip(
        pdfs=(
            DownloadedPdf(
                content=first_content,
                sha256=hashlib.sha256(first_content).hexdigest(),
                url_final="https://pncp.gov.br/edital.zip",
                content_type="application/pdf",
            ),
            DownloadedPdf(
                content=second_content,
                sha256=hashlib.sha256(second_content).hexdigest(),
                url_final="https://pncp.gov.br/edital.zip",
                content_type="application/pdf",
            ),
        ),
        sha256=hashlib.sha256(archive_content).hexdigest(),
        url_final="https://pncp.gov.br/edital.zip",
        content_type="application/zip",
    )

    async def fake_download(url):
        return archive

    def fake_extract(content):
        text = (
            "A licitante deverá apresentar atestado de capacidade técnica."
            if content == first_content
            else "A licitante deverá apresentar declaração de inexistência de impedimento."
        )
        return PdfTextResult(
            paginas=[PageText(1, text, len(text), 1.0, "texto_suficiente")],
            parser="fixture",
        )

    monkeypatch.setattr(edital_analysis_service, "extrair_texto_pdf", fake_extract)
    result = await EditalAnalysisService(downloader=fake_download).analisar_documentos(
        [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.zip"}],
        contratacao_key="123:2026:zip",
    )

    assert result.status == "sucesso"
    assert result.documentos_analisados[0].paginas == 2
    assert {entry.pagina for entry in result.exigencias} == {1, 2}
    assert {entry.categoria for entry in result.exigencias} == {
        "qualificacao_tecnica",
        "declaracoes",
    }


@pytest.mark.asyncio
async def test_interrompe_zip_acima_do_limite_agregado_de_paginas(monkeypatch):
    content = b"%PDF-1.7 edital"
    pdf = DownloadedPdf(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        url_final="https://pncp.gov.br/edital.zip",
        content_type="application/pdf",
    )
    archive = DownloadedZip(
        pdfs=(pdf, pdf),
        sha256=hashlib.sha256(b"zip").hexdigest(),
        url_final="https://pncp.gov.br/edital.zip",
        content_type="application/zip",
    )

    async def fake_download(url):
        return archive

    monkeypatch.setattr(
        edital_analysis_service,
        "extrair_texto_pdf",
        lambda content: PdfTextResult(
            paginas=[PageText(1, "texto", 5, 1.0, "texto_suficiente")],
            parser="fixture",
        ),
    )
    monkeypatch.setattr(edital_analysis_service.settings, "edital_zip_max_total_pages", 1)

    result = await EditalAnalysisService(downloader=fake_download).analisar_documentos(
        [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.zip"}],
        contratacao_key="123:2026:zip-page-limit",
    )

    assert result.status == "erro"
    assert result.documentos_analisados[0].status == "erro"
    assert "limite total de páginas" in result.documentos_analisados[0].mensagem
