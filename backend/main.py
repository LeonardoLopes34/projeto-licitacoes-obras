import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.admin import admin_router, verificar_admin, verificar_api_key
from backend.config import settings
from backend.database import init_db
from backend.exceptions import PNCPConnectionError, PNCPResponseError
from backend.schemas import ResultadoBusca, ResultadoDocumentos, ResultadoExigencias, TipoContratacaoOut
from backend.services.edital_analysis_service import AnalysisCapacityError, EditalAnalysisService
from backend.services.ocr_service import verificar_disponibilidade_tesseract
from backend.services.pncp_service import (
    PNCP_MAX_PAGE_SIZE,
    PNCP_MIN_PAGE_SIZE,
    PaginationCursorError,
    PaginationSnapshotExpiredError,
    buscar_documentos_pncp,
    buscar_tipo_contratacao_pncp,
    documentos_request_timeout_seconds,
    fechar_cliente_pncp,
    obter_metricas_pncp,
    search_request_timeout_seconds,
    search_licitacoes_construction,
    stream_licitacoes_construction,
)
from backend.services.query_snapshot_repository import QuerySnapshotStorageError
from backend.services.vector_index_repository import get_completed_requirement_result, get_requirement_analysis_status
from backend.services.vector_indexing_service import VectorIndexingService


logger = logging.getLogger(__name__)
edital_analysis_service = EditalAnalysisService()
vector_indexing_service = VectorIndexingService()


def _ocr_status() -> tuple[bool, dict[str, str | None]]:
    """Retorna o estado público do OCR sem tratar desativação intencional como falha."""

    if not settings.edital_ocr_enabled:
        return True, {
            "status": "desativado",
            "idioma": settings.edital_ocr_language,
            "versao": None,
            "erro": None,
        }
    ocr = verificar_disponibilidade_tesseract()
    return ocr.disponivel, {
        "status": ocr.status,
        "idioma": ocr.idioma,
        "versao": ocr.versao,
        "erro": ocr.erro,
    }


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
    # Jobs sobrevivem a reinícios pelo banco; a recuperação só roda quando a
    # feature foi explicitamente ativada e validada na configuração.
    await vector_indexing_service.start_available_jobs()
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
    allow_headers=["Content-Type", "X-Admin-Key", "X-API-Key"],
)
app.include_router(admin_router)


@app.get("/")
def home():
    return {"status": "online", "database": "configured", "environment": settings.app_env}


@app.get("/health")
def health():
    """Expõe um estado operacional seguro, incluindo a disponibilidade do OCR."""
    ocr_disponivel, ocr = _ocr_status()
    return {
        "status": "online" if ocr_disponivel else "degradado",
        "database": "configured",
        "environment": settings.app_env,
        "ocr": ocr,
    }


@app.get("/admin/operations/metrics")
def operations_metrics(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")):
    """Métricas administrativas sem expor resultados, PDFs ou URLs externas."""
    verificar_admin(x_admin_key)
    _, ocr = _ocr_status()
    return {
        "pncp": obter_metricas_pncp(),
        "analises_edital": dict(edital_analysis_service.metrics),
        "indexacao_assistida": dict(vector_indexing_service.metrics),
        "ocr": {key: ocr[key] for key in ("status", "idioma", "versao")},
    }


@app.get("/api/v1/obras", response_model=ResultadoBusca, dependencies=[Depends(verificar_api_key)])
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
    termo: str | None = Query(None, max_length=1000, description="Expressão textual: use - para excluir e aspas para frases"),
    termos_inclusao: list[str] | None = Query(None, description="Lista estruturada de termos incluídos; não combine com termo"),
    termos_exclusao: list[str] | None = Query(None, description="Lista estruturada de termos excluídos; não combine com termo"),
    escopo_busca: str = Query("objeto_itens", pattern=r"^(objeto_itens|objeto_itens_orgao|todos_metadados)$"),
    modo_inclusao: str = Query("qualquer", pattern=r"^(qualquer|todos)$"),
    ordenacao: str = Query("data_desc", pattern=r"^(data_desc|data_asc|valor_desc|valor_asc|orgao)$"),
    incluir_pavimentacao: bool = Query(
        True,
        description="Quando falso, exclui obras de pavimentação e recapeamento",
    ),
    forcar_atualizacao: bool = Query(
        False,
        description="Quando verdadeiro, ignora os dados locais e atualiza a consulta no PNCP",
    ),
):
    inicial_date = _request_date(inicial_date, "inicial_date")
    final_date = _request_date(final_date, "final_date")
    try:
        request_timeout = max(30.0, search_request_timeout_seconds(modalidade, max_paginas))
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
                termo=termo,
                termos_inclusao=termos_inclusao,
                termos_exclusao=termos_exclusao,
                escopo_busca=escopo_busca,
                modo_inclusao=modo_inclusao,
                ordenacao=ordenacao,
                incluir_pavimentacao=incluir_pavimentacao,
                forcar_atualizacao=forcar_atualizacao,
            ),
            timeout=request_timeout,
        )
    except PaginationSnapshotExpiredError as exc:
        raise HTTPException(
            status_code=410,
            detail={"code": exc.code, "mensagem": "A consulta expirou. Atualize para reiniciar mantendo os filtros."},
        ) from exc
    except PaginationCursorError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "mensagem": "O cursor não corresponde a esta consulta. Reinicie a navegação."},
        ) from exc
    except QuerySnapshotStorageError as exc:
        raise HTTPException(status_code=503, detail={"code": "snapshot_indisponivel", "mensagem": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        logger.error("Busca PNCP excedeu o timeout global")
        raise HTTPException(status_code=504, detail="A consulta ao PNCP excedeu o tempo limite") from exc


@app.get("/api/v1/obras/stream", dependencies=[Depends(verificar_api_key)])
async def stream_jobs(
    inicial_date: str | None = Query(None, pattern=r"^\d{8}$"),
    final_date: str | None = Query(None, pattern=r"^\d{8}$"),
    modalidade: int = Query(0, ge=0, description="4: Concorrência, 6: Pregão, 8: Dispensa, 0: Todas"),
    max_paginas: int = Query(settings.pncp_max_paginas, ge=1, le=100),
    tamanho_pagina: int = Query(50, ge=PNCP_MIN_PAGE_SIZE, le=PNCP_MAX_PAGE_SIZE),
    uf: str | None = Query(None, min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    termo: str | None = Query(None, max_length=1000),
    termos_inclusao: list[str] | None = Query(None),
    termos_exclusao: list[str] | None = Query(None),
    escopo_busca: str = Query("objeto_itens", pattern=r"^(objeto_itens|objeto_itens_orgao|todos_metadados)$"),
    modo_inclusao: str = Query("qualquer", pattern=r"^(qualquer|todos)$"),
    ordenacao: str = Query("data_desc", pattern=r"^(data_desc|data_asc|valor_desc|valor_asc|orgao)$"),
    incluir_pavimentacao: bool = Query(True),
    forcar_atualizacao: bool = Query(False),
):
    """Entrega eventos SSE para popular os cards assim que cada página chega."""

    inicial_date = _request_date(inicial_date, "inicial_date")
    final_date = _request_date(final_date, "final_date")

    async def events():
        try:
            async for event in stream_licitacoes_construction(
                data_inicial=inicial_date,
                data_final=final_date,
                modalidade=modalidade,
                max_paginas=max_paginas,
                tamanho_pagina=tamanho_pagina,
                uf=uf.upper() if uf else None,
                termo=termo,
                termos_inclusao=termos_inclusao,
                termos_exclusao=termos_exclusao,
                escopo_busca=escopo_busca,
                modo_inclusao=modo_inclusao,
                ordenacao=ordenacao,
                incluir_pavimentacao=incluir_pavimentacao,
                forcar_atualizacao=forcar_atualizacao,
            ):
                yield f"event: {event['tipo']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except ValueError as exc:
            event = {"tipo": "erro", "mensagem": str(exc), "status": "erro"}
            yield f"event: erro\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:  # A conexão SSE não deve ficar aberta sem um evento terminal.
            logger.exception("Falha na busca progressiva de obras")
            event = {"tipo": "erro", "mensagem": "Falha ao consultar o PNCP.", "status": "erro"}
            yield f"event: erro\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get(
    "/api/v1/obras/{cnpj}/{ano}/{sequencial}/tipo",
    response_model=TipoContratacaoOut,
    dependencies=[Depends(verificar_api_key)],
)
async def get_tipo_contratacao(
    cnpj: str = Path(..., min_length=14, max_length=14),
    ano: int = Path(..., ge=1),
    sequencial: int = Path(..., ge=1),
    modalidade: str | None = Query(None, max_length=255),
    tipo_instrumento: str | None = Query(None, max_length=255),
):
    """Completa o tipo com o critério publicado nos itens da contratação."""

    try:
        return await buscar_tipo_contratacao_pncp(
            cnpj,
            ano,
            sequencial,
            modalidade=modalidade,
            tipo_instrumento=tipo_instrumento,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (PNCPConnectionError, PNCPResponseError) as exc:
        raise HTTPException(status_code=503, detail="Não foi possível consultar o tipo no PNCP") from exc


@app.get(
    "/api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos",
    response_model=ResultadoDocumentos,
    dependencies=[Depends(verificar_api_key)],
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
    dependencies=[Depends(verificar_api_key)],
)
async def list_exigencias(
    cnpj: str = Path(..., min_length=14, max_length=14, pattern=r"^[A-Za-z0-9]{14}$"),
    ano: int = Path(..., ge=1),
    sequencial: int = Path(..., ge=1),
    forcar: bool = Query(False, description="Ignora o cache compatível e refaz a análise"),
):
    """Analisa habilitação sob demanda, sem afetar a listagem de obras."""
    try:
        contratacao_chave = f"{cnpj}:{ano}:{sequencial}"
        if vector_indexing_service.enabled():
            if not forcar:
                assisted = await asyncio.to_thread(get_completed_requirement_result, contratacao_chave)
                if assisted is not None:
                    return assisted
            # A solicitação só persiste o job e devolve o controle. O fallback
            # determinístico abaixo mantém o detalhe disponível agora.
            asyncio.create_task(
                vector_indexing_service.request_for_contract(contratacao_chave=contratacao_chave),
                name=f"vector-index-{contratacao_chave}",
            )
        fallback = await asyncio.wait_for(
            edital_analysis_service.analisar_contratacao(cnpj, ano, sequencial, forcar=forcar),
            timeout=settings.edital_analysis_timeout_seconds,
        )
        fallback_result = ResultadoExigencias.model_validate(fallback)
        if vector_indexing_service.enabled() and not fallback_result.analise_assistida:
            assisted_status = await asyncio.to_thread(get_requirement_analysis_status, contratacao_chave)
            if assisted_status is not None:
                return fallback_result.model_copy(update={"analise_assistida_status": assisted_status})
        return fallback_result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        logger.warning("Análise de exigências excedeu o timeout global")
        raise HTTPException(
            status_code=503,
            detail="A análise dos documentos excedeu o tempo limite; tente novamente.",
        ) from exc
    except AnalysisCapacityError as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "5"}) from exc
    except PNCPConnectionError as exc:
        logger.warning("Falha de conexão ao iniciar análise de exigências: %s", exc)
        raise HTTPException(status_code=503, detail="Não foi possível carregar os documentos do PNCP agora") from exc
    except PNCPResponseError as exc:
        logger.warning("Resposta inválida do PNCP ao iniciar análise de exigências: %s", exc)
        raise HTTPException(status_code=502, detail="O PNCP retornou uma resposta inválida para os documentos") from exc
