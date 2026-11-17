"""Snapshot temporário e imutável de uma consulta de obras."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuerySnapshotModel(Base):
    """Conjunto normalizado usado pelas páginas seguintes de uma consulta."""

    __tablename__ = "query_snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dados: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    resultado: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
