"""Regressões promovidas da auditoria de confiabilidade (spec 013)."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.schemas import ResultadoExigencias
from backend.services import edital_analysis_service as analysis
from backend.services import pncp_service
from backend.services.pdf_download_service import DownloadedPdf, PdfDownloadError
from backend.services.pdf_text_service import PageText
from backend.services.query_snapshot_repository import QuerySnapshot


def _extract(text: str):
    page = PageText(1, text, len(text), 1.0, "texto_suficiente")
    document = analysis.SelectedDocument(1, "Edital", "https://pncp.gov.br/edital.pdf", 0, True)
    return analysis.localizar_exigencias(documento=document, paginas=[(page, "pdf_texto", None)])


def test_normalizacao_nao_desloca_evidencia_original():
    phrase = "A licitante deverá apresentar contrato social atualizado."
    entries = _extract("Introdução.\n\n" + " " * 40 + phrase)

    assert len(entries) == 1
    assert entries[0]["evidencia"] == phrase
    assert entries[0]["pagina"] == 1


def test_duas_exigencias_tecnicas_distintas_na_mesma_pagina_sao_preservadas():
    entries = _extract(
        "A licitante deverá apresentar atestado de capacidade técnica e "
        "registro profissional no CREA."
    )

    assert len(entries) == 2
    assert {entry["categoria"] for entry in entries} == {"qualificacao_tecnica"}


@pytest.mark.asyncio
async def test_manifesto_de_cache_mantem_anexo_com_falha_visivel(monkeypatch):
    async def download(url: str):
        if url.endswith("anexo.pdf"):
            raise PdfDownloadError("Falha transitória simulada")
        return DownloadedPdf(b"%PDF-fixture", "hash-estavel", url, "application/pdf")

    async def analyze(item):
        if not item.pdfs:
            return {
                "documento_id": item.document.documento_id,
                "titulo": item.document.titulo,
                "paginas": 0,
                "paginas_com_ocr": 0,
                "status": "erro",
                "mensagem": item.error,
            }, [], True
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
    documents = [{"sequencial_documento": 1, "titulo": "Edital", "url": "https://pncp.gov.br/edital.pdf"}]

    await service.analisar_documentos(documents, contratacao_key="manifesto")
    documents.append({"sequencial_documento": 2, "titulo": "Anexo", "url": "https://pncp.gov.br/anexo.pdf"})
    result = await service.analisar_documentos(documents, contratacao_key="manifesto")

    assert {item.documento_id for item in result.documentos_analisados} == {1, 2}
    assert next(item for item in result.documentos_analisados if item.documento_id == 2).status == "erro"


@pytest.mark.asyncio
async def test_tarefa_terminada_depois_do_timeout_e_removida_do_registro(monkeypatch):
    service = analysis.EditalAnalysisService()
    release = asyncio.Event()

    async def delayed(*args, **kwargs):
        await release.wait()
        return ResultadoExigencias(status="sem_documento_analisavel", mensagem="ok", analisador_versao="teste")

    monkeypatch.setattr(service, "_analisar_documentos_locked", delayed)
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(service.analisar_documentos([], contratacao_key="timeout"), 0.01)
    task = service._inflight["timeout"]
    release.set()
    await task
    await asyncio.sleep(0)

    assert "timeout" not in service._inflight


def test_busca_ordenacao_e_indicadores_abrangem_todo_o_snapshot():
    dados = [
        {
            "id_pncp": str(index),
            "orgao": f"Órgão {index:02d}",
            "objeto": "Pavimentação" if index == 22 else "Reforma",
            "uf": "RS" if index % 2 else "SC",
            "modalidade": "Concorrência" if index % 2 else "Pregão",
            "data_publicacao": f"2026-09-{(index % 28) + 1:02d}",
            "valor_estimado": None if index == 29 else index * 100,
        }
        for index in range(30)
    ]

    filtered, summary = pncp_service._ordenar_e_resumir_consulta(
        dados, termo="pavimentacao", ordenacao="valor_desc"
    )

    assert [item["id_pncp"] for item in filtered] == ["22"]
    assert summary["total_coletado"] == 30
    assert summary["total_filtrado"] == 1
    assert summary["volume_estimado"] == 2200
    assert summary["maior_valor"] == 2200


def test_maior_valor_ignora_itens_sem_valor_e_considera_todo_o_snapshot():
    dados = [
        {"id_pncp": "1", "orgao": "A", "objeto": "Reforma", "valor_estimado": 500},
        {"id_pncp": "2", "orgao": "B", "objeto": "Reforma", "valor_estimado": None},
        {"id_pncp": "3", "orgao": "C", "objeto": "Reforma", "valor_estimado": "1546620.47"},
    ]

    _, summary = pncp_service._ordenar_e_resumir_consulta(dados, termo=None, ordenacao="orgao")

    assert summary["maior_valor"] == Decimal("1546620.47")
    assert summary["quantidade_sem_valor"] == 1

    _, vazio = pncp_service._ordenar_e_resumir_consulta([dados[1]], termo=None, ordenacao="orgao")
    assert vazio["maior_valor"] is None


def test_cursor_vincula_snapshot_filtro_e_expiracao():
    now = datetime.now(timezone.utc)
    snapshot = QuerySnapshot(
        id="snapshot-seguro",
        fingerprint="filtro-a",
        dados=[{"id_pncp": str(index)} for index in range(30)],
        resultado={"status": "sucesso_real", "mensagem": "ok", "total_encontradas": 30, "metadados": {}},
        created_at=now,
        expires_at=now + timedelta(minutes=5),
    )

    first = pncp_service._paginate_snapshot(snapshot, offset=0, tamanho_resultado=15)
    snapshot_id, offset, _ = pncp_service._decode_snapshot_cursor(
        first["paginacao"]["proximo_cursor"], fingerprint="filtro-a", tamanho_resultado=15
    )

    assert snapshot_id == snapshot.id
    assert offset == 15
    with pytest.raises(pncp_service.PaginationCursorError):
        pncp_service._decode_snapshot_cursor(
            first["paginacao"]["proximo_cursor"], fingerprint="outro-filtro", tamanho_resultado=15
        )
