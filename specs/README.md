# Specs — Sistema de Licitações de Obras (PNCP)

**Stack:** Python 3.x + FastAPI (backend) · SQLite + SQLAlchemy (persistência) · React + Vite (frontend)
**Origem:** relatório de auditoria técnica do projeto `projeto-licitacoes-obras`
**Metodologia:** Spec-Driven Development — cada pasta abaixo é uma spec independente e rastreável, com `requirements.md` (o quê / por quê, em formato EARS), `design.md` (como, tecnicamente) e `tasks.md` (checklist de implementação). Nenhuma tarefa é considerada concluída sem o critério de aceitação associado (em `requirements.md`) verificado.

## Índice de specs

| # | Spec | Fase | Bloqueia produção? |
|---|---|---|---|
| 001 | [TLS e transporte seguro](./001-tls-e-transporte-seguro/) | 1 — Segurança/infra | Sim |
| 002 | [Paginação PNCP](./002-paginacao-pncp/) | 1 — Segurança/infra | Sim |
| 003 | [Tratamento de erros](./003-tratamento-de-erros/) | 1 — Segurança/infra | Sim |
| 004 | [CORS e endpoints admin](./004-cors-e-admin/) | 1 — Segurança/infra | Sim |
| 005 | [Config de ambiente do frontend](./005-config-ambiente-frontend/) | 1 — Segurança/infra | Sim |
| 006 | [Higiene do Git](./006-higiene-git/) | 1 — Segurança/infra | Sim |
| 007 | [Modelo de dados e persistência](./007-modelo-de-dados/) | 2 — Dados | Parcial (Numeric/CNPJ/Alembic bloqueiam; cache/upsert não) |
| 008 | [Filtro de obras](./008-filtro-de-obras/) | 3 — Qualidade funcional | Não (maior risco a médio prazo) |
| 009 | [Frontend e acessibilidade](./009-frontend-acessibilidade/) | 4 — Frontend | Não |
| 010 | [Qualidade geral e testes](./010-qualidade-e-testes/) | 5 — Fechamento | Recomendado antes de release estável |
| 011 | [Documentos PNCP](./011-documentos-pncp/) | 3 — Funcionalidade | Não |
| 012 | [Análise de exigências por PDF/OCR](./012-analise-exigencias-ocr/) | 3 — Funcionalidade | Não |

## Formato de requisito (EARS)

- **Ubíquo:** "O sistema DEVE..."
- **Evento:** "QUANDO `<evento>` ENTÃO o sistema DEVE `<resposta>`"
- **Estado:** "ENQUANTO `<estado>` o sistema DEVE `<comportamento>`"
- **Indesejado:** "SE `<condição indesejada>` ENTÃO o sistema DEVE `<mitigação>`"

## Roadmap de execução (ordem recomendada)

1. **Segurança e infraestrutura** — specs 001, 004, 005, 006
2. **Confiabilidade de dados do PNCP** — specs 002, 003
3. **Modelo de dados e persistência** — spec 007
4. **Testes de base** — parte da spec 010, cobrindo specs 002–004 e 007
5. **Frontend e acessibilidade** — spec 009
6. **Higiene e organização final** — conclusão da spec 006, limpeza de legados (spec 009)
7. **Filtro de obras** (melhoria orientada a dados) — spec 008
8. **Qualidade geral consolidada** — fechamento da spec 010 (lint, README, whitespace)

## Definition of Done (aplicável a toda spec)

- [ ] Requisitos da spec implementados e rastreáveis no código (nome de função/comentário referenciando o ID do requisito, quando fizer sentido).
- [ ] Critérios de aceitação da spec (em `requirements.md`) verificados manualmente ou via teste automatizado.
- [ ] Nenhuma regressão introduzida nas specs já concluídas (suíte de testes completa passando).
- [ ] Lint limpo (`ruff`/`flake8` no backend, `eslint` no frontend).
- [ ] `design.md` da spec atualizado caso a implementação real tenha divergido do design original.
- [ ] Revisão de código confirmando que nenhum item da Fase 1 (segurança) foi reintroduzido inadvertidamente.
