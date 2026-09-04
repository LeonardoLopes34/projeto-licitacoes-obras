# Spec 002 — Paginação Completa da API do PNCP

**Origem:** `backend/services/pncp_service.py:318,324` — `max_paginas` usado parcialmente como quantidade de dias.
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim
**Referência externa:** Manual oficial de APIs de Consultas do PNCP (paginação via `pagina` e `tamanhoPagina`)

## Contexto

Em alguns cenários, a busca percorre somente os últimos dias do intervalo solicitado e ignora o restante, porque o parâmetro `max_paginas` está sendo reaproveitado como se fosse quantidade de dias. Isso causa perda silenciosa de dados.

## Requisitos

| ID | Requisito |
|---|---|
| R002-1 | O sistema DEVE paginar usando os parâmetros oficiais `pagina` e `tamanhoPagina`, conforme o Manual de APIs de Consultas do PNCP. |
| R002-2 | QUANDO `totalRegistros` retornado pela API for maior que os registros já coletados ENTÃO o sistema DEVE continuar buscando páginas subsequentes. |
| R002-3 | SE o resultado retornado ao usuário for parcial (limite de páginas atingido, erro em página) ENTÃO o sistema DEVE sinalizar isso explicitamente na resposta. |
| R002-4 | O sistema NÃO DEVE reutilizar o parâmetro de quantidade de páginas como se fosse quantidade de dias do intervalo de busca. |

## Critérios de aceitação

- [ ] Busca cobre 100% do intervalo de datas solicitado (validado comparando contagem obtida com `totalRegistros` da API).
- [ ] `intervalo_dias` (janela de datas) e `max_paginas` (limite de paginação) são parâmetros distintos e independentes no código.
- [ ] Teste unitário simula `totalRegistros` maior que uma página e valida que todas as páginas necessárias são buscadas.
- [ ] Teste unitário cobre o caso de `max_paginas` atingido antes do fim dos registros, validando que o sistema sinaliza parcialidade (integra com Spec 003).
