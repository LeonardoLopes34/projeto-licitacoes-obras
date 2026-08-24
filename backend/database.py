import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# URL do Banco de Dados: SQLite local por padrao (apontando de forma absoluta para a raiz do projeto)
DEFAULT_SQLITE_PATH = BASE_DIR / "licitacoes_obras.db"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
elif DATABASE_URL.startswith("sqlite:///."):
    rel_path = DATABASE_URL.replace("sqlite:///./", "").replace("sqlite:///", "")
    DATABASE_URL = f"sqlite:///{(BASE_DIR / rel_path).as_posix()}"
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)

# Configuracoes de conexao especificas para SQLite vs PostgreSQL
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """Dependency para obter sessao do banco de dados no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Inicializa as tabelas do banco de dados e remove eventuais dados de mock."""
    Base.metadata.create_all(bind=engine)
    print(f"[DATABASE] Banco de dados inicializado com sucesso via: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    
    # Limpeza preventiva de dados mock/teste salvos no banco
    try:
        from backend.services.db_service import delete_mock_obras
        with SessionLocal() as db:
            delete_mock_obras(db)
    except Exception as e:
        print(f"[DATABASE WARNING] Falha ao expurgar mocks no init_db: {e}")
