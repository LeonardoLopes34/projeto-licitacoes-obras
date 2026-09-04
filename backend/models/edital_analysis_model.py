"""Persistência do resultado normalizado de análise, nunca do PDF bruto."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EditalAnalysisModel(Base):
    __tablename__ = "edital_analyses"
    __table_args__ = (
        UniqueConstraint(
            "contratacao_chave",
            "documentos_hash",
            "analisador_versao",
            name="uq_edital_analysis_document_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contratacao_chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    documentos_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    analisador_versao: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    resultado: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
