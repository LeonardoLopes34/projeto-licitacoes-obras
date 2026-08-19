import asyncio
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.services.pncp_service import search_licitacoes_construction, processar_itens_raw, get_mock_licitacoes

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
    modalidade: int = Query(4, description="Código da Modalidade (4: Concorrência, 6: Pregão, 0: Todas)"),
    max_paginas: int = Query(3, ge=1, le=10, description="Quantidade de páginas para varrer"),
    force_mock: bool = Query(False, description="Forçar o uso de dados Mock de teste")
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
        print(f"[ERROR] Endpoint timeout ou exceção capturada: {type(e).__name__}")
        dados_filtrados = processar_itens_raw(get_mock_licitacoes(), inicial_date, final_date, modalidade)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_FALLBACK"
        return {
            "status": "sucesso_mock_fallback",
            "mensagem": "Serviço temporariamente indisponível. Exibindo dados de contingência.",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }