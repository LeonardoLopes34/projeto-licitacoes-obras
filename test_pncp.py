import httpx
import asyncio
import logging


logging.basicConfig(level=logging.INFO)

async def testar_conexao_pncp():
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params = {
        "dataInicial": "20260801",
        "dataFinal": "20260803",
        "codigoModalidadeContratacao": 8,
        "pagina": 1,
        "tamanhoPagina": 10
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }

    timeout = httpx.Timeout(30.0, connect=10.0)
    
    print("Testando consulta a API do PNCP (endpoint: /v1/contratacoes/publicacao)...")
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                licitacoes = data.get("data", [])
                print(f"Conexao OK! Encontradas {len(licitacoes)} licitacoes nesta pagina.\n")
                
                if licitacoes:
                    item = licitacoes[0]
                    orgao = item.get("orgaoEntidade", {}).get("razaoSocial", "Não Informado")
                    objeto = item.get("objeto", "Sem descrição")
                    valor = item.get("valorTotalEstimado", 0.0)
                    
                    print("Exemplo de Licitacao Encontrada:")
                    print(f"Orgao: {orgao}")
                    print(f"Valor Estimado: R$ {valor:,.2f}" if valor else "Valor: Nao informado")
                    print(f"Objeto: {objeto[:150]}...")
                else:
                    print("Conexao bem-sucedida, mas nenhuma licitacao retornada para essas datas/filtros.")
            else:
                print(f"Erro HTTP {response.status_code}: {response.text[:200]}")
                
    except (httpx.HTTPError, ValueError) as e:
        print(f"Erro de conexao: {e}")

if __name__ == "__main__":
    asyncio.run(testar_conexao_pncp())
