"""Persistência limitada de snapshots de consulta compartilhados entre processos."""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.database import SessionLocal
from backend.models.query_snapshot_model import QuerySnapshotModel


logger = logging.getLogger(__name__)
_TEST_SNAPSHOTS: dict[str, QuerySnapshot] = {}


class QuerySnapshotStorageError(RuntimeError):
    """Falha que impede emitir um cursor que não poderá continuar."""


@dataclass(frozen=True)
class QuerySnapshot:
    id: str
    fingerprint: str
    dados: list[dict[str, Any]]
    resultado: dict[str, Any]
    created_at: datetime
    expires_at: datetime


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _as_snapshot(record: QuerySnapshotModel) -> QuerySnapshot:
    return QuerySnapshot(
        id=record.id,
        fingerprint=record.fingerprint,
        dados=list(record.dados),
        resultado=dict(record.resultado),
        created_at=_utc(record.created_at),
        expires_at=_utc(record.expires_at),
    )


def _trim_snapshots(db) -> None:
    now = datetime.now(timezone.utc)
    db.execute(delete(QuerySnapshotModel).where(QuerySnapshotModel.expires_at <= now))
    surplus = db.scalars(
        select(QuerySnapshotModel.id)
        .order_by(QuerySnapshotModel.created_at.desc(), QuerySnapshotModel.id.desc())
        .offset(settings.query_snapshot_max_count)
    ).all()
    if surplus:
        db.execute(delete(QuerySnapshotModel).where(QuerySnapshotModel.id.in_(surplus)))


def salvar_snapshot_consulta(
    *,
    fingerprint: str,
    dados: list[dict[str, Any]],
    resultado: dict[str, Any],
) -> QuerySnapshot:
    """Grava o conjunto completo antes de a API emitir o cursor da primeira página."""

    if len(dados) > settings.query_snapshot_max_records:
        raise QuerySnapshotStorageError("A consulta excedeu o limite de registros navegáveis.")
    try:
        encoded = json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise QuerySnapshotStorageError("Não foi possível preparar a consulta para paginação.") from exc
    if len(encoded) > settings.query_snapshot_max_bytes:
        raise QuerySnapshotStorageError("A consulta excedeu o limite de tamanho navegável.")

    now = datetime.now(timezone.utc)
    record = QuerySnapshotModel(
        id=secrets.token_urlsafe(24),
        fingerprint=fingerprint,
        dados=dados,
        resultado=resultado,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.query_snapshot_ttl_seconds),
    )
    if settings.app_env.strip().lower() in {"test", "testing"}:
        snapshot = _as_snapshot(record)
        _TEST_SNAPSHOTS[snapshot.id] = snapshot
        return snapshot
    try:
        with SessionLocal() as db:
            _trim_snapshots(db)
            db.add(record)
            db.commit()
            db.refresh(record)
            return _as_snapshot(record)
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível gravar snapshot de consulta: %s", exc)
        raise QuerySnapshotStorageError("Não foi possível manter esta consulta para a próxima página.") from exc


def obter_snapshot_consulta(snapshot_id: str) -> QuerySnapshot | None:
    if settings.app_env.strip().lower() in {"test", "testing"}:
        snapshot = _TEST_SNAPSHOTS.get(snapshot_id)
        if snapshot is None or snapshot.expires_at <= datetime.now(timezone.utc):
            _TEST_SNAPSHOTS.pop(snapshot_id, None)
            return None
        return snapshot
    try:
        with SessionLocal() as db:
            record = db.get(QuerySnapshotModel, snapshot_id)
            if record is None:
                return None
            snapshot = _as_snapshot(record)
            if snapshot.expires_at <= datetime.now(timezone.utc):
                db.delete(record)
                db.commit()
                return None
            return snapshot
    except SQLAlchemyError as exc:
        logger.warning("Não foi possível ler snapshot de consulta: %s", exc)
        raise QuerySnapshotStorageError("Não foi possível recuperar a consulta anterior.") from exc
