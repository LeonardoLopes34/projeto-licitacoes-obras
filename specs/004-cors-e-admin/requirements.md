# Spec 004 — CORS e Endpoints Administrativos

**Origem:** `backend/main.py:20` (CORS aberto), `backend/main.py:94,98` (endpoints públicos de estatísticas, limpeza de banco e ativação de mocks).
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim

## Contexto

O backend aceita qualquer origem via CORS e expõe endpoints administrativos (estatísticas, limpeza de banco, ativação de mocks) sem autenticação. Em produção isso permite que qualquer site de terceiros chame a API do usuário e que qualquer pessoa execute ações destrutivas (ex. limpar o banco).

## Requisitos

| ID | Requisito |
|---|---|
| R004-1 | O sistema DEVE restringir CORS a uma lista explícita de origens permitidas por ambiente (dev/staging/prod), nunca `allow_origins=["*"]` em produção. |
| R004-2 | O sistema DEVE exigir autenticação e autorização em endpoints administrativos (estatísticas sensíveis, limpeza de banco, ativação de mocks). |
| R004-3 | SE uma requisição não autenticada acessar um endpoint administrativo ENTÃO o sistema DEVE retornar `401/403` sem executar a ação. |

## Critérios de aceitação

- [ ] `allow_origins` em produção é uma lista fechada de domínios conhecidos, lida de variável de ambiente.
- [ ] Endpoints administrativos (`/admin/*` ou equivalentes) retornam 401/403 sem credencial válida.
- [ ] Endpoints administrativos executam a ação normalmente com credencial válida.
- [ ] Teste de integração cobre acesso negado e acesso autorizado para cada endpoint administrativo.
