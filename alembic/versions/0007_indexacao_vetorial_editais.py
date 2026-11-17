"""Cria a persistência versionada da indexação vetorial de editais.

Revision ID: 0007_indexacao_vetorial_editais
Revises: 0006_tipo_contratacao
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from backend.models.vector_index_model import VectorEmbedding


revision = "0007_indexacao_vetorial_editais"
down_revision = "0006_tipo_contratacao"
branch_labels = None
depends_on = None


def _create_indexed_documents() -> None:
    op.create_table(
        "indexed_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contratacao_chave", sa.String(length=80), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("url_origem", sa.Text(), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("manifesto_hash", sa.String(length=64), nullable=False),
        sa.Column("versao_extracao", sa.String(length=80), nullable=False),
        sa.Column("versao_chunking", sa.String(length=80), nullable=False),
        sa.Column("modelo_embedding", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("erro_codigo", sa.String(length=80), nullable=True),
        sa.Column("erro_mensagem_segura", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contratacao_chave",
            "documento_id",
            "pdf_sha256",
            "versao_extracao",
            "versao_chunking",
            "modelo_embedding",
            name="uq_indexed_document_content_version",
        ),
    )
    for name, columns in {
        "ix_indexed_documents_contratacao_chave": ["contratacao_chave"],
        "ix_indexed_documents_documento_id": ["documento_id"],
        "ix_indexed_documents_uf": ["uf"],
        "ix_indexed_documents_pdf_sha256": ["pdf_sha256"],
        "ix_indexed_documents_source_hash": ["source_hash"],
        "ix_indexed_documents_manifesto_hash": ["manifesto_hash"],
        "ix_indexed_documents_status": ["status"],
        "ix_indexed_documents_ativo": ["ativo"],
    }.items():
        op.create_index(name, "indexed_documents", columns)


def _create_document_chunks() -> None:
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("indexed_document_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("pagina_inicio", sa.Integer(), nullable=False),
        sa.Column("pagina_fim", sa.Integer(), nullable=False),
        sa.Column("inicio_caractere", sa.Integer(), nullable=False),
        sa.Column("fim_caractere", sa.Integer(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("texto_hash", sa.String(length=64), nullable=False),
        sa.Column("origem_texto", sa.String(length=20), nullable=False),
        sa.Column("confianca_ocr", sa.Float(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("tamanho_caracteres", sa.Integer(), nullable=False),
        sa.Column("embedding", VectorEmbedding(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["indexed_document_id"], ["indexed_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("indexed_document_id", "ordem", "texto_hash", name="uq_document_chunk_order_hash"),
    )
    op.create_index("ix_document_chunks_indexed_document_id", "document_chunks", ["indexed_document_id"])
    op.create_index("ix_document_chunks_texto_hash", "document_chunks", ["texto_hash"])


def _create_jobs() -> None:
    op.create_table(
        "document_index_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contratacao_chave", sa.String(length=80), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("motivo", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column("limite_bytes", sa.Integer(), nullable=False),
        sa.Column("limite_paginas", sa.Integer(), nullable=False),
        sa.Column("limite_chunks", sa.Integer(), nullable=False),
        sa.Column("erro_codigo", sa.String(length=80), nullable=True),
        sa.Column("erro_mensagem_segura", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for name, columns in {
        "ix_document_index_jobs_contratacao_chave": ["contratacao_chave"],
        "ix_document_index_jobs_uf": ["uf"],
        "ix_document_index_jobs_status": ["status"],
        "ix_document_index_jobs_available_at": ["available_at"],
        "ix_document_index_jobs_lease_until": ["lease_until"],
    }.items():
        op.create_index(name, "document_index_jobs", columns)


def _create_requirement_analyses() -> None:
    op.create_table(
        "document_requirement_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contratacao_chave", sa.String(length=80), nullable=False),
        sa.Column("manifesto_hash", sa.String(length=64), nullable=False),
        sa.Column("fonte_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_hashes", sa.JSON(), nullable=False),
        sa.Column("modelo_embedding", sa.String(length=120), nullable=False),
        sa.Column("modelo_analise", sa.String(length=120), nullable=False),
        sa.Column("versao_prompt", sa.String(length=80), nullable=False),
        sa.Column("versao_schema", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("custo_estimado_usd", sa.Float(), nullable=False),
        sa.Column("latencia_ms", sa.Integer(), nullable=False),
        sa.Column("erro_codigo", sa.String(length=80), nullable=True),
        sa.Column("erro_mensagem_segura", sa.String(length=500), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contratacao_chave",
            "fonte_hash",
            "modelo_embedding",
            "modelo_analise",
            "versao_prompt",
            "versao_schema",
            name="uq_requirement_analysis_version",
        ),
    )
    for name, columns in {
        "ix_document_requirement_analyses_contratacao_chave": ["contratacao_chave"],
        "ix_document_requirement_analyses_manifesto_hash": ["manifesto_hash"],
        "ix_document_requirement_analyses_fonte_hash": ["fonte_hash"],
        "ix_document_requirement_analyses_status": ["status"],
        "ix_document_requirement_analyses_ativo": ["ativo"],
    }.items():
        op.create_index(name, "document_requirement_analyses", columns)


def _create_requirement_items() -> None:
    op.create_table(
        "document_requirement_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(length=80), nullable=False),
        sa.Column("nome_documento", sa.String(length=255), nullable=False),
        sa.Column("resumo", sa.String(length=600), nullable=False),
        sa.Column("documento_id", sa.Integer(), nullable=False),
        sa.Column("titulo_documento", sa.String(length=500), nullable=False),
        sa.Column("url_documento", sa.Text(), nullable=True),
        sa.Column("pagina", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("evidencia", sa.Text(), nullable=False),
        sa.Column("confianca", sa.Float(), nullable=False),
        sa.Column("estado", sa.String(length=40), nullable=False),
        sa.Column("origem_texto", sa.String(length=20), nullable=False),
        sa.Column("aceito_por_schema", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["document_requirement_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "categoria", "nome_documento", "chunk_id", name="uq_requirement_item_source"),
    )
    for name, columns in {
        "ix_document_requirement_items_analysis_id": ["analysis_id"],
        "ix_document_requirement_items_categoria": ["categoria"],
        "ix_document_requirement_items_documento_id": ["documento_id"],
    }.items():
        op.create_index(name, "document_requirement_items", columns)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    existing = set(inspect(bind).get_table_names())
    if "indexed_documents" not in existing:
        _create_indexed_documents()
    if "document_chunks" not in existing:
        _create_document_chunks()
    if "document_index_jobs" not in existing:
        _create_jobs()
    if "document_requirement_analyses" not in existing:
        _create_requirement_analyses()
    if "document_requirement_items" not in existing:
        _create_requirement_items()


def downgrade() -> None:
    existing = set(inspect(op.get_bind()).get_table_names())
    for table in (
        "document_requirement_items",
        "document_requirement_analyses",
        "document_index_jobs",
        "document_chunks",
        "indexed_documents",
    ):
        if table in existing:
            op.drop_table(table)
