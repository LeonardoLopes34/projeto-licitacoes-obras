# Linha de base — pipeline documental da Spec 015

**Finalidade deste registro:** mapear o comportamento existente antes de qualquer
indexação vetorial. Este arquivo não aprova um provedor, não fixa dimensão de
vetor, não provisiona PostgreSQL e não marca nenhuma tarefa da spec como
concluída.

**Dados incluídos:** somente nomes de módulos, contratos, limites de
configuração e referências a testes sintéticos. Não há PDF, ZIP, URL concreta,
texto de edital, credencial ou resultado de consulta PNCP neste documento.

## Método e evidências reproduzíveis

A linha de base foi obtida por inspeção dos módulos abaixo e dos testes unitários
existentes. Os testes citados usam doubles/fixtures sintéticos; eles são a forma
de verificar os comportamentos sem baixar nem registrar um documento real.

| Comportamento | Evidência no código | Teste existente verificável |
| --- | --- | --- |
| Normalização, cache e snapshot da lista de documentos | `backend/services/pncp_service.py` (`normalizar_documentos_pncp`, `_registrar_documentos_reais`, `buscar_documentos_pncp`) e `backend/services/document_snapshot_repository.py` | `backend/tests/unit/test_documentos_pncp.py` |
| Download HTTPS, validação de redirecionamento, limites e ZIP em memória | `backend/services/pdf_download_service.py` (`validar_url_documento`, `baixar_pdf_pncp`, `extrair_pdfs_zip`) | `backend/tests/unit/test_pdf_download_service.py` |
| Extração por página e seleção de páginas para OCR | `backend/services/pdf_text_service.py` (`extrair_texto_pdf`, `renderizar_pagina_para_ocr`) | `backend/tests/unit/test_pdf_text_service.py` |
| OCR local, idioma e confiança | `backend/services/ocr_service.py` (`TesseractOcrService.reconhecer`) | `backend/tests/unit/test_ocr_service.py` |
| Orquestração, limites, PDF dentro de ZIP, resultado parcial e cache de exigências | `backend/services/edital_analysis_service.py` (`EditalAnalysisService`) | `backend/tests/unit/test_edital_analysis_service.py` |
| Persistência atual sem binário bruto | `backend/models/document_snapshot_model.py`, `backend/models/edital_analysis_model.py` e seus repositórios | `backend/tests/unit/test_document_snapshot_repository.py` e `backend/tests/unit/test_edital_analysis_repository.py` |
| Corpus anotado sintético e ausência de bytes brutos na persistência de análise | `tests/fixtures/corpus_indexacao_015.json` | `backend/tests/unit/test_corpus_indexacao_015.py` |

Uma execução local que não consulta o PNCP e evita cache do pytest pode usar:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider `
  backend/tests/unit/test_documentos_pncp.py `
  backend/tests/unit/test_pdf_download_service.py `
  backend/tests/unit/test_pdf_text_service.py `
  backend/tests/unit/test_ocr_service.py `
  backend/tests/unit/test_edital_analysis_service.py
```

**Registro de execução local (16/09/2026):** os cinco arquivos acima concluíram
com **46 testes aprovados em 1,72 s**. Eles verificam a linha de base sintética,
não uma infraestrutura vetorial. A validação PostgreSQL/`pgvector` permanece
bloqueada conforme a seção final.

## Mapa preciso do pipeline atual

```text
rota de exigências
  -> EditalAnalysisService.analisar_contratacao
  -> buscar_documentos_pncp
  -> lista normalizada + snapshot de metadados
  -> seleção voltada a exigências de habilitação
  -> baixar_pdf_pncp (PDF ou ZIP, em memória)
  -> extrair_texto_pdf por página
  -> OCR somente nas páginas insuficientes/sem texto
  -> filtro/regras de exigências
  -> cache em memória + resultado normalizado persistido
```

### 1. Lista e manifesto de documentos PNCP

- A rota `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias` em
  `backend/main.py` chama `EditalAnalysisService.analisar_contratacao` sob o
  timeout `edital_analysis_timeout_seconds`.
- `analisar_contratacao` usa `buscar_documentos_pncp` em
  `backend/services/pncp_service.py`. A chave da contratação é
  `cnpj:ano:sequencial`.
- `normalizar_documentos_pncp` mantém apenas identificador sequencial, URL,
  tipo, título e data de publicação; remove duplicatas pelo sequencial e rejeita
  identificadores inválidos.
- `_registrar_documentos_reais` grava de modo auxiliar um snapshot da lista.
  Falhar ao persistir o snapshot não descarta a resposta remota. Em falha do
  PNCP, `buscar_documentos_pncp` pode devolver o último snapshot marcado como
  desatualizado.
- `DocumentSnapshotModel` armazena a chave da contratação, hash da lista e JSON
  normalizado de metadados. Não possui coluna para bytes de PDF/ZIP.

**Implicação para a Spec 015:** o hash de `documentos_hash` é um manifesto da
lista publicada, não a identidade do conteúdo de cada PDF. A indexação futura
deve acrescentar o SHA-256 de cada PDF efetivamente obtido, inclusive dos PDFs
internos de um ZIP.

### 2. Seleção e download seguro

- `selecionar_documentos_para_analise` em
  `backend/services/edital_analysis_service.py` prioriza edital e anexos ligados
  à habilitação. Documentos complementares continuam visíveis no resultado, mas
  não entram automaticamente na análise.
- Para cada documento selecionado, `_download_document` chama
  `baixar_pdf_pncp` em `backend/services/pdf_download_service.py`.
- O downloader aceita somente HTTPS, host autorizado em
  `pncp_document_hosts`, sem credenciais na URL e porta padrão; revalida os
  redirecionamentos. Também valida tipo/assinatura, tamanho anunciado e tamanho
  efetivamente recebido.
- `DownloadedPdf` mantém `content`, `sha256`, URL final e tipo apenas em
  memória. `DownloadedZip` representa o ZIP por seus `DownloadedPdf` internos;
  o ZIP bruto não é extraído para o disco nem persistido.
- `extrair_pdfs_zip` normaliza os nomes internos, rejeita path traversal,
  criptografia, excesso de entradas, taxa de compressão insegura e excesso de
  bytes. Cada PDF interno recebe seu próprio hash de conteúdo.

**Implicação para a Spec 015:** o downloader é o ponto obrigatório de reuso de
R015-1. A seleção atual, porém, é específica de habilitação e não pode definir
sozinha o corpus completo de um edital.

### 3. Extração por página e OCR seletivo

- `extrair_texto_pdf` em `backend/services/pdf_text_service.py` opera sobre
  `bytes` em memória e retorna `PdfTextResult` com uma `PageText` por página.
  Tenta `pdfplumber` e usa `pypdf` como fallback.
- Cada `PageText` preserva número da página, texto, contagem de caracteres,
  proporção imprimível, estado e possível erro. Texto é suficiente quando passa
  o limiar configurado de caracteres e 85% de caracteres imprimíveis.
- `EditalAnalysisService._analisar_pdf` envia apenas páginas com `sem_texto` ou
  `texto_insuficiente` para `renderizar_pagina_para_ocr` e depois para
  `TesseractOcrService.reconhecer`.
- O orquestrador anexa à página a origem `pdf_texto` ou `ocr` e, para OCR, a
  confiança retornada pelo Tesseract. Erros de uma página/PDF produzem análise
  parcial em vez de esconder o problema.

**Implicação para a Spec 015:** a informação necessária já existe durante a
execução, mas é representada internamente como tuplas dentro do serviço de
exigências. Será necessário extrair um contrato reutilizável por página que
preserve origem, confiança, erros e offsets antes do filtro de domínio.

### 4. Análise de exigências e persistência atual

- Após a extração, `localizar_exigencias_com_metricas` aplica regras de
  habilitação a segmentos de texto. Esse resultado é deliberadamente um
  subconjunto do edital e não pode ser usado como corpus vetorial.
- O cache em memória é uma `TTLCache` indexada por contratação, hash do
  manifesto de download e `edital_analyzer_version`. Processamentos simultâneos
  da mesma contratação são compartilhados em memória por `_inflight`.
- `edital_analyses` persiste `contratacao_chave`, `documentos_hash`, versão,
  estado e o JSON de `ResultadoExigencias`, sob unicidade composta. Não há
  coluna de PDF/ZIP bruto nem vetor.
- O JSON do resultado pode conter evidências textuais selecionadas pela análise;
  portanto, a ausência de binários não equivale a uma política de retenção para
  todo texto derivado. A Spec 015 precisa tratar explicitamente a retenção dos
  chunks e a minimização de telemetria.
- `backend/main.py` expõe métricas administrativas de PNCP, análise e OCR, mas
  não há métricas por estágio de indexação, fila persistente ou provedor de
  embeddings.

## Limites atuais que a indexação deve respeitar

Os valores abaixo são os defaults de `backend/config.py`; a configuração de
ambiente pode torná-los mais restritivos. Eles são limites do pipeline atual,
não substituem os limites próprios de chunks, lotes, embeddings e custo de
R015-7.

| Grupo | Limite atual | Origem |
| --- | ---: | --- |
| Consulta PNCP | 1 requisição concorrente; intervalo de 2 s | `pncp_max_concurrent_requests`, `pncp_request_interval_seconds` |
| Download por tentativa | conexão 5 s; total 30 s; 2 retries | `edital_download_*` |
| PDF | 20 MiB; 150 páginas | `edital_pdf_max_bytes`, `edital_pdf_max_pages` |
| ZIP | 100 entradas; 10 PDFs; 60 MiB descompactados; razão 100:1; 150 páginas no total | `edital_zip_*` |
| Texto extraído | 80 caracteres e razão imprimível mínima de 0,85 para evitar OCR | `edital_text_min_characters` e `_status_texto` |
| OCR | 250 DPI; idioma `por`; 45 s por página | `edital_ocr_*` |
| Análises em paralelo | 2 ativas; fila em memória de até 8 esperas | `edital_analysis_concurrency`, `edital_analysis_queue_maxsize` |
| Contratação analisada | 20 documentos; 50 MiB; 300 páginas | `edital_analysis_max_*` |
| Resposta de exigências | 180 s | `edital_analysis_timeout_seconds` |

## Cobertura atual e gaps frente a R015

| Requisito | Situação da linha de base | Gap a fechar antes da aceitação |
| --- | --- | --- |
| R015-1 | Parcialmente atendido: download, PDF/ZIP em memória, extração e OCR seletivo já existem. | Separar a representação reutilizável por página e demonstrar, por teste de integração, que a indexação não grava bytes brutos. |
| R015-2 | Parcialmente atendido: páginas, ordem e texto existem durante a análise. | Não há chunker estável, offsets, sobreposição ou corpus além do filtro de habilitação. |
| R015-3 | Não atendido. | Não existem chunks, vetores, hashes por chunk, versões de extração/chunking ou metadados de citação completos. |
| R015-4 | Parcialmente atendido somente para cache de análise por hash/versão. | Não há deduplicação transacional de documentos/chunks nem prevenção de nova chamada ao provedor. |
| R015-5 | Não atendido. | Não há versões ativas/inativas, `superseded_at` nem ativação somente após conclusão completa. |
| R015-6 | Parcialmente atendido para download/OCR e resposta parcial. | Não há estado persistente de embeddings, retry controlado, lease ou recuperação após reinício. |
| R015-7 | Parcialmente atendido pelos limites acima. | Faltam limites de chunks, tokens, lotes, custo, workers e orçamento diário. |
| R015-8 | Não atendido. | Não há PostgreSQL/`pgvector`, migração de extensão nem bloqueio explícito de indexação real em SQLite. |
| R015-9 | Não atendido. | Não há repositório vetorial, filtros de proveniência ou consulta interna restrita. |
| R015-10 | Parcialmente atendido: há contadores PNCP/análise/OCR e erros seguros. | Faltam métricas/falhas por etapa de indexação e uma revisão explícita de redaction para texto, URL e credenciais. |
| R015-11 | Não atendido. | Não existe provedor, credencial explícita, identificador do conteúdo enviado ou chave de desativação. |
| R015-12 | Não atendido para dados vetoriais. | Não há política/rotina de inativação ou limpeza de chunks e vetores; a retenção atual é de dados de obras, não do futuro corpus. |
| R015-13 | Atendido na linha de base. | Preservar: não criar rota pública, frontend, chat, agente ou dependência de agente nesta spec. |

## Riscos identificados

1. **Corpus incompleto por acoplamento ao domínio:** o serviço existente escolhe
   documentos e segmentos para exigências. Reusar esse resultado excluiria texto
   relevante, contrariando o desenho da spec.
2. **Proveniência perdida na fronteira atual:** número da página, origem e
   confiança chegam ao orquestrador, mas não formam um contrato persistível
   independente. Offsets de caracteres e identidade de PDF interno de ZIP ainda
   não são propagados como dados de indexação.
3. **Idempotência e concorrência apenas locais:** `_inflight` e `TTLCache` são
   memória de um processo. Eles não fornecem exclusão mútua, retomada nem
   deduplicação entre processos/reinícios.
4. **Capacidade/custo sem orçamento vetorial:** os limites atuais protegem
   download/OCR, mas não impedem uma explosão de chunks, tokens, chamadas ao
   provedor ou custo diário.
5. **Privacidade e telemetria:** editar arquivos publicados não elimina a
   necessidade de minimização. Anexos podem conter dados pessoais; logs e
   métricas novos não podem registrar chunk integral, URL privada ou segredo.
6. **Versionamento inseguro se for in-place:** atualizar o mesmo registro ao
   mudar PDF, estratégia ou modelo misturaria resultados e impediria auditoria.
   A versão anterior só pode ser inativada após a nova ficar completa.
7. **SQLite como falso positivo:** o núcleo tem fallback SQLite e
   `Base.metadata.create_all` em desenvolvimento. Importar um modelo vetorial
   sem guarda explícita pode criar uma experiência aparentemente funcional, mas
   sem `pgvector` nem busca vetorial válida.
8. **Garantia de produção não demonstrada:** a busca interna de vizinhos,
   migrações, leases e expiração precisam ser testados em PostgreSQL descartável;
   testes SQLite não provam esses comportamentos.

## Bloqueios explícitos da Fase 0

### T015-02 — Política de dados e provedor de embeddings

**Bloqueado por decisão de produto/política ainda ausente.** A própria
`requirements.md` lista como pendente comparar alternativa hospedada e local,
aprovar formalmente se trechos podem sair do ambiente e somente então fixar
modelo, dimensão, versões e orçamento. Não há, no código atual, um provedor,
modelo aprovado, dimensão de vetor, credencial autorizada ou limite de custo
para registrar.

Sem essa decisão, é proibitivo e tecnicamente indefensável escolher por conta
própria a dimensão da coluna `vector`, enviar texto a um serviço externo ou
incluir uma chave em código, fixture ou documentação. A continuidade requer:

1. decisão formal sobre tratamento/transferência de dados;
2. modelo e identificador aprovados (local ou hospedado), dimensão e versão
   iniciais; e
3. orçamento mensurável de piloto, incluindo teto de custo e latência aceitável.

### T015-03 — PostgreSQL com `pgvector`

**Bloqueado por infraestrutura ainda não disponibilizada.** O código atual
suporta URLs PostgreSQL por meio do driver `psycopg2`, mas seu banco padrão é
SQLite (`backend/database.py`). A busca no repositório não encontrou migração
que execute `CREATE EXTENSION vector`, modelo com tipo vetorial, ambiente
descartável PostgreSQL/`pgvector` ou teste de vizinhos mais próximos; as únicas
referências a `pgvector` estão nos documentos da Spec 015.

Enquanto não houver uma instância descartável com a extensão instalada, não é
possível validar CA015-6 nem escolher HNSW/IVFFlat com segurança. A continuidade
requer:

1. ambiente de desenvolvimento/teste PostgreSQL isolado com `pgvector`;
2. procedimento de conexão sem credenciais versionadas;
3. migração que falhe de modo operacional claro quando a extensão estiver
   ausente; e
4. teste de migração e consulta de vizinhos filtrada por contratação, além de
   teste que confirme que SQLite deixa a indexação real desativada.

## Limite desta evidência

Esta linha de base não mede ainda uma amostra real de PDFs digitais,
digitalizados ou ZIPs e não comprova `recall@k`. O corpus anotado sintético e
reproduzível está em `tests/fixtures/corpus_indexacao_015.json`; ele cobre os
formatos e citações esperadas, mas a métrica de recuperação continua dependente
da decisão de T015-02. A amostra real de T015-01 também depende de uma seleção
permitida de referências sem dados sensíveis. Nenhuma implementação de
indexação, busca semântica, agente, chat, endpoint público ou frontend foi
introduzida por este artefato.

## Atualização de implementação — 16/09/2026

O limite acima descreve a fotografia da linha de base, anterior à implementação.
Nesta atualização, a Spec 015 recebeu extração reutilizável, chunking, fila
persistente, adaptadores OpenAI, modelos/migração pgvector, projeção no card e
retenção de derivados. A validação isolada aplicou `alembic upgrade head` e
`alembic check` em PostgreSQL 17 com pgvector e executou a busca interna
filtrada por contratação, documento, página e UF.

Essa validação não realizou chamada à OpenAI nem promove a feature para
produção. Permanecem pendentes uma amostra controlada com a conta aprovada,
métricas de qualidade/recall e a revisão operacional de privacidade e custo.
