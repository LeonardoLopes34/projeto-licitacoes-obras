# Captação de Obras Públicas

Dashboard para localizar oportunidades de licitações de engenharia, construção,
reformas e pavimentação publicadas no Portal Nacional de Contratações Públicas
(PNCP).

## Arquitetura

- `backend/`: API FastAPI, integração com PNCP, classificação, persistência e rotas administrativas.
- `frontend/`: aplicação React/Vite com filtros, indicadores e detalhes da licitação.
- `alembic/`: migrações versionadas do banco de dados.
- `specs/`: especificações funcionais e técnicas que orientam a evolução do projeto.

As consultas ao PNCP são paginadas por modalidade e preservam metadados de
execução (`parcial`, páginas consultadas, páginas com erro e origem dos dados).
A API devolve no máximo 15 cards por resposta, com um cursor opaco assinado em
`paginacao.proximo_cursor`; o frontend usa esse cursor para navegar entre as
páginas sem carregar todos os cards no navegador.
A busca padrão começa nas licitações publicadas no dia atual, mas o período
pode ser alterado pelos filtros de data. O PNCP é
sempre consultado primeiro; somente uma falha de transporte, HTTP, timeout ou
resposta parcial com erro permite retornar o último resultado em cache ou os
registros salvos no banco. Uma resposta válida sem resultados permanece vazia.

Para evitar que a indisponibilidade do PNCP deixe a tela aguardando, cada
página consultada tem um limite configurável de 3 segundos
(`PNCP_TIMEOUT_SECONDS`). Quando a busca solicita todas as modalidades, elas são
consultadas em paralelo e uma modalidade lenta não bloqueia as demais. Ao atingir esse limite, o sistema consulta o
banco local. Após três falhas consecutivas, um circuit breaker bloqueia
novas chamadas ao PNCP por 30 segundos e usa o banco diretamente; depois disso,
permite uma tentativa de recuperação.

## Configuração

1. Configure o único arquivo `.env` na raiz do projeto (use `.env.example` como referência).
2. Defina `ADMIN_API_KEY` para habilitar as rotas administrativas.
3. Em produção, configure `DATABASE_URL`, `ALLOWED_ORIGINS`, `VITE_API_URL` e, se necessário,
   `PNCP_CA_BUNDLE` com o caminho do certificado CA confiável.

O backend usa SQLite local por padrão (`licitacoes_obras.db`) e aceita
PostgreSQL por meio de `DATABASE_URL`.

Em produção, o banco deve ser atualizado exclusivamente com `alembic upgrade
head`. O bootstrap automático de tabelas fica restrito aos ambientes de
desenvolvimento e teste.

### OCR local (Tesseract)

A análise de exigências usa primeiro a camada de texto do PDF e só envia para
OCR as páginas sem texto suficiente. Também aceita arquivos ZIP publicados pelo
PNCP: os PDFs internos são lidos exclusivamente em memória, com limites de
arquivos, páginas, tamanho descompactado e taxa de compressão. Instale o
Tesseract com os dados do idioma português (`por`) na máquina que executa o
backend. No Windows, informe o caminho do executável em `TESSERACT_CMD` se ele
não estiver no `PATH`, por exemplo `C:\Program Files\Tesseract-OCR\tesseract.exe`.
Valide a instalação com `tesseract --list-langs`; a saída deve incluir `por`.

Os limites do download, de PDFs dentro de ZIP, de páginas, DPI, tempo de OCR e
hosts permitidos estão em `.env.example`. O sistema não salva PDFs ou ZIPs;
persiste somente o resultado
normalizado, associado à contratação, hash do PDF e versão do analisador.

## Execução local

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn backend.main:app --reload
```

Frontend, em outro terminal:

```powershell
cd frontend
npm ci
npm run dev
```

O frontend lê `VITE_API_URL` e `VITE_SANDBOX_URL` do `.env` na raiz. Durante o
desenvolvimento, o Vite encaminha `/api` para `http://127.0.0.1:8000`; em
produção, configure o reverse proxy para compartilhar o mesmo domínio.

## Qualidade

```powershell
ruff check backend
pytest
cd frontend
npm run test
npm run lint
npm run build
```

## Rotas principais

- `GET /health`: estado operacional da aplicação e do Tesseract, sem expor configuração sensível.
- `GET /api/v1/obras`: consulta licitações por período, modalidade, UF e paginação. Aceita `tamanho_resultado` (1 a 15) e o `cursor` retornado pela resposta. O período padrão é o dia atual.
- `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos`: consulta, sob demanda, os documentos publicados de uma contratação. Em falha do PNCP, pode retornar o último snapshot persistido com `origem=cache_persistente` e `desatualizado=true`.
- `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias`: analisa, sob demanda, exigências de habilitação encontradas no edital. Use `?forcar=true` para reprocessar ignorando um resultado compatível em cache. Quando o PNCP estiver indisponível, a última análise compatível pode ser exibida como desatualizada.
- `GET /admin/database/stats`: estatísticas do banco, exige `X-Admin-Key`.
- `GET /admin/operations/metrics`: contadores operacionais do PNCP, análises e estado do OCR; exige `X-Admin-Key`.
- `POST /admin/database/cleanup?days=2`: remove registros locais expirados, exige `X-Admin-Key`.

A seção de documentos na aba de detalhes exibe os arquivos publicados pelo PNCP
(título, tipo, data e link). Ela não representa uma checklist jurídica de
documentos obrigatórios nem valida o conteúdo dos arquivos.

Quando a tela mostrar “resultado salvo anteriormente”, os dados são a última
versão persistida e podem estar desatualizados porque a consulta atual ao PNCP
falhou. PDFs brutos não são armazenados: somente a lista normalizada de
documentos e os resultados de análise são persistidos.

A seção “Exigências identificadas no edital” localiza evidências textuais de
habilitação do licitante e informa documento, página e trecho. Ela não verifica
uma empresa, não substitui a leitura do edital e não constitui parecer jurídico.
Cada item também recebe uma descrição semântica curta para leitura rápida no
card. Essa descrição é gerada por regras locais e conservadoras, sem copiar a
redação do PDF; o trecho original continua disponível em “Ver trecho original”
para conferência.

Os códigos de modalidade usados pelo domínio são `4` (Concorrência), `6`
(Pregão), `8` (Dispensa) e `0` (todas as modalidades suportadas).

Para evitar bloqueios do PNCP, a consulta usa por padrão no máximo uma página
por modalidade, com pelo menos 10 registros por página, e encerra a busca
normalmente ao receber `204 No Content`. Respostas `429` e erros temporários
recebem retry controlado; outros erros HTTP são contabilizados nos metadados. O
limite pode ser ajustado por `PNCP_MAX_PAGINAS` ou pelo parâmetro `max_paginas` da
API, respeitando o limite de 50 registros por página do PNCP.
