"""Modelo inicial e campos de rastreabilidade PNCP."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0001_modelo_obras"
down_revision = None
branch_labels = None
depends_on = None


def _create_table() -> None:
    op.create_table(
        "obras",
        sa.Column("id_pncp", sa.String(length=120), nullable=False),
        sa.Column("numero_controle_pncp", sa.String(length=120), nullable=True),
        sa.Column("cnpj", sa.String(length=20), nullable=True),
        sa.Column("ano", sa.Integer(), nullable=True),
        sa.Column("sequencial", sa.Integer(), nullable=True),
        sa.Column("orgao", sa.String(length=255), nullable=False),
        sa.Column("municipio", sa.String(length=150), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("objeto", sa.Text(), nullable=False),
        sa.Column("valor_estimado", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("data_publicacao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("modalidade", sa.String(length=100), nullable=True),
        sa.Column("modalidade_codigo", sa.Integer(), nullable=True),
        sa.Column("link_pncp", sa.Text(), nullable=True),
        sa.Column("fonte", sa.String(length=50), nullable=False, server_default="PNCP_REAL"),
        sa.Column("status_classificacao", sa.String(length=30), nullable=False, server_default="aprovado"),
        sa.Column("score_classificacao", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload_original", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id_pncp"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "obras" not in inspector.get_table_names():
        _create_table()
        return

    existing = {column["name"] for column in inspector.get_columns("obras")}
    additions = {
        "cnpj": sa.Column("cnpj", sa.String(length=20), nullable=True),
        "ano": sa.Column("ano", sa.Integer(), nullable=True),
        "sequencial": sa.Column("sequencial", sa.Integer(), nullable=True),
        "modalidade_codigo": sa.Column("modalidade_codigo", sa.Integer(), nullable=True),
        "status_classificacao": sa.Column("status_classificacao", sa.String(length=30), nullable=False, server_default="aprovado"),
        "score_classificacao": sa.Column("score_classificacao", sa.Integer(), nullable=False, server_default="0"),
        "payload_original": sa.Column("payload_original", sa.JSON(), nullable=True),
    }
    for name, column in additions.items():
        if name not in existing:
            op.add_column("obras", column)

    with op.batch_alter_table("obras", recreate="auto") as batch:
        if "valor_estimado" in existing:
            batch.alter_column("valor_estimado", type_=sa.Numeric(precision=18, scale=4))
        if "data_publicacao" in existing:
            batch.alter_column("data_publicacao", type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    op.drop_table("obras")
