"""Adiciona snapshots temporários para paginação estável de consultas."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0005_query_snapshots"
down_revision = "0004_alinha_indices_obras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "query_snapshots" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "query_snapshots",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("resultado", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_query_snapshots_fingerprint", "query_snapshots", ["fingerprint"])
    op.create_index("ix_query_snapshots_expires_at", "query_snapshots", ["expires_at"])


def downgrade() -> None:
    if "query_snapshots" in inspect(op.get_bind()).get_table_names():
        op.drop_table("query_snapshots")
