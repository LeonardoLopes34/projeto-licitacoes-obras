# Spec 003 — Erros Não Devem Virar Sucesso Silencioso

**Origem:** `backend/main.py:55`, `backend/services/pncp_service.py:358,467` — exceções amplas retornando banco local ou lista vazia.
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim
**Depende de:** Spec 002 (metadados de paginação)

## Contexto

A aplicação captura praticamente qualquer exceção e retorna o banco local ou uma lista vazia, sem distinguir tipos de falha. Falhas de páginas individuais são ignoradas. O usuário pode receber uma lista incompleta acreditando que a consulta terminou corretamente.

## Requisitos

| ID | Requisito |
|---|---|
| R003-1 | O sistema NÃO DEVE capturar exceções genéricas (`except Exception`) sem diferenciar o tipo de falha (rede, timeout, parsing, banco). |
| R003-2 | QUANDO uma página da API do PNCP falhar ENTÃO o sistema DEVE registrar essa falha individualmente e contabilizá-la na resposta, não apenas ignorá-la. |
| R003-3 | O sistema DEVE retornar ao frontend um objeto de metadados de execução em toda resposta de busca, incluindo ao menos: `parcial`, `paginas_consultadas`, `paginas_com_erro`, `origem` (`"PNCP"` ou `"banco_local"`). |
| R003-4 | SE a origem dos dados for fallback local (não PNCP ao vivo) ENTÃO o sistema DEVE informar isso de forma visível na resposta. |

## Critérios de aceitação

- [ ] Resposta da API sempre contém o bloco de metadados (`parcial`, `paginas_consultadas`, `paginas_com_erro`, `origem`).
- [ ] Falha simulada em uma página não interrompe as demais, e é contabilizada em `paginas_com_erro`.
- [ ] Fallback para banco local é visível no payload retornado.
- [ ] Não existe nenhum `except Exception` (ou equivalente genérico) sem log estruturado e sem re-raise/tratamento específico downstream.
