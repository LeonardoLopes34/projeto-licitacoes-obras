import logging
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.exceptions import DatabaseServiceError
from backend.models.obra_model import ObraModel, validar_modalidade


logger = logging.getLogger(__name__)
MOCK_ID_PREFIXES = ("TEST-", "VAL-", "MOCK-", "DEV-")
KNOWN_MOCK_IDS = {
    "94309291000148-1-000130/2026",
    "88309291000199-1-000045/2026",
    "77104212000188-1-000512/2026",
    "00509018000113-1-001422/2026",
    "82804212000196-1-000214/2026",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def is_mock_item(item: dict[str, Any]) -> bool:
    id_pncp = str(item.get("id_pncp") or item.get("numero_controle_pncp") or "").strip()
    fonte = str(item.get("fonte") or "").upper()
    orgao = str(item.get("orgao") or "").upper()
    return (
        any(id_pncp.startswith(prefix) for prefix in MOCK_ID_PREFIXES)
        or id_pncp in KNOWN_MOCK_IDS
        or any(marker in fonte for marker in ("MOCK", "TEST", "SANDBOX"))
        or "PREFEITURA TESTE" in orgao
        or "MOCK" in orgao
    )


def _real_records_clause():
    return (
        ~ObraModel.id_pncp.like("TEST%"),
        ~ObraModel.id_pncp.like("VAL%"),
        ~ObraModel.id_pncp.like("MOCK%"),
        ~ObraModel.id_pncp.like("DEV%"),
        ~ObraModel.id_pncp.like("%MOCK%"),
        ~ObraModel.fonte.ilike("%MOCK%"),
        ~ObraModel.fonte.ilike("%TEST%"),
        ~ObraModel.fonte.ilike("%SANDBOX%"),
        ~ObraModel.id_pncp.in_(KNOWN_MOCK_IDS),
    )


def delete_mock_obras(db: Session) -> int:
    # A forma explícita mantém compatibilidade com SQLite e PostgreSQL.
    stmt = delete(ObraModel).where(
        (ObraModel.id_pncp.like("TEST%"))
        | (ObraModel.id_pncp.like("VAL%"))
        | (ObraModel.id_pncp.like("MOCK%"))
        | (ObraModel.id_pncp.like("DEV%"))
        | (ObraModel.id_pncp.like("%MOCK%"))
        | (ObraModel.fonte.ilike("%MOCK%"))
        | (ObraModel.fonte.ilike("%TEST%"))
        | (ObraModel.fonte.ilike("%SANDBOX%"))
        | (ObraModel.id_pncp.in_(KNOWN_MOCK_IDS))
    )
    try:
        result = db.execute(stmt)
        db.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info("Removidos %s registros mock/teste", deleted)
        return deleted
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseServiceError("Falha ao remover registros de teste") from exc


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        raise ValueError("data_publicacao ausente")
    if len(text) == 8 and text.isdigit():
        parsed = datetime.strptime(text, "%Y%m%d")
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"valor_estimado inválido: {value}") from exc


def _parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"valor inteiro inválido: {value}") from exc


def _row_from_item(item: dict[str, Any]) -> dict[str, Any]:
    id_pncp = str(item.get("id_pncp") or item.get("numero_controle_pncp") or "").strip()
    if not id_pncp:
        raise ValueError("registro PNCP sem identificador")

    modalidade_codigo = item.get("modalidade_codigo")
    if modalidade_codigo is not None:
        modalidade_codigo = validar_modalidade(modalidade_codigo, permitir_todas=False)

    data_publicacao = _parse_datetime(item.get("data_publicacao"))
    numero_controle = item.get("numero_controle_pncp") or item.get("id_pncp")
    payload = item.get("payload_original") or item.get("_raw")

    return {
        "id_pncp": id_pncp,
        "numero_controle_pncp": str(numero_controle) if numero_controle else None,
        "cnpj": str(item.get("cnpj")) if item.get("cnpj") else None,
        "ano": _parse_int(item.get("ano")),
        "sequencial": _parse_int(item.get("sequencial")),
        "orgao": str(item.get("orgao") or "Não informado"),
        "municipio": item.get("municipio"),
        "uf": str(item.get("uf") or "BR").upper().strip(),
        "objeto": str(item.get("objeto") or ""),
        "valor_estimado": _parse_decimal(item.get("valor_estimado")),
        "data_publicacao": data_publicacao,
        "modalidade": item.get("modalidade"),
        "modalidade_codigo": modalidade_codigo,
        "link_pncp": item.get("link_pncp"),
        "fonte": "PNCP_REAL",
        "status_classificacao": item.get("status_classificacao") or "aprovado",
        "score_classificacao": int(item.get("score_classificacao") or 0),
        "payload_original": payload,
        "created_at": utc_now(),
    }


def upsert_obras(db: Session, obras: list[dict[str, Any]]) -> int:
    """Persiste registros válidos em uma única operação de upsert."""
    rows = []
    for item in obras:
        if is_mock_item(item):
            continue
        rows.append(_row_from_item(item))
    if not rows:
        return 0

    try:
        if db.bind is not None and db.bind.dialect.name == "sqlite":
            stmt = sqlite_insert(ObraModel).values(rows)
            update_columns = {
                column: getattr(stmt.excluded, column)
                for column in rows[0]
                if column != "id_pncp"
            }
            db.execute(stmt.on_conflict_do_update(index_elements=["id_pncp"], set_=update_columns))
        else:
            # Fallback compatível com PostgreSQL; o caminho SQLite é batch.
            for row in rows:
                db.merge(ObraModel(**row))
        db.commit()
        return len(rows)
    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        if isinstance(exc, ValueError):
            raise
        raise DatabaseServiceError("Falha ao fazer upsert das obras") from exc


def save_obras_batch(db: Session, obras: list[dict[str, Any]]) -> int:
    """Compatibilidade com o nome antigo do serviço."""
    return upsert_obras(db, obras)


def cleanup_expired_obras(db: Session, max_age_days: int = 2) -> int:
    cutoff_date = utc_now() - timedelta(days=max_age_days)
    try:
        result = db.execute(delete(ObraModel).where(ObraModel.created_at < cutoff_date))
        db.commit()
        deleted = result.rowcount or 0
        if deleted:
            logger.info("Excluídas %s obras expiradas", deleted)
        return deleted
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseServiceError("Falha na limpeza de retenção") from exc


def _boundary(value: str | None, end: bool = False) -> datetime | None:
    if not value:
        return None
    parsed = datetime.strptime(value, "%Y%m%d").date()
    return datetime.combine(parsed, time.max if end else time.min, tzinfo=timezone.utc)


def get_obras_from_db(
    db: Session,
    uf: str | None = None,
    modalidade: Any = None,
    data_inicial: str | None = None,
    data_final: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    clauses = list(_real_records_clause())
    if uf and uf.upper() != "TODOS":
        clauses.append(ObraModel.uf == uf.upper().strip())
    if modalidade not in (None, "", 0, "0"):
        code = validar_modalidade(modalidade, permitir_todas=False)
        clauses.append(ObraModel.modalidade_codigo == code)
    start = _boundary(data_inicial)
    end = _boundary(data_final, end=True)
    if start:
        clauses.append(ObraModel.data_publicacao >= start)
    if end:
        clauses.append(ObraModel.data_publicacao <= end)

    stmt = (
        select(ObraModel)
        .where(*clauses)
        .order_by(ObraModel.data_publicacao.desc(), ObraModel.created_at.desc())
        .limit(max(1, min(limit, 1000)))
    )
    try:
        return [record.to_dict() for record in db.scalars(stmt).all()]
    except SQLAlchemyError as exc:
        raise DatabaseServiceError("Falha ao consultar obras locais") from exc


def get_db_stats(db: Session) -> dict[str, Any]:
    clauses = list(_real_records_clause())
    try:
        total = db.scalar(select(func.count()).select_from(ObraModel).where(*clauses)) or 0
        oldest = db.scalar(select(func.min(ObraModel.created_at)).where(*clauses))
        newest = db.scalar(select(func.max(ObraModel.created_at)).where(*clauses))
        return {
            "total_obras_armazenadas": total,
            "registro_mais_antigo": oldest.isoformat() if oldest else None,
            "registro_mais_recente": newest.isoformat() if newest else None,
            "politica_retencao": "Exclusão automática conforme RETENTION_DAYS",
        }
    except SQLAlchemyError as exc:
        raise DatabaseServiceError("Falha ao consultar estatísticas do banco") from exc
