# Design — Spec 007: Modelo de Dados e Persistência

## Modelo (SQLAlchemy)

```python
from decimal import Decimal
from datetime import datetime
from enum import IntEnum
from sqlalchemy import String, Numeric, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

class Modalidade(IntEnum):
    PREGAO = 0
    CONCORRENCIA = 4
    DISPENSA = 6
    # ... completar com os valores válidos reais do domínio PNCP

class Obra(Base):
    __tablename__ = "obras"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero_controle_pncp: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    cnpj: Mapped[str] = mapped_column(String(20))  # alfanumérico a partir de jul/2026 — nunca int
    ano: Mapped[int]
    sequencial: Mapped[int]
    modalidade: Mapped[Modalidade] = mapped_column(SAEnum(Modalidade))
    data_publicacao: Mapped[datetime] = mapped_column(DateTime)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payload_original: Mapped[dict] = mapped_column(JSON)  # preserva o retorno bruto da API
```

## Alembic

```bash
pip install alembic
alembic init alembic
# alembic/env.py: apontar target_metadata para Base.metadata
alembic revision --autogenerate -m "captura schema atual"
alembic upgrade head
```
Toda alteração futura de schema passa a ser uma nova revisão Alembic — `Base.metadata.create_all()` deixa de ser usado para atualizar schema existente (pode continuar sendo usado apenas para criar banco novo em ambiente de teste/dev vazio).

## Limpeza de registros antigos desacoplada

```python
# database.py
def limpar_registros_antigos(dias: int = 90):
    limite = datetime.utcnow() - timedelta(days=dias)
    with SessionLocal() as session:
        session.query(Obra).filter(Obra.data_publicacao < limite).delete()
        session.commit()
```
Chamada a partir do `lifespan` do FastAPI (startup) ou de um scheduler dedicado — nunca condicionada ao sucesso da última busca ao PNCP.

## Upsert em lote (SQLite)

```python
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

def upsert_obras(session, obras: list[dict]):
    stmt = sqlite_insert(Obra).values(obras)
    stmt = stmt.on_conflict_do_update(
        index_elements=["numero_controle_pncp"],
        set_={c: stmt.excluded[c] for c in ("valor", "modalidade", "payload_original")},
    )
    session.execute(stmt)
    session.commit()
```

## Cache com TTL

```python
from cachetools import TTLCache

_cache = TTLCache(maxsize=256, ttl=300)  # 5 minutos, no máximo 256 entradas
```
Se Redis estiver disponível na infraestrutura, preferir Redis (`redis-py` + `expire`) para cache compartilhado entre processos; `cachetools.TTLCache` é a solução intermediária local aceitável para este escopo.

## Auditoria de dependências

```bash
pip install pip-autoremove  # ou revisão manual
grep -rl "^import requests\|^from requests" backend/ || echo "requests não usado"
# repetir para pdfplumber, pypdf, asyncpg, apscheduler
```
Remover do `requirements.txt` tudo que não aparece em nenhum `import` real.
