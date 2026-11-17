"""Adiciona campos atômicos e composto do tipo de contratação."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0006_tipo_contratacao"
down_revision = "0005_query_snapshots"
branch_labels = None
depends_on = None


_ADDITIONS = {
    "criterio_julgamento": sa.Column("criterio_julgamento", sa.String(length=255), nullable=True),
    "tipo_instrumento": sa.Column("tipo_instrumento", sa.String(length=255), nullable=True),
    "tipo_contratacao": sa.Column("tipo_contratacao", sa.String(length=255), nullable=True),
    "tipo_contratacao_origem": sa.Column("tipo_contratacao_origem", sa.JSON(), nullable=True),
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "obras" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("obras")}
    for name, column in _ADDITIONS.items():
        if name not in existing:
            op.add_column("obras", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "obras" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("obras")}
    removable = [name for name in _ADDITIONS if name in existing]
    if not removable:
        return
    with op.batch_alter_table("obras", recreate="auto") as batch:
        for name in removable:
            batch.drop_column(name)
