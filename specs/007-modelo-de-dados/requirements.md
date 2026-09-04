# Spec 007 — Modelo de Dados e Persistência

**Origem:** datas como string livre; `modalidade` sem validação; `Float` para valores financeiros (`backend/models/obra_model.py:20`); `data_publicacao` como `String`; ausência de Alembic; limpeza de registros antigos condicionada a busca bem-sucedida (`backend/database.py:45`); consulta ao banco por item em vez de upsert em lote; cache global em memória sem expiração (`backend/services/pncp_service.py:8`); CNPJ alfanumérico (Manual de Integração PNCP v2.5, suporte a partir de julho/2026); dependências não usadas (`requests`, `pdfplumber`, `pypdf`, `asyncpg`, `apscheduler`).
**Fase:** 2 — Modelo de Dados e Persistência · **Bloqueia produção:** Parcial (Numeric/CNPJ/Alembic bloqueiam; cache/upsert em lote não são bloqueantes)

## Requisitos

| ID | Requisito |
|---|---|
| R007-1 | O sistema DEVE armazenar datas em colunas `DateTime`/`Date`, não `String` livre. |
| R007-2 | O sistema DEVE validar `modalidade` contra um conjunto fechado de valores válidos (ex.: 0, 4, 6) antes de persistir. |
| R007-3 | O sistema DEVE armazenar valores financeiros em `Numeric`, não `Float`, para evitar perda de precisão. |
| R007-4 | O sistema DEVE tratar `CNPJ` sempre como texto (`String`), aceitando formato alfanumérico, sem validação exclusivamente numérica. |
| R007-5 | O sistema DEVE usar Alembic para qualquer alteração de schema; `create_all()` não deve ser o único mecanismo de migração. |
| R007-6 | ENQUANTO o sistema estiver em execução, a limpeza de registros antigos DEVE ocorrer em rotina própria (agendada ou no startup), independente do sucesso da última busca ao PNCP. |
| R007-7 | O sistema DEVE preservar corretamente `numeroControlePNCP`, `CNPJ`, `ano`, `sequencial` e o payload original retornado pela API. |
| R007-8 | O sistema DEVE realizar upsert em lote (batch), não uma consulta ao banco por item. |
| R007-9 | O sistema DEVE substituir o cache global em memória sem expiração por uma solução com limite de tamanho e TTL real. |
| R007-10 | O sistema NÃO DEVE manter dependências não utilizadas (`requests`, `pdfplumber`, `pypdf`, `asyncpg`, `apscheduler`) a menos que haja plano concreto de uso. |

## Critérios de aceitação

- [ ] Migração Alembic aplicada sem perda de dados existentes.
- [ ] Teste unitário rejeita `modalidade` fora do conjunto válido.
- [ ] Teste unitário confirma que valores financeiros mantêm precisão decimal exata (ex. `R$ 1.234.567,89` não vira `1234567.8899999`).
- [ ] Teste unitário aceita CNPJ alfanumérico válido.
- [ ] Limpeza de registros antigos roda mesmo quando a última busca ao PNCP falhou.
- [ ] Benchmark mostra redução do número de queries no upsert (lote vs item a item).
- [ ] Cache tem TTL e `maxsize` configuráveis, testado com expiração.
- [ ] `requirements.txt` sem dependências órfãs (nenhum import correspondente no código).
