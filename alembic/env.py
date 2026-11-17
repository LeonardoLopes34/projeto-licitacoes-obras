from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.config import settings
from backend.database import Base
from backend.models import (  # noqa: F401 - registra modelos
    DocumentSnapshotModel,
    DocumentChunkModel,
    DocumentIndexJobModel,
    DocumentRequirementAnalysisModel,
    DocumentRequirementItemModel,
    EditalAnalysisModel,
    IndexedDocumentModel,
    ObraModel,
    QuerySnapshotModel,
)


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option(
    "sqlalchemy.url",
    (settings.database_url or "sqlite:///./licitacoes_obras.db").replace("%", "%%"),
)
target_metadata = Base.metadata


def _compare_vector_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """pgvector pode ser refletido como tipo desconhecido sem o adaptador Python.

    A revisão é criada pela migração explícita e não deve fazer `alembic check`
    falhar apenas pela reflexão do tipo `vector` no PostgreSQL.
    """

    if (
        context.dialect.name == "postgresql"
        and inspected_column.table.name == "document_chunks"
        and inspected_column.name == "embedding"
    ):
        return False
    return None


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=_compare_vector_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=_compare_vector_type)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
