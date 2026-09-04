"""Adaptador isolado do Tesseract para páginas já selecionadas para OCR."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import pytesseract

from backend.config import settings


_TESSERACT_COMMAND_LOCK = threading.Lock()


@dataclass(frozen=True)
class OcrPageResult:
    pagina: int
    texto: str
    confianca: float | None
    idioma: str
    duracao_ms: int
    status: str
    erro: str | None = None


@dataclass(frozen=True)
class TesseractAvailability:
    """Resultado da pré-verificação do binário e idioma do Tesseract."""

    status: str
    idioma: str
    versao: str | None
    idiomas_disponiveis: tuple[str, ...]
    erro: str | None = None

    @property
    def disponivel(self) -> bool:
        return self.status == "disponivel"


@contextmanager
def _configured_tesseract_command(tesseract_cmd: str | None) -> Iterator[None]:
    """Executa uma chamada do pytesseract com restauração atômica do comando global."""

    with _TESSERACT_COMMAND_LOCK:
        previous_cmd = pytesseract.pytesseract.tesseract_cmd
        try:
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            yield
        finally:
            pytesseract.pytesseract.tesseract_cmd = previous_cmd


def verificar_disponibilidade_tesseract(
    *,
    language: str | None = None,
    tesseract_cmd: str | None = None,
) -> TesseractAvailability:
    """Verifica se Tesseract e o idioma configurado estão prontos para o OCR.

    A função não altera permanentemente ``pytesseract.tesseract_cmd`` e pode ser
    chamada na inicialização da aplicação ou por uma rota de saúde.
    """

    configured_language = language or settings.edital_ocr_language
    configured_command = tesseract_cmd if tesseract_cmd is not None else settings.tesseract_cmd
    try:
        with _configured_tesseract_command(configured_command):
            version = str(pytesseract.get_tesseract_version())
            languages = tuple(pytesseract.get_languages())
    except (FileNotFoundError, pytesseract.TesseractNotFoundError):
        return TesseractAvailability(
            status="binario_ausente",
            idioma=configured_language,
            versao=None,
            idiomas_disponiveis=(),
            erro="Tesseract não está instalado ou configurado.",
        )
    except pytesseract.TesseractError:
        return TesseractAvailability(
            status="erro",
            idioma=configured_language,
            versao=None,
            idiomas_disponiveis=(),
            erro="Não foi possível verificar a disponibilidade do Tesseract.",
        )

    if configured_language not in languages:
        return TesseractAvailability(
            status="idioma_ausente",
            idioma=configured_language,
            versao=version,
            idiomas_disponiveis=languages,
            erro=f"O idioma OCR configurado ({configured_language}) não está instalado.",
        )
    return TesseractAvailability(
        status="disponivel",
        idioma=configured_language,
        versao=version,
        idiomas_disponiveis=languages,
    )


class TesseractOcrService:
    """Executa Tesseract em uma imagem já renderizada, sem acesso a URLs/PDFs."""

    def __init__(
        self,
        *,
        language: str | None = None,
        timeout_seconds: float | None = None,
        tesseract_cmd: str | None = None,
    ) -> None:
        self.language = language or settings.edital_ocr_language
        self.timeout_seconds = timeout_seconds or settings.edital_ocr_timeout_seconds
        self.tesseract_cmd = tesseract_cmd if tesseract_cmd is not None else settings.tesseract_cmd

    def verificar_disponibilidade(self) -> TesseractAvailability:
        """Retorna o estado operacional do binário e idioma deste serviço."""

        return verificar_disponibilidade_tesseract(
            language=self.language,
            tesseract_cmd=self.tesseract_cmd,
        )

    def reconhecer(self, image: Any, pagina: int) -> OcrPageResult:
        if pagina < 1:
            raise ValueError("pagina deve ser maior que zero")
        started_at = time.monotonic()
        try:
            with _configured_tesseract_command(self.tesseract_cmd):
                data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                    timeout=self.timeout_seconds,
                )
        except pytesseract.TesseractNotFoundError:
            return self._error_result(pagina, started_at, "Tesseract não está instalado ou configurado.")
        except RuntimeError:
            return self._error_result(pagina, started_at, "O OCR excedeu o tempo limite ou falhou.")
        except Exception:
            return self._error_result(pagina, started_at, "Não foi possível reconhecer o texto da página.")

        words = [str(word).strip() for word in data.get("text", []) if str(word).strip()]
        confidence_values: list[float] = []
        for value in data.get("conf", []):
            try:
                confidence = float(value)
            except (TypeError, ValueError):
                continue
            if confidence >= 0:
                confidence_values.append(confidence)
        confidence = min(1.0, max(0.0, sum(confidence_values) / len(confidence_values) / 100)) if confidence_values else None
        text = " ".join(words)
        duration_ms = round((time.monotonic() - started_at) * 1000)
        if not text:
            return OcrPageResult(
                pagina=pagina,
                texto="",
                confianca=confidence,
                idioma=self.language,
                duracao_ms=duration_ms,
                status="erro",
                erro="O OCR não identificou texto legível na página.",
            )
        return OcrPageResult(
            pagina=pagina,
            texto=text,
            confianca=confidence,
            idioma=self.language,
            duracao_ms=duration_ms,
            status="baixa_qualidade" if confidence is not None and confidence < 0.45 else "sucesso",
        )

    def _error_result(self, pagina: int, started_at: float, message: str) -> OcrPageResult:
        return OcrPageResult(
            pagina=pagina,
            texto="",
            confianca=None,
            idioma=self.language,
            duracao_ms=round((time.monotonic() - started_at) * 1000),
            status="erro",
            erro=message,
        )
