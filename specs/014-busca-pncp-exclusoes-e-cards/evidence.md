# Evidências de implementação — Spec 014

Data: 14/09/2026. As verificações abaixo usam somente a API local e fixtures versionadas; não tratam o contador do portal PNCP como universo completo.

## Linha de base local

Período local `20260914` a `20260914`, resposta `GET /api/v1/obras`:

| Consulta | Origem | Coletado | Após filtro | Cards na primeira página |
|---|---:|---:|---:|---:|
| sem expressão | banco local | 133 | 133 | 15 |
| `pavimentacao -drenagem` | banco local | 133 | 9 | 9 |

A segunda consulta registrou 7 exclusões explícitas. A primeira emitiu cursor e a página seguinte retornou outros 15 cards, preservando o mesmo snapshot de 133 registros.

No frontend, a troca de UF, modalidade, ordenação, pavimentação, expressão ou escopo filtra o último conjunto recebido. Ela não chama o PNCP; apenas mudança de período, ausência de dados locais para o período ou **Atualizar Dados** inicia coleta externa.

## Regressões determinísticas

- Parser, fixture anotada, escopos, exclusões e auditoria: 16 testes.
- Integração antes de paginação, deduplicação, página progressiva e cursor: 5 testes.
- Tipo de contratação, schema e persistência: 6 testes.
- Frontend (chips, card, detalhe, filtro e expressão local): 17 testes.

Uma tentativa limitada de atualização PNCP (`modalidade=4`, uma página) foi tratada como indisponibilidade externa e retornou o fallback local com `origem=banco_local`, sem marcar os dados locais como resposta PNCP. Por isso, T014-16 permanece pendente de uma janela de disponibilidade do serviço externo.
