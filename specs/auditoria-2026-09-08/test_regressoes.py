"""Casos de auditoria: afirmam o comportamento desejado e expõem falhas atuais.

Execução explícita; fora de testpaths da suíte normal. Sem rede ou banco real.
"""

import asyncio

import pytest

from backend.schemas import ExecucaoBusca, ResultadoExigencias
from backend.services import edital_analysis_service as analysis
from backend.services import pncp_service as pncp
from backend.services import db_service
from backend.services.circuit_breaker import CircuitBreaker
from backend.services.pdf_download_service import DownloadedPdf, PdfDownloadError
from backend.services.pdf_text_service import PageText


def extract(text):
    page = PageText(1, text, len(text), 1.0, "texto_suficiente")
    document = analysis.SelectedDocument(1, "Edital", "https://pncp.gov.br/edital.pdf", 0, True)
    return analysis.localizar_exigencias(documento=document, paginas=[(page, "pdf_texto", None)])


def test_espacos_de_diagramacao_nao_apagam_exigencia():
    phrase = "A licitante deverá apresentar contrato social atualizado."
    assert len(extract(phrase)) == 1  # controle: a regra reconhece a mesma obrigação
    assert len(extract("Introdução." + " " * 100 + "Informações gerais.\n" + phrase)) == 1


def test_duas_exigencias_tecnicas_na_mesma_pagina_sao_preservadas():
    first = "A licitante deverá apresentar atestado de capacidade técnica."
    second = "A licitante deverá apresentar registro profissional no CREA."
    assert len(extract(first)) == 1
    assert len(extract(second)) == 1
    assert len(extract(first + "\n" + second)) == 2


@pytest.mark.asyncio
async def test_tarefa_concluida_apos_timeout_e_removida(monkeypatch):
    service = analysis.EditalAnalysisService()
    release = asyncio.Event()

    async def delayed(*args, **kwargs):
        await release.wait()
        return ResultadoExigencias(
            status="sem_documento_analisavel", mensagem="Teste", analisador_versao="audit"
        )

    monkeypatch.setattr(service, "_analisar_documentos_locked", delayed)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(service.analisar_documentos([], contratacao_key="audit"), 0.01)
    task = service._inflight["audit"]
    release.set()
    await task
    await asyncio.sleep(0)
    assert "audit" not in service._inflight


@pytest.mark.asyncio
async def test_paginacao_nao_repete_registro_quando_fonte_muda(monkeypatch):
    from backend import database

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    records = [{"id": str(i)} for i in range(30)]

    async def client():
        return object()

    async def search(*args):
        return list(records), ExecucaoBusca()

    monkeypatch.setattr(pncp, "obter_cliente_pncp", client)
    monkeypatch.setattr(pncp, "_execute_search", search)
    monkeypatch.setattr(pncp, "processar_itens_raw", lambda raw, *args: raw)
    monkeypatch.setattr(pncp, "_result", lambda **kwargs: kwargs)
    monkeypatch.setattr(pncp, "_PNCP_CIRCUIT", CircuitBreaker())
    monkeypatch.setattr(pncp, "_CACHE", {})
    monkeypatch.setattr(database, "SessionLocal", FakeSession)
    monkeypatch.setattr(db_service, "save_obras_batch", lambda *args: None)
    monkeypatch.setattr(db_service, "cleanup_expired_obras", lambda *args, **kwargs: None)

    params = dict(data_inicial="20260908", data_final="20260908", max_paginas=1)
    first = await pncp.search_licitacoes_construction(**params)
    records.insert(0, {"id": "nova-publicacao"})
    second = await pncp.search_licitacoes_construction(**params, cursor=first["paginacao"]["proximo_cursor"])
    first_ids = {item["id"] for item in first["dados"]}
    second_ids = {item["id"] for item in second["dados"]}
    assert first_ids.isdisjoint(second_ids), f"Registros repetidos: {first_ids & second_ids}"


@pytest.mark.asyncio
async def test_novo_anexo_com_download_falho_nao_desaparece_no_cache(monkeypatch):
    async def download(url):
        if url.endswith("anexo.pdf"):
            raise PdfDownloadError("Falha transitória simulada")
        return DownloadedPdf(b"%PDF-fixture", "hash-estavel", url, "application/pdf")

    async def analyze(item):
        return {
            "documento_id": item.document.documento_id,
            "titulo": item.document.titulo,
            "paginas": 1,
            "paginas_com_ocr": 0,
            "status": "analisado",
        }, [], False

    monkeypatch.setattr(analysis, "obter_analise", lambda *args: None)
    monkeypatch.setattr(analysis, "salvar_analise", lambda *args: None)
    service = analysis.EditalAnalysisService(downloader=download)
    monkeypatch.setattr(service, "_analisar_pdf", analyze)
    docs = [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}]
    await service.analisar_documentos(docs, contratacao_key="audit-cache")
    docs.append({"sequencial_documento": 2, "titulo": "Anexo", "url": "https://pncp.gov.br/anexo.pdf"})
    result = await service.analisar_documentos(docs, contratacao_key="audit-cache")
    assert {document.documento_id for document in result.documentos_analisados} == {1, 2}
