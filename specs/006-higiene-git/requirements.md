# Spec 006 — Higiene do Repositório Git

**Origem:** arquivos funcionais não rastreados (`backend/database.py`, `backend/models/`, `backend/services/db_service.py`, `frontend/src/sandbox/NeitImportsApp.jsx`); `__pycache__` versionado.
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim

## Contexto

Há arquivos funcionais essenciais fora do controle de versão e artefatos gerados (`__pycache__`) versionados por engano. Um commit parcial pode deixar o backend quebrado em outra máquina ou incluir binários desnecessários no histórico.

## Requisitos

| ID | Requisito |
|---|---|
| R006-1 | O sistema DEVE ter todo arquivo funcional necessário para rodar o backend e o frontend rastreado no Git. |
| R006-2 | O sistema NÃO DEVE versionar artefatos gerados (`__pycache__`, `*.pyc`, `dist/`, `node_modules/`). |
| R006-3 | O repositório DEVE conter `.gitignore` cobrindo artefatos Python e Node. |

## Critérios de aceitação

- [ ] `git status` limpo em checkout novo após `pip install` e `npm install`.
- [ ] Clonar o repositório em máquina limpa e rodar backend + frontend sem nenhum arquivo faltando.
- [ ] Nenhum diretório `__pycache__` ou arquivo `.pyc` presente no histórico do Git após a limpeza.
