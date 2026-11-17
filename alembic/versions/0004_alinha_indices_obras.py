"""Alinha índices e nulabilidade de obras ao modelo SQLAlchemy atual."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0004_alinha_indices_obras"
down_revision = "0003_document_snapshots"
branch_labels = None
depends_on = None


_INDEXES = {
    "ix_obras_ano": ["ano"],
    "ix_obras_cnpj": ["cnpj"],
    "ix_obras_created_at": ["created_at"],
    "ix_obras_data_publicacao": ["data_publicacao"],
    "ix_obras_modalidade_codigo": ["modalidade_codigo"],
    "ix_obras_numero_controle_pncp": ["numero_controle_pncp"],
    "ix_obras_status_classificacao": ["status_classificacao"],
    "ix_obras_uf": ["uf"],
    "ix_obras_valor_estimado": ["valor_estimado"],
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"]: column for column in inspector.get_columns("obras")}

    # Registros legados sem data recebem apenas o instante da migração. Valores
    # existentes são preservados; não se executa retenção nem remoção de linhas.
    if columns.get("created_at", {}).get("nullable", False):
        op.execute(sa.text("UPDATE obras SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        with op.batch_alter_table("obras", recreate="auto") as batch:
            batch.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
            )

    existing = {index["name"] for index in inspect(bind).get_indexes("obras")}
    for name, columns_for_index in _INDEXES.items():
        if name not in existing:
            op.create_index(name, "obras", columns_for_index)


def downgrade() -> None:
    bind = op.get_bind()
    existing = {index["name"] for index in inspect(bind).get_indexes("obras")}
    for name in _INDEXES:
        if name in existing:
            op.drop_index(name, table_name="obras")
    with op.batch_alter_table("obras", recreate="auto") as batch:
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
