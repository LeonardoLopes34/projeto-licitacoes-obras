import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import FastAPI, Header, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.admin import admin_router, verificar_admin
from backend.config import settings
from backend.database import init_db
from backend.exceptions import PNCPConnectionError, PNCPResponseError
from backend.schemas import ResultadoBusca, ResultadoDocumentos, ResultadoExigencias
from backend.services.edital_analysis_service import EditalAnalysisService
from backend.services.ocr_service import verificar_disponibilidade_tesseract
from backend.services.pncp_service import (
    PNCP_MAX_PAGE_SIZE,
    PNCP_MIN_PAGE_SIZE,
    buscar_documentos_pncp,
    documentos_request_timeout_seconds,
    fechar_cliente_pncp,
    obter_metricas_pncp,
    search_licitacoes_construction,
)


logger = logging.getLogger(__name__)
edital_analysis_service = EditalAnalysisService()


def _default_date(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).strftime("%Y%m%d")


DEFAULT_INITIAL_DATE = _default_date(0)
DEFAULT_FINAL_DATE = _default_date(0)


def _request_date(value: str | None, field_name: str) -> str:
    # Chamadas normais do FastAPI recebem str; chamadas diretas em testes podem
    # preservar o objeto Query usado como default.
    requested = value if isinstance(value, str) and value else _default_date(0)
    try:
        datetime.strptime(requested, "%Y%m%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} deve ser uma data válida no formato AAAAMMDD") from exc
    return requested


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        yield
    finally:
        await fechar_cliente_pncp()


app = FastAPI(
    title="Engine de Captação de Obras - PNCP",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Key"],
)
app.include_router(admin_router)


@app.get("/")
def home():
    return {"status": "online", "database": "configured", "environment": settings.app_env}


@app.get("/health")
def health():
    """Expõe um estado operacional seguro, incluindo a disponibilidade do OCR."""
    ocr = verificar_disponibilidade_tesseract()
    return {
        "status": "online" if ocr.disponivel else "degradado",
        "database": "configured",
        "environment": settings.app_env,
        "ocr": {
            "status": ocr.status,
            "idioma": ocr.idioma,
            "versao": ocr.versao,
            "erro": ocr.erro,
        },
    }


@app.get("/admin/operations/metrics")
def operations_metrics(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """Métricas administrativas sem expor resultados, PDFs ou URLs externas."""
    verificar_admin(x_admin_key)
    ocr = verificar_disponibilidade_tesseract()
    return {
        "pncp": obter_metricas_pncp(),
        "analises_edital": dict(edital_analysis_service.metrics),
        "ocr": {"status": ocr.status, "idioma": ocr.idioma, "versao": ocr.versao},
    }


@app.get("/api/v1/obras", response_model=ResultadoBusca)
async def list_jobs(
    inicial_date: str | None = Query(None, pattern=r"^\d{8}$"),
    final_date: str | None = Query(None, pattern=r"^\d{8}$"),
    modalidade: int = Query(0, ge=0, description="4: Concorrência, 6: Pregão, 8: Dispensa, 0: Todas"),
    max_paginas: int = Query(settings.pncp_max_paginas, ge=1, le=100, description="Limite de páginas por modalidade"),
    tamanho_pagina: int = Query(
        50,
        ge=PNCP_MIN_PAGE_SIZE,
        le=PNCP_MAX_PAGE_SIZE,
        description="Quantidade de registros por página aceitos pelo PNCP: 10 a 50",
    ),
    uf: str | None = Query(None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    cursor: str | None = Query(None, min_length=1, max_length=512, description="Cursor opaco da próxima página"),
    tamanho_resultado: int = Query(15, ge=1, le=15, description="Máximo de licitações retornadas por página"),
):
    inicial_date = _request_date(inicial_date, "inicial_date")
    final_date = _request_date(final_date, "final_date")
    try:
        request_timeout = max(
            30.0,
            settings.pncp_timeout_seconds
            * max_paginas
            * (3 if modalidade == 0 else 1),
        )
        return await asyncio.wait_for(
            search_licitacoes_construction(
                data_inicial=inicial_date,
                data_final=final_date,
                modalidade=modalidade,
                max_paginas=max_paginas,
                tamanho_pagina=tamanho_pagina,
                uf=uf.upper() if uf else None,
                cursor=cursor,
                tamanho_resultado=tamanho_resultado,
            ),
            timeout=request_timeout,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        logger.error("Busca PNCP excedeu o timeout global")
        raise HTTPException(status_code=504, detail="A consulta ao PNCP excedeu o tempo limite") from exc


@app.get(
    "/api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos",
    response_model=ResultadoDocumentos,
)
async def list_documents(
    cnpj: str = Path(..., min_length=14, max_length=14, pattern=r"^[A-Za-z0-9]{14}$"),
    ano: int = Path(..., ge=1),
    sequencial: int = Path(..., ge=1),
):
    try:
        return await asyncio.wait_for(
            buscar_documentos_pncp(cnpj, ano, sequencial),
            timeout=documentos_request_timeout_seconds(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        logger.warning("Consulta de documentos excedeu o timeout global")
        raise HTTPException(status_code=503, detail="Não foi possível carregar os documentos do PNCP agora") from exc
    except PNCPConnectionError as exc:
        logger.warning("Falha de conexão ao consultar documentos do PNCP: %s", exc)
        raise HTTPException(status_code=503, detail="Não foi possível carregar os documentos do PNCP agora") from exc
    except PNCPResponseError as exc:
        logger.warning("Resposta inválida do PNCP ao consultar documentos: %s", exc)
        raise HTTPException(status_code=502, detail="O PNCP retornou uma resposta inválida para os documentos") from exc


@app.get(
    "/api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias",
    response_model=ResultadoExigencias,
)
async def list_exigencias(
    cnpj: str = Path(..., min_length=14, max_length=14, pattern=r"^[A-Za-z0-9]{14}$"),
    ano: int = Path(..., ge=1),
    sequencial: int = Path(..., ge=1),
    forcar: bool = Query(False, description="Ignora o cache compatível e refaz a análise"),
):
    """Analisa habilitação sob demanda, sem afetar a listagem de obras."""
    try:
        return await asyncio.wait_for(
            edital_analysis_service.analisar_contratacao(cnpj, ano, sequencial, forcar=forcar),
            timeout=settings.edital_analysis_timeout_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        logger.warning("Análise de exigências excedeu o timeout global")
        raise HTTPException(
            status_code=503,
            detail="A análise dos documentos excedeu o tempo limite; tente novamente.",
        ) from exc
    except PNCPConnectionError as exc:
        logger.warning("Falha de conexão ao iniciar análise de exigências: %s", exc)
        raise HTTPException(status_code=503, detail="Não foi possível carregar os documentos do PNCP agora") from exc
    except PNCPResponseError as exc:
        logger.warning("Resposta inválida do PNCP ao iniciar análise de exigências: %s", exc)
        raise HTTPException(status_code=502, detail="O PNCP retornou uma resposta inválida para os documentos") from exc
