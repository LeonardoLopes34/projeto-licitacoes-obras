"""Extração de texto e rasterização seletiva de páginas de PDF."""

from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber
import pypdfium2 as pdfium
from pypdf import PdfReader

from backend.config import settings


class PdfTextError(RuntimeError):
    """O PDF não pôde ser lido ou renderizado para análise."""


class PdfPageLimitError(PdfTextError):
    """O documento excede o limite de páginas seguro para o pipeline."""


@dataclass(frozen=True)
class PageText:
    pagina: int
    texto: str
    caracteres: int
    proporcao_imprimivel: float
    status: str
    erro: str | None = None


@dataclass(frozen=True)
class PdfTextResult:
    paginas: list[PageText]
    parser: str

    @property
    def total_paginas(self) -> int:
        return len(self.paginas)

    @property
    def paginas_para_ocr(self) -> list[int]:
        return [
            pagina.pagina
            for pagina in self.paginas
            if pagina.status in {"texto_insuficiente", "sem_texto"}
        ]


def _status_texto(texto: str) -> tuple[int, float, str]:
    chars = len(texto)
    printable = sum(char.isprintable() or char.isspace() for char in texto)
    ratio = printable / chars if chars else 0.0
    if not texto.strip():
        return chars, ratio, "sem_texto"
    if chars >= settings.edital_text_min_characters and ratio >= 0.85:
        return chars, ratio, "texto_suficiente"
    return chars, ratio, "texto_insuficiente"


def _page_text(pagina: int, texto: str, erro: str | None = None) -> PageText:
    clean_text = texto.strip()
    chars, ratio, status = _status_texto(clean_text)
    return PageText(
        pagina=pagina,
        texto=clean_text,
        caracteres=chars,
        proporcao_imprimivel=ratio,
        status=status,
        erro=erro,
    )


def _check_page_limit(page_count: int) -> None:
    if page_count < 1:
        raise PdfTextError("O PDF não possui páginas analisáveis.")
    if page_count > settings.edital_pdf_max_pages:
        raise PdfPageLimitError("O PDF excede o limite de páginas para análise.")


def _extract_with_pypdf(content: bytes) -> PdfTextResult:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PdfTextError("O PDF está protegido por senha.")
        _check_page_limit(len(reader.pages))
        pages: list[PageText] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                pages.append(_page_text(page_number, page.extract_text() or ""))
            except Exception:  # parser de PDF retorna erros variados por fornecedor
                pages.append(_page_text(page_number, "", "Não foi possível extrair o texto da página."))
        return PdfTextResult(paginas=pages, parser="pypdf")
    except PdfTextError:
        raise
    except Exception as exc:
        raise PdfTextError("Não foi possível ler o PDF publicado no PNCP.") from exc


def extrair_texto_pdf(content: bytes) -> PdfTextResult:
    """Extrai texto por página; usa pypdf somente se pdfplumber não abrir o PDF."""
    if not content.startswith(b"%PDF-"):
        raise PdfTextError("O conteúdo recebido não é um PDF válido.")
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            _check_page_limit(len(pdf.pages))
            pages: list[PageText] = []
            for page_number, page in enumerate(pdf.pages, start=1):
                try:
                    pages.append(_page_text(page_number, page.extract_text() or ""))
                except Exception:
                    pages.append(_page_text(page_number, "", "Não foi possível extrair o texto da página."))
            return PdfTextResult(paginas=pages, parser="pdfplumber")
    except PdfPageLimitError:
        raise
    except PdfTextError:
        raise
    except Exception:
        return _extract_with_pypdf(content)


def renderizar_pagina_para_ocr(content: bytes, pagina: int):
    """Converte exclusivamente uma página já marcada para OCR em imagem PIL."""
    if pagina < 1:
        raise PdfTextError("O número da página para OCR é inválido.")
    document = None
    page = None
    try:
        document = pdfium.PdfDocument(content)
        _check_page_limit(len(document))
        if pagina > len(document):
            raise PdfTextError("A página solicitada não existe no PDF.")
        page = document[pagina - 1]
        bitmap = page.render(scale=settings.edital_ocr_dpi / 72)
        return bitmap.to_pil().convert("RGB")
    except PdfTextError:
        raise
    except Exception as exc:
        raise PdfTextError("Não foi possível preparar a página para OCR.") from exc
    finally:
        if page is not None:
            page.close()
        if document is not None:
            document.close()
