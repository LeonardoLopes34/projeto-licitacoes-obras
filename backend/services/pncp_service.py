import httpx
import unicodedata
import asyncio
from typing import List, Dict, Any

# ==========================================
# 1. (MOCK DATA)
# ==========================================
MOCK_LICITACOES_BASE = [
    {
        "id_pncp": "94309291000148-1-000130/2026",
        "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TRAMANDAI", "cnpj": "94309291000148"},
        "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Tramandaí"},
        "objetoCompra": "CONTRATAÇÃO DE EMPRESA ESPECIALIZADA EM ENGENHARIA PARA EXECUÇÃO DE OBRAS DE PAVIMENTAÇÃO ASFÁLTICA E DRENAGEM PLUVIAL NA AV. BEIRA MAR.",
        "valorTotalEstimado": 1250000.00,
        "dataPublicacaoPncp": "2026-08-01T09:00:00",
        "modalidadeNome": "Concorrência - Eletrônica",
        "anoCompra": "2026",
        "sequencialCompra": "130"
    },
    {
        "id_pncp": "88309291000199-1-000045/2026",
        "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TORRES", "cnpj": "88309291000199"},
        "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Torres"},
        "objetoCompra": "REFORMA E AMPLIAÇÃO ESTRUTURAL DA ESCOLA MUNICIPAL DE ENSINO FUNDAMENTAL COM SUBSTITUIÇÃO DE COBERTURA PREDIAL E RECONSTRUÇÃO DE MURO.",
        "valorTotalEstimado": 450000.50,
        "dataPublicacaoPncp": "2026-08-02T14:30:00",
        "modalidadeNome": "Concorrência - Eletrônica",
        "anoCompra": "2026",
        "sequencialCompra": "45"
    },
    {
        "id_pncp": "00509018000113-1-001422/2026",
        "orgaoEntidade": {"razaoSocial": "TRIBUNAL SUPERIOR ELEITORAL", "cnpj": "00509018000113"},
        "unidadeOrgao": {"ufSigla": "SE", "municipioNome": "Aracaju"},
        "objetoCompra": "AQUISIÇÃO DE CABO DE POTÊNCIA DE COBRE E TERMINAL À COMPRESSÃO COM COBERTURA ANTICHAMA.",
        "valorTotalEstimado": 27805.00,
        "dataPublicacaoPncp": "2026-08-01T07:57:21",
        "modalidadeNome": "Dispensa",
        "anoCompra": "2026",
        "sequencialCompra": "1422"
    },
    {
        "id_pncp": "82804212000196-1-000214/2026",
        "orgaoEntidade": {"razaoSocial": "MUNICIPIO DE AGUAS DE CHAPECO", "cnpj": "82804212000196"},
        "unidadeOrgao": {"ufSigla": "SC", "municipioNome": "Águas de Chapecó"},
        "objetoCompra": "AQUISIÇÃO DE MATERIAIS PARA COBERTURA DA GARAGEM DO QUARTEL DA POLICIA MILITAR DE ÁGUAS DE CHAPECÓ.",
        "valorTotalEstimado": 8818.50,
        "dataPublicacaoPncp": "2026-08-01T08:25:09",
        "modalidadeNome": "Dispensa",
        "anoCompra": "2026",
        "sequencialCompra": "214"
    }
]

# ==========================================
# 2. Filters
# ==========================================
KEYWORDS_OBRAS = [
    "construc", "reform", "paviment", "obra", "arrimo", "drenagem", 
    "asfalt", "recape", "saneamento", "calcamento", "edifica", "demolicao", 
    "conten", "muro", "pontes", "viaria", "urbanizac", "canalizac", 
    "terraplenagem", "dique"
]

EXCLUDE_KEYWORDS = [
    # Materiais e TI
    "aquisicao de material", "aquisicao de materiais", "compra de material",
    "cabo de potencia", "cabo eletrico", "cobertura antichama", "isolamento",
    "wi-fi", "wifi", "internet", "software", "impressora", "plotter", 
    "extintor", "iluminacao", "veiculo", "combustivel", "merenda", 
    "seguro patrimonial", "apolice", "locacao de equipamento",
    
    # Veículos, Frota e Peças de Maquinário
    "pecas", "peca", "mao de obra mecanica", "manutencao corretiva", 
    "manutencao preventiva", "chave de seta", "lanterna", "caminhao", 
    "retroescavadeira", "troca de pneu", "troca de pneus", "revisao obrigatoria",
    "revisao de", "frota", "mecanica", "auto pecas", "autopeceas"
]

def remover_acentos(texto: str) -> str:
    if not texto:
        return ""
    texto_nfd = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto_nfd if unicodedata.category(c) != "Mn").lower()

def is_interesting_construction(objeto: str) -> bool:
    if not objeto:
        return False
        
    objeto_limpo = remover_acentos(objeto)
    
    if any(ex in objeto_limpo for ex in EXCLUDE_KEYWORDS):
        return False

    if "secretaria de obras" in objeto_limpo or "secretaria municipal de obras" in objeto_limpo:
        verbos_execucao = ["execucao", "construcao de", "reforma de", "pavimentacao", "recapeamento", "ampliacao de"]
        if not any(v in objeto_limpo for v in verbos_execucao):
            return False

    if "cobertur" in objeto_limpo and not any(kw in objeto_limpo for kw in ["obra", "reform", "construc", "execuc", "estrutura"]):
        return False

    return any(kw in objeto_limpo for kw in KEYWORDS_OBRAS)

def processar_itens_raw(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aplica o filtro de keywords e formata os dados para o padrão da aplicação."""
    resultados = []
    for item in items:
        objeto = item.get("objetoCompra") or item.get("objeto") or ""

        if is_interesting_construction(objeto):
            cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")
            ano = item.get("anoCompra") or item.get("ano", "")
            sequencial = item.get("sequencialCompra") or item.get("sequencialContratacao") or ""
            
            link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}" if cnpj and ano and sequencial else None

            resultados.append({
                "id_pncp": item.get("numeroControlePNCP") or item.get("id_pncp"),
                "orgao": item.get("orgaoEntidade", {}).get("razaoSocial"),
                "cnpj": cnpj,
                "uf": item.get("unidadeOrgao", {}).get("ufSigla"),
                "municipio": item.get("unidadeOrgao", {}).get("municipioNome"),
                "objeto": objeto,
                "valor_estimado": item.get("valorTotalEstimado"),
                "data_publicacao": item.get("dataPublicacaoPncp"),
                "modalidade": item.get("modalidadeNome"),
                "link_pncp": link,
                "fonte": "PNCP_REAL"
            })
    return resultados

# ==========================================
# 3. WORKER ASSÍNCRONO DE PÁGINA INDIVIDUAL
# ==========================================
async def fetch_pagina(client: httpx.AsyncClient, url: str, params: dict, headers: dict) -> List[dict]:
    # Pequeno atraso baseado no número da página para não golpear o servidor do PNCP de uma vez só
    pagina = params.get("pagina", 1)
    if pagina > 1:
        await asyncio.sleep((pagina - 1) * 0.15)  # 150ms de intervalo entre páginas
        
    try:
        response = await client.get(url, params=params, headers=headers)
        if response.status_code == 200:
            return response.json().get("data", [])
        return []
    except Exception as e:
        print(f"⚠️ Erro ao buscar página {pagina}: {type(e).__name__}")
        return []

# ==========================================
# 4. SERVICE PRINCIPAL COM BUSCA PARALELA
# ==========================================
async def search_licitacoes_construction(
    data_inicial: str, 
    data_final: str, 
    modalidade: int = 8, 
    tamanho_pagina: int = 50,
    max_paginas: int = 3,
    force_mock: bool = False
) -> Dict[str, Any]:
    
    if force_mock:
        print("🛠️ [MODO MOCK ATIVADO MANUALMENTE]")
        dados_filtrados = processar_itens_raw(MOCK_LICITACOES_BASE)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_LOCAL"
        return {
            "status": "sucesso_mock",
            "mensagem": "Dados fictícios de desenvolvimento",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    # Timeout total por requisição paralela
    timeout = httpx.Timeout(20.0, connect=4.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            # 1. Monta as tarefas concorrentes para todas as páginas solicitadas
            tasks = []
            for pagina in range(1, max_paginas + 1):
                params = {
                    "dataInicial": data_inicial,
                    "dataFinal": data_final,
                    "codigoModalidadeContratacao": modalidade,
                    "pagina": pagina,
                    "tamanhoPagina": tamanho_pagina
                }
                tasks.append(fetch_pagina(client, url, params, headers))

            paginas_resultados = await asyncio.gather(*tasks)

            raw_items = [item for sublista in paginas_resultados for item in sublista]

        if not raw_items:
            raise httpx.HTTPError("Nenhum item recuperado da API do PNCP.")

        dados_filtrados = processar_itens_raw(raw_items)
        return {
            "status": "sucesso_real",
            "mensagem": f"Analisados {len(raw_items)} itens brutos em paralelo de {max_paginas} páginas.",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }

    except Exception as e:
        print(f"🚨 Instabilidade/Timeout detectado no PNCP: {type(e).__name__}. Retornando MOCK de desenvolvimento.")
        dados_filtrados = processar_itens_raw(MOCK_LICITACOES_BASE)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_FALLBACK"
            
        return {
            "status": "sucesso_mock_fallback",
            "mensagem": "API do PNCP indisponível no momento. Exibindo dados de teste.",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }