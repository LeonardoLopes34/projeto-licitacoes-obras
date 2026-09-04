# Spec 010 — Suíte de Testes, Lint e Documentação

**Origem:** ausência de suíte automatizada real para o backend; 7 warnings de lint no frontend; espaços em branco no fim de linha (`git diff --check`); `README.md` mínimo.
**Fase:** 5 — Fechamento · **Bloqueia produção:** Recomendado antes de release estável
**Depende de:** Specs 002, 003, 004, 007, 008 (cobertura de teste destas specs)

## Requisitos

| ID | Requisito |
|---|---|
| R010-1 | O backend DEVE ter uma suíte de testes automatizados (`pytest`) cobrindo ao menos: paginação (Spec 002), tratamento de erros/metadados (Spec 003), autenticação de rotas admin (Spec 004), modelo de dados (Spec 007) e filtro de obras (Spec 008). |
| R010-2 | O sistema DEVE rodar com zero warnings de lint (`npm run lint` no frontend, `ruff`/`flake8` no backend). |
| R010-3 | O sistema NÃO DEVE conter espaços em branco no final de linha (`git diff --check` limpo). |
| R010-4 | O `README.md` DEVE descrever: como rodar backend e frontend localmente, variáveis de ambiente necessárias, como rodar os testes, e a arquitetura geral do sistema. |

## Critérios de aceitação

- [ ] `pytest` cobre os cenários críticos das specs 002, 003, 004, 007 e 008.
- [ ] `npm run lint` e `ruff`/`flake8` retornam zero warnings/erros.
- [ ] `git diff --check` sem apontamentos.
- [ ] `README.md` permite a um novo desenvolvedor rodar o projeto do zero seguindo apenas o documento.
