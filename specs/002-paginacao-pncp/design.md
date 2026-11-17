# Design — Spec 002: Paginação Completa da API do PNCP

## Abordagem

1. Separar explicitamente dois conceitos hoje confundidos no código:
   - `intervalo_dias`: janela de datas da busca (ex. últimos 30 dias).
   - `max_paginas`: limite de segurança de quantas páginas buscar por chamada (para evitar looping infinito ou timeout excessivo).
2. Implementar loop de paginação real, consultando `totalRegistros` retornado pela própria API a cada chamada.
3. Expor, na resposta interna do serviço, quantas páginas foram efetivamente consultadas e se o total foi coberto — isso alimenta a Spec 003 (metadados de execução).

## Trecho ilustrativo

```python
def buscar_obras_pncp(intervalo_dias: int, max_paginas: int = 50, tamanho_pagina: int = 50):
    data_inicio, data_fim = calcular_intervalo(intervalo_dias)
    pagina = 1
    registros = []
    total_registros = None
    paginas_com_erro = 0

    while True:
        try:
            resp = client.get(url, params={
                "dataInicial": data_inicio,
                "dataFinal": data_fim,
                "pagina": pagina,
                "tamanhoPagina": tamanho_pagina,
            })
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Falha ao buscar página %s: %s", pagina, e)
            paginas_com_erro += 1
            pagina += 1
            if pagina > max_paginas:
                break
            continue

        total_registros = payload.get("totalRegistros", total_registros)
        registros.extend(payload.get("data", []))

        if pagina * tamanho_pagina >= (total_registros or 0):
            break
        pagina += 1
        if pagina > max_paginas:
            break

    parcial = (total_registros is not None and len(registros) < total_registros) or paginas_com_erro > 0
    return registros, {
        "parcial": parcial,
        "paginas_consultadas": pagina,
        "paginas_com_erro": paginas_com_erro,
    }
```

## Impacto em outras specs

- Spec 003 consome diretamente o dicionário de metadados (`parcial`, `paginas_consultadas`, `paginas_com_erro`) produzido aqui.
- Spec 009 exibe esses metadados na UI.
