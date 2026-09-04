from datetime import datetime, timezone
from decimal import Decimal
from enum import IntEnum
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Modalidade(IntEnum):
    """Códigos usados pelo domínio de consulta do PNCP neste produto."""

    CONCORRENCIA = 4
    PREGAO = 6
    DISPENSA = 8


VALID_MODALIDADES = {0, *(int(item) for item in Modalidade)}


def validar_modalidade(value: Any, *, permitir_todas: bool = True) -> int:
    try:
        code = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Modalidade deve ser um código inteiro válido") from exc
    if code not in VALID_MODALIDADES or (code == 0 and not permitir_todas):
        raise ValueError(f"Modalidade inválida: {value}")
    return code


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ObraModel(Base):
    __tablename__ = "obras"

    id_pncp: Mapped[str] = mapped_column(String(120), primary_key=True)
    numero_controle_pncp: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    ano: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sequencial: Mapped[int | None] = mapped_column(Integer, nullable=True)

    orgao: Mapped[str] = mapped_column(String(255), nullable=False)
    municipio: Mapped[str | None] = mapped_column(String(150), nullable=True)
    uf: Mapped[str] = mapped_column(String(2), nullable=False, index=True)

    objeto: Mapped[str] = mapped_column(Text, nullable=False)
    valor_estimado: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True, index=True)
    data_publicacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    modalidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modalidade_codigo: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    link_pncp: Mapped[str | None] = mapped_column(Text, nullable=True)
    fonte: Mapped[str] = mapped_column(String(50), default="PNCP_REAL", nullable=False)

    status_classificacao: Mapped[str] = mapped_column(String(30), default="aprovado", nullable=False, index=True)
    score_classificacao: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_original: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

    def to_dict(self, *, include_payload: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id_pncp": self.id_pncp,
            "numero_controle_pncp": self.numero_controle_pncp,
            "cnpj": self.cnpj,
            "ano": self.ano,
            "sequencial": self.sequencial,
            "orgao": self.orgao,
            "municipio": self.municipio,
            "uf": self.uf,
            "objeto": self.objeto,
            "valor_estimado": self.valor_estimado,
            "data_publicacao": self.data_publicacao.isoformat() if self.data_publicacao else None,
            "modalidade": self.modalidade,
            "modalidade_codigo": self.modalidade_codigo,
            "link_pncp": self.link_pncp,
            "fonte": self.fonte,
            "status_classificacao": self.status_classificacao,
            "score_classificacao": self.score_classificacao,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_payload:
            result["payload_original"] = self.payload_original
        return result
