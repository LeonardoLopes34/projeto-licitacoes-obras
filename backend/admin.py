import secrets

from fastapi import APIRouter, Header, HTTPException, Query

from backend.config import settings
from backend.database import SessionLocal
from backend.services.db_service import cleanup_expired_obras, get_db_stats


def verificar_admin(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    if not settings.admin_api_key or not x_admin_key:
        raise HTTPException(status_code=401, detail="Credencial administrativa inválida")
    if not secrets.compare_digest(x_admin_key, settings.admin_api_key):
        raise HTTPException(status_code=401, detail="Credencial administrativa inválida")


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/database/stats", dependencies=[])
def database_stats(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    verificar_admin(x_admin_key)
    with SessionLocal() as db:
        return get_db_stats(db)


@admin_router.post("/database/cleanup")
def database_cleanup(
    days: int = Query(2, ge=1, le=365),
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
):
    verificar_admin(x_admin_key)
    with SessionLocal() as db:
        excluded = cleanup_expired_obras(db, max_age_days=days)
    return {
        "status": "sucesso",
        "obras_excluidas": excluded,
        "dias_retencao": days,
    }
