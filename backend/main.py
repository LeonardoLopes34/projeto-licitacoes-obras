import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.database import init_db, get_db
from backend.services.pncp_service import search_licitacoes_construction, processar_itens_raw, get_mock_licitacoes
from backend.services.db_service import get_db_stats, cleanup_expired_obras, get_obras_from_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializacao automatica do banco de dados na subida do servidor e limpeza de mocks
    init_db()
    yield

app = FastAPI(
    title="Engine de Captacao de Obras - PNCP",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def home():
    return {"status": "online", "database": "active"}

@app.get("/api/v1/obras")
async def list_jobs(
    inicial_date: str = Query("20260701", description="Data inicial no formato YYYYMMDD"),
    final_date: str = Query("20260715", description="Data final no formato YYYYMMDD"),
    modalidade: int = Query(4, description="Codigo da Modalidade (4: Concorrencia, 6: Pregao, 0: Todas)"),
    max_paginas: int = Query(3, ge=1, le=10, description="Quantidade de paginas para varrer"),
    force_mock: bool = Query(False, description="Forcar o uso de dados Mock de teste")
):
    try:
        resultado = await asyncio.wait_for(
            search_licitacoes_construction(
                data_inicial=inicial_date,
                data_final=final_date,
                modalidade=modalidade,
                max_paginas=max_paginas,
                force_mock=force_mock
            ),
            timeout=16.0
        )
        return resultado
    except Exception as e:
        print(f"[ERROR] Endpoint timeout ou excecao capturada: {type(e).__name__}")
        
        # 1. Se force_mock estiver ativo, retorna dados mockados
        if force_mock:
            dados_filtrados = processar_itens_raw(get_mock_licitacoes(), inicial_date, final_date, modalidade)
            for item in dados_filtrados:
                item["fonte"] = "MOCK_LOCAL"
            return {
                "status": "sucesso_mock",
                "mensagem": "Modo de teste ativo: exibindo dados simulados.",
                "total_encontradas": len(dados_filtrados),
                "dados": dados_filtrados
            }

        # 2. Tenta recuperar do banco de dados local dados reais
        try:
            from backend.database import SessionLocal
            with SessionLocal() as db:
                obras_locais = get_obras_from_db(db, modalidade=modalidade, data_inicial=inicial_date, data_final=final_date)
                if obras_locais:
                    return {
                        "status": "sucesso_offline_db",
                        "mensagem": f"Servico do PNCP temporariamente instavel ({type(e).__name__}). Exibindo {len(obras_locais)} obras reais do banco local.",
                        "total_encontradas": len(obras_locais),
                        "dados": obras_locais
                    }
        except Exception as db_err:
            print(f"[ERROR] Falha ao consultar banco local no handler principal: {db_err}")

        # 3. Se nao houver dados reais, retorna erro claro sem forjar dados mockados
        return {
            "status": "erro",
            "mensagem": f"Servico do PNCP temporariamente instavel ({type(e).__name__}). Nao ha dados locais salvos para estes filtros.",
            "total_encontradas": 0,
            "dados": []
        }

@app.get("/api/v1/database/stats")
def database_stats(db: Session = Depends(get_db)):
    """Retorna o status atual do banco de dados e retencao de 2 dias."""
    return get_db_stats(db)

@app.post("/api/v1/database/cleanup")
def database_cleanup(days: int = Query(2, ge=1, le=30), db: Session = Depends(get_db)):
    """Executa manualmente a limpeza de obras mais antigas que X dias."""
    excluidas = cleanup_expired_obras(db, max_age_days=days)
    return {
        "status": "sucesso",
        "obras_excluidas": excluidas,
        "dias_retencao": days
    }
