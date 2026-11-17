# Spec 008 — Classificador/Filtro de Obras por Palavras-Chave

**Origem:** `backend/services/pncp_service.py:92` — filtro baseado em substring simples (`in`), risco de falsos positivos/negativos (ex. "hospitalar", "cabo elétrico").
**Fase:** 3 — Qualidade Funcional · **Bloqueia produção:** Não (mas é o maior risco funcional a médio prazo)

## Contexto

O filtro que decide se uma licitação é "obra" usa comparação de substring (`in`), o que:
- exclui obras hospitalares legítimas por causa da palavra "hospitalar";
- exclui obras elétricas por causa de "cabo elétrico";
- inclui falsos positivos por buscar substrings dentro de outras palavras;
- perde obras descritas com vocabulário diferente do esperado.

## Requisitos

| ID | Requisito |
|---|---|
| R008-1 | O sistema DEVE comparar palavras inteiras (word boundaries), não substrings arbitrárias. |
| R008-2 | O sistema DEVE calcular uma pontuação de relevância por item, combinando termos positivos, negativos e de contexto, em vez de uma decisão binária simples. |
| R008-3 | O sistema DEVE manter uma base de casos aprovados/rejeitados para avaliação de precisão e cobertura do filtro. |
| R008-4 | O sistema DEVE permitir revisão manual de resultados com pontuação intermediária (duvidosos). |
| R008-5 | O sistema DEVE medir e reportar precisão e cobertura (precision/recall) do filtro contra a base de casos. |

## Critérios de aceitação

- [ ] Casos conhecidos de falso positivo ("cabo elétrico") e falso negativo ("hospitalar") do relatório original passam a ser classificados corretamente.
- [ ] Teste automatizado roda a base de casos e reporta precisão/cobertura a cada execução (regressão do classificador).
- [ ] Itens em zona duvidosa aparecem marcados como pendentes de revisão manual, não descartados nem aprovados automaticamente.
