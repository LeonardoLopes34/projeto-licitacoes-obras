"""Leitura/gravação tolerante a falhas para o cache persistente de análises."""

import logging
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database import SessionLocal
from backend.models.edital_analysis_model import EditalAnalysisModel
from backend.schemas import ResultadoExigencias


logger = logging.getLogger(__name__)

_REUSABLE_ANALYSIS_STATUSES = ("sucesso", "sucesso_parcial", "sem_documento_analisavel")


@dataclass(frozen=True)
class AnalisePersistida:
    """Resultado compatível com a versão atual e seu instante de atualização."""

    resultado: ResultadoExigencias
    updated_at: datetime


def obter_analise(
    contratacao_chave: str,
    documentos_hash: str,
    analisador_versao: str,
) -> ResultadoExigencias | None:
    try:
        with SessionLocal() as db:
            record = db.scalar(
                select(EditalAnalysisModel).where(
                    EditalAnalysisModel.contratacao_chave == contratacao_chave,
                    EditalAnalysisModel.documentos_hash == documentos_hash,
                    EditalAnalysisModel.analisador_versao == analisador_versao,
                )
            )
            return ResultadoExigencias.model_validate(record.resultado) if record else None
    except (SQLAlchemyError, ValidationError) as exc:
        logger.warning("Cache persistente de análise indisponível: %s", exc)
        return None


def salvar_analise(
    contratacao_chave: str,
    documentos_hash: str,
    result: ResultadoExigencias,
) -> None:
    try:
        with SessionLocal() as db:
            record = db.scalar(
                select(EditalAnalysisModel).where(
                    EditalAnalysisModel.contratacao_chave == contratacao_chave,
                    EditalAnalysisModel.documentos_hash == documentos_hash,
                    EditalAnalysisModel.analisador_versao == result.analisador_versao,
                )
            )
            if record is None:
                record = EditalAnalysisModel(
                    contratacao_chave=contratacao_chave,
                    documentos_hash=documentos_hash,
                    analisador_versao=result.analisador_versao,
                    status=result.status,
                    resultado=result.model_dump(mode="json"),
                )
                db.add(record)
            else:
                record.status = result.status
                record.resultado = result.model_dump(mode="json")
            db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível persistir a análise de edital: %s", exc)


def obter_ultima_analise_com_atualizacao(
    contratacao_chave: str,
    analisador_versao: str,
) -> AnalisePersistida | None:
    """Recupera a análise reutilizável mais recente da contratação.

    A compatibilidade exige a mesma versão do analisador. Registros inválidos
    ou resultados de erro são ignorados: um fallback não deve substituir uma
    consulta remota por uma falha antiga.
    """

    try:
        with SessionLocal() as db:
            records = db.scalars(
                select(EditalAnalysisModel)
                .where(
                    EditalAnalysisModel.contratacao_chave == contratacao_chave,
                    EditalAnalysisModel.analisador_versao == analisador_versao,
                    EditalAnalysisModel.status.in_(_REUSABLE_ANALYSIS_STATUSES),
                )
                .order_by(EditalAnalysisModel.updated_at.desc(), EditalAnalysisModel.id.desc())
            ).all()
        for record in records:
            try:
                result = ResultadoExigencias.model_validate(record.resultado)
            except ValidationError as exc:
                logger.warning("Análise persistente inválida ignorada: %s", exc)
                continue
            if result.analisador_versao != analisador_versao:
                logger.warning("Análise persistente com versão inconsistente foi ignorada")
                continue
            return AnalisePersistida(resultado=result, updated_at=record.updated_at)
    except SQLAlchemyError as exc:
        logger.warning("Última análise persistente indisponível: %s", exc)
    return None


def obter_ultima_analise_compativel(
    contratacao_chave: str,
    analisador_versao: str,
) -> ResultadoExigencias | None:
    """Atalho para consumidores que não precisam do timestamp do fallback."""

    persisted = obter_ultima_analise_com_atualizacao(contratacao_chave, analisador_versao)
    return persisted.resultado if persisted else None


def obter_resumos_contratacoes(contratacao_chaves: set[str]) -> dict[str, dict[str, object]]:
    """Retorna resumos já calculados para os cards, sem iniciar OCR/download."""
    if not contratacao_chaves:
        return {}
    try:
        with SessionLocal() as db:
            records = db.scalars(
                select(EditalAnalysisModel)
                .where(
                    EditalAnalysisModel.contratacao_chave.in_(contratacao_chaves),
                    EditalAnalysisModel.analisador_versao == settings.edital_analyzer_version,
                )
                .order_by(EditalAnalysisModel.updated_at.desc())
            ).all()
        summaries: dict[str, dict[str, object]] = {}
        for record in records:
            if record.contratacao_chave in summaries:
                continue
            result = ResultadoExigencias.model_validate(record.resultado)
            summaries[record.contratacao_chave] = {
                "status": result.status,
                "total_exigencias": result.total_exigencias,
                "categorias": result.categorias,
                "analisador_versao": result.analisador_versao,
            }
        return summaries
    except (SQLAlchemyError, ValidationError) as exc:
        logger.warning("Resumo persistente de análise indisponível: %s", exc)
        return {}
