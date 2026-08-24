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
# 1. (MOCK DATA PARA TESTES EXPLICITOS)
# ==========================================
def get_mock_licitacoes() -> List[Dict[str, Any]]:
    today = datetime.now()
    d0 = today.strftime("%Y-%m-%dT10:00:00")
    d1 = (today - timedelta(days=1)).strftime("%Y-%m-%dT14:30:00")
    d2 = (today - timedelta(days=2)).strftime("%Y-%m-%dT09:15:00")

    return [
        {
            "id_pncp": "MOCK-94309291000148-1-000130/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TRAMANDAI", "cnpj": "94309291000148"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Tramandai"},
            "objetoCompra": "CONTRATACAO DE EMPRESA ESPECIALIZADA EM ENGENHARIA PARA EXECUCAO DE OBRAS DE PAVIMENTACAO ASFALTICA E DRENAGEM PLUVIAL NA AV. BEIRA MAR.",
            "valorTotalEstimado": 1250000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrencia - Eletronica",
            "anoCompra": str(today.year),
            "sequencialCompra": "130",
            "fonte": "MOCK_LOCAL"
        },
        {
            "id_pncp": "MOCK-88309291000199-1-000045/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TORRES", "cnpj": "88309291000199"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Torres"},
            "objetoCompra": "REFORMA E AMPLIACAO ESTRUTURAL DA ESCOLA MUNICIPAL DE ENSINO FUNDAMENTAL COM SUBSTITUICAO DE COBERTURA PREDIAL E RECONSTRUCAO DE MURO.",
            "valorTotalEstimado": 450000.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrencia - Eletronica",
            "anoCompra": str(today.year),
            "sequencialCompra": "45",
            "fonte": "MOCK_LOCAL"
        },
        {
            "id_pncp": "MOCK-77104212000188-1-000512/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE OSORIO", "cnpj": "77104212000188"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Osorio"},
            "objetoCompra": "EXECUCAO DE OBRAS DE PAVIMENTACAO E RECAPEAMENTO ASFALTICO EM DIVERSAS VIAS DO MUNICIPIO.",
            "valorTotalEstimado": 890000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 6,
            "modalidadeNome": "Pregao - Eletronico",
            "anoCompra": str(today.year),
            "sequencialCompra": "512",
            "fonte": "MOCK_LOCAL"
        },
        {
            "id_pncp": "MOCK-00509018000113-1-001422/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE CAPAO DA CANOA", "cnpj": "00509018000113"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Capao da Canoa"},
            "objetoCompra": "REFORMA DE PREDIO PUBLICO MUNICIPAL E DRENAGEM DE VIA PUBLICA.",
            "valorTotalEstimado": 27805.00,
            "dataPublicacaoPncp": d2,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitacao",
            "anoCompra": str(today.year),
            "sequencialCompra": "1422",
            "fonte": "MOCK_LOCAL"
        },
        {
            "id_pncp": "MOCK-82804212000196-1-000214/2026",
            "orgaoEntidade": {"razaoSocial": "MUNICIPIO DE AGUAS DE CHAPECO", "cnpj": "82804212000196"},
            "unidadeOrgao": {"ufSigla": "SC", "municipioNome": "Aguas de Chapeco"},
            "objetoCompra": "CONSTRUCAO DE COBERTURA E ESTRUTURA PARA A GARAGEM DO QUARTEL DA POLICIA MILITAR DE AGUAS DE CHAPECO.",
            "valorTotalEstimado": 8818.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitacao",
            "anoCompra": str(today.year),
            "sequencialCompra": "214",
            "fonte": "MOCK_LOCAL"
        }
    ]

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
    # Saude, Odontologia e Hospitalar
    "odontologia", "odontologico", "odontologica", "hospitalar", "medicamento", "medicamentos",
    "ambulatorial", "farmaceutico", "vacina", "insumos medicos",
    
    # Dedetizacao, Pragas, Higienizacao, Limpeza Urbana e Sanitaria
    "dedetizacao", "desratizacao", "descupinizacao", "controle sanitario", "pragas",
    "higienizacao", "limpeza de caixa", "limpeza de caixas", "limpeza e conservacao",
    "coleta de lixo", "coleta de residuos", "varricao", "capina", "rocada",
    
    # TI, Licencas, Impressao e Equipamentos Eletro-eletronicos
    "wi-fi", "wifi", "internet", "software", "impressora", "plotter", "computador", "notebook",
    "extintor", "veiculo", "combustivel", "merenda", "seguro patrimonial", "apolice",
    "lixeira", "lixeiras", "contentor", "piso tatil", "cabo de potencia", "cabo eletrico",
    
    # Veiculos, Frota, Pecas e Mecanica
    "pecas", "peca", "mao de obra mecanica", "manutencao corretiva de veiculo", 
    "manutencao preventiva de veiculo", "chave de seta", "lanterna", "caminhao", 
    "retroescavadeira", "troca de pneu", "troca de pneus", "revisao obrigatoria",
    "frota", "mecanica", "auto pecas", "autopeceas",
    
    # Locacao de Mao de Obra Nao-Civil e Terceirizacao Continua
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
    
    # 1. Filtro absoluto de termos nao relacionados a engenharia civil
    if any(ex in objeto_limpo for ex in EXCLUDE_KEYWORDS):
        return False

    # 2. Compra exclusiva de materiais sem contratacao de execucao de obra
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

    # 5. Validacao de palavras-chave do universo de obras e engenharia
    return any(kw in objeto_limpo for kw in KEYWORDS_OBRAS)

MODALIDADES_PADRAO_TODAS = [4, 6]

def processar_itens_raw(
    items: List[Dict[str, Any]], 
    data_inicial: str = None, 
    data_final: str = None, 
    modalidade: int = None
) -> List[Dict[str, Any]]:
    """Aplica o filtro de keywords, datas e modalidade, formatando os dados para o padrao da aplicacao."""
    resultados = []
    for item in items:
        # 1. Filtro de Data
        pub_date = item.get("dataPublicacaoPncp") or item.get("data_publicacao") or ""
        if data_inicial and data_final and pub_date:
            date_clean = pub_date[:10].replace("-", "")
            if len(date_clean) == 8 and not (data_inicial <= date_clean <= data_final):
                continue

        # 2. Filtro de Modalidade (4: Concorrencia Eletronica, 6: Pregao Eletronico)
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
            cnpj = item.get("orgaoEntidade", {}).get("cnpj", "") or item.get("cnpj", "")
            ano = item.get("anoCompra") or item.get("ano", "")
            sequencial = item.get("sequencialCompra") or item.get("sequencialContratacao") or ""
            
            link = item.get("link_pncp")
            if not link and cnpj and ano and sequencial:
                link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"

            fonte = item.get("fonte") or "PNCP_REAL"

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
                "fonte": fonte
            })
    return resultados

# ==========================================
# 3. UTILS DE PAGINACAO E INTERVALO DE DIAS
# ==========================================
def _calculate_days_in_range(data_inicial: str, data_final: str) -> List[str]:
    try:
        d_ini = datetime.strptime(data_inicial, "%Y%m%d")
        d_fim = datetime.strptime(data_final, "%Y%m%d")
        if d_ini > d_fim:
            d_ini, d_fim = d_fim, d_ini
            
        days = []
        curr = d_fim
        while curr >= d_ini:
            days.append(curr.strftime("%Y%m%d"))
            curr -= timedelta(days=1)
        return days
    except Exception:
        return [data_final or data_inicial]

async def fetch_pagina(
    client: httpx.AsyncClient, 
    semaphore: asyncio.Semaphore, 
    url: str, 
    params: dict, 
    headers: dict,
    max_retries: int = 2,
    delay: float = 0.0
) -> List[Dict[str, Any]]:
    if delay > 0:
        await asyncio.sleep(delay)

    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        return data.get("data", [])
                    elif isinstance(data, list):
                        return data
                elif response.status_code == 429:
                    backoff_delay = 1.0 * (attempt + 1)
                    print(f"[WARNING] PNCP 429 (Too Many Requests) mod {params.get('codigoModalidadeContratacao')} dia {params.get('dataInicial')} pag {params.get('pagina')}, aguardando {backoff_delay}s...")
                    await asyncio.sleep(backoff_delay)
                elif response.status_code in [400, 422]:
                    print(f"[WARNING] PNCP status {response.status_code} na requisicao: {response.text[:200]}")
                    break
                else:
                    print(f"[WARNING] PNCP status {response.status_code} na pagina {params.get('pagina')}")
                    break
            except Exception as e:
                print(f"[WARNING] Erro tentativa {attempt+1} pag {params.get('pagina')}: {type(e).__name__}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.4 * (attempt + 1))
        return []

# ==========================================
# 4. SERVICE PRINCIPAL COM CONTROLE DE TAXA E BANCO DE DADOS
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
    semaphore = asyncio.Semaphore(2)

    days = _calculate_days_in_range(data_inicial, data_final)
    modalidades_consulta = MODALIDADES_PADRAO_TODAS if (modalidade is None or modalidade == 0) else [modalidade]

    tasks = []
    task_idx = 0

    if modalidade == 0:
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
    
    # 1. Se force_mock for solicitado explicitamente
    if force_mock:
        print("[MODO MOCK ATIVADO MANUALMENTE]")
        dados_filtrados = processar_itens_raw(get_mock_licitacoes(), data_inicial, data_final, modalidade)
        for item in dados_filtrados:
            item["fonte"] = "MOCK_LOCAL"
        return {
            "status": "sucesso_mock",
            "mensagem": "Modo de teste: exibindo dados ficticios de desenvolvimento.",
            "total_encontradas": len(dados_filtrados),
            "dados": dados_filtrados
        }

    # 2. Verificar Cache em memoria
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

    timeout = httpx.Timeout(7.0, connect=4.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False, follow_redirects=True) as client:
            raw_items = await asyncio.wait_for(
                _execute_search(client, url, headers, data_inicial, data_final, modalidade, tamanho_pagina, max_paginas),
                timeout=14.0
            )

        if raw_items:
            dados_filtrados = processar_itens_raw(raw_items, data_inicial, data_final, modalidade)
            modalidades_msg = "todas as modalidades (Concorrencia + Pregao)" if modalidade == 0 else f"modalidade {modalidade}"
            resultado = {
                "status": "sucesso_real",
                "mensagem": f"Analisados {len(raw_items)} itens brutos em ate {max_paginas} pagina(s) para {modalidades_msg}.",
                "total_encontradas": len(dados_filtrados),
                "dados": dados_filtrados
            }
            
            # Persistir no Banco de Dados e Executar Limpeza Automatica de 2 dias (48 horas)
            try:
                from backend.database import SessionLocal
                from backend.services.db_service import save_obras_batch, cleanup_expired_obras
                with SessionLocal() as db_session:
                    salvos = save_obras_batch(db_session, dados_filtrados)
                    cleanup_expired_obras(db_session, max_age_days=2)
                    print(f"[DATABASE] {salvos} obras salvas/atualizadas no banco de dados com sucesso.")
            except Exception as db_err:
                print(f"[DATABASE WARNING] Falha ao persistir no banco: {db_err}")

            _CACHE[cache_key] = {"timestamp": time.time(), "data": resultado}
            return resultado
        else:
            print("[INFO] API PNCP nao retornou itens. Consultando banco local...")
            try:
                from backend.database import SessionLocal
                from backend.services.db_service import get_obras_from_db
                with SessionLocal() as db_session:
                    obras_locais = get_obras_from_db(db_session, modalidade=modalidade, data_inicial=data_inicial, data_final=data_final)
                    if obras_locais:
                        return {
                            "status": "sucesso_offline_db",
                            "mensagem": f"Nenhum novo edital no PNCP. Exibindo {len(obras_locais)} obras reais salvas no banco de dados.",
                            "total_encontradas": len(obras_locais),
                            "dados": obras_locais
                        }
            except Exception as db_err:
                print(f"[DATABASE WARNING] Erro ao consultar banco local: {db_err}")

            return {
                "status": "sucesso_vazio",
                "mensagem": "Nenhuma licitacao de obras encontrada no PNCP para os filtros selecionados.",
                "total_encontradas": 0,
                "dados": []
            }

    except (asyncio.TimeoutError, Exception) as e:
        print(f"[WARNING] Instabilidade/Timeout detectado no PNCP ({type(e).__name__}). Consultando banco local...")
        try:
            from backend.database import SessionLocal
            from backend.services.db_service import get_obras_from_db
            with SessionLocal() as db_session:
                obras_locais = get_obras_from_db(db_session, modalidade=modalidade, data_inicial=data_inicial, data_final=data_final)
                if obras_locais:
                    return {
                        "status": "sucesso_offline_db",
                        "mensagem": f"API do PNCP instavel ({type(e).__name__}). Exibindo {len(obras_locais)} obras reais salvas no banco de dados local.",
                        "total_encontradas": len(obras_locais),
                        "dados": obras_locais
                    }
        except Exception as db_err:
            print(f"[DATABASE WARNING] Erro ao consultar banco local: {db_err}")

        return {
            "status": "erro",
            "mensagem": f"O servico do PNCP esta temporariamente instavel ({type(e).__name__}) e nao ha registros salvos para estes filtros.",
            "total_encontradas": 0,
            "dados": []
        }
