# Tasks — Documentos das Licitações PNCP

Cada tarefa deve deixar o projeto executável ou registrar claramente o bloqueio encontrado.

## Fase 0 — Preparação e confirmação do contrato

- [x] **T-001 — Registrar a especificação**
  - criar requirements, design e tasks;
  - registrar que o arquivo SINAPI é somente referência estrutural;
  - registrar a ambiguidade dos prefixos `/api/consulta` e `/api/pncp`.

- [x] **T-002 — Confirmar o endpoint real de documentos**
  - validar a rota em Swagger ou chamada controlada;
  - verificar status 200, 204, 401/403 e formato do payload;
  - atualizar somente a constante do adaptador se o prefixo divergir;
  - validado com a contratação `87613022000105/2026/126`: HTTP 200, lista direta com 24 documentos e campos oficiais esperados.

## Fase 1 — Contrato e integração backend

- [x] **T-003 — Criar `DocumentoOut` e `ResultadoDocumentos`**
  - definir campos normalizados;
  - permitir campos opcionais retornados incompletos;
  - manter o contrato de `ObraOut` inalterado.

- [x] **T-004 — Implementar normalização**
  - mapear campos oficiais do PNCP;
  - aceitar wrapper `documentos`, `data` ou lista direta;
  - descartar registros sem sequencial;
  - filtrar URLs que não sejam HTTP/HTTPS;
  - deduplicar por sequencial preservando ordem.

- [x] **T-005 — Implementar consulta de documentos**
  - validar identificadores;
  - usar `httpx.AsyncClient` com TLS e timeout existentes;
  - tratar 204, 429, 5xx, timeout e JSON inválido;
  - criar cache TTL separado.

- [x] **T-006 — Expor rota FastAPI**
  - criar `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos`;
  - mapear erros para 422, 502 e 503;
  - devolver o contrato normalizado.

## Fase 2 — Integração da interface

- [x] **T-007 — Adicionar cliente em `frontend/src/api.js`**
  - montar caminho com encoding seguro;
  - aceitar `AbortSignal`;
  - converter mensagens HTTP em erro exibível.

- [x] **T-008 — Carregar documentos no detalhe**
  - iniciar consulta somente com modal aberto;
  - resetar estado quando a obra mudar;
  - abortar ou ignorar resposta obsoleta;
  - não consultar registros mockados/sem identificadores.

- [x] **T-009 — Exibir lista e estados**
  - criar seção acessível;
  - mostrar título, tipo, data e link;
  - adicionar loading, vazio, erro, retry e indisponibilidade de identificadores;
  - preservar o layout e os temas atuais.

## Fase 3 — Testes e documentação

- [x] **T-010 — Testar normalização e serviço**
  - payload oficial normal;
  - lista vazia/204;
  - campos ausentes;
  - URL inválida;
  - duplicidade;
  - erro externo.

- [x] **T-011 — Testar endpoint**
  - sucesso;
  - retorno vazio;
  - identificador inválido;
  - erro PNCP convertido corretamente.

- [x] **T-012 — Validar frontend**
  - lint;
  - build;
  - inspeção visual da seção no modal com resposta real do PNCP;
  - conferência de foco, teclado e links externos.

- [x] **T-013 — Executar validação final**
  - executar `ruff check backend`;
  - executar `pytest`;
  - executar `npm run lint`;
  - executar `npm run build`;
  - atualizar esta lista e registrar limitações do ambiente; a consulta geral pode operar em modo offline quando o PNCP excede o timeout, sem impedir a consulta sob demanda de documentos.

## Pós-entrega

- [ ] **T-014 — Checklist opcional de documentos**
  - somente iniciar com regra de negócio aprovada;
  - definir checklist por modalidade/categoria;
  - distinguir “não publicado”, “não localizado” e “não aplicável”;
  - nunca apresentar inferência automática como validação jurídica.

- [ ] **T-015 — Documentos relacionados**
  - avaliar documentos de atas, contratos e termos;
  - definir se serão exibidos em seções separadas;
  - manter a contratação principal separada dos atos posteriores.
