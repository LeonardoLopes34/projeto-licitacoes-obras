"""Armazena snapshots normalizados de documentos retornados pelo PNCP."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0003_document_snapshots"
down_revision = "0002_analises_edital"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "document_snapshots" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "document_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contratacao_chave", sa.String(length=80), nullable=False),
        sa.Column("documentos_hash", sa.String(length=64), nullable=False),
        sa.Column("documentos", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "contratacao_chave",
            "documentos_hash",
            name="uq_document_snapshot_contract_hash",
        ),
    )
    op.create_index(
        "ix_document_snapshots_contratacao_chave",
        "document_snapshots",
        ["contratacao_chave"],
    )
    op.create_index(
        "ix_document_snapshots_documentos_hash",
        "document_snapshots",
        ["documentos_hash"],
    )


def downgrade() -> None:
    op.drop_table("document_snapshots")
