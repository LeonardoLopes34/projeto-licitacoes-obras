# Design — Spec 010: Suíte de Testes, Lint e Documentação

## Estrutura de testes do backend

```
backend/
  tests/
    unit/
      test_paginacao.py        # Spec 002
      test_filtro_obras.py     # Spec 008
      test_modelo_dados.py     # Spec 007
    integration/
      test_endpoints_obras.py  # Spec 003 (metadados de resposta)
      test_endpoints_admin.py  # Spec 004 (auth)
    fixtures/
      casos_filtro.json        # Spec 008
```

- Testes de integração usam `fastapi.testclient.TestClient` (ou `httpx.AsyncClient` para rotas assíncronas).
- Testes que dependem da API real do PNCP usam `respx`/`responses` para mockar as chamadas HTTP, evitando dependência de rede em CI.

## CI (exemplo GitHub Actions)

```yaml
name: ci
on: [pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r backend/requirements.txt --break-system-packages
      - run: ruff check backend/
      - run: pytest backend/tests
      - run: git diff --check
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm ci --prefix frontend
      - run: npm run lint --prefix frontend
      - run: npm run build --prefix frontend
```

## Estrutura do README

```markdown
# Projeto Licitações de Obras

## Visão geral
## Arquitetura (backend FastAPI + SQLite, frontend React + Vite, integração PNCP)
## Requisitos (Python x.x, Node x.x)
## Instalação
### Backend
### Frontend
## Variáveis de ambiente
(tabela: nome, onde configurar, exemplo, obrigatória?)
## Como rodar localmente
## Como rodar os testes
## Limitações conhecidas
```
