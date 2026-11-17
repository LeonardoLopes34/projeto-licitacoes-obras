import hashlib

import pytest

from backend.services import document_text_indexing_service
from backend.services.document_text_indexing_service import IndexableDocumentSource, extract_indexable_document
from backend.services.pdf_download_service import DownloadedPdf
from backend.services.pdf_text_service import PageText, PdfTextResult


@pytest.mark.asyncio
async def test_extracao_indexavel_com_ocr_desativado_preserva_texto_nativo_e_registra_pagina_ignorada(monkeypatch):
    content = b"%PDF-1.7 document fixture"
    downloaded = DownloadedPdf(
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        url_final="https://pncp.gov.br/edital-sintetico.pdf",
        content_type="application/pdf",
    )

    def unexpected_renderer(*args, **kwargs):
        raise AssertionError("O renderizador não deve ser chamado quando OCR está desativado.")

    class UnexpectedOcr:
        def reconhecer(self, *args, **kwargs):
            raise AssertionError("O Tesseract não deve ser chamado quando OCR está desativado.")

    monkeypatch.setattr(
        document_text_indexing_service,
        "extrair_texto_pdf",
        lambda _content: PdfTextResult(
            paginas=[
                PageText(1, "Texto digital preservado para indexação.", 40, 1.0, "texto_suficiente"),
                PageText(2, "", 0, 0.0, "sem_texto"),
            ],
            parser="fixture",
        ),
    )
    monkeypatch.setattr(document_text_indexing_service, "renderizar_pagina_para_ocr", unexpected_renderer)

    result = await extract_indexable_document(
        IndexableDocumentSource(15, "Edital sintético", downloaded.url_final),
        downloaded,
        ocr_service=UnexpectedOcr(),
        ocr_enabled=False,
        max_total_pages=10,
    )

    assert result.total_paginas == 2
    assert result.paginas_ocr == 0
    assert len(result.pdfs) == 1
    assert result.pdfs[0].pdf_sha256 == downloaded.sha256
    assert [(page.pagina, page.texto, page.origem_texto) for page in result.pdfs[0].paginas] == [
        (1, "Texto digital preservado para indexação.", "pdf_texto")
    ]
    assert any("OCR está desativado" in failure for failure in result.falhas)
