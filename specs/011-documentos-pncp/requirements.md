# Plano de Execução — Documentos das Licitações PNCP

**Status:** plano para implementação da funcionalidade  
**Versão:** 1.0  
**Data:** 2026-09-02  
**Idioma da interface:** português do Brasil (`pt-BR`)

## 1. Origem e interpretação

Este plano usa o arquivo `SINAPI_EXCEL_ADDIN_SPEC.md` como referência de organização, detalhamento e ordem de execução. O arquivo de referência descreve outro produto e outro stack; suas instruções de Excel, SINAPI, Kotlin, Spring Boot e Office.js não fazem parte deste projeto e não serão importadas.

As decisões deste plano são específicas do sistema de Captação de Obras Públicas e prevalecem sobre o documento de referência:

- frontend React/Vite existente;
- backend FastAPI/Python existente;
- banco local já utilizado como fallback;
- PNCP como fonte externa;
- consulta de documentos somente quando o usuário abrir os detalhes da obra;
- nenhuma mudança na busca ou no filtro de obras além do necessário para transportar os identificadores.

## 2. Objetivo

Permitir que o usuário abra o detalhe de uma obra/licitação e visualize os documentos publicados para aquela contratação no PNCP, com título, tipo, data de publicação e link para abertura/download.

O produto deve apresentar esses arquivos como **documentos publicados no PNCP**. A primeira versão não deve afirmar que a lista é uma checklist jurídica completa nem marcar documentos como obrigatórios ou ausentes sem uma regra específica.

## 3. Base técnica do PNCP

O Manual de Integração do PNCP documenta a contratação por `cnpj`, `ano` e `sequencial` e o serviço de documentos em:

```text
/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
```

O retorno documentado contém:

```text
documentos[].sequencialDocumento
documentos[].url
documentos[].tipoDocumentoId
documentos[].tipoDocumentoNome
documentos[].titulo
documentos[].dataPublicacaoPncp
```

Referências oficiais:

- [Manual de Integração PNCP](https://pncp.gov.br/manual/pt-br/latest/singlehtml/index.html)
- [Consulta de uma contratação](https://pncp.gov.br/manual/pt-br/latest/contratacao/consultar_uma_contratacao.html)
- [Manuais do PNCP](https://www.gov.br/pncp/pt-br/pncp/manuais)

O projeto mantém a busca geral em `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao`, mas a rota de arquivos foi validada em produção usando `https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos`. A contratação `87613022000105/2026/126` respondeu com HTTP 200 e uma lista direta de 24 documentos, sem necessidade de autenticação.

## 4. Escopo da entrega

### 4.1. Incluído

- rota própria do backend para buscar documentos de uma contratação;
- normalização do payload externo para um contrato estável do produto;
- validação de CNPJ, ano e sequencial;
- timeout, tratamento de erros HTTP, resposta vazia e JSON incompatível;
- cache curto em memória para evitar chamadas repetidas;
- consulta sob demanda quando a aba/modal de detalhes for aberta;
- exibição acessível dos documentos no detalhe da obra;
- estados de carregamento, vazio, erro, modo mock e identificadores ausentes;
- testes unitários da normalização e testes de integração do endpoint;
- documentação da funcionalidade e seus limites.

### 4.2. Não incluído nesta entrega

- análise automática do conteúdo de PDFs;
- checklist jurídico de documentos obrigatórios;
- classificação de documento como “faltante”, “irregular” ou “insuficiente”;
- download e armazenamento dos arquivos no banco local;
- consulta automática de documentos de atas, contratos ou termos posteriores;
- upload, edição ou exclusão de documentos no PNCP;
- consulta de documentos para todos os cards ao carregar a listagem;
- alteração do mecanismo atual de fallback da busca de obras.

## 5. Requisitos funcionais

**RF-001 — Identificação da contratação**  
O sistema deve consultar documentos somente quando possuir `cnpj`, `ano` e `sequencial` válidos.

**RF-002 — Integração encapsulada**  
Somente o backend deve chamar o PNCP. O frontend deve chamar exclusivamente a rota própria do backend.

**RF-003 — Contrato normalizado**  
O backend deve devolver campos em `snake_case`, sem expor nomes ou estrutura bruta do PNCP ao frontend.

**RF-004 — Lista de documentos**  
Cada documento deve exibir, quando disponível, título, tipo, data de publicação e ação para abrir o arquivo.

**RF-005 — Consulta sob demanda**  
A abertura de um detalhe deve disparar no máximo uma consulta ativa para aquela contratação. A listagem de cards não deve gerar consultas de documentos em massa.

**RF-006 — Resposta vazia**  
Se a contratação não possuir documentos retornados, o detalhe deve informar que nenhum documento foi disponibilizado ou localizado no PNCP.

**RF-007 — Falha externa**  
Timeout, indisponibilidade, erro HTTP ou payload incompatível devem produzir mensagem compreensível sem expor stack trace, credenciais ou payload completo.

**RF-008 — Resposta obsoleta**  
Se o usuário fechar o detalhe ou selecionar outra obra enquanto a consulta estiver em andamento, a resposta antiga não deve atualizar uma obra diferente.

**RF-009 — Modo mock/offline**  
Registros mockados ou sem identificadores devem apresentar uma mensagem explícita de que os documentos reais não podem ser consultados para aquele registro.

**RF-010 — Sem inferência jurídica**  
O texto da interface deve dizer “Documentos publicados no PNCP” e não “Documentos obrigatórios” nesta versão.

## 6. Requisitos não funcionais

**RNF-001 — Desempenho**  
A chamada deve ter timeout independente e feedback visual imediato no modal.

**RNF-002 — Resiliência**  
Uma falha na consulta de documentos não pode impedir a abertura ou a exibição dos demais dados da obra.

**RNF-003 — Segurança**  
URLs retornadas pelo PNCP devem ser aceitas como links somente quando forem HTTP/HTTPS. O backend não deve aceitar URL externa arbitrária como parâmetro do cliente.

**RNF-004 — Acessibilidade**  
Links, mensagens e estados de carregamento devem ser compreensíveis por teclado e leitor de tela, respeitando o sistema visual já existente.

**RNF-005 — Manutenibilidade**  
As regras de integração e normalização devem ficar no serviço PNCP; componentes React devem cuidar da apresentação e do estado local.

**RNF-006 — Compatibilidade**  
A solução deve preservar a resposta atual de `GET /api/v1/obras` para consumidores existentes.

## 7. Critérios de aceitação

- [x] Ao abrir os detalhes de uma obra real com identificadores válidos, o sistema consulta o backend de documentos.
- [x] O backend consulta o endpoint de arquivos da contratação no PNCP.
- [x] A interface exibe título, tipo e data quando fornecidos.
- [x] Cada documento possui ação para abrir/download quando há URL válida.
- [x] Nenhum documento é consultado para todos os cards durante o carregamento da lista.
- [x] O modal mostra carregamento enquanto aguarda a resposta.
- [x] Uma contratação sem documentos mostra estado vazio compreensível.
- [x] Um erro do PNCP mostra erro localizado na seção de documentos, mantendo o restante do detalhe disponível.
- [x] Um registro mockado ou sem identificadores não gera chamada inválida ao PNCP.
- [x] A mudança/fechamento do modal não permite atualização por resposta obsoleta.
- [x] O backend rejeita identificador de CNPJ com caracteres inválidos.
- [x] O backend não devolve URL com esquema diferente de HTTP/HTTPS.
- [x] Testes do backend cobrem normalização, resposta vazia, erro externo e contrato HTTP.
- [x] `ruff check backend`, `pytest`, `npm run lint` e `npm run build` passam, respeitando limitações existentes do ambiente.

## 8. Definição de pronto

A funcionalidade estará pronta quando os critérios acima forem atendidos, a documentação estiver atualizada e o fluxo manual de abrir uma obra real e visualizar seus documentos tiver sido validado ou, se o PNCP estiver indisponível, a limitação estiver registrada sem simular sucesso.
