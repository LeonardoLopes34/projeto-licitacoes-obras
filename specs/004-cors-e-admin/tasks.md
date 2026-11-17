# Tasks — Spec 004: CORS e Endpoints Administrativos

- [ ] Criar `Settings` (Pydantic `BaseSettings`) com `allowed_origins` e `admin_api_key` lidos de variável de ambiente (R004-1, R004-2)
- [ ] Atualizar `CORSMiddleware` em `backend/main.py:20` para usar `settings.allowed_origins` em vez de origem aberta (R004-1)
- [ ] Definir `.env.example` documentando `ALLOWED_ORIGINS` e `ADMIN_API_KEY` (sem valores reais) (R004-1, R004-2)
- [ ] Criar dependência `verificar_admin` validando header `X-Admin-Key` (R004-2, R004-3)
- [ ] Mover endpoints de `backend/main.py:94` (estatísticas sensíveis) e `:98` (limpeza de banco/mocks) para `admin_router` protegido (R004-2)
- [ ] Registrar `admin_router` na aplicação FastAPI (R004-2)
- [ ] Escrever teste de integração: chamada sem header retorna 401 (R004-3)
- [ ] Escrever teste de integração: chamada com header correto executa a ação (R004-2)
- [ ] Confirmar que `.env` real não está versionado (conecta com Spec 006)
