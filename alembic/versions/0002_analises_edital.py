"""Armazena resultados normalizados da análise de editais."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0002_analises_edital"
down_revision = "0001_modelo_obras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "edital_analyses" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "edital_analyses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("contratacao_chave", sa.String(length=80), nullable=False),
        sa.Column("documentos_hash", sa.String(length=64), nullable=False),
        sa.Column("analisador_versao", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "contratacao_chave",
            "documentos_hash",
            "analisador_versao",
            name="uq_edital_analysis_document_version",
        ),
    )
    op.create_index("ix_edital_analyses_contratacao_chave", "edital_analyses", ["contratacao_chave"])
    op.create_index("ix_edital_analyses_documentos_hash", "edital_analyses", ["documentos_hash"])
    op.create_index("ix_edital_analyses_analisador_versao", "edital_analyses", ["analisador_versao"])


def downgrade() -> None:
    op.drop_table("edital_analyses")
