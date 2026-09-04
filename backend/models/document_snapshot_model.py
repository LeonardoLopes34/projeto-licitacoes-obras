"""Snapshot normalizado dos documentos publicados por uma contratação."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DocumentSnapshotModel(Base):
    """Mantém o último conteúdo conhecido de cada versão da lista do PNCP.

    O hash permite atualizar o timestamp de uma lista já vista sem duplicá-la,
    ao mesmo tempo em que preserva versões anteriores quando a publicação muda.
    PDFs brutos nunca são persistidos aqui.
    """

    __tablename__ = "document_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "contratacao_chave",
            "documentos_hash",
            name="uq_document_snapshot_contract_hash",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contratacao_chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    documentos_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    documentos: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
