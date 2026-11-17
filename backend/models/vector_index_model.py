"""Modelos persistentes da indexação vetorial e análise assistida (Spec 015)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, UserDefinedType

from backend.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _PostgresVector(UserDefinedType):
    """Tipo pgvector sem acoplar o runtime ao pacote Python pgvector."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_kw: Any) -> str:
        return f"VECTOR({self.dimensions})"


class VectorEmbedding(TypeDecorator[list[float] | None]):
    """Armazena vetores como pgvector no PostgreSQL e texto inerte no SQLite.

    A feature é bloqueada pela configuração em SQLite; o fallback de tipo existe
    somente para manter migrações e testes do núcleo compatíveis com esse banco.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1536) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PostgresVector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | str | None, dialect):  # type: ignore[no-untyped-def]
        if value is None or isinstance(value, str):
            return value
        if len(value) != self.dimensions:
            raise ValueError(f"O embedding precisa ter {self.dimensions} dimensões")
        if not all(math.isfinite(float(item)) for item in value):
            raise ValueError("O embedding contém valor não finito")
        return "[" + ",".join(format(float(item), ".10g") for item in value) + "]"

    def process_result_value(self, value: str | list[float] | None, dialect):  # type: ignore[no-untyped-def]
        if value is None or isinstance(value, list):
            return value
        raw = str(value).strip().strip("[]")
        return [float(item) for item in raw.split(",") if item.strip()] if raw else []


class IndexedDocumentModel(Base):
    __tablename__ = "indexed_documents"
    __table_args__ = (
        UniqueConstraint(
            "contratacao_chave",
            "documento_id",
            "pdf_sha256",
            "versao_extracao",
            "versao_chunking",
            "modelo_embedding",
            name="uq_indexed_document_content_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contratacao_chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    documento_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(500), nullable=False)
    url_origem: Mapped[str | None] = mapped_column(Text, nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Agrupa todos os PDFs internos de uma mesma origem (inclusive ZIP). Só a
    # troca completa desse conjunto pode substituir a versão ativa anterior.
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    manifesto_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    versao_extracao: Mapped[str] = mapped_column(String(80), nullable=False)
    versao_chunking: Mapped[str] = mapped_column(String(80), nullable=False)
    modelo_embedding: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pendente", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem_segura: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("indexed_document_id", "ordem", "texto_hash", name="uq_document_chunk_order_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    indexed_document_id: Mapped[int] = mapped_column(
        ForeignKey("indexed_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    pagina_fim: Mapped[int] = mapped_column(Integer, nullable=False)
    inicio_caractere: Mapped[int] = mapped_column(Integer, nullable=False)
    fim_caractere: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    texto_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    origem_texto: Mapped[str] = mapped_column(String(20), nullable=False)
    confianca_ocr: Mapped[float | None] = mapped_column(nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tamanho_caracteres: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(VectorEmbedding(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class DocumentIndexJobModel(Base):
    __tablename__ = "document_index_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contratacao_chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    motivo: Mapped[str] = mapped_column(String(80), nullable=False, default="abertura_contratacao")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pendente", index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    limite_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_paginas: Mapped[int] = mapped_column(Integer, nullable=False)
    limite_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem_segura: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentRequirementAnalysisModel(Base):
    __tablename__ = "document_requirement_analyses"
    __table_args__ = (
        UniqueConstraint(
            "contratacao_chave",
            "fonte_hash",
            "modelo_embedding",
            "modelo_analise",
            "versao_prompt",
            "versao_schema",
            name="uq_requirement_analysis_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contratacao_chave: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    manifesto_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fonte_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    modelo_embedding: Mapped[str] = mapped_column(String(120), nullable=False)
    modelo_analise: Mapped[str] = mapped_column(String(120), nullable=False)
    versao_prompt: Mapped[str] = mapped_column(String(80), nullable=False)
    versao_schema: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custo_estimado_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    latencia_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erro_codigo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    erro_mensagem_segura: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentRequirementItemModel(Base):
    __tablename__ = "document_requirement_items"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "categoria", "nome_documento", "chunk_id", name="uq_requirement_item_source"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("document_requirement_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    categoria: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    nome_documento: Mapped[str] = mapped_column(String(255), nullable=False)
    resumo: Mapped[str] = mapped_column(String(600), nullable=False)
    documento_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    titulo_documento: Mapped[str] = mapped_column(String(500), nullable=False)
    url_documento: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagina: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True)
    evidencia: Mapped[str] = mapped_column(Text, nullable=False)
    confianca: Mapped[float] = mapped_column(nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False)
    origem_texto: Mapped[str] = mapped_column(String(20), nullable=False)
    aceito_por_schema: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
