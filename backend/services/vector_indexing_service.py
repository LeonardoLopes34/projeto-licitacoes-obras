"""Fila e trabalhador limitado da indexação/ análise assistida da Spec 015."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.config import settings
from backend.exceptions import PNCPConnectionError, PNCPResponseError
from backend.services.document_text_indexing_service import IndexableDocumentSource, extract_indexable_document
from backend.services.edital_analysis_service import SelectedDocument, selecionar_documentos_para_analise
from backend.services.ocr_service import OpenAIVisionOcrService, TesseractOcrService, criar_servico_ocr
from backend.services.openai_edital_service import (
    AnalysisChunkContext,
    OpenAIEmbeddingProvider,
    OpenAIRequirementAnalyzer,
    OpenAIServiceError,
)
from backend.services.pdf_download_service import DownloadedDocument, PdfDownloadError, baixar_pdf_pncp
from backend.services.pncp_service import buscar_documentos_pncp
from backend.services.vector_chunk_service import ChunkLimitError, chunk_pages
from backend.services import vector_index_repository as repository


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DownloadResult:
    source: IndexableDocumentSource
    downloaded: DownloadedDocument | None
    error: str | None = None


class VectorIndexingService:
    """Executa somente jobs persistidos, sem prender endpoints à OpenAI."""

    def __init__(
        self,
        *,
        downloader: Callable[[str], Awaitable[DownloadedDocument]] = baixar_pdf_pncp,
        ocr_service: TesseractOcrService | OpenAIVisionOcrService | None = None,
        embedding_provider: OpenAIEmbeddingProvider | None = None,
        requirement_analyzer: OpenAIRequirementAnalyzer | None = None,
    ) -> None:
        self.downloader = downloader
        self.ocr_service = ocr_service or criar_servico_ocr()
        self.embedding_provider = embedding_provider or OpenAIEmbeddingProvider()
        self.requirement_analyzer = requirement_analyzer or OpenAIRequirementAnalyzer()
        self.worker_id = f"indexer-{uuid.uuid4().hex[:12]}"
        self.metrics: Counter[str] = Counter()
        self._drain_task: asyncio.Task[None] | None = None
        self._drain_lock = asyncio.Lock()
        self._slots = asyncio.Semaphore(settings.vector_index_worker_concurrency)

    @staticmethod
    def enabled() -> bool:
        return settings.vector_indexing_enabled

    async def request_for_contract(self, *, contratacao_chave: str, uf: str | None = None) -> None:
        """Agenda em segundo plano; uma falha na fila não afeta a rota chamadora."""

        if not self.enabled():
            self.metrics["disabled_requests"] += 1
            return
        try:
            await asyncio.to_thread(repository.enqueue_job, contratacao_chave, uf=uf)
            self.metrics["jobs_enqueued"] += 1
            await self.start_available_jobs()
        except Exception:
            self.metrics["enqueue_failures"] += 1
            logger.exception("Não foi possível agendar indexação assistida")

    async def start_available_jobs(self) -> None:
        if not self.enabled():
            return
        async with self._drain_lock:
            if self._drain_task is not None and not self._drain_task.done():
                return
            self._drain_task = asyncio.create_task(self._drain(), name="vector-indexing-drain")

    async def wait_for_idle(self) -> None:
        task = self._drain_task
        if task is not None:
            await asyncio.shield(task)

    async def _drain(self) -> None:
        while True:
            workers = [
                asyncio.create_task(self._work_once())
                for _ in range(settings.vector_index_worker_concurrency)
            ]
            worked = await asyncio.gather(*workers)
            if not any(worked):
                return

    async def _work_once(self) -> bool:
        async with self._slots:
            job = await asyncio.to_thread(repository.claim_next_job, self.worker_id)
            if job is None:
                return False
            self.metrics["jobs_started"] += 1
            try:
                await self._process(job)
            except OpenAIServiceError as exc:
                self.metrics[f"openai_{exc.code}"] += 1
                await asyncio.to_thread(
                    repository.finish_job,
                    job.id,
                    status="esgotado" if exc.code == "orcamento_esgotado" else "falho_permanente",
                    error_code=exc.code,
                    error_message=str(exc),
                    retryable=exc.retryable,
                )
            except (PNCPConnectionError, PNCPResponseError, PdfDownloadError) as exc:
                self.metrics["source_failures"] += 1
                await asyncio.to_thread(
                    repository.finish_job,
                    job.id,
                    status="falho_permanente",
                    error_code="fonte_indisponivel",
                    error_message="Não foi possível obter o documento publicado.",
                    retryable=True,
                )
                logger.info("Fonte documental indisponível para job %s: %s", job.id, type(exc).__name__)
            except (ChunkLimitError, ValueError) as exc:
                self.metrics["limit_rejections"] += 1
                await asyncio.to_thread(
                    repository.finish_job,
                    job.id,
                    status="parcial",
                    error_code="limite_processamento",
                    error_message=str(exc),
                )
            except Exception:
                self.metrics["unexpected_failures"] += 1
                logger.exception("Falha inesperada no job de indexação %s", job.id)
                await asyncio.to_thread(
                    repository.finish_job,
                    job.id,
                    status="falho_permanente",
                    error_code="erro_interno",
                    error_message="A indexação encontrou uma falha interna.",
                    retryable=True,
                )
            return True

    async def _download(self, selected: SelectedDocument) -> _DownloadResult:
        source = IndexableDocumentSource(selected.documento_id, selected.titulo, selected.url)
        if not selected.url:
            return _DownloadResult(source=source, downloaded=None, error="Documento sem URL pública.")
        try:
            return _DownloadResult(source=source, downloaded=await self.downloader(selected.url))
        except PdfDownloadError as exc:
            return _DownloadResult(source=source, downloaded=None, error=str(exc))

    @staticmethod
    def _manifest_hash(documentos: list[dict[str, Any]]) -> str:
        normalized = [
            {
                "id": item.get("sequencial_documento"),
                "titulo": item.get("titulo"),
                "url": item.get("url"),
                "tipo": item.get("tipo_documento_nome"),
            }
            for item in documentos
        ]
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _process(self, job: repository.ClaimedJob) -> None:
        cnpj, ano, sequencial = job.contratacao_chave.split(":", 2)
        documents_response = await buscar_documentos_pncp(cnpj, int(ano), int(sequencial))
        documents = list(documents_response.get("documentos") or [])
        selected = [item for item in selecionar_documentos_para_analise(documents) if item.selecionado]
        self.metrics["documents_selected"] += len(selected)
        if not selected:
            await asyncio.to_thread(repository.finish_job, job.id, status="concluido")
            self.metrics["jobs_without_documents"] += 1
            return
        if len(selected) > min(settings.vector_index_max_documents, settings.edital_analysis_max_documents):
            raise ChunkLimitError("A contratação excede o limite de documentos para indexação.")

        downloads = await asyncio.gather(*(self._download(item) for item in selected))
        self.metrics["downloads_requested"] += len(downloads)
        if not any(result.downloaded is not None for result in downloads):
            raise PdfDownloadError("Nenhum documento público pôde ser obtido para indexação.")
        total_bytes = sum(
            sum(len(pdf.content) for pdf in result.downloaded.pdfs)
            if result.downloaded is not None and hasattr(result.downloaded, "pdfs")
            else len(result.downloaded.content)
            if result.downloaded is not None
            else 0
            for result in downloads
        )
        if total_bytes > job.limite_bytes:
            raise ChunkLimitError("A contratação excede o limite de bytes para indexação.")

        manifest_hash = self._manifest_hash(documents)
        all_chunks: list[repository.StoredChunk] = []
        partial = False
        spent = 0.0
        for downloaded in downloads:
            if downloaded.downloaded is None:
                partial = True
                self.metrics["download_failures"] += 1
                continue
            self.metrics["downloads_completed"] += 1
            extracted = await extract_indexable_document(
                downloaded.source,
                downloaded.downloaded,
                ocr_service=self.ocr_service,
                ocr_enabled=settings.edital_ocr_enabled,
                max_total_pages=job.limite_paginas,
            )
            self.metrics["pages_extracted"] += extracted.total_paginas
            self.metrics["pages_ocr"] += extracted.paginas_ocr
            partial = partial or bool(extracted.falhas)
            self.metrics["extraction_failures"] += len(extracted.falhas)
            source_hash = hashlib.sha256(
                "".join(pdf.pdf_sha256 for pdf in extracted.pdfs).encode("ascii")
            ).hexdigest()
            for extracted_pdf in extracted.pdfs:
                existing = await asyncio.to_thread(
                    repository.get_completed_indexed_document,
                    contratacao_chave=job.contratacao_chave,
                    documento_id=downloaded.source.documento_id,
                    pdf_sha256=extracted_pdf.pdf_sha256,
                )
                if existing is not None:
                    await asyncio.to_thread(
                        repository.update_document_source_membership,
                        existing.id,
                        source_hash=source_hash,
                        manifesto_hash=manifest_hash,
                    )
                    all_chunks.extend(await asyncio.to_thread(repository.stored_chunks_for_document, existing.id))
                    self.metrics["indexed_document_reused"] += 1
                    continue
                drafts = chunk_pages(extracted_pdf.paginas)
                self.metrics["chunks_created"] += len(drafts)
                if len(all_chunks) + len(drafts) > job.limite_chunks:
                    raise ChunkLimitError("A contratação excede o limite total de trechos para indexação.")
                vectors: list[list[float]] = []
                for offset in range(0, len(drafts), settings.openai_embedding_batch_size):
                    batch = drafts[offset : offset + settings.openai_embedding_batch_size]
                    embedding_result = await self.embedding_provider.embed(
                        [chunk.texto for chunk in batch],
                        remaining_budget_usd=max(0.0, settings.vector_index_max_cost_usd_per_job - spent),
                    )
                    spent += embedding_result.cost_usd
                    vectors.extend(embedding_result.vectors)
                    self.metrics["embedding_tokens"] += embedding_result.input_tokens
                _, stored, reused = await asyncio.to_thread(
                    repository.persist_indexed_document,
                    contratacao_chave=job.contratacao_chave,
                    source=downloaded.source,
                    uf=job.uf,
                    manifesto_hash=manifest_hash,
                    source_hash=source_hash,
                    pdf_sha256=extracted_pdf.pdf_sha256,
                    chunks=drafts,
                    embeddings=vectors,
                )
                all_chunks.extend(stored)
                self.metrics["indexed_document_reused" if reused else "indexed_documents_created"] += 1
            if extracted.pdfs and not extracted.falhas:
                await asyncio.to_thread(
                    repository.activate_document_source,
                    contratacao_chave=job.contratacao_chave,
                    documento_id=downloaded.source.documento_id,
                    source_hash=source_hash,
                )

        if not all_chunks:
            raise OpenAIServiceError("contexto_insuficiente", "Não há texto elegível para indexação assistida.")
        analysis_chunks = all_chunks[: settings.openai_analysis_max_chunks]
        partial = partial or len(analysis_chunks) < len(all_chunks)
        contexts = [
            AnalysisChunkContext(
                chunk_id=chunk.id,
                documento_id=chunk.documento_id,
                titulo_documento=chunk.titulo_documento,
                url_documento=chunk.url_documento,
                pagina=chunk.pagina,
                texto=chunk.texto,
                origem_texto=chunk.origem_texto,
            )
            for chunk in analysis_chunks
        ]
        try:
            analysis_result = await self.requirement_analyzer.analyze(
                contexts,
                remaining_budget_usd=max(0.0, settings.vector_index_max_cost_usd_per_job - spent),
            )
        except OpenAIServiceError as exc:
            await asyncio.to_thread(
                repository.record_requirement_failure,
                contratacao_chave=job.contratacao_chave,
                manifesto_hash=manifest_hash,
                chunks=analysis_chunks,
                error_code=exc.code,
                error_message=str(exc),
            )
            raise
        spent += analysis_result.cost_usd
        status = "sucesso_parcial" if partial or analysis_result.rejected_count else "sucesso"
        persisted = await asyncio.to_thread(
            repository.persist_requirement_analysis,
            contratacao_chave=job.contratacao_chave,
            manifesto_hash=manifest_hash,
            chunks=analysis_chunks,
            result=analysis_result,
            status=status,
        )
        if persisted is None:
            raise OpenAIServiceError("persistencia", "Não foi possível persistir a análise assistida.", retryable=True)
        self.metrics["analysis_input_tokens"] += analysis_result.input_tokens
        self.metrics["analysis_output_tokens"] += analysis_result.output_tokens
        self.metrics["analysis_rejected_items"] += analysis_result.rejected_count
        self.metrics["estimated_cost_microusd"] += round(spent * 1_000_000)
        await asyncio.to_thread(repository.finish_job, job.id, status="parcial" if status == "sucesso_parcial" else "concluido")
        self.metrics["jobs_completed"] += 1
