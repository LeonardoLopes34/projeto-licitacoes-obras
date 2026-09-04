"""Cache persistente dos índices de documentos publicados pelo PNCP."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.database import SessionLocal
from backend.models.document_snapshot_model import DocumentSnapshotModel, utc_now


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SnapshotDocumentosPersistidos:
    """Versão recuperável de uma lista de documentos da contratação."""

    documentos: list[dict[str, Any]]
    documentos_hash: str
    created_at: datetime
    updated_at: datetime


def _as_dict(documento: Any) -> dict[str, Any]:
    if hasattr(documento, "model_dump"):
        return documento.model_dump()
    return documento if isinstance(documento, dict) else {}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalizar_documentos_snapshot(documentos: Iterable[Any]) -> list[dict[str, Any]]:
    """Gera uma lista estável, sem campos transitórios, para persistência.

    A entrada normalmente já vem de ``normalizar_documentos_pncp``. Esta
    segunda normalização mantém o repositório seguro para reuso e torna o hash
    independente da ordem ou de campos extras de uma resposta remota.
    """

    normalized_by_sequence: dict[int, dict[str, Any]] = {}
    for raw_document in documentos:
        document = _as_dict(raw_document)
        sequence = _optional_int(document.get("sequencial_documento"))
        if sequence is None:
            sequence = _optional_int(document.get("sequencialDocumento"))
        if sequence is None or sequence < 1 or sequence in normalized_by_sequence:
            continue

        normalized_by_sequence[sequence] = {
            "sequencial_documento": sequence,
            "url": _optional_text(document.get("url")),
            "tipo_documento_id": _optional_int(
                document.get("tipo_documento_id", document.get("tipoDocumentoId"))
            ),
            "tipo_documento_nome": _optional_text(
                document.get("tipo_documento_nome", document.get("tipoDocumentoNome"))
            ),
            "titulo": _optional_text(document.get("titulo")),
            "data_publicacao_pncp": _optional_text(
                document.get("data_publicacao_pncp", document.get("dataPublicacaoPncp"))
            ),
        }
    return [normalized_by_sequence[sequence] for sequence in sorted(normalized_by_sequence)]


def calcular_hash_documentos(documentos: Iterable[Any]) -> str:
    """Calcula um hash estável da versão normalizada da lista de documentos."""

    normalized = normalizar_documentos_snapshot(documentos)
    canonical_json = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _to_snapshot(record: DocumentSnapshotModel) -> SnapshotDocumentosPersistidos:
    return SnapshotDocumentosPersistidos(
        documentos=copy.deepcopy(record.documentos),
        documentos_hash=record.documentos_hash,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def salvar_snapshot_documentos(
    contratacao_chave: str,
    documentos: Iterable[Any],
) -> SnapshotDocumentosPersistidos | None:
    """Grava a lista conhecida e atualiza o instante da última consulta real."""

    normalized = normalizar_documentos_snapshot(documentos)
    documentos_hash = calcular_hash_documentos(normalized)
    try:
        with SessionLocal() as db:
            record = db.scalar(
                select(DocumentSnapshotModel).where(
                    DocumentSnapshotModel.contratacao_chave == contratacao_chave,
                    DocumentSnapshotModel.documentos_hash == documentos_hash,
                )
            )
            if record is None:
                record = DocumentSnapshotModel(
                    contratacao_chave=contratacao_chave,
                    documentos_hash=documentos_hash,
                    documentos=normalized,
                )
                db.add(record)
            else:
                record.documentos = normalized
                record.updated_at = utc_now()
            db.commit()
            db.refresh(record)
            return _to_snapshot(record)
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível persistir o snapshot de documentos: %s", exc)
        return None


def obter_snapshot_documentos(contratacao_chave: str) -> SnapshotDocumentosPersistidos | None:
    """Retorna o snapshot mais recente conhecido da contratação."""

    try:
        with SessionLocal() as db:
            record = db.scalar(
                select(DocumentSnapshotModel)
                .where(DocumentSnapshotModel.contratacao_chave == contratacao_chave)
                .order_by(DocumentSnapshotModel.updated_at.desc(), DocumentSnapshotModel.id.desc())
            )
            return _to_snapshot(record) if record else None
    except SQLAlchemyError as exc:
        logger.warning("Snapshot persistente de documentos indisponível: %s", exc)
        return None
