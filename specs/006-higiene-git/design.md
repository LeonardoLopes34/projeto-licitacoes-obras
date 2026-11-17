# Design — Spec 006: Higiene do Repositório Git

## Abordagem

1. Auditar o repositório com `git status --ignored` e comparar com os arquivos que o backend/frontend realmente importam, para identificar tudo que está fora do controle de versão mas é necessário.
2. Adicionar/atualizar `.gitignore` cobrindo artefatos de build e cache antes de adicionar os arquivos faltantes (para não versionar lixo junto).
3. Fazer commits isolados: um commit só para `.gitignore` + remoção de `__pycache__`, outro commit separado só para adicionar os arquivos funcionais faltantes.
4. `frontend/src/sandbox/NeitImportsApp.jsx` deve ser avaliado: se for código de experimentação sem uso em produção, decidir entre versionar como sandbox documentado ou remover (ver também Spec 009, limpeza de legados).

## `.gitignore` sugerido

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
*.egg-info/

# Node / Vite
node_modules/
frontend/dist/
frontend/.vite/

# Ambiente
.env
.env.local
.env.production.local

# Banco local (se aplicável)
*.db
*.sqlite3
```

## Comandos de limpeza

```bash
git rm -r --cached backend/__pycache__ 2>/dev/null
find . -name "__pycache__" -exec git rm -r --cached {} + 2>/dev/null
git add .gitignore
git commit -m "chore: adicionar .gitignore e remover __pycache__ versionado"

git add backend/database.py backend/models/ backend/services/db_service.py
git commit -m "fix: versionar arquivos funcionais do backend ausentes do Git"
```

## Impacto em outras specs

- Spec 004 depende de `.env` estar no `.gitignore` (chave administrativa não deve ir para o histórico).
