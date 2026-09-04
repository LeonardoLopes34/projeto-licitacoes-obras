"""Regras determinísticas para localizar exigências de habilitação em editais."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from cachetools import TTLCache

from backend.config import settings
from backend.exceptions import PNCPConnectionError, PNCPResponseError
from backend.schemas import ResultadoExigencias
from backend.services.ocr_service import TesseractOcrService
from backend.services.edital_analysis_repository import (
    obter_analise,
    obter_ultima_analise_com_atualizacao,
    salvar_analise,
)
from backend.services.pdf_download_service import (
    DownloadedDocument,
    DownloadedPdf,
    DownloadedZip,
    PdfDownloadError,
    baixar_pdf_pncp,
)
from backend.services.pdf_text_service import (
    PageText,
    PdfPageLimitError,
    PdfTextError,
    extrair_texto_pdf,
    renderizar_pagina_para_ocr,
)
from backend.services.pncp_service import buscar_documentos_pncp
from backend.services.semantic_summary_service import gerar_descricao_resumida


logger = logging.getLogger(__name__)

PRIORITY_TERMS = (
    (0, ("edital", "instrumento convocatorio")),
    (1, ("habilitacao", "qualificacao")),
    (2, ("anexo",)),
    (3, ("termo de referencia", "projeto basico")),
)
EXCLUDED_TERMS = (
    "proposta",
    "precificacao",
    "execucao contratual",
    "da contratada",
    "contratada devera",
    "garantia contratual",
    "medicao",
    "art/rrt",
    "art ",
    "rrt ",
)
CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "habilitacao_juridica",
        "Documento de habilitação jurídica",
        ("contrato social", "ato constitutivo", "estatuto", "registro comercial", "inscricao no registro"),
    ),
    (
        "qualificacao_tecnica",
        "Comprovação de qualificação técnica",
        ("atestado", "capacidade tecnica", "acervo tecnico", "registro profissional", "crea", "cau"),
    ),
    (
        "regularidade_fiscal_social_trabalhista",
        "Comprovação de regularidade fiscal, social ou trabalhista",
        ("regularidade fiscal", "fgts", "cnd", "certidao negativa", "receita federal", "trabalhista"),
    ),
    (
        "qualificacao_economico_financeira",
        "Comprovação de qualificação econômico-financeira",
        ("balanco patrimonial", "patrimonio liquido", "indice de liquidez", "indices de liquidez"),
    ),
    ("declaracoes", "Declaração exigida", ("declaracao", "declaracoes")),
)


@dataclass(frozen=True)
class SelectedDocument:
    documento_id: int
    titulo: str
    url: str | None
    prioridade: int | None
    selecionado: bool


@dataclass(frozen=True)
class _DownloadedDocument:
    document: SelectedDocument
    arquivo: DownloadedDocument | None
    error: str | None = None

    @property
    def pdfs(self) -> tuple[DownloadedPdf, ...]:
        if self.arquivo is None:
            return ()
        if isinstance(self.arquivo, DownloadedZip):
            return self.arquivo.pdfs
        return (self.arquivo,)


def normalizar_texto(texto: str) -> str:
    normalized = unicodedata.normalize("NFD", texto or "")
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _document_dict(document: Any) -> dict[str, Any]:
    return document.model_dump() if hasattr(document, "model_dump") else dict(document)


def selecionar_documentos_para_analise(documentos: list[Any]) -> list[SelectedDocument]:
    """Prioriza edital/anexos e explicita, em vez de ocultar, o que ficou fora."""
    selected: list[SelectedDocument] = []
    for raw_document in documentos:
        document = _document_dict(raw_document)
        try:
            document_id = int(document.get("sequencial_documento"))
        except (TypeError, ValueError):
            continue
        title = str(document.get("titulo") or document.get("tipo_documento_nome") or f"Documento {document_id}")
        index_text = normalizar_texto(f"{document.get('tipo_documento_nome') or ''} {title}")
        priority = next(
            (candidate_priority for candidate_priority, terms in PRIORITY_TERMS if any(term in index_text for term in terms)),
            None,
        )
        selected.append(
            SelectedDocument(
                documento_id=document_id,
                titulo=title,
                url=str(document.get("url")).strip() if document.get("url") else None,
                prioridade=priority,
                selecionado=priority is not None and priority < 3,
            )
        )
    return sorted(
        selected,
        key=lambda item: (
            not item.selecionado,
            item.prioridade if item.prioridade is not None else 99,
            item.documento_id,
        ),
    )


def _sentence_around(texto: str, start: int) -> str:
    left = max(texto.rfind("\n", 0, start), texto.rfind(".", 0, start), texto.rfind(";", 0, start)) + 1
    right_candidates = [
        position
        for position in (texto.find("\n", start), texto.find(".", start), texto.find(";", start))
        if position != -1
    ]
    right = min(right_candidates) + 1 if right_candidates else len(texto)
    return re.sub(r"\s+", " ", texto[left:right]).strip()[:600]


def _is_out_of_scope(normalized_evidence: str) -> bool:
    if any(term in normalized_evidence for term in EXCLUDED_TERMS):
        return True
    if "administracao" in normalized_evidence and not any(
        subject in normalized_evidence for subject in ("licitante", "empresa", "participante")
    ):
        return True
    return False


def _source_confidence(origem: str, ocr_confidence: float | None) -> float:
    if origem == "pdf_texto":
        return 0.85
    return ocr_confidence if ocr_confidence is not None else 0.60


def localizar_exigencias(
    *,
    documento: SelectedDocument,
    paginas: list[tuple[PageText, str, float | None]],
) -> list[dict[str, Any]]:
    """Extrai somente trechos textuais com categoria e página verificáveis."""
    entries: list[dict[str, Any]] = []
    deduplicated: set[tuple[str, str]] = set()
    for page, origem, ocr_confidence in paginas:
        original = page.texto
        normalized_page = normalizar_texto(original)
        if not original:
            continue
        for category, label, keywords in CATEGORY_RULES:
            for keyword in keywords:
                match = re.search(rf"\b{re.escape(keyword)}\b", normalized_page)
                if match is None:
                    continue
                evidence = _sentence_around(original, match.start())
                normalized_evidence = normalizar_texto(evidence)
                if not evidence or _is_out_of_scope(normalized_evidence):
                    continue
                key = (category, normalized_evidence)
                if key in deduplicated:
                    continue
                deduplicated.add(key)
                referenced = any(term in normalized_evidence for term in ("anexo", "conforme item", "conforme modelo"))
                confidence = _source_confidence(origem, ocr_confidence)
                if referenced:
                    confidence = min(confidence, 0.65)
                entries.append(
                    {
                        "categoria": category,
                        "rotulo": label,
                        "descricao_resumida": gerar_descricao_resumida(category, evidence),
                        "descricao_original": evidence,
                        "documento_id": documento.documento_id,
                        "titulo_documento": documento.titulo,
                        "url_documento": documento.url,
                        "pagina": page.pagina,
                        "evidencia": evidence,
                        "confianca": round(confidence, 2),
                        "origem_texto": origem,
                        "status": "referenciado_em_outro_documento" if referenced else "identificado_no_edital",
                    }
                )
                break
    return entries


class EditalAnalysisService:
    """Orquestra download, texto/OCR, regras e cache por hash de documento."""

    def __init__(
        self,
        *,
        downloader: Callable[[str], Awaitable[DownloadedDocument]] = baixar_pdf_pncp,
        ocr_service: TesseractOcrService | None = None,
    ) -> None:
        self.downloader = downloader
        self.ocr_service = ocr_service or TesseractOcrService()
        self.cache: TTLCache[str, ResultadoExigencias] = TTLCache(
            maxsize=settings.edital_analysis_cache_maxsize,
            ttl=settings.edital_analysis_cache_ttl_seconds,
        )
        self._inflight: dict[str, asyncio.Task[ResultadoExigencias]] = {}
        self._inflight_guard = asyncio.Lock()
        self.metrics: Counter[str] = Counter()

    async def analisar_contratacao(
        self,
        cnpj: str,
        ano: int,
        sequencial: int,
        *,
        forcar: bool = False,
    ) -> ResultadoExigencias:
        contratacao_key = f"{cnpj}:{ano}:{sequencial}"
        try:
            documents_result = await buscar_documentos_pncp(cnpj, ano, sequencial)
        except (PNCPConnectionError, PNCPResponseError):
            persisted = await self._obter_analise_persistida_desatualizada(contratacao_key)
            if persisted is not None:
                return persisted
            raise

        if documents_result.get("desatualizado"):
            persisted = await self._obter_analise_persistida_desatualizada(contratacao_key)
            if persisted is not None:
                return persisted
        return await self.analisar_documentos(
            documents_result.get("documentos", []),
            contratacao_key=contratacao_key,
            forcar=forcar,
        )

    async def _obter_analise_persistida_desatualizada(
        self,
        contratacao_key: str,
    ) -> ResultadoExigencias | None:
        persisted = await asyncio.to_thread(
            obter_ultima_analise_com_atualizacao,
            contratacao_key,
            settings.edital_analyzer_version,
        )
        if persisted is None:
            return None
        return persisted.resultado.model_copy(
            update={
                "origem": "cache_persistente",
                "desatualizado": True,
                "atualizado_em": persisted.updated_at.isoformat(),
                "mensagem": "Exibindo a última análise conhecida; o PNCP está indisponível no momento.",
            }
        )

    async def analisar_documentos(
        self,
        documentos: list[Any],
        *,
        contratacao_key: str,
        forcar: bool = False,
    ) -> ResultadoExigencias:
        async with self._inflight_guard:
            task = self._inflight.get(contratacao_key)
            if task is None:
                task = asyncio.create_task(
                    self._analisar_documentos_locked(documentos, contratacao_key, forcar=forcar)
                )
                self._inflight[contratacao_key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._inflight_guard:
                    if self._inflight.get(contratacao_key) is task:
                        self._inflight.pop(contratacao_key, None)

    async def _download_document(self, document: SelectedDocument) -> _DownloadedDocument:
        if not document.url:
            return _DownloadedDocument(document, None, "O documento não possui link público para análise.")
        try:
            return _DownloadedDocument(document, await self.downloader(document.url))
        except PdfDownloadError as exc:
            return _DownloadedDocument(document, None, str(exc))

    def _document_hash(self, downloaded: list[_DownloadedDocument]) -> str:
        hashes = ":".join(
            f"{item.document.documento_id}:{item.arquivo.sha256}"
            for item in downloaded
            if item.arquivo is not None
        )
        return hashlib.sha256(hashes.encode()).hexdigest()

    def _cache_key(self, contract_key: str, document_hash: str) -> str:
        raw_key = f"{contract_key}|{document_hash}|{settings.edital_analyzer_version}"
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def _analisar_documentos_locked(
        self,
        documentos: list[Any],
        contratacao_key: str,
        *,
        forcar: bool,
    ) -> ResultadoExigencias:
        started_at = time.monotonic()
        selected = selecionar_documentos_para_analise(documentos)
        selected_for_analysis = [item for item in selected if item.selecionado]
        if not selected_for_analysis:
            return self._result_without_documents(selected)

        semaphore = asyncio.Semaphore(max(1, settings.edital_analysis_concurrency))

        async def controlled_download(document: SelectedDocument) -> _DownloadedDocument:
            async with semaphore:
                return await self._download_document(document)

        downloaded = await asyncio.gather(*(controlled_download(item) for item in selected_for_analysis))
        document_hash = self._document_hash(downloaded)
        cache_key = self._cache_key(contratacao_key, document_hash)
        cached = self.cache.get(cache_key)
        if cached is not None and not forcar:
            self.metrics["cache_hits"] += 1
            return cached.model_copy(deep=True)
        if not forcar:
            persisted = await asyncio.to_thread(
                obter_analise,
                contratacao_key,
                document_hash,
                settings.edital_analyzer_version,
            )
            if persisted is not None:
                self.metrics["persistent_cache_hits"] += 1
                self.cache[cache_key] = persisted.model_copy(deep=True)
                return persisted

        self.metrics["analyses_started"] += 1
        documents_out = [
            {
                "documento_id": item.documento_id,
                "titulo": item.titulo,
                "url": item.url,
                "paginas": 0,
                "paginas_com_ocr": 0,
                "status": "nao_selecionado",
                "mensagem": "Documento complementar não foi selecionado automaticamente para habilitação.",
            }
            for item in selected
            if not item.selecionado
        ]
        entries: list[dict[str, Any]] = []
        failures = 0
        analyzed = 0
        for item in downloaded:
            document_out, document_entries, failed = await self._analisar_pdf(item)
            documents_out.append(document_out)
            entries.extend(document_entries)
            analyzed += int(document_out["status"] in {"analisado", "analise_parcial"})
            failures += int(failed)

        status, message = self._result_status(analyzed, failures, entries)
        result = ResultadoExigencias(
            status=status,
            mensagem=message,
            total_exigencias=len(entries),
            categorias=dict(Counter(entry["categoria"] for entry in entries)),
            documentos_analisados=documents_out,
            exigencias=entries,
            analisador_versao=settings.edital_analyzer_version,
        )
        self.metrics["documents_selected"] += len(selected_for_analysis)
        # Todos os caminhos de análise devem expor a mesma estrutura. O download
        # de um PDF pode falhar depois que o documento foi selecionado; nesse
        # caso a paginação é zero, mas a métrica ainda precisa ser calculada.
        self.metrics["pages_ocr"] += sum(item.get("paginas_com_ocr", 0) for item in documents_out)
        self.metrics[f"status_{status}"] += 1
        self.metrics["duration_ms"] += round((time.monotonic() - started_at) * 1000)
        logger.info(
            "Análise de edital concluída: status=%s documentos=%s paginas_ocr=%s versao=%s duracao_ms=%s",
            status,
            len(selected_for_analysis),
            sum(item.get("paginas_com_ocr", 0) for item in documents_out),
            settings.edital_analyzer_version,
            round((time.monotonic() - started_at) * 1000),
        )
        if any(item.arquivo is not None for item in downloaded):
            self.cache[cache_key] = result.model_copy(deep=True)
            await asyncio.to_thread(salvar_analise, contratacao_key, document_hash, result)
        return result

    def _result_without_documents(self, documents: list[SelectedDocument]) -> ResultadoExigencias:
        return ResultadoExigencias(
            status="sem_documento_analisavel",
            mensagem="Não há edital ou anexo de habilitação disponível para análise automática.",
            documentos_analisados=[
                {
                    "documento_id": item.documento_id,
                    "titulo": item.titulo,
                    "url": item.url,
                    "paginas": 0,
                    "paginas_com_ocr": 0,
                    "status": "nao_selecionado",
                    "mensagem": "Documento não identificado como edital ou anexo de habilitação.",
                }
                for item in documents
            ],
            analisador_versao=settings.edital_analyzer_version,
        )

    async def _analisar_pdf(
        self,
        downloaded: _DownloadedDocument,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        """Analisa um PDF único ou todos os PDFs seguros extraídos de um ZIP."""
        document = downloaded.document
        base = {
            "documento_id": document.documento_id,
            "titulo": document.titulo,
            "url": document.url,
            "paginas": 0,
            "paginas_com_ocr": 0,
        }
        if not downloaded.pdfs:
            return ({**base, "status": "erro", "mensagem": downloaded.error}, [], True)

        pages: list[tuple[PageText, str, float | None]] = []
        ocr_pages = 0
        failures: list[str] = []
        total_pages = 0
        extracted_pdfs: list[tuple[DownloadedPdf, Any]] = []
        is_zip = isinstance(downloaded.arquivo, DownloadedZip)
        for pdf in downloaded.pdfs:
            try:
                text_result = await asyncio.to_thread(extrair_texto_pdf, pdf.content)
            except (PdfPageLimitError, PdfTextError) as exc:
                failures.append(str(exc))
                continue
            total_pages += text_result.total_paginas
            if is_zip and total_pages > settings.edital_zip_max_total_pages:
                return (
                    {
                        **base,
                        "status": "erro",
                        "mensagem": "O arquivo ZIP excede o limite total de páginas para análise.",
                    },
                    [],
                    True,
                )
            extracted_pdfs.append((pdf, text_result))

        if total_pages == 0:
            return (
                {
                    **base,
                    "status": "erro",
                    "mensagem": failures[0] if failures else "Nenhum PDF pôde ser analisado.",
                },
                [],
                True,
            )

        page_offset = 0
        for pdf, text_result in extracted_pdfs:
            for page in text_result.paginas:
                global_page = page.pagina + page_offset
                if page.status == "texto_suficiente":
                    pages.append(
                        (
                            PageText(
                                pagina=global_page,
                                texto=page.texto,
                                caracteres=page.caracteres,
                                proporcao_imprimivel=page.proporcao_imprimivel,
                                status=page.status,
                                erro=page.erro,
                            ),
                            "pdf_texto",
                            None,
                        )
                    )
                    continue
                ocr_pages += 1
                try:
                    image = await asyncio.to_thread(renderizar_pagina_para_ocr, pdf.content, page.pagina)
                    ocr_result = await asyncio.to_thread(self.ocr_service.reconhecer, image, page.pagina)
                except PdfTextError:
                    failures.append("Uma página não pôde ser preparada para OCR.")
                    continue
                if ocr_result.status == "erro":
                    failures.append(ocr_result.erro or "Uma página não pôde ser lida por OCR.")
                    continue
                pages.append(
                    (
                        PageText(
                            pagina=global_page,
                            texto=ocr_result.texto,
                            caracteres=len(ocr_result.texto),
                            proporcao_imprimivel=1.0,
                            status="texto_suficiente",
                        ),
                        "ocr",
                        ocr_result.confianca,
                    )
                )
            page_offset += text_result.total_paginas

        entries = localizar_exigencias(documento=document, paginas=pages)
        document_status = "analise_parcial" if failures else "analisado"
        message = (
            "Uma ou mais páginas ou PDFs não puderam ser lidos integralmente."
            if failures
            else None
        )
        return (
            {
                **base,
                "paginas": total_pages,
                "paginas_com_ocr": ocr_pages,
                "status": document_status,
                "mensagem": message,
            },
            entries,
            bool(failures),
        )

    @staticmethod
    def _result_status(analyzed: int, failures: int, entries: list[dict[str, Any]]) -> tuple[str, str]:
        if analyzed == 0:
            return "erro", "Não foi possível analisar os documentos selecionados do edital."
        if failures:
            return "sucesso_parcial", "Exigências identificadas no edital; alguns anexos não puderam ser analisados."
        if entries:
            return "sucesso", "Exigências identificadas no edital. A lista não substitui a leitura do documento."
        return "sucesso", "Nenhuma exigência de habilitação foi identificada automaticamente no texto analisado."
