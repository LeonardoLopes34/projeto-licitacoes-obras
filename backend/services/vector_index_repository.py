"""Repositório transacional e idempotente da Spec 015."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import delete, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.config import settings
from backend.database import SessionLocal
from backend.models.vector_index_model import (
    DocumentChunkModel,
    DocumentIndexJobModel,
    DocumentRequirementAnalysisModel,
    DocumentRequirementItemModel,
    IndexedDocumentModel,
)
from backend.schemas import ResultadoExigencias
from backend.services.document_text_indexing_service import IndexableDocumentSource
from backend.services.openai_edital_service import RequirementAnalysisResult
from backend.services.vector_chunk_service import ChunkDraft


logger = logging.getLogger(__name__)
_TERMINAL_JOB_STATUSES = {"concluido", "parcial", "falho_permanente", "esgotado"}
_ACTIVE_ANALYSIS_STATUSES = {"sucesso", "sucesso_parcial"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    contratacao_chave: str
    uf: str | None
    attempt: int
    limite_bytes: int
    limite_paginas: int
    limite_chunks: int


@dataclass(frozen=True)
class StoredChunk:
    id: int
    documento_id: int
    titulo_documento: str
    url_documento: str | None
    pagina: int
    texto: str
    texto_hash: str
    origem_texto: str
    confianca_ocr: float | None


def enqueue_job(contratacao_chave: str, *, uf: str | None = None, motivo: str = "abertura_contratacao") -> int:
    """Deduplica jobs pendentes/em execução; não inicia processamento aqui."""

    try:
        with SessionLocal() as db:
            existing = db.scalar(
                select(DocumentIndexJobModel)
                .where(
                    DocumentIndexJobModel.contratacao_chave == contratacao_chave,
                    DocumentIndexJobModel.status.in_(("pendente", "em_execucao")),
                )
                .order_by(DocumentIndexJobModel.id.desc())
            )
            if existing is not None:
                return existing.id
            job = DocumentIndexJobModel(
                contratacao_chave=contratacao_chave,
                uf=uf,
                motivo=motivo,
                status="pendente",
                attempt=0,
                limite_bytes=settings.edital_analysis_max_total_bytes,
                limite_paginas=settings.edital_analysis_max_total_pages,
                limite_chunks=settings.vector_index_max_chunks_per_job,
            )
            db.add(job)
            db.commit()
            return job.id
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível enfileirar indexação da contratação %s: %s", contratacao_chave, exc)
        raise


def claim_next_job(worker_id: str) -> ClaimedJob | None:
    """Obtém um lease. PostgreSQL usa bloqueio de linha; SQLite fica só para testes."""

    now = _now()
    try:
        with SessionLocal() as db:
            stmt = (
                select(DocumentIndexJobModel)
                .where(
                    (DocumentIndexJobModel.status == "pendente")
                    | (
                        (DocumentIndexJobModel.status == "em_execucao")
                        & (DocumentIndexJobModel.lease_until.is_not(None))
                        & (DocumentIndexJobModel.lease_until < now)
                    )
                )
                .where(DocumentIndexJobModel.available_at <= now)
                .order_by(DocumentIndexJobModel.created_at, DocumentIndexJobModel.id)
            )
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)
            job = db.scalar(stmt)
            if job is None:
                return None
            job.status = "em_execucao"
            job.attempt += 1
            job.worker_id = worker_id
            job.started_at = now
            job.lease_until = now + timedelta(seconds=settings.vector_index_lease_seconds)
            job.erro_codigo = None
            job.erro_mensagem_segura = None
            db.commit()
            return ClaimedJob(
                id=job.id,
                contratacao_chave=job.contratacao_chave,
                uf=job.uf,
                attempt=job.attempt,
                limite_bytes=job.limite_bytes,
                limite_paginas=job.limite_paginas,
                limite_chunks=job.limite_chunks,
            )
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível obter job de indexação: %s", exc)
        return None


def finish_job(
    job_id: int,
    *,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    retryable: bool = False,
) -> None:
    """Finaliza ou devolve o job à fila, sempre com mensagem segura."""

    now = _now()
    try:
        with SessionLocal() as db:
            job = db.get(DocumentIndexJobModel, job_id)
            if job is None:
                return
            job.erro_codigo = error_code
            job.erro_mensagem_segura = (error_message or "")[:500] or None
            job.lease_until = None
            job.worker_id = None
            if retryable and job.attempt < settings.vector_index_max_attempts:
                job.status = "pendente"
                job.available_at = now + timedelta(seconds=min(60, 2**job.attempt))
                job.finished_at = None
            else:
                job.status = "esgotado" if retryable else status
                job.finished_at = now
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível finalizar job de indexação %s: %s", job_id, exc)


def get_completed_indexed_document(
    *,
    contratacao_chave: str,
    documento_id: int,
    pdf_sha256: str,
) -> IndexedDocumentModel | None:
    """Localiza versão compatível antes de chamar o provedor de embeddings."""

    try:
        with SessionLocal() as db:
            return db.scalar(
                select(IndexedDocumentModel).where(
                    IndexedDocumentModel.contratacao_chave == contratacao_chave,
                    IndexedDocumentModel.documento_id == documento_id,
                    IndexedDocumentModel.pdf_sha256 == pdf_sha256,
                    IndexedDocumentModel.versao_extracao == settings.vector_extraction_version,
                    IndexedDocumentModel.versao_chunking == settings.vector_chunking_version,
                    IndexedDocumentModel.modelo_embedding == settings.openai_embedding_model,
                    IndexedDocumentModel.status == "concluido",
                )
            )
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível consultar versão indexada: %s", exc)
        return None


def stored_chunks_for_document(indexed_document_id: int) -> list[StoredChunk]:
    try:
        with SessionLocal() as db:
            document = db.get(IndexedDocumentModel, indexed_document_id)
            if document is None:
                return []
            rows = db.scalars(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.indexed_document_id == indexed_document_id)
                .order_by(DocumentChunkModel.ordem)
            ).all()
            return [
                StoredChunk(
                    id=row.id,
                    documento_id=document.documento_id,
                    titulo_documento=document.titulo,
                    url_documento=document.url_origem,
                    pagina=row.pagina_inicio,
                    texto=row.texto,
                    texto_hash=row.texto_hash,
                    origem_texto=row.origem_texto,
                    confianca_ocr=row.confianca_ocr,
                )
                for row in rows
            ]
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível recuperar chunks indexados: %s", exc)
        return []


def persist_indexed_document(
    *,
    contratacao_chave: str,
    source: IndexableDocumentSource,
    uf: str | None,
    manifesto_hash: str,
    source_hash: str,
    pdf_sha256: str,
    chunks: Sequence[ChunkDraft],
    embeddings: Sequence[list[float]],
) -> tuple[int, list[StoredChunk], bool]:
    """Persiste versão completa e só então inativa a versão anterior."""

    if len(chunks) != len(embeddings):
        raise ValueError("A quantidade de embeddings não corresponde aos chunks")
    now = _now()
    try:
        with SessionLocal() as db:
            document = db.scalar(
                select(IndexedDocumentModel).where(
                    IndexedDocumentModel.contratacao_chave == contratacao_chave,
                    IndexedDocumentModel.documento_id == source.documento_id,
                    IndexedDocumentModel.pdf_sha256 == pdf_sha256,
                    IndexedDocumentModel.versao_extracao == settings.vector_extraction_version,
                    IndexedDocumentModel.versao_chunking == settings.vector_chunking_version,
                    IndexedDocumentModel.modelo_embedding == settings.openai_embedding_model,
                )
            )
            if document is not None and document.status == "concluido":
                if document.source_hash != source_hash or document.manifesto_hash != manifesto_hash:
                    document.source_hash = source_hash
                    document.manifesto_hash = manifesto_hash
                    db.commit()
                document_id = document.id
                reused = True
            else:
                reused = False
                if document is None:
                    document = IndexedDocumentModel(
                        contratacao_chave=contratacao_chave,
                        documento_id=source.documento_id,
                        titulo=source.titulo,
                        url_origem=source.url,
                        uf=uf,
                        pdf_sha256=pdf_sha256,
                        source_hash=source_hash,
                        manifesto_hash=manifesto_hash,
                        versao_extracao=settings.vector_extraction_version,
                        versao_chunking=settings.vector_chunking_version,
                        modelo_embedding=settings.openai_embedding_model,
                        status="em_execucao",
                        tentativas=1,
                        ativo=False,
                    )
                    db.add(document)
                    db.flush()
                else:
                    db.execute(delete(DocumentChunkModel).where(DocumentChunkModel.indexed_document_id == document.id))
                    document.source_hash = source_hash
                    document.manifesto_hash = manifesto_hash
                    document.status = "em_execucao"
                    document.tentativas += 1
                for draft, embedding in zip(chunks, embeddings, strict=True):
                    db.add(
                        DocumentChunkModel(
                            indexed_document_id=document.id,
                            ordem=draft.ordem,
                            pagina_inicio=draft.pagina_inicio,
                            pagina_fim=draft.pagina_fim,
                            inicio_caractere=draft.inicio_caractere,
                            fim_caractere=draft.fim_caractere,
                            texto=draft.texto,
                            texto_hash=draft.texto_hash,
                            origem_texto=draft.origem_texto,
                            confianca_ocr=draft.confianca_ocr,
                            token_count=draft.token_count,
                            tamanho_caracteres=len(draft.texto),
                            embedding=embedding,
                        )
                    )
                db.flush()
                document.status = "concluido"
                document.indexed_at = now
                document.erro_codigo = None
                document.erro_mensagem_segura = None
                db.commit()
                document_id = document.id
        return document_id, stored_chunks_for_document(document_id), reused
    except IntegrityError:
        # Outra instalação pode ter persistido a mesma versão entre consulta e
        # inserção. Reusar o registro é seguro e evita duplicidade.
        completed = get_completed_indexed_document(
            contratacao_chave=contratacao_chave, documento_id=source.documento_id, pdf_sha256=pdf_sha256
        )
        if completed is not None:
            return completed.id, stored_chunks_for_document(completed.id), True
        raise


def activate_document_source(*, contratacao_chave: str, documento_id: int, source_hash: str) -> None:
    """Ativa um conjunto completo de PDFs e só então inativa sua versão anterior.

    ZIPs podem conter vários PDFs para o mesmo documento publicado. A ativação
    por conjunto evita que o último PDF interno desative os demais.
    """

    now = _now()
    try:
        with SessionLocal() as db:
            current = db.scalars(
                select(IndexedDocumentModel).where(
                    IndexedDocumentModel.contratacao_chave == contratacao_chave,
                    IndexedDocumentModel.documento_id == documento_id,
                    IndexedDocumentModel.source_hash == source_hash,
                    IndexedDocumentModel.status == "concluido",
                )
            ).all()
            if not current:
                return
            for document in current:
                document.ativo = True
                document.superseded_at = None
            previous = db.scalars(
                select(IndexedDocumentModel).where(
                    IndexedDocumentModel.contratacao_chave == contratacao_chave,
                    IndexedDocumentModel.documento_id == documento_id,
                    IndexedDocumentModel.source_hash != source_hash,
                    IndexedDocumentModel.ativo.is_(True),
                )
            ).all()
            for document in previous:
                document.ativo = False
                document.superseded_at = now
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível ativar a versão indexada do documento %s: %s", documento_id, exc)


def update_document_source_membership(
    indexed_document_id: int, *, source_hash: str, manifesto_hash: str
) -> None:
    """Atualiza o conjunto de origem sem gerar novamente vetores idênticos."""

    try:
        with SessionLocal() as db:
            document = db.get(IndexedDocumentModel, indexed_document_id)
            if document is None:
                return
            document.source_hash = source_hash
            document.manifesto_hash = manifesto_hash
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível atualizar o conjunto de origem do documento indexado: %s", exc)


def analysis_source_hash(chunks: Iterable[StoredChunk]) -> str:
    payload = "".join(sorted(chunk.texto_hash for chunk in chunks))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def get_completed_requirement_result(contratacao_chave: str) -> ResultadoExigencias | None:
    try:
        with SessionLocal() as db:
            analysis = db.scalar(
                select(DocumentRequirementAnalysisModel)
                .where(
                    DocumentRequirementAnalysisModel.contratacao_chave == contratacao_chave,
                    DocumentRequirementAnalysisModel.modelo_embedding == settings.openai_embedding_model,
                    DocumentRequirementAnalysisModel.modelo_analise == settings.openai_analysis_model,
                    DocumentRequirementAnalysisModel.versao_prompt == settings.openai_analysis_prompt_version,
                    DocumentRequirementAnalysisModel.versao_schema == settings.openai_analysis_schema_version,
                    DocumentRequirementAnalysisModel.ativo.is_(True),
                    DocumentRequirementAnalysisModel.status.in_(_ACTIVE_ANALYSIS_STATUSES),
                )
                .order_by(DocumentRequirementAnalysisModel.updated_at.desc(), DocumentRequirementAnalysisModel.id.desc())
            )
            if analysis is None:
                return None
            items = db.scalars(
                select(DocumentRequirementItemModel)
                .where(DocumentRequirementItemModel.analysis_id == analysis.id, DocumentRequirementItemModel.aceito_por_schema.is_(True))
                .order_by(DocumentRequirementItemModel.id)
            ).all()
            categories: dict[str, int] = {}
            requirements = []
            summaries = []
            documents: dict[int, dict[str, object]] = {}
            for item in items:
                categories[item.categoria] = categories.get(item.categoria, 0) + 1
                status = "identificado_no_edital" if item.estado == "identificado" else "revisao_necessaria"
                requirements.append(
                    {
                        "categoria": item.categoria,
                        "rotulo": item.nome_documento,
                        "descricao_resumida": item.resumo,
                        "filtro_documental": "analise_assistida",
                        "descricao_original": item.evidencia,
                        "documento_id": item.documento_id,
                        "titulo_documento": item.titulo_documento,
                        "url_documento": item.url_documento,
                        "pagina": item.pagina,
                        "evidencia": item.evidencia,
                        "confianca": item.confianca,
                        "origem_texto": item.origem_texto,
                        "status": status,
                        "estado": item.estado,
                    }
                )
                if item.estado != "nao_identificado":
                    summaries.append(
                        {
                            "nome": item.nome_documento,
                            "categoria": item.categoria,
                            "confianca": item.confianca,
                            "estado": item.estado,
                        }
                    )
                documents.setdefault(
                    item.documento_id,
                    {
                        "documento_id": item.documento_id,
                        "titulo": item.titulo_documento,
                        "url": item.url_documento,
                        "paginas": 0,
                        "paginas_com_ocr": 0,
                        "status": "analisado_assistido",
                    },
                )
            status = "sucesso" if analysis.status == "sucesso" else "sucesso_parcial"
            return ResultadoExigencias(
                status=status,
                mensagem="Documentos exigidos identificados por análise assistida; confira as fontes no detalhe.",
                total_exigencias=len(requirements),
                categorias=categories,
                documentos_analisados=list(documents.values()),
                exigencias=requirements,
                analisador_versao=(
                    f"openai:{analysis.modelo_analise}:{analysis.versao_prompt}:{analysis.versao_schema}"
                ),
                documentos_exigidos=summaries,
                analise_assistida=True,
                analise_assistida_status=analysis.status,
            )
    except (SQLAlchemyError, ValueError) as exc:
        logger.warning("Resultado assistido indisponível para a contratação %s: %s", contratacao_chave, exc)
        return None


def get_requirement_analysis_status(contratacao_chave: str) -> str | None:
    """Estado mais recente da análise assistida compatível, sem expor o erro."""

    try:
        with SessionLocal() as db:
            return db.scalar(
                select(DocumentRequirementAnalysisModel.status)
                .where(
                    DocumentRequirementAnalysisModel.contratacao_chave == contratacao_chave,
                    DocumentRequirementAnalysisModel.modelo_embedding == settings.openai_embedding_model,
                    DocumentRequirementAnalysisModel.modelo_analise == settings.openai_analysis_model,
                    DocumentRequirementAnalysisModel.versao_prompt == settings.openai_analysis_prompt_version,
                    DocumentRequirementAnalysisModel.versao_schema == settings.openai_analysis_schema_version,
                )
                .order_by(DocumentRequirementAnalysisModel.updated_at.desc(), DocumentRequirementAnalysisModel.id.desc())
            )
    except SQLAlchemyError as exc:
        logger.warning("Estado de análise assistida indisponível para a contratação %s: %s", contratacao_chave, exc)
        return None


def persist_requirement_analysis(
    *,
    contratacao_chave: str,
    manifesto_hash: str,
    chunks: Sequence[StoredChunk],
    result: RequirementAnalysisResult,
    status: str,
) -> ResultadoExigencias | None:
    """Persiste apenas itens validados e ativa a nova versão ao final."""

    source_hash = analysis_source_hash(chunks)
    now = _now()
    by_chunk = {chunk.id: chunk for chunk in chunks}
    existing_active = False
    try:
        with SessionLocal() as db:
            analysis = db.scalar(
                select(DocumentRequirementAnalysisModel).where(
                    DocumentRequirementAnalysisModel.contratacao_chave == contratacao_chave,
                    DocumentRequirementAnalysisModel.fonte_hash == source_hash,
                    DocumentRequirementAnalysisModel.modelo_embedding == settings.openai_embedding_model,
                    DocumentRequirementAnalysisModel.modelo_analise == settings.openai_analysis_model,
                    DocumentRequirementAnalysisModel.versao_prompt == settings.openai_analysis_prompt_version,
                    DocumentRequirementAnalysisModel.versao_schema == settings.openai_analysis_schema_version,
                )
            )
            if analysis is not None and analysis.status in _ACTIVE_ANALYSIS_STATUSES:
                existing_active = True
            elif analysis is None:
                analysis = DocumentRequirementAnalysisModel(
                    contratacao_chave=contratacao_chave,
                    manifesto_hash=manifesto_hash,
                    fonte_hash=source_hash,
                    chunk_hashes=[chunk.texto_hash for chunk in chunks],
                    modelo_embedding=settings.openai_embedding_model,
                    modelo_analise=settings.openai_analysis_model,
                    versao_prompt=settings.openai_analysis_prompt_version,
                    versao_schema=settings.openai_analysis_schema_version,
                    status=status,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    custo_estimado_usd=result.cost_usd,
                    latencia_ms=result.latency_ms,
                    ativo=False,
                )
                db.add(analysis)
                db.flush()
            else:
                db.execute(delete(DocumentRequirementItemModel).where(DocumentRequirementItemModel.analysis_id == analysis.id))
                analysis.status = status
                analysis.manifesto_hash = manifesto_hash
                analysis.input_tokens = result.input_tokens
                analysis.output_tokens = result.output_tokens
                analysis.custo_estimado_usd = result.cost_usd
                analysis.latencia_ms = result.latency_ms
                # Uma nova execução bem-sucedida pode reutilizar a versão que
                # antes guardava uma falha. O diagnóstico anterior não pode
                # permanecer associado ao resultado ativo.
                analysis.erro_codigo = None
                analysis.erro_mensagem_segura = None
            if not existing_active:
                for candidate in result.accepted:
                    source = by_chunk[candidate.chunk_id]
                    db.add(
                        DocumentRequirementItemModel(
                            analysis_id=analysis.id,
                            categoria=candidate.categoria,
                            nome_documento=candidate.nome_documento,
                            resumo=candidate.resumo,
                            documento_id=source.documento_id,
                            titulo_documento=source.titulo_documento,
                            url_documento=source.url_documento,
                            pagina=source.pagina,
                            chunk_id=source.id,
                            evidencia=candidate.evidencia,
                            confianca=candidate.confianca,
                            estado=candidate.estado,
                            origem_texto=source.origem_texto,
                            aceito_por_schema=True,
                        )
                    )
                if status in _ACTIVE_ANALYSIS_STATUSES:
                    old = db.scalars(
                        select(DocumentRequirementAnalysisModel).where(
                            DocumentRequirementAnalysisModel.contratacao_chave == contratacao_chave,
                            DocumentRequirementAnalysisModel.id != analysis.id,
                            DocumentRequirementAnalysisModel.ativo.is_(True),
                        )
                    ).all()
                    for previous in old:
                        previous.ativo = False
                        previous.superseded_at = now
                    analysis.ativo = True
                db.commit()
        return get_completed_requirement_result(contratacao_chave)
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível persistir análise assistida da contratação %s: %s", contratacao_chave, exc)
        return None


def record_requirement_failure(
    *,
    contratacao_chave: str,
    manifesto_hash: str,
    chunks: Sequence[StoredChunk],
    error_code: str,
    error_message: str,
) -> None:
    """Mantém diagnóstico seguro sem ativar uma análise falha."""

    source_hash = analysis_source_hash(chunks)
    try:
        with SessionLocal() as db:
            analysis = DocumentRequirementAnalysisModel(
                contratacao_chave=contratacao_chave,
                manifesto_hash=manifesto_hash,
                fonte_hash=source_hash,
                chunk_hashes=[chunk.texto_hash for chunk in chunks],
                modelo_embedding=settings.openai_embedding_model,
                modelo_analise=settings.openai_analysis_model,
                versao_prompt=settings.openai_analysis_prompt_version,
                versao_schema=settings.openai_analysis_schema_version,
                status="indisponivel",
                erro_codigo=error_code,
                erro_mensagem_segura=error_message[:500],
                ativo=False,
            )
            db.add(analysis)
            db.commit()
    except IntegrityError:
        # A mesma falha/versionamento pode ser observada por mais de um worker;
        # a unicidade é o mecanismo de deduplicação, sem necessidade de logar texto.
        return
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível registrar falha da análise assistida: %s", exc)


def assisted_summaries(contratacao_chaves: set[str]) -> dict[str, dict[str, object]]:
    """Projeção compacta para a listagem de cards, sem download ou chamada OpenAI."""

    summaries: dict[str, dict[str, object]] = {}
    for key in contratacao_chaves:
        result = get_completed_requirement_result(key)
        if result is None:
            continue
        summaries[key] = {
            "status": result.status,
            "total_exigencias": result.total_exigencias,
            "categorias": result.categorias,
            "analisador_versao": result.analisador_versao,
            "documentos_exigidos": [item.model_dump() for item in result.documentos_exigidos],
            "analise_assistida": True,
            "analise_assistida_status": result.analise_assistida_status,
        }
    return summaries


def inactivate_contract(contratacao_chave: str) -> None:
    """Retenção lógica de vetores/textos derivados quando a contratação expira."""

    now = _now()
    try:
        with SessionLocal() as db:
            for record in db.scalars(
                select(IndexedDocumentModel).where(
                    IndexedDocumentModel.contratacao_chave == contratacao_chave,
                    IndexedDocumentModel.ativo.is_(True),
                )
            ):
                record.ativo = False
                record.superseded_at = now
            for analysis in db.scalars(
                select(DocumentRequirementAnalysisModel).where(
                    DocumentRequirementAnalysisModel.contratacao_chave == contratacao_chave,
                    DocumentRequirementAnalysisModel.ativo.is_(True),
                )
            ):
                analysis.ativo = False
                analysis.superseded_at = now
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível inativar derivados da contratação %s: %s", contratacao_chave, exc)


def purge_expired_inactive_derivatives(*, max_age_days: int) -> int:
    """Remove texto/vetores derivados já inativos, preservando os jobs operacionais.

    O corte só alcança versões substituídas, resultados indisponíveis ou
    contratações previamente inativadas. Nenhuma versão ativa é eliminada.
    """

    cutoff = _now() - timedelta(days=max_age_days)
    try:
        with SessionLocal() as db:
            analyses = db.execute(
                delete(DocumentRequirementAnalysisModel).where(
                    DocumentRequirementAnalysisModel.ativo.is_(False),
                    or_(
                        DocumentRequirementAnalysisModel.superseded_at < cutoff,
                        DocumentRequirementAnalysisModel.created_at < cutoff,
                    ),
                )
            )
            documents = db.execute(
                delete(IndexedDocumentModel).where(
                    IndexedDocumentModel.ativo.is_(False),
                    or_(IndexedDocumentModel.superseded_at < cutoff, IndexedDocumentModel.created_at < cutoff),
                )
            )
            db.commit()
            return (analyses.rowcount or 0) + (documents.rowcount or 0)
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível remover derivados vetoriais expirados: %s", exc)
        return 0


def search_similar_chunks(
    *,
    contratacao_chave: str,
    embedding: list[float],
    limit: int = 5,
    documento_id: int | None = None,
    pagina: int | None = None,
    uf: str | None = None,
) -> list[dict[str, object]]:
    """Consulta interna de validação; nunca é exposta como rota pública."""

    if len(embedding) != settings.openai_embedding_dimensions or not all(math.isfinite(float(item)) for item in embedding):
        raise ValueError("Embedding de consulta inválido")
    if not 1 <= limit <= 20:
        raise ValueError("Limite de busca interna deve estar entre 1 e 20")
    vector = "[" + ",".join(format(float(item), ".10g") for item in embedding) + "]"
    try:
        with SessionLocal() as db:
            if db.bind is None or db.bind.dialect.name != "postgresql":
                raise RuntimeError("Busca vetorial requer PostgreSQL com pgvector")
            filters = [
                "d.contratacao_chave = :contratacao_chave",
                "d.ativo = true",
                "d.status = 'concluido'",
                "c.embedding IS NOT NULL",
            ]
            params: dict[str, object] = {
                "embedding": vector,
                "contratacao_chave": contratacao_chave,
                "limit": limit,
            }
            if documento_id is not None:
                filters.append("d.documento_id = :documento_id")
                params["documento_id"] = documento_id
            if pagina is not None:
                filters.append("c.pagina_inicio <= :pagina AND c.pagina_fim >= :pagina")
                params["pagina"] = pagina
            if uf:
                filters.append("d.uf = :uf")
                params["uf"] = uf.upper().strip()
            rows = db.execute(
                text(
                    "SELECT c.id, c.texto, c.pagina_inicio, c.embedding <=> CAST(:embedding AS vector) AS distancia "
                    "FROM document_chunks c "
                    "JOIN indexed_documents d ON d.id = c.indexed_document_id "
                    f"WHERE {' AND '.join(filters)} "
                    "ORDER BY c.embedding <=> CAST(:embedding AS vector) LIMIT :limit"
                ),
                params,
            ).mappings()
            return [dict(row) for row in rows]
    except SQLAlchemyError as exc:
        raise RuntimeError("Não foi possível executar a busca vetorial interna.") from exc
