import logging
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from backend.config import settings


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = BASE_DIR / "licitacoes_obras.db"
logger = logging.getLogger(__name__)


def _database_url() -> str:
    configured = settings.database_url or os.getenv("DATABASE_URL")
    if not configured:
        return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
    if configured.startswith("sqlite:///./"):
        relative_path = configured.removeprefix("sqlite:///./")
        return f"sqlite:///{(BASE_DIR / relative_path).as_posix()}"
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql+psycopg2://", 1)
    if configured.startswith("postgresql+asyncpg://"):
        return configured.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return configured


DATABASE_URL = _database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency para obter sessão do banco de dados no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _schema_bootstrap_permitted() -> bool:
    return settings.app_env.strip().lower() in {"development", "dev", "test", "testing"}


def init_db() -> None:
    """Faz bootstrap de banco vazio e executa limpeza independente do PNCP."""
    from backend.models import EditalAnalysisModel, ObraModel  # noqa: F401 - registra modelos no metadata
    from backend.services.db_service import cleanup_expired_obras, delete_mock_obras

    if _schema_bootstrap_permitted():
        Base.metadata.create_all(bind=engine)
    else:
        required_tables = {"obras", "edital_analyses", "document_snapshots"}
        existing_tables = set(inspect(engine).get_table_names())
        missing_tables = required_tables - existing_tables
        if missing_tables:
            raise RuntimeError(
                "O banco de produção não possui as migrações necessárias. "
                "Execute 'alembic upgrade head' antes de iniciar a aplicação."
            )
    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    logger.info("Banco de dados inicializado via %s", safe_url)

    with SessionLocal() as db:
        delete_mock_obras(db)
        cleanup_expired_obras(db, max_age_days=settings.retention_days)
