# Tasks — Spec 006: Higiene do Repositório Git

- [ ] Rodar `git status --ignored` e listar todos os arquivos funcionais não rastreados (R006-1)
- [ ] Criar/atualizar `.gitignore` cobrindo `__pycache__/`, `*.pyc`, `node_modules/`, `dist/`, `.env`, `*.db` (R006-2, R006-3)
- [ ] Remover `__pycache__` já versionado com `git rm -r --cached` (R006-2)
- [ ] Commit isolado apenas para `.gitignore` + remoção de artefatos (R006-2)
- [ ] Adicionar `backend/database.py`, `backend/models/`, `backend/services/db_service.py` ao controle de versão (R006-1)
- [ ] Avaliar `frontend/src/sandbox/NeitImportsApp.jsx`: manter documentado como sandbox ou remover (conecta com Spec 009) (R006-1)
- [ ] Commit isolado para os arquivos funcionais adicionados (R006-1)
- [ ] Validar em clone limpo: `git clone` + `pip install` + `npm install` + rodar backend e frontend sem erro de arquivo faltando (R006-1)
