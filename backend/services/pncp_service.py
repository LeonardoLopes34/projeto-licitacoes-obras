import httpx
import unicodedata
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Simple in-memory cache to prevent hitting PNCP rate limits on repeated filter changes
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 180

# ==========================================
# 1. (MOCK DATA GERADO DINAMICAMENTE)
# ==========================================
def get_mock_licitacoes() -> List[Dict[str, Any]]:
    today = datetime.now()
    d0 = today.strftime("%Y-%m-%dT10:00:00")
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%dT14:30:00")
    d2 = (today - timedelta(days=2)).strftime("%Y-%m-%dT09:15:00")

    return [
        {
            "id_pncp": "94309291000148-1-000130/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TRAMANDAI", "cnpj": "94309291000148"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Tramandaí"},
            "objetoCompra": "CONTRATAÇÃO DE EMPRESA ESPECIALIZADA EM ENGENHARIA PARA EXECUÇÃO DE OBRAS DE PAVIMENTAÇÃO ASFÁLTICA E DRENAGEM PLUVIAL NA AV. BEIRA MAR.",
            "valorTotalEstimado": 1250000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrência - Eletrônica",
            "anoCompra": str(today.year),
            "sequencialCompra": "130"
        },
        {
            "id_pncp": "88309291000199-1-000045/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TORRES", "cnpj": "88309291000199"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Torres"},
            "objetoCompra": "REFORMA E AMPLIAÇÃO ESTRUTURAL DA ESCOLA MUNICIPAL DE ENSINO FUNDAMENTAL COM SUBSTITUIÇÃO DE COBERTURA PREDIAL E RECONSTRUÇÃO DE MURO.",
            "valorTotalEstimado": 450000.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrência - Eletrônica",
            "anoCompra": str(today.year),
            "sequencialCompra": "45"
        },
        {
            "id_pncp": "77104212000188-1-000512/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE OSORIO", "cnpj": "77104212000188"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Osório"},
            "objetoCompra": "EXECUÇÃO DE OBRAS DE PAVIMENTAÇÃO E RECAPEAMENTO ASFÁLTICO EM DIVERSAS VIAS DO MUNICÍPIO.",
            "valorTotalEstimado": 890000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 6,
            "modalidadeNome": "Pregão - Eletrônico",
            "anoCompra": str(today.year),
            "sequencialCompra": "512"
        },
        {
            "id_pncp": "00509018000113-1-001422/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE CAPAO DA CANOA", "cnpj": "00509018000113"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Capão da Canoa"},
            "objetoCompra": "REFORMA DE PRÉDIO PÚBLICO MUNICIPAL E DRENAGEM DE VIA PÚBLICA.",
            "valorTotalEstimado": 27805.00,
            "dataPublicacaoPncp": d2,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitação",
            "anoCompra": str(today.year),
            "sequencialCompra": "1422"
        },
        {
            "id_pncp": "82804212000196-1-000214/2026",
            "orgaoEntidade": {"razaoSocial": "MUNICIPIO DE AGUAS DE CHAPECO", "cnpj": "82804212000196"},
            "unidadeOrgao": {"ufSigla": "SC", "municipioNome": "Águas de Chapecó"},
            "objetoCompra": "CONSTRUÇÃO DE COBERTURA E ESTRUTURA PARA A GARAGEM DO QUARTEL DA POLÍCIA MILITAR DE ÁGUAS DE CHAPECÓ.",
            "valorTotalEstimado": 8818.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitação",
            "anoCompra": str(today.year),
            "sequencialCompra": "214"
        }
    ]

MOCK_LICITACOES_BASE = get_mock_licitacoes()

# ==========================================
# 2. Filters & Keyword Engineering Rules
# ==========================================
KEYWORDS_OBRAS = [
    "construcao", "reforma", "pavimentacao", "recapeamento", "recape", 
    "drenagem", "saneamento", "calcamento", "edificacao", "edificacoes", 
    "demolicao", "contencao", "muro de arrimo", "muro de contencao", 
    "obra", "obras", "ponte", "pontes", "viaria", "urbanizacao", 
    "canalizacao", "terraplenagem", "dique", "duplicacao", "reconstrucao",
    "ampliacao predial", "ampliacao de escola", "ampliacao de hospital",
    "terraplanagem", "enrocamento", "desassoreamento"
]

EXCLUDE_KEYWORDS = [
    # Saúde, Odontologia e Hospitalar
    "odontologia", "odontologico", "odontologica", "hospitalar", "medicamento", "medicamentos",
    "ambulatorial", "farmaceutico", "vacina", "insumos medicos",
    
    # Dedetização, Pragas, Higienização, Limpeza Urbana e Sanitária
    "dedetizacao", "desratizacao", "descupinizacao", "controle sanitario", "pragas",
    "higienizacao", "limpeza de caixa", "limpeza de caixas", "limpeza e conservacao",
    "coleta de lixo", "coleta de residuos", "varricao", "capina", "rocada",
    
    # TI, Licenças, Impressão e Equipamentos Eletro-eletrônicos
    "wi-fi", "wifi", "internet", "software", "impressora", "plotter", "computador", "notebook",
    "extintor", "veiculo", "combustivel", "merenda", "seguro patrimonial", "apolice",
    "lixeira", "lixeiras", "contentor", "piso tatil", "cabo de potencia", "cabo eletrico",
    
    # Veículos, Frota, Peças e Mecânica
    "pecas", "peca", "mao de obra mecanica", "manutencao corretiva de veiculo", 
    "manutencao preventiva de veiculo", "chave de seta", "lanterna", "caminhao", 
    "retroescavadeira", "troca de pneu", "troca de pneus", "revisao obrigatoria",
    "frota", "mecanica", "auto pecas", "autopeceas",
    
    # Locação de Mão de Obra Não-Civil e Terceirização Contínua
    "locacao de mao de obra", "posto de trabalho", "servico de portaria", "servicos de portaria",
    "vigilancia armada", "vigilancia desarmada", "recepcionista",
    
    # Treinamento
    "capacitacao", "treinamento", "curso", "encontro nacional", "simposio", "workshop", "congresso"
]

COMPRA_MATERIAIS_KEYWORDS = [
    "aquisicao de material", "aquisicao de materiais", "compra de material", "compra de materiais",
    "fornecimento de material", "fornecimento de materiais", "material de construcao", "materiais de construcao",
    "material para construcao", "materiais para construcao", "aquisicao de cimento", "aquisicao de tinta",
    "aquisicao de tubos", "compra de cimento", "compra de tinta", "compra de tubos", "compra de tijolos",
    "aquisicao de travamento"
]

VERBOS_EXECUCAO = [
    "construcao de", "execucao de", "reforma de", "pavimentacao de", 
    "recapeamento de", "ampliacao de", "obra de", "obras de", "implantacao de"
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
    
    # 1. Filtro absoluto de termos não relacionados a engenharia civil
    if any(ex in objeto_limpo for ex in EXCLUDE_KEYWORDS):
        return False

    # 2. Compra exclusiva de materiais sem contratação de execução de obra
    if any(cm in objeto_limpo for cm in COMPRA_MATERIAIS_KEYWORDS):
        if not any(v in objeto_limpo for v in VERBOS_EXECUCAO):
            return False

    # 3. Tratamento de 'Secretaria de Obras'
    if "secretaria de obras" in objeto_limpo or "secretaria municipal de obras" in objeto_limpo:
        if not any(v in objeto_limpo for v in VERBOS_EXECUCAO):
            return False

    # 4. Tratamento do termo 'cobertura'
    if "cobertura" in objeto_limpo and not any(kw in objeto_limpo for kw in ["obra", "reforma", "construcao", "execucao", "estrutura"]):
        return False

    # 5. Validação de palavras-chave do universo de obras e engenharia
    return any(kw in objeto_limpo for kw in KEYWORDS_OBRAS)

# Modalidades de Engenharia e Obras consultadas quando 'Todas' (0) é selecionado:
# 4: Concorrência Eletrônica | 6: Pregão Eletrônico
MODALIDADES_PADRAO_TODAS = [4, 6]

def processar_itens_raw(
    items: List[Dict[str, Any]], 
    data_inicial: str = None, 
    data_final: str = None, 
    modalidade: int = None
) -> List[Dict[str, Any]]:
    """Aplica o filtro de keywords, datas e modalidade, formatando os dados para o padrão da aplicação."""
    resultados = []
    for item in items:
        # 1. Filtro de Data
        pub_date = item.get("dataPublicacaoPncp") or ""
        if data_inicial and data_final and pub_date:
            date_clean = pub_date[:10].replace("-", "")
            if len(date_clean) == 8 and not (data_inicial <= date_clean <= data_final):
                continue

        # 2. Filtro de Modalidade (4: Concorrência Eletrônica, 6: Pregão Eletrônico)
        if modalidade is not None and modalidade != 0:
            m_id = item.get("modalidadeId") or item.get("modalidade_id") or item.get("codigoModalidadeContratacao")
            m_nome = (item.get("modalidadeNome") or item.get("modalidade") or "").lower()
            
            match_found = False
            if m_id is not None:
                try:
                    if int(m_id) == int(modalidade):
                        match_found = True
                except ValueError:
                    pass
            
            if not match_found and m_nome:
                if int(modalidade) == 4 and ("concorrencia" in m_nome or "concorrência" in m_nome):
                    match_found = True
                elif int(modalidade) == 6 and ("pregao" in m_nome or "pregão" in m_nome):
                    match_found = True

            if not match_found:
                continue

        # 3. Filtro de Obra
        objeto = item.get("objetoCompra") or item.get("objeto") or ""

        if is_interesting_construction(objeto):
            cnpj = item.get("orgaoEntidade", {}).get("cnpj", "")
            ano = item.get("anoCompra") or item.get("ano", "")
            sequencial = item.get("sequencialCompra") or item.get("sequencialContratacao") or ""
            
            link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}" if cnpj and ano and sequencial else None

            resultados.append({
                "id_pncp": item.get("numeroControlePNCP") or item.get("id_pncp"),
                "orgao": item.get("orgaoEntidade", {}).get("razaoSocial") or item.get("orgao"),
                "cnpj": cnpj,
                "uf": item.get("unidadeOrgao", {}).get("ufSigla") or item.get("uf"),
                "municipio": item.get("unidadeOrgao", {}).get("municipioNome") or item.get("municipio"),
                "objeto": objeto,
                "valor_estimado": item.get("valorTotalEstimado") or item.get("valor_estimado"),
                "data_publicacao": item.get("dataPublicacaoPncp") or item.get("data_publicacao"),
                "modalidade": item.get("modalidadeNome") or item.get("modalidade"),
                "link_pncp": link,
                "fonte": "PNCP_REAL"
            })
    return resultados

def _calculate_days_in_range(data_inicial: str, data_final: str) -> List[str]:
    """Retorna lista de datas YYYYMMDD em ordem decrescente (do mais recente ao mais antigo)."""
    try:
        d_start = datetime.strptime(data_inicial, "%Y%m%d")
        d_end = datetime.strptime(data_final, "%Y%m%d")
        cur = d_end
        days = []
        while cur >= d_start:
            days.append(cur.strftime("%Y%m%d"))
            cur -= timedelta(days=1)
        return days if days else [data_final]
    except Exception:
        return [data_final, data_inicial] if data_final != data_inicial else [data_final]

# ==========================================
# 3. WORKER ASSÍNCRONO COM SEMÁFORO E BACKOFF
# ==========================================
async def fetch_pagina(
    client: httpx.AsyncClient, 
    semaphore: asyncio.Semaphore,
    url: str, 
    params: dict, 
    headers: dict,
    delay: float = 0.0
) -> List[Dict[str, Any]]:
    if delay > 0:
        await asyncio.sleep(delay)
        
    async with semaphore:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    return data
                elif response.status_code == 429:
                    # Exponential backoff para Rate Limit do PNCP
                    backoff_delay = 1.0 * (attempt + 1)
                    print(f"[WARNING] PNCP 429 (Too Many Requests) mod {params.get('codigoModalidadeContratacao')} dia {params.get('dataInicial')} pág {params.get('pagina')}, aguardando {backoff_delay}s...")
                    await asyncio.sleep(backoff_delay)
                elif response.status_code in [400, 422]:
                    print(f"[WARNING] PNCP status {response.status_code} na requisição: {response.text[:200]}")
                    break
                else:
                    print(f"[WARNING] PNCP status {response.status_code} na página {params.get('pagina')}")
                    break
            except Exception as e:
                print(f"[WARNING] Erro tentativa {attempt+1} pág {params.get('pagina')}: {type(e).__name__}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.4 * (attempt + 1))
        return []

# ==========================================
# 4. SERVICE PRINCIPAL COM DISTRIBUIÇÃO DIÁRIA E CONTROLE DE TAXA
# ==========================================
async def _execute_search(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    data_inicial: str,
    data_final: str,
    modalidade: int,
    tamanho_pagina: int,
    max_paginas: int
) -> List[Dict[str, Any]]:
    # Semáforo limitando a 2 conexões simultâneas para estabilidade total contra 429
    semaphore = asyncio.Semaphore(2)

    days = _calculate_days_in_range(data_inicial, data_final)
    modalidades_consulta = MODALIDADES_PADRAO_TODAS if (modalidade is None or modalidade == 0) else [modalidade]

    tasks = []
    task_idx = 0

    if modalidade == 0:
        # Quando 'Todas' está selecionado (Concorrência + Pregão):
        # Distribui as requisições pelos dias mais recentes do período selecionado
        dias_alvo = days[:max(1, max_paginas)]
        pages_per_day = 2 if len(dias_alvo) == 1 else 1

        for d in dias_alvo:
            for mod in modalidades_consulta:
                for pagina in range(1, pages_per_day + 1):
                    params = {
                        "dataInicial": d,
                        "dataFinal": d,
                        "codigoModalidadeContratacao": mod,
                        "pagina": pagina,
                        "tamanhoPagina": tamanho_pagina
                    }
                    delay = task_idx * 0.08
                    task_idx += 1
                    tasks.append(fetch_pagina(client, semaphore, url, params, headers, delay=delay))
    else:
        # Modalidade específica selecionada (ex: Concorrência ou Pregão)
        dias_alvo = days[:max(1, max_paginas)]
        pages_per_day = max(1, max_paginas // len(dias_alvo)) if len(dias_alvo) < max_paginas else 1

        for d in dias_alvo:
            for pagina in range(1, pages_per_day + 1):
                params = {
                    "dataInicial": d,
                    "dataFinal": d,
                    "codigoModalidadeContratacao": modalidade,
                    "pagina": pagina,
                    "tamanhoPagina": tamanho_pagina
                }
                delay = task_idx * 0.08
                task_idx += 1
                tasks.append(fetch_pagina(client, semaphore, url, params, headers, delay=delay))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    raw_items = []
    seen_ids = set()

    for res in results:
        if isinstance(res, list):
            for item in res:
                item_id = item.get("numeroControlePNCP") or item.get("id_pncp") or f"{item.get('orgaoEntidade', {}).get('cnpj')}_{item.get('sequencialCompra')}"
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    raw_items.append(item)
                elif not item_id:
                    raw_items.append(item)

    return raw_items

async def search_licitacoes_construction(
    data_inicial: str, 
    data_final: str, 
    modalidade: int = 4, 
    tamanho_pagina: int = 50,
    max_paginas: int = 3,
    force_mock: bool = False
) -> Dict[str, Any]:
    
    if force_mock:
        print("[MODO MOCK ATIVADO MANUALMENTE]")
        dados_filtrados = processar_itens_raw(get_mock_licitacoes(), data_inicial, data_final, modalidade)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_LOCAL"
        return {
            "status": "sucesso_mock",
            "mensagem": "Dados fictícios de desenvolvimento",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }

    # Verificar Cache em memória
    cache_key = f"{data_inicial}_{data_final}_{modalidade}_{tamanho_pagina}_{max_paginas}"
    now = time.time()
    if cache_key in _CACHE:
        cached_entry = _CACHE[cache_key]
        if now - cached_entry["timestamp"] < CACHE_TTL_SECONDS:
            print(f"[CACHE HIT] Retornando dados salvos em cache para a chave: {cache_key}")
            return cached_entry["data"]

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    # Timeout ágil por requisição (7s de resposta, 4s de conexão)
    timeout = httpx.Timeout(7.0, connect=4.0)

    try:
        # Timeout limite global de 14 segundos para toda a busca combinada
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            raw_items = await asyncio.wait_for(
                _execute_search(client, url, headers, data_inicial, data_final, modalidade, tamanho_pagina, max_paginas),
                timeout=14.0
            )

        if raw_items:
            dados_filtrados = processar_itens_raw(raw_items, data_inicial, data_final, modalidade)
            modalidades_msg = "todas as modalidades (Concorrência + Pregão)" if modalidade == 0 else f"modalidade {modalidade}"
            resultado = {
                "status": "sucesso_real",
                "mensagem": f"Analisados {len(raw_items)} itens brutos em até {max_paginas} página(s) para {modalidades_msg}.",
                "total_encontradas": len(dados_filtrados),
                "dados": dados_filtrados
            }
            # Salvar no cache
            _CACHE[cache_key] = {"timestamp": time.time(), "data": resultado}
            return resultado
        else:
            print("[WARNING] API PNCP não retornou itens. Usando fallback mock.")
            raise httpx.HTTPError("Nenhum dado retornado pela API do PNCP.")

    except (asyncio.TimeoutError, Exception) as e:
        print(f"[ERROR] Instabilidade/Timeout detectado no PNCP ({type(e).__name__}). Retornando MOCK de desenvolvimento.")
        dados_filtrados = processar_itens_raw(get_mock_licitacoes(), data_inicial, data_final, modalidade)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_FALLBACK"
            
        return {
            "status": "sucesso_mock_fallback",
            "mensagem": "API do PNCP instável ou fora do ar. Exibindo dados de contingência.",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }