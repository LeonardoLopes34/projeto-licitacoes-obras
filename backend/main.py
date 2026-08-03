from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.services.pncp_service import search_licitacoes_construction

app = FastAPI(
    title="Engine de Captação de Obras - PNCP",
    version="1.0.0"
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
    return {"status": "online"}

@app.get("/api/v1/obras")
async def list_jobs(
    inicial_date: str = Query("20260701", description="Data inicial no formato YYYYMMDD"),
    final_date: str = Query("20260715", description="Data final no formato YYYYMMDD"),
    modalidade: int = Query(8, description="Código da Modalidade (8: Concorrência, 6: Pregão, 4: Dispensa)"),
    max_paginas: int = Query(3, ge=1, le=10, description="Quantidade de páginas para varrer"),
    force_mock: bool = Query(False, description="Forçar o uso de dados Mock de teste")
):
    resultado = await search_licitacoes_construction(
        data_inicial=inicial_date,
        data_final=final_date,
        modalidade=modalidade,
        max_paginas=max_paginas,
        force_mock=force_mock
    )
    
    return resultado