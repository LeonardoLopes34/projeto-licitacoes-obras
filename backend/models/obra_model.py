from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class ObraModel(Base):
    __tablename__ = "obras"

    # Chave primária única: ID ou número de controle do PNCP
    id_pncp: Mapped[str] = mapped_column(String(120), primary_key=True, index=True)
    numero_controle_pncp: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    
    # Dados da entidade e localização
    orgao: Mapped[str] = mapped_column(String(255), nullable=False)
    municipio: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    uf: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    
    # Dados técnicos da licitação
    objeto: Mapped[str] = mapped_column(Text, nullable=False)
    valor_estimado: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    data_publicacao: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    modalidade: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    link_pncp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fonte: Mapped[str] = mapped_column(String(50), default="PNCP_REAL")
    
    # Data de captura no sistema - Usada para o expurgo automático de 2 dias (48 horas)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    def to_dict(self):
        return {
            "id_pncp": self.id_pncp,
            "numero_controle_pncp": self.numero_controle_pncp,
            "orgao": self.orgao,
            "municipio": self.municipio,
            "uf": self.uf,
            "objeto": self.objeto,
            "valor_estimado": self.valor_estimado,
            "data_publicacao": self.data_publicacao,
            "modalidade": self.modalidade,
            "link_pncp": self.link_pncp,
            "fonte": self.fonte,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
