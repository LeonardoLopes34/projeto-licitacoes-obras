# Design — Spec 015: Indexação vetorial de editais

## 1. Direção de implementação

Esta feature cria uma capacidade de dados e análise assistida, não uma experiência de conversação. O resultado será um acervo de trechos vetorizados e um conjunto de requisitos documentais estruturados, verificáveis e versionados. A API da OpenAI será usada no processamento interno dos editais; um agente futuro poderá consumir esse acervo, mas não será criado nesta spec.

O desenho preserva as decisões atuais do projeto:

- PDFs e ZIPs são obtidos somente pelo downloader que valida host, HTTPS, redirecionamentos, tipo e tamanho;
- o conteúdo permanece em memória durante download, extração e OCR;
- a extração é por página e o OCR é seletivo;
- falhas parciais são informadas em vez de ocultadas;
- persistência síncrona não deve bloquear rotas assíncronas.

Não reutilizar o resultado de exigências como corpus: ele contém apenas trechos que atendem regras específicas de habilitação e omitiria o restante do edital. A indexação deve receber o texto por página antes desse filtro de domínio. A análise OpenAI pode usar todos os chunks elegíveis do edital/anexos selecionados, mas deve retornar somente documentos cuja exigência esteja sustentada por evidência.

## 2. Fluxo de dados

```text
lista de documentos PNCP
  → seleção e manifesto da contratação
  → download seguro de PDF/ZIP em memória
  → extração por página + OCR seletivo
  → normalização mínima e chunking
  ├→ lote de embeddings → PostgreSQL + pgvector
  └→ análise estruturada OpenAI → requisitos documentais → resumo compatível com os cards
  → estado, métricas, proveniência e fallback
```

O serviço de indexação/análise deve receber os bytes já baixados e o resultado de extração, evitando segundo download para a mesma execução. Para PDF dentro de ZIP, cada PDF interno é uma fonte própria, identificado pelo hash do conteúdo; o ZIP é apenas o contêiner de entrada.

O caminho de análise para os cards é deliberadamente separado da recuperação futura e começa quando o usuário abre uma contratação:

1. selecionar chunks e páginas elegíveis do edital;
2. enviar lotes delimitados à OpenAI com instrução de saída estruturada;
3. validar JSON, páginas, evidências, categorias e confiança localmente;
4. persistir o resultado versionado;
5. projetar o resumo para o contrato atual `resumo_exigencias` e os documentos exigidos exibidos no card;
6. atualizar ou recarregar o card atual quando o job terminar, sem exigir uma nova busca no PNCP.

O texto do edital é conteúdo não confiável. O prompt deve delimitá-lo como dados, ignorar instruções encontradas no documento e não permitir que o edital altere o formato, as regras ou as ferramentas do sistema.

## 3. Modelo de dados

Usar PostgreSQL com `pgvector` no mesmo banco da aplicação. A migração deve criar a extensão de modo explícito e falhar com mensagem operacional clara quando ela não estiver disponível. O tipo vetorial terá dimensão fixa correspondente ao modelo aprovado na Fase 0.

### 3.1. `indexed_documents`

Representa uma versão concreta de conteúdo indexável.

| Campo | Uso |
|---|---|
| `id` | chave interna estável |
| `contratacao_chave` | vínculo com `cnpj:ano:sequencial` |
| `documento_id`, `titulo`, `url_origem` | identificação e futura citação |
| `pdf_sha256` | identidade do conteúdo efetivamente baixado |
| `manifesto_hash` | vínculo com a lista de documentos publicada pelo PNCP |
| `versao_extracao`, `versao_chunking`, `modelo_embedding` | compatibilidade/reindexação |
| `status`, `tentativas`, `erro_codigo`, `erro_mensagem_segura` | operação e recuperação |
| `ativo`, `indexed_at`, `superseded_at` | ciclo de vida |

A unicidade deve abranger pelo menos contratação, documento, `pdf_sha256`, versão de extração, versão de chunking e modelo. A alteração de qualquer entrada que afete os vetores não sobrescreve silenciosamente a versão anterior.

### 3.2. `document_chunks`

| Campo | Uso |
|---|---|
| `id`, `indexed_document_id`, `ordem` | identidade e ordenação |
| `pagina_inicio`, `pagina_fim`, `inicio_caractere`, `fim_caractere` | localização auditável no texto extraído |
| `texto` e `texto_hash` | evidência exibível e deduplicação |
| `origem_texto`, `confianca_ocr` | qualidade da extração |
| `token_count`/tamanho | controle de lote e custos |
| `embedding` | vetor `pgvector` com dimensão definida |
| `created_at` | auditoria |

Adicionar unicidade por documento indexado, ordem e hash do texto. Criar índice B-tree para `indexed_document_id` e filtros frequentes; criar índice vetorial HNSW ou IVFFlat somente depois de medir volume e padrão de escrita. A primeira carga, a construção do índice e a escolha HNSW/IVFFlat devem ser tratadas como operação observável, não como detalhe implícito de startup.

### 3.3. `document_index_jobs`

Fila persistente para não depender de tarefas em memória:

| Campo | Uso |
|---|---|
| `id`, `contratacao_chave`, `motivo` | unidade solicitada |
| `status`, `attempt`, `available_at` | agendamento e retry |
| `lease_until`, `worker_id` | exclusão mútua entre processos |
| `limite_bytes`, `limite_paginas`, `limite_chunks` | orçamento da execução |
| `erro_codigo`, `erro_mensagem_segura`, `finished_at` | diagnóstico |

O trabalhador deve obter jobs usando transação e bloqueio apropriado do PostgreSQL. Em caso de expiração do lease, o job pode ser retomado de maneira idempotente. A aplicação não deve afirmar garantia global de concorrência se for executada em mais de uma instalação sem um banco/fila compartilhados.

### 3.4. `document_requirement_analyses` e `document_requirement_items`

Manter a análise assistida separada do cache local atual de `edital_analyses`, para que uma resposta da OpenAI não seja confundida com uma análise determinística existente.

`document_requirement_analyses` deve guardar:

- contratação e manifesto/hash dos PDFs usados;
- hashes dos chunks enviados;
- `embedding_model`, `analysis_model`, `prompt_version` e `schema_version`;
- status (`sucesso`, `sucesso_parcial`, `indisponivel`, `erro`), tokens, latência e custo estimado;
- resposta estruturada validada e timestamps.

`document_requirement_items` deve guardar um item por documento exigido:

| Campo | Uso |
|---|---|
| `categoria` | qualificação técnica, habilitação jurídica, fiscal/trabalhista, declarações etc. |
| `nome_documento` | identificação curta do documento solicitado |
| `resumo` | descrição curta para o card/detalhe |
| `documento_id`, `pagina`, `chunk_id` | fonte rastreável |
| `evidencia` | trecho original delimitado para conferência |
| `confianca`, `estado` | controle de incerteza |
| `aceito_por_schema` | impede exibir JSON inválido como resultado |

O repositório deve oferecer um adaptador que agregue esses itens para o formato já consumido por `ResumoExigenciasOut`: `status`, `total_exigencias`, `categorias`, `analisador_versao` e uma lista compacta de `documentos_exigidos`. O frontend atual continua consumindo esse contrato; os dados de fonte permanecem disponíveis no detalhe.

`documentos_exigidos` deve conter somente dados próprios para o card, por exemplo `nome`, `categoria`, `confianca` e `estado`. A evidência completa não deve ser colocada na lista do card; ela permanece associada ao item no detalhe para não poluir a leitura nem aumentar desnecessariamente a resposta da busca de obras.

## 4. Chunking e qualidade do texto

O chunker recebe páginas com o texto original e produz trechos de tamanho limitado, com pequena sobreposição contextual. A estratégia inicial deve:

- privilegiar limites de parágrafo, item e seção antes de cortar por tamanho;
- nunca juntar documentos distintos;
- preservar número da página e faixa de caracteres;
- descartar somente cabeçalhos/rodapés repetitivos quando a regra for comprovada por amostra;
- manter texto original para prova, com normalização separada apenas para deduplicação;
- marcar chunks derivados de OCR com confiança baixa para avaliação posterior;
- ter versão explícita (`chunking-v1` ou equivalente).

O tamanho exato não deve ser codificado antes do benchmark do modelo. A configuração deve impor máximo de caracteres/tokens por chunk, máximo total de chunks por documento e máximo de texto enviado por job. Ao exceder um limite, o documento termina em estado parcial ou rejeitado, jamais com indexação silenciosamente incompleta.

## 5. Geração de embeddings pela OpenAI

Definir uma interface de infraestrutura, por exemplo `OpenAIEmbeddingProvider`, isolando:

- validação de `OPENAI_API_KEY`, modelo, dimensão e disponibilidade;
- geração em lotes com tamanho máximo;
- dimensão e identificador do modelo;
- classificação de erros transitórios, permanentes, de autenticação e de limite;
- contagem de texto/unidades e custo estimado quando disponível.

O adaptador não deve fazer chamadas de rede quando a indexação estiver desabilitada ou quando a execução já tiver excedido o orçamento. Nenhuma chave deve ser exposta por healthcheck, métricas, logs ou respostas de erro.

O primeiro modelo de embeddings deve ser configurável e validado por uma amostra; a opção inicial do plano é `text-embedding-3-small`. Trocar de modelo é uma reindexação: cria outra versão de `indexed_documents` e outro conjunto de vetores, preservando a origem. Não misturar vetores de modelos ou dimensões diferentes no mesmo índice consultável.

### 5.1. Análise estruturada para os cards

Definir uma interface separada, por exemplo `OpenAIRequirementAnalyzer`, para não misturar geração de vetor com interpretação do edital. Ela deve:

- receber somente chunks selecionados, com IDs e páginas, em lotes com limite de tokens;
- usar `OPENAI_ANALYSIS_MODEL` separado de `OPENAI_EMBEDDING_MODEL`;
- enviar prompt versionado e schema JSON estrito;
- exigir que cada item cite `chunk_id`, página e evidência textual;
- rejeitar categorias, páginas, URLs ou documentos que não existam no contexto;
- validar e normalizar a resposta antes da persistência;
- retornar `sucesso_parcial` quando apenas parte dos lotes for aproveitável.

O modelo não deve receber credenciais, instruções internas, acesso ao banco ou ferramentas. Ele só produz uma proposta estruturada; regras locais decidem o que pode aparecer no card.

## 6. Disparo e processamento

Na primeira fase haverá uma origem de job, sem agente conversacional:

1. **Abertura da contratação:** ao abrir o detalhe de uma contratação, verificar se existe resultado compatível. Se não existir, enfileirar embeddings e análise estruturada para aquela contratação. O lote histórico e a indexação em massa ficam para uma fase posterior.

O endpoint atual de exigências passa a poder retornar o resultado estruturado da análise assistida, com fallback para a análise local já existente. Uma falha de embeddings ou da OpenAI não altera a disponibilidade da listagem de obras; o resultado deve indicar `sucesso_parcial`, `indisponivel` ou equivalente. A indexação/análise pode reutilizar o mesmo resultado de extração da execução atual; em reprocessamentos posteriores, o job baixa novamente usando o fluxo seguro, pois PDFs brutos não são guardados.

O caminho para os cards deve alimentar os mesmos campos já usados por `resumo_exigencias`, `total_exigencias` e `categorias`, acrescentando `documentos_exigidos`. O card deve informar “análise assistida”, mostrar os nomes dos documentos identificados e abrir o detalhe com evidência, mas não deve transformar a saída em parecer jurídico. Quando o job concluir, o detalhe/card pode atualizar seu estado sem repetir a consulta ao PNCP.

## 7. Estados e versionamento

Estados sugeridos:

```text
pendente → em_execucao → concluido
                     ↘ parcial
                     ↘ falho_transitorio → pendente
                     ↘ falho_permanente
                     ↘ esgotado
```

`concluido` exige que todos os chunks elegíveis tenham vetor persistido. `parcial` deve enumerar os documentos/páginas que falharam. `falho_permanente` não é repetido sem intervenção ou alteração material do input/configuração. `esgotado` representa tentativas ou orçamento consumidos.

O manifesto da contratação, hash de cada PDF, versão da extração, versão do chunker, modelo de embedding, modelo de análise, versão do prompt e versão do schema compõem a identidade do processamento. Ao surgir uma versão nova, marcar as anteriores como inativas depois de a nova ficar completa; isso impede que cards e recuperação futura misturem edital desatualizado e atual.

## 8. Configuração, segurança e privacidade

Novas configurações devem ser explícitas e desligadas por padrão:

| Grupo | Exemplos |
|---|---|
| ativação | `VECTOR_INDEXING_ENABLED`, ambiente permitido |
| banco | PostgreSQL/pgvector; no compose local, `DATABASE_URL` usa `localhost:55432` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL=text-embedding-3-small`, `OPENAI_ANALYSIS_MODEL` em variante small/mini, dimensões e credenciais somente por ambiente |
| capacidade | workers, fila, lote, tentativas, timeout |
| orçamento | máximo de bytes, páginas, chunks e custo por job/dia |
| retenção | idade, inativação e limpeza de versões/documentos |

Como a OpenAI será usada nesta fase, documentar o tratamento de dados e obter aprovação antes de ativar em produção. Embora editais sejam documentos públicos, seus anexos podem conter dados pessoais e a publicidade não substitui o princípio de minimização. Logs devem guardar IDs, contagens, hashes, modelo e custo; nunca chave, prompt completo, resposta integral ou texto integral dos chunks.

## 9. Validação da indexação e dos cards

Não será criada API pública de busca ou agente nesta etapa. Para provar que a indexação funciona, os testes de integração podem executar uma consulta de similaridade diretamente pelo repositório vetorial com filtros obrigatórios de contratação/documento. Para provar a análise dos cards, os testes devem executar o analisador OpenAI com mock de resposta e, separadamente, uma amostra real controlada.

Criar uma amostra anotada de editais em português com documentos exigidos, páginas, evidências e categorias esperadas. Medir `recall@k`, posição do primeiro trecho correto, precisão dos itens aceitos, taxa de alucinação, taxa de chunks OCR, custo e latência por contratação aberta. Confirmar que o card mostra os nomes dos documentos e que a fonte completa fica no detalhe. A decisão de expor uma futura ferramenta a agente depende desses resultados e de uma spec separada.

## 10. Impacto em outras specs

- **Spec 011:** reutiliza a lista, snapshots e regras de obtenção de documentos PNCP.
- **Spec 012:** reutiliza download seguro, limites, extração por página e OCR; o novo analisador deve manter o formato/fallback das exigências existentes.
- **Spec 013:** adota as decisões de fila, capacidade, persistência fora do loop, migrações e observabilidade.
- **Spec 010:** amplia testes, ambiente PostgreSQL descartável e documentação de dependências.
- **Futura spec de recuperação/agente:** definirá autorização, ferramentas, resposta com citações, filtros e experiência de usuário. Ela consumirá os vetores e itens estruturados, mas não faz parte desta spec.
