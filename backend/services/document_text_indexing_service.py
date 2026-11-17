"""Extração reutilizável por página para a indexação, sem gravar arquivos brutos."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.pdf_download_service import DownloadedDocument, DownloadedPdf, DownloadedZip
from backend.services.pdf_text_service import PdfPageLimitError, PdfTextError, extrair_texto_pdf, renderizar_pagina_para_ocr

if TYPE_CHECKING:
    # Só para tipos: ocr_service -> openai_edital_service -> vector_chunk_service importa este módulo.
    from backend.services.ocr_service import OpenAIVisionOcrService, TesseractOcrService


@dataclass(frozen=True)
class IndexableDocumentSource:
    documento_id: int
    titulo: str
    url: str | None


@dataclass(frozen=True)
class ExtractedIndexPage:
    pagina: int
    texto: str
    origem_texto: str
    confianca_ocr: float | None


@dataclass(frozen=True)
class ExtractedIndexPdf:
    pdf_sha256: str
    paginas: tuple[ExtractedIndexPage, ...]


@dataclass(frozen=True)
class ExtractedIndexDocument:
    source: IndexableDocumentSource
    pdfs: tuple[ExtractedIndexPdf, ...]
    total_paginas: int
    paginas_ocr: int
    falhas: tuple[str, ...]


def _safe_pdfs(downloaded: DownloadedDocument) -> tuple[DownloadedPdf, ...]:
    return downloaded.pdfs if isinstance(downloaded, DownloadedZip) else (downloaded,)


async def extract_indexable_document(
    source: IndexableDocumentSource,
    downloaded: DownloadedDocument,
    *,
    ocr_service: TesseractOcrService | OpenAIVisionOcrService,
    ocr_enabled: bool,
    max_total_pages: int,
) -> ExtractedIndexDocument:
    """Reutiliza extração/OCR existentes e mantém cada PDF interno independente."""

    extracted_pdfs: list[ExtractedIndexPdf] = []
    failures: list[str] = []
    total_pages = 0
    ocr_pages = 0

    for pdf in _safe_pdfs(downloaded):
        try:
            text_result = await asyncio.to_thread(extrair_texto_pdf, pdf.content)
        except (PdfPageLimitError, PdfTextError) as exc:
            failures.append(str(exc))
            continue

        total_pages += text_result.total_paginas
        if total_pages > max_total_pages:
            failures.append("O documento excede o limite total de páginas para indexação.")
            break

        pages: list[ExtractedIndexPage] = []
        for page in text_result.paginas:
            if page.status == "texto_suficiente" and page.texto:
                pages.append(
                    ExtractedIndexPage(
                        pagina=page.pagina,
                        texto=page.texto,
                        origem_texto="pdf_texto",
                        confianca_ocr=None,
                    )
                )
                continue
            if not ocr_enabled:
                failures.append(
                    "O OCR está desativado por configuração; uma página sem texto digital foi ignorada."
                )
                continue
            try:
                image = await asyncio.to_thread(renderizar_pagina_para_ocr, pdf.content, page.pagina)
                ocr_result = await asyncio.to_thread(ocr_service.reconhecer, image, page.pagina)
            except PdfTextError:
                failures.append("Uma página não pôde ser preparada para OCR.")
                continue
            if ocr_result.status == "erro" or not ocr_result.texto:
                failures.append(ocr_result.erro or "Uma página não pôde ser lida por OCR.")
                continue
            ocr_pages += 1
            pages.append(
                ExtractedIndexPage(
                    pagina=page.pagina,
                    texto=ocr_result.texto,
                    origem_texto="ocr",
                    confianca_ocr=ocr_result.confianca,
                )
            )
        if pages:
            extracted_pdfs.append(ExtractedIndexPdf(pdf_sha256=pdf.sha256, paginas=tuple(pages)))

    return ExtractedIndexDocument(
        source=source,
        pdfs=tuple(extracted_pdfs),
        total_paginas=total_pages,
        paginas_ocr=ocr_pages,
        falhas=tuple(failures),
    )
