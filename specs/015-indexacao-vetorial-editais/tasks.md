# Tasks — Spec 015: Indexação vetorial de editais

**Status:** implementação interna concluída; a validação de qualidade com uma amostra OpenAI controlada e a revisão operacional de produção continuam pendentes.
**Restrição preservada:** não implementar agente conversacional, busca pública, chat ou interface nova. A API OpenAI é usada somente no processamento interno de embeddings e análise estruturada dos editais.
**Regra de conclusão:** marcar uma tarefa somente depois de verificar os critérios CA015 correspondentes em `requirements.md` e registrar a evidência.

## Fase 0 — Decisões, dados de referência e ambiente

- [ ] **T015-01 — Registrar a linha de base do pipeline documental** (R015-1, R015-6, R015-7)
  - Mapear os pontos de download, extração, OCR, análise e persistência atuais.
  - Medir uma amostra controlada de PDFs digitais, escaneados e ZIPs: páginas, caracteres, OCR, tempo e falhas.
  - Confirmar, por inspeção e teste, que PDFs/ZIPs não são persistidos.
  - **Aceite:** CA015-1 e uma evidência versionada sem dados sensíveis ou arquivos brutos.

- [ ] **T015-02 — Registrar OpenAI, modelos small e política de dados** (R015-3, R015-11, R015-14, R015-20)
  - Registrar OpenAI como provedor dos embeddings e da análise estruturada desta fase.
  - Fixar `text-embedding-3-small` para embeddings e uma variante small/mini de menor custo em `OPENAI_ANALYSIS_MODEL`; confirmar o nome disponível na conta na implementação.
  - Registrar que o envio de trechos à OpenAI está aprovado, incluindo a conta/projeto, retenção aplicável e tratamento de dados pessoais.
  - Fixar dimensão, versões de prompt/schema, orçamento mensurável e política de reprocessamento.
  - **Aceite:** decisão documentada; nenhuma credencial inserida em código, fixtures ou documentação pública.

- [x] **T015-03 — Preparar infraestrutura PostgreSQL com pgvector** (R015-8)
  - Criar ambiente descartável de desenvolvimento/teste com extensão disponível.
  - Definir o comportamento explícito em SQLite: núcleo funcional continua disponível, indexação vetorial não é ativada.
  - Validar criação da extensão, conexão, migração vazia e operação básica de vetor no ambiente descartável.
  - **Aceite:** CA015-6 para banco vazio, sem tocar no banco local existente.

- [ ] **T015-04 — Criar corpus anotado e métricas de recuperação** (R015-2, R015-9)
  - Preparar referências permitidas, anonimizadas ou sintéticas que cubram PDF digital, OCR, tabelas, listas e ZIP.
  - Para cada pergunta de validação, registrar documento, página e trecho esperado.
  - Definir metas de `recall@k`, latência, custo, taxa de OCR e critérios de não regressão.
  - **Aceite:** CA015-9 possui casos reproduzíveis independentes do PNCP em tempo real.

## Fase 1 — Contratos, modelos e migrações

- [x] **T015-05 — Criar contratos de configuração e estados da indexação/análise** (R015-6, R015-7, R015-10, R015-11, R015-18, R015-20)
  - Adicionar configurações explícitas, desabilitadas por padrão, para PostgreSQL/pgvector, fila, capacidade, orçamento, retenção e OpenAI.
  - Normalizar `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_ANALYSIS_MODEL`, versão de prompt/schema, timeout e limite de tokens.
  - Modelar estados de documento/job/análise, códigos de erro seguros e transições permitidas.
  - Validar configuração incompleta e impedir ativação com SQLite, chave ausente ou modelo não configurado.
  - **Aceite:** CA015-5, CA015-8 e CA015-16 para validação, sem chamada externa acidental.

- [x] **T015-06 — Criar migração de documentos, chunks, jobs e análises de requisitos** (R015-3, R015-4, R015-5, R015-8, R015-12, R015-15, R015-17)
  - Criar `indexed_documents`, `document_chunks`, `document_index_jobs`, `document_requirement_analyses` e `document_requirement_items`, com restrições de unicidade, filtros e relações.
  - Instalar/validar `pgvector`, dimensão fixa aprovada e índices vetoriais no banco PostgreSQL descartável.
  - Guardar modelo de análise, versão do prompt/schema, chunks usados, tokens, custo estimado e estado sem misturar com o cache local legado.
  - Projetar migração e downgrade sem editar revisões já aplicadas; manter SQLite fora das operações vetoriais reais.
  - **Aceite:** CA015-2, CA015-3, CA015-4, CA015-6 e CA015-14 em banco descartável.

- [x] **T015-07 — Implementar repositórios idempotentes e ciclo de vida** (R015-3, R015-4, R015-5, R015-9, R015-12)
  - Persistir documento/chunks em transação curta, sem sessão cruzando threads.
  - Garantir unicidade por conteúdo e versão; ativar a nova versão somente quando completa.
  - Implementar inativação/retenção e filtros obrigatórios de proveniência.
  - **Aceite:** CA015-3, CA015-4 e CA015-6, incluindo concorrência e reprocessamento.

## Fase 2 — Extração, chunks e embeddings

- [x] **T015-08 — Extrair um resultado textual reutilizável para indexação** (R015-1, R015-2)
  - Separar do fluxo de exigências uma representação por página que preserve texto, origem, qualidade e erros.
  - Reutilizar download, limites, PDF/ZIP e OCR existentes; não fazer cópia de bytes em disco.
  - Cobrir documentos digitais, OCR seletivo, PDFs internos de ZIP e falhas parciais.
  - **Aceite:** CA015-1 e CA015-2; os testes existentes de exigências permanecem aprovados.

- [x] **T015-09 — Implementar chunker versionado e limitado** (R015-2, R015-3, R015-7)
  - Delimitar chunks por parágrafo/seção antes de usar corte por tamanho; preservar página e offsets.
  - Aplicar sobreposição controlada, hash do texto e limites de chunks/tokens por página e documento.
  - Registrar estado parcial ou rejeitado quando exceder orçamento, sem omissão silenciosa.
  - **Aceite:** CA015-2 e CA015-8 com fixtures de texto contínuo, listas e OCR.

- [x] **T015-10 — Implementar adaptador de embeddings OpenAI em lotes** (R015-3, R015-6, R015-7, R015-11)
  - Isolar API OpenAI, modelo, credencial, dimensão, timeout, lote e classificação de erro.
  - Medir volume/custo e recusar envio depois do orçamento; nunca registrar conteúdo integral ou segredo.
  - Criar provedor falso determinístico para testes unitários; chamadas reais ficam somente em validação explícita.
  - **Aceite:** CA015-5 e CA015-8; o pipeline é desativável e a falha externa não afeta rotas atuais.

- [x] **T015-10A — Implementar analisador estruturado de documentos exigidos pela OpenAI** (R015-14, R015-15, R015-17, R015-18, R015-20)
  - Enviar chunks delimitados com IDs/páginas para `OPENAI_ANALYSIS_MODEL`, usando prompt versionado e schema JSON estrito.
  - Tratar o edital como dado não confiável; ignorar instruções contidas no texto e não fornecer ferramentas, credenciais ou acesso ao banco ao modelo.
  - Validar categorias, documentos, páginas, `chunk_id`, evidência, confiança e estado antes da persistência.
  - Classificar timeout, limite, autenticação, JSON inválido e contexto insuficiente sem marcar sucesso indevido.
  - Criar mock determinístico e uma fixture real controlada, sem depender do PNCP no teste unitário.
  - **Aceite:** CA015-11, CA015-12, CA015-14, CA015-15 e CA015-16.

- [x] **T015-11 — Persistir chunks e vetores com versão completa** (R015-3, R015-4, R015-5, R015-9)
  - Gravar em lotes com transações delimitadas, associando documento, página, texto, hash e vetor.
  - Reaproveitar versão idêntica e criar nova versão quando input/chunker/modelo mudar.
  - Executar busca interna de vizinhos apenas nos testes, sempre filtrada por proveniência.
  - **Aceite:** CA015-3, CA015-4 e CA015-6; nenhuma rota pública é adicionada.

- [x] **T015-11A — Persistir itens e projetar documentos exigidos nos cards** (R015-15, R015-16, R015-17, R015-19, R015-22)
  - Gravar a análise OpenAI e seus itens somente após validação do schema e dos vínculos de fonte.
  - Agregar itens em `status`, `total_exigencias`, `categorias`, `documentos_exigidos` e `analisador_versao`, mantendo o contrato de `ResumoExigenciasOut`/`resumo_exigencias`.
  - Definir estado e fallback quando a análise for parcial/indisponível; não substituir silenciosamente uma análise local válida por erro externo.
  - Exibir no card uma lista compacta de documentos e, no detalhe, origem assistida, página e evidência, com aviso de que não é parecer jurídico.
  - **Aceite:** CA015-12, CA015-13, CA015-14, CA015-17 e CA015-18 sem alteração incompatível no card atual.

## Fase 3 — Orquestração e preenchimento do acervo

- [x] **T015-12 — Implementar fila persistente e trabalhador limitado para OpenAI** (R015-6, R015-7, R015-10, R015-18, R015-20, R015-21)
  - Enfileirar embeddings/análise ao abrir uma contratação sem bloquear endpoints atuais; usar lease, tentativas e retomada após reinício.
  - Limitar concorrência, bytes, páginas, chunks, tokens, tempo e custo por execução/instalação.
  - Emitir métricas separadas de download, OCR, embeddings e análise estruturada.
  - **Aceite:** CA015-5, CA015-7, CA015-8 e CA015-16 sob falha, saturação e reinício simulados.

- [x] **T015-13 — Integrar abertura da contratação, análise e cards atuais** (R015-1, R015-6, R015-13, R015-16, R015-19, R015-21, R015-22)
  - Enfileirar conteúdo elegível após extração, sem acoplar a resposta HTTP à conclusão de embeddings ou análise OpenAI.
  - Publicar no resumo do card somente resultado validado; manter a análise local como fallback e fontes no detalhe.
  - Garantir que falha OpenAI não derrube a listagem de obras nem transforme o resultado em parecer jurídico.
  - Atualizar/recarregar o card atual ao concluir a análise, exibindo documentos exigidos e indicação de análise assistida.
  - Verificar que não foi criado agente conversacional, chat, endpoint público ou nova tela de interface.
  - **Aceite:** CA015-5, CA015-10, CA015-13, CA015-15, CA015-17 e CA015-18 em testes de integração.

- [x] **T015-14 — Reservar preenchimento histórico para fase posterior** (R015-4, R015-6, R015-7, R015-12)
  - Não executar lote histórico na primeira entrega; documentar apenas o comando/contrato futuro e seus limites.
  - Manter o job acionado pela abertura de uma contratação deduplicado e retomável.
  - **Aceite:** a primeira fase não baixa nem analisa contratos fora da contratação aberta; a expansão histórica permanece explicitamente postergada.

## Fase 4 — Qualidade, operação e entrega

- [ ] **T015-15 — Validar recuperação, análise estruturada e documentos nos cards** (R015-9, R015-15, R015-16, R015-19)
  - Executar o corpus anotado contra os embeddings OpenAI e calcular `recall@k`, posição do primeiro resultado correto, latência e custo.
  - Comparar itens documentais identificados com anotação humana: precisão, omissões, alucinações, páginas, evidências e nomes exibidos no card.
  - Separar resultados de texto digital e OCR; registrar limitações e casos de revisão humana.
  - Ajustar chunker, prompt ou modelo somente com nova versão e repetição dos testes.
  - **Aceite:** CA015-9, CA015-12, CA015-13 e CA015-18 atingidos ou decisão explícita de não promover a feature.

- [ ] **T015-16 — Validar segurança, retenção e observabilidade da OpenAI** (R015-10, R015-11, R015-12, R015-20)
  - Inspecionar logs, respostas, métricas e banco para garantir ausência de segredos, prompts completos e conteúdo integral em telemetria.
  - Testar desativação da feature, chave ausente, modelo inválido, limite/custo excedido, remoção/inativação de documento e expiração de versões.
  - Revisar permissões do banco e política aprovada de dados externos.
  - **Aceite:** CA015-5, CA015-8, CA015-15 e CA015-16, com evidências de operação segura.

- [ ] **T015-17 — Atualizar documentação operacional e fechar a spec** (R015-1 a R015-22)
  - Documentar PostgreSQL/pgvector no compose (`localhost:55432`), configuração OpenAI, orçamento, fila, retenção, fallback e procedimento de reindexação.
  - Registrar os modelos efetivamente aprovados, dimensão, prompt/schema, evidências de qualidade e limitações conhecidas.
  - Executar testes, lint, migrações em ambiente descartável e revisão de escopo sem agente conversacional.
  - **Aceite:** todos os CA015 verificados; qualquer decisão sobre agente permanece em spec futura.

## Matriz de cobertura do plano

| Requisito | Tarefas principais |
|---|---|
| R015-1 | T015-01, T015-08, T015-13 |
| R015-2 | T015-04, T015-08, T015-09 |
| R015-3 | T015-06, T015-07, T015-10, T015-11 |
| R015-4 | T015-06, T015-07, T015-11, T015-14 |
| R015-5 | T015-06, T015-07, T015-11 |
| R015-6 | T015-01, T015-05, T015-10, T015-12, T015-13 |
| R015-7 | T015-01, T015-05, T015-09, T015-10, T015-12, T015-14 |
| R015-8 | T015-03, T015-06, T015-11 |
| R015-9 | T015-04, T015-07, T015-11, T015-15 |
| R015-10 | T015-05, T015-12, T015-16 |
| R015-11 | T015-02, T015-05, T015-10, T015-16 |
| R015-12 | T015-06, T015-07, T015-14, T015-16 |
| R015-13 | T015-13, T015-17 |
| R015-14 | T015-10A, T015-15 |
| R015-15 | T015-06, T015-10A, T015-11A, T015-15 |
| R015-16 | T015-11A, T015-13, T015-15 |
| R015-17 | T015-06, T015-10A, T015-11A, T015-15 |
| R015-18 | T015-10A, T015-12, T015-13, T015-16 |
| R015-19 | T015-11A, T015-13, T015-15 |
| R015-20 | T015-05, T015-10A, T015-12, T015-16 |
| R015-21 | T015-12, T015-13, T015-14 |
| R015-22 | T015-11A, T015-13, T015-15 |
