# Spec 005 — Configuração de Ambiente do Frontend (Vite)

**Origem:** `.env` na raiz do projeto (fora de `frontend/`); fallback hardcoded em `frontend/src/App.jsx:103` (`http://127.0.0.1:8000/api/v1/obras`).
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim

## Contexto

O `.env` está na raiz do repositório, mas o Vite roda dentro de `frontend/` e não o enxerga automaticamente. Isso faz o build de produção cair no fallback hardcoded de `localhost`, apontando o frontend publicado para uma API que não existe em produção.

## Requisitos

| ID | Requisito |
|---|---|
| R005-1 | O sistema DEVE ler a URL da API a partir de variáveis de ambiente específicas do Vite (`VITE_API_URL`), definidas em `frontend/.env.production` e `frontend/.env.development`. |
| R005-2 | O sistema NÃO DEVE conter URL de `localhost`/`127.0.0.1` como fallback no bundle de produção. |
| R005-3 | SE `VITE_API_URL` não estiver definida no build de produção ENTÃO o build DEVE falhar (fail-fast), não usar um fallback silencioso. |

## Critérios de aceitação

- [ ] `npm run build` falha claramente se `VITE_API_URL` ausente em produção.
- [ ] Bundle de produção (`dist/`) não contém a string `127.0.0.1` nem `localhost`.
- [ ] Build de desenvolvimento continua funcionando localmente apontando para `http://127.0.0.1:8000` via `.env.development`.
