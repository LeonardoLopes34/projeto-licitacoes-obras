# Tasks — Análise de exigências de editais por PDF/OCR

As tarefas abaixo são apenas o plano. Nenhuma delas foi executada nesta etapa.

## Fase 0 — Decisões e amostra

- [x] **T-001 — Confirmar o significado de “empresa que vai executar”**
  - primeira versão limitada à habilitação do licitante;
  - obrigações da contratada e documentos de execução ficam fora do escopo;
  - proposta e planilha não entram no mesmo fluxo.

- [ ] **T-002 — Montar benchmark de editais**
  - selecionar entre 10 e 20 contratações reais;
  - incluir PDFs digitais, escaneados, com tabelas e anexos;
  - registrar manualmente algumas exigências por categoria e página;
  - não versionar documentos públicos grandes sem decisão de armazenamento.

- [x] **T-003 — Definir comportamento dos cards**
  - o clique no card abre o detalhe e inicia a análise;
  - o modal não espera o OCR para exibir os dados básicos da obra;
  - o card mostra resumo quando houver resultado em cache/persistência;
  - a necessidade de persistência entre reinícios será decidida em T-016.

## Fase 1 — Dependências e infraestrutura

- [ ] **T-004 — Reconciliar dependências do ambiente**
  - confirmar versões de `pypdf`, `pdfplumber`, `pdfminer.six`, `Pillow` e `pypdfium2`;
  - declarar no arquivo de dependências somente o que for usado;
  - validar instalação em ambiente limpo.

- [ ] **T-005 — Escolher o motor local de OCR**
  - estratégia local confirmada;
  - comparar Tesseract com outras alternativas locais somente se necessário;
  - avaliar idioma português, tabelas, números, siglas e instalação no Windows;
  - definir se o binário será pré-requisito do ambiente ou empacotado;
  - só instalar após a escolha técnica ser aprovada.

- [ ] **T-006 — Definir configurações e limites**
  - timeout de download;
  - limite de bytes e páginas;
  - DPI e idioma do OCR;
  - concorrência máxima;
  - TTL/cache e versão do analisador;
  - política de logs e retenção.

## Fase 2 — Download e leitura de PDF

- [ ] **T-007 — Criar downloader seguro do PNCP**
  - permitir somente hosts e esquemas autorizados;
  - bloquear SSRF, redirects externos e arquivos fora do limite;
  - validar assinatura PDF, content-type e tamanho;
  - calcular hash do arquivo;
  - testar timeout, 404, PDF inválido e arquivo protegido.

- [ ] **T-008 — Implementar extração de texto por página**
  - usar `pdfplumber` como caminho principal;
  - usar `pypdf`/`pdfminer.six` como fallback e diagnóstico;
  - registrar qualidade e erros por página;
  - manter o número de página compatível com a visualização humana.

- [ ] **T-009 — Implementar renderização para OCR**
  - usar `pypdfium2` ou Poppler conforme o benchmark;
  - renderizar somente páginas que precisarem;
  - limitar memória, DPI, resolução e concorrência;
  - criar fixture de página digital e página escaneada.

- [ ] **T-010 — Implementar adaptador OCR**
  - encapsular o motor escolhido;
  - configurar idioma português;
  - devolver texto, página, confiança e estado;
  - tratar ausência do binário, timeout e baixa qualidade;
  - não retornar sucesso total quando houver páginas ilegíveis.

## Fase 3 — Análise das exigências

- [ ] **T-011 — Criar seleção de edital e anexos**
  - priorizar metadados do PNCP e títulos;
  - identificar referências a anexos e documentos complementares;
  - manter documentos não selecionados visíveis como não analisados.

- [ ] **T-012 — Criar localizador de seções**
  - normalizar caixa e acentuação sem perder o texto original;
  - localizar habilitação, qualificação, regularidade e declarações;
  - respeitar títulos, numeração e limites de seção;
  - guardar páginas e trechos.

- [ ] **T-013 — Criar classificador determinístico inicial**
  - mapear categorias e termos;
  - diferenciar empresa, Administração e objeto do contrato;
  - marcar ambiguidades como revisão necessária;
  - não gerar itens sem evidência.

- [ ] **T-014 — Avaliar IA opcional**
  - somente após validar a camada determinística;
  - definir política de dados, custo e fornecedor/modelo;
  - exigir JSON validado e evidência presente no texto;
  - comparar ganho real contra regras simples.

- [ ] **T-015 — Criar contrato normalizado**
  - schemas de análise, documento analisado, categoria e exigência;
  - estados sucesso, parcial, vazio e erro;
  - confiança, origem do texto e versão do analisador;
  - preservar compatibilidade com `ResultadoDocumentos`.

## Fase 4 — Persistência, API e resiliência

- [ ] **T-016 — Decidir cache versus persistência**
  - usar cache em memória no spike;
  - se o resumo aparecer entre reinícios, criar modelo/tabela de análise;
  - indexar por `id_pncp`, hash e versão;
  - definir invalidação e reprocessamento.

- [ ] **T-017 — Expor endpoint de exigências**
  - criar `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias`;
  - processar sob demanda;
  - devolver estado parcial sem bloquear os demais dados da obra;
  - evitar chamadas repetidas concorrentes para a mesma contratação.

- [ ] **T-018 — Adicionar observabilidade**
  - registrar duração, páginas, OCR e estados;
  - não registrar PDFs completos ou conteúdo desnecessário;
  - adicionar métricas para falha de download, parsing e OCR.

## Fase 5 — Interface

- [ ] **T-019 — Exibir resumo nos cards**
  - mostrar quantidade/categorias somente quando houver análise;
  - mostrar estado não analisado, deixando claro que o processamento começa ao abrir o detalhe;
  - não consultar todos os cards ao carregar a listagem.

- [ ] **T-020 — Exibir detalhe rastreável**
  - agrupar exigências por categoria;
  - mostrar descrição original, documento, página, trecho e confiança;
  - manter seção de documentos publicados separada;
  - abrir fonte em nova aba com proteção de segurança.

- [ ] **T-021 — Tratar estados e acessibilidade**
  - carregando, sucesso, parcial, vazio, erro e revisão necessária;
  - foco, teclado, leitores de tela e feedback de progresso;
  - linguagem que não sugira parecer jurídico.

## Fase 6 — Testes e aceite

- [ ] **T-022 — Testar PDF e OCR**
  - PDF digital;
  - PDF escaneado;
  - tabelas e duas colunas;
  - caracteres quebrados;
  - página ilegível;
  - arquivo inválido/protegido;
  - limite de tamanho e páginas.

- [ ] **T-023 — Testar análise semântica**
  - categorias;
  - referências a anexos;
  - duplicidade;
  - ambiguidade;
  - evidência de página;
  - ausência de invenção de itens.

- [ ] **T-024 — Testar API e resiliência**
  - sucesso total e parcial;
  - cache e reprocessamento;
  - falha de download/OCR;
  - concorrência;
  - host não autorizado e redirect inseguro.

- [ ] **T-025 — Validar com benchmark manual**
  - comparar resultados com a anotação humana;
  - medir cobertura por seção e categoria;
  - revisar falsos positivos e omissões;
  - aprovar limiares antes de chamar a análise de “disponível”.

- [ ] **T-026 — Validar frontend e documentação**
  - lint e build;
  - fluxo de card para detalhe;
  - inspeção visual com PDF digital e escaneado;
  - atualizar README e esta spec;
  - registrar limitações conhecidas.

## Pós-entrega

- [ ] **T-027 — Acompanhar qualidade do OCR**
  - revisar amostras de baixa confiança;
  - atualizar regras sem apagar evidências anteriores;
  - versionar o analisador e reprocessar somente documentos afetados.

- [ ] **T-028 — Avaliar documentos de execução contratual**
  - somente após a habilitação estar estável;
  - separar garantia, ART/RRT, seguros, medições e obrigações;
  - confirmar regras de negócio antes de exibir como exigência.
