# Design — Spec 013: Confiabilidade e melhorias após auditoria

**Status:** proposta técnica para execução futura. Nenhuma alteração de aplicação, configuração ou banco é executada por este documento.

## 1. Direção de implementação

Usar a arquitetura atual: FastAPI, SQLAlchemy, SQLite/PostgreSQL, React/Vite e OCR local. Evoluir os serviços existentes em etapas, com contratos compatíveis sempre que possível. Não adicionar um serviço externo de cache ou processamento como pré-requisito desta spec.

As escolhas abaixo são propostas deste plano. Não representam funcionalidades já implementadas ou decisões anteriormente confirmadas pelo usuário.

| Área | Decisão proposta | Requisitos |
| --- | --- | --- |
| Evidências | Separar trechos originais antes da normalização e manter referência de origem | R013-1, R013-2 |
| Cache de análise | Associar resultado ao manifesto completo de documentos e à versão da análise | R013-3 |
| Navegação | Usar snapshot imutável e temporário da consulta, compartilhado pelo banco | R013-4, R013-5 |
| Busca e indicadores | Filtrar, ordenar e agregar o snapshot no backend antes de selecionar a página | R013-9 |
| Execução | Controlar ciclo de vida, fila e capacidade por serviço/processo | R013-6, R013-10 |
| Banco | Manter SQLAlchemy síncrono com unidades de trabalho fora do loop assíncrono | R013-7, R013-11 |
| Qualidade | Incorporar regressões e instalação reproduzível ao CI | R013-8, R013-12 a R013-15 |

## 2. Extração de exigências e preservação da evidência

Fluxo proposto: página original → trechos com limites e origem → normalização de cada trecho → busca de todas as ocorrências → filtro documental → deduplicação → itens com evidência.

O recorte original será a fonte de `evidencia` e `descricao_original`. A normalização servirá para comparar termos, sem fornecer diretamente posições de recorte do original. Se uma estratégia de correspondência por posição for necessária, manter mapa explícito entre índices normalizados e originais.

A segmentação deverá reconhecer numeração de itens e frases quebradas em linhas, evitando dividir uma obrigação apenas porque existe uma quebra de linha ou ponto em `8.4.1`. Preservar os limites da página; requisitos continuados em outra página deverão ter evidências rastreáveis, sem inventar continuação.

Remover a interrupção que aceita somente um item por categoria/página. Inspecionar todas as ocorrências, inclusive quando a primeira menção do termo for um cabeçalho ou contexto rejeitado. Deduplicar por conceito documental e evidência, mantendo distintos atestado, registro profissional e outros documentos diferentes da mesma categoria.

Manter as exclusões atuais de proposta e execução contratual. Comparar os resultados com os casos negativos existentes antes de aumentar a sensibilidade. Incrementar a versão do analisador quando a regra mudar para evitar reutilização de análises produzidas pelas regras antigas.

## 3. Cache e cobertura documental

Representar a consulta atual por um manifesto ordenado contendo todos os documentos selecionados: identificador, metadados relevantes à seleção, origem, hash quando disponível e estado atual de download/processamento. Ausência de hash por erro é um estado explícito, não motivo para retirar o documento do manifesto.

A compatibilidade do resultado agregado depende desse manifesto e da versão de regras/OCR. Um novo documento com download falho deve gerar cobertura parcial, preservando as evidências válidas dos demais. Não retornar antecipadamente um resultado completo apenas porque o subconjunto de downloads bem-sucedidos tem o mesmo hash anterior.

Começar com invalidação do agregado e reaproveitamento da infraestrutura existente. Cache individual por hash pode ser introduzido na mesma etapa somente se necessário para evitar reextração relevante; preservar a composição do resultado com os estados atuais. Falhas transitórias não devem impedir nova tentativa após recuperação.

Resultados persistidos devem obedecer à mesma compatibilidade e à política de validade documentada. Em fallback, informar origem, atualização e cobertura conhecida. Não persistir PDFs/ZIPs brutos. O relatório de análise deve distinguir documento não selecionado, falha de download, falha de extração e análise concluída.

## 4. Snapshot de consulta, cursor e validade

Na consulta inicial sem cursor, consultar o PNCP seguindo a política atual de transporte, limites e fallback. Criar um snapshot da lista normalizada coletada, deduplicada por identificador, com metadados de origem, parcialidade, instante de criação e expiração.

Persistir o snapshot em tabela própria com identificador imprevisível, expiração e payload normalizado. Definir limite de registros, bytes por snapshot e quantidade/volume de snapshots; remover expirados em limpeza periódica limitada. A atualização de schema deve ser uma nova migração, independente da correção dos índices de obras.

As páginas seguintes leem o mesmo snapshot, inclusive quando atendidas por outro processo ligado ao mesmo banco. Elas não repetem a coleta PNCP. Uma ação explícita de atualizar cria nova consulta; isso preserva o comportamento de consultar a fonte na abertura/atualização sem alterar silenciosamente a lista durante a navegação.

O cursor assinado deverá vincular versão do formato, snapshot, expiração, posição, tamanho da página e assinatura dos filtros/ordenação. Verificar assinatura e parâmetros antes de fazer trabalho custoso. Não incluir dados sensíveis no token; exigir segredo próprio em produção e definir efeito da rotação: consultas antigas devem reiniciar explicitamente.

Tratamento proposto: cursor inválido ou incompatível → 422 com código estável; snapshot expirado ou removido → 410 com orientação de reinício. Não aplicar um cursor antigo a dados novos nem convertê-lo silenciosamente em página 1. O frontend precisa tratar esses casos antes da ativação do novo formato; cursores antigos serão invalidados de modo explícito na transição.

Se o armazenamento do snapshot falhar, devolver erro operacional compreensível e permitir nova tentativa. Nunca emitir cursor cuja continuidade não possa ser garantida. A validade do snapshot não implica que os dados correspondam ao estado atual do PNCP.

## 5. Busca textual, ordenação e indicadores

Adotar a interpretação de busca em **todos os registros coletados para a consulta**, respeitando o limite de páginas PNCP. Não apresentar esse conjunto como todo o universo nacional de oportunidades.

Aplicar termo, normalização de caixa/acentos e ordenação no backend. Campos pesquisáveis: município, UF, órgão, objeto, modalidade, fonte e data de publicação, mantendo o alcance funcional atual. A ordenação deve ser determinística, com identificador como desempate; valores ausentes ficam ao final, com regra documentada.

Contrato aditivo proposto para a rota de obras:

| Campo | Uso planejado |
| --- | --- |
| Parâmetro `termo` | Pesquisa no conjunto coletado antes da paginação |
| Parâmetro `ordenacao` | Enumeração validada para data, valor e órgão; mantém a opção padrão da interface |
| Metadados de consulta | Identificação opaca, criação, expiração e alcance parcial/completo da coleta configurada |
| Resumo da consulta | Total coletado, total após filtros, volume estimado conhecido, quantidade sem valor e agregados por UF/modalidade |
| Paginação existente | Até 15 cards; cursor e indicação de continuidade |

Preservar campos existentes e documentar a semântica de cada total antes da mudança. Estatísticas devem derivar do mesmo conjunto usado para gerar os cards, com valores financeiros calculados em Decimal no backend. Valores desconhecidos não podem ser apresentados como estimativas reais de zero.

O frontend exibirá “Volume estimado da consulta” e, quando aplicável, “Consulta parcial”. Gráficos e totais não variam apenas por mudar de página. Ao alterar filtros/ordenação, reiniciar a navegação e invalidar respostas anteriores; o mecanismo de cancelamento não pode deixar uma resposta antiga sobrescrever a atual.

Renderizar controles de paginação fora do bloco que decide entre lista e estado vazio. Exibir mensagens distintas para ausência global de resultados, página sem itens e consulta expirada. Validar teclado, foco, leitores de tela e preservação de filtros no reinício.

## 6. Ciclo de vida, concorrência e memória

Registrar uma tarefa compartilhada por contratação e contexto compatível. A própria conclusão da tarefa deve disparar limpeza com verificação de identidade, evitando que uma tarefa antiga remova outra mais nova. Consumir exceções e contabilizar sucesso, falha, cancelamento e timeout, mesmo quando todos os clientes abandonarem a espera.

Separar o tempo limite do consumidor do orçamento do processamento compartilhado. Política proposta para `forcar=true`: nunca reutilizar tarefa concluída; se houver análise normal ainda ativa, aguardar sua conclusão e iniciar uma execução forçada compartilhada entre solicitantes equivalentes, sem executar duas análises da mesma contratação simultaneamente. Explicitar timeout dessa espera e impedir acumulação ilimitada de pedidos forçados.

Colocar os limites de análises, downloads e fila na instância do serviço, compartilhados entre diferentes contratações do mesmo processo. Definir também limite de documentos selecionados, bytes acumulados por análise, páginas e prazo total. Processar arquivos gradualmente, liberando buffers e imagens após o uso; qualquer corte deve aparecer na cobertura devolvida.

Uma operação enviada para thread pode continuar após cancelamento da espera. Manter sua vaga contabilizada até a execução terminar. Onde for exigido encerramento rígido do parser, usar processo isolado com prazo e limpeza próprios; não afirmar que cancelar uma coroutine interrompe uma biblioteca nativa. O OCR mantém também o timeout do subprocesso.

O limite por processo deve compor um orçamento da instalação: documentar capacidade total como função da quantidade de processos. Configuração com múltiplos processos não pode prometer limite global único sem coordenação correspondente. Recusar novas análises quando a fila estiver cheia com estado temporário e orientação de repetição.

Métricas mínimas: ativos, fila, rejeições por capacidade, duração, timeouts, hits de cache, falhas por estágio e bytes de arquivos em processamento. Registrar consumo de memória do processo no ensaio de carga, pois bytes de arquivos não representam toda a memória dos parsers.

## 7. Persistência e migrações

### 7.1. Operações de banco fora do loop assíncrono

Mover cada unidade síncrona de banco para execução controlada fora do loop da API, incluindo consulta de resumos, fallback, snapshots e persistência de obras. Criar, usar e fechar a sessão no mesmo contexto de execução. Não transportar sessão ativa entre threads.

Retornar estruturas desacopladas da sessão. Delimitar transações; em erro, fazer rollback e preservar a classificação correta entre falha de banco e falha PNCP. Dimensionar o executor junto ao pool do banco para não trocar bloqueio do loop por fila ilimitada de conexões.

### 7.2. Alinhamento do schema de obras

Criar nova revisão Alembic após a revisão vigente. Acrescentar os índices em `ano`, `cnpj`, `created_at`, `data_publicacao`, `modalidade_codigo`, `numero_controle_pncp`, `status_classificacao`, `uf` e `valor_estimado`, conforme o modelo auditado.

Antes de impor `created_at` não nulo, preservar valores válidos e preencher apenas os nulos. Usar data de criação confiável quando existir em dados legados; na ausência, usar o instante da migração, documentando a origem inferida para não inventar histórico. Não executar limpeza por retenção durante esse preenchimento.

Cobrir bancos criados por migração e por bootstrap, incluindo índices já existentes. Validar em SQLite e PostgreSQL descartáveis. Não alterar revisões já aplicadas, não remover registros para satisfazer a restrição e não executar a migração no banco local durante a elaboração do plano.

## 8. Ambiente, CI e higiene

Inventariar a resolução de dependências instalada, definir arquivos de lock/constraints com dependências diretas e transitivas por plataforma quando necessário e verificar instalação limpa. Proposta inicial: validar Python 3.12 e 3.14, refletindo CI e ambiente observados; uma versão só será declarada suportada depois de passar na matriz. Alinhar o alvo do lint com a menor versão suportada. Declarar Node e gerenciador de pacotes compatíveis com o frontend instalado.

Resolver o aviso TestClient/httpx após conferir compatibilidade das versões usadas; não fixar uma troca de pacote apenas pela mensagem de depreciação nem desativar todos os avisos.

No CI, executar testes backend, testes frontend, Ruff, lint atual do frontend (oxlint), build, comparação das migrações, instalação reproduzível e higiene de diffs. Usar banco temporário e configuração de teste; simular PNCP nos testes determinísticos. Um job dedicado com OCR obrigatório deve usar o executável configurado e idioma português.

O teste de disponibilidade reutilizará a resolução da aplicação. Testes unitários com OCR simulado continuam independentes do binário; o teste de integração obrigatório deve falhar quando o executável ou idioma não estiver disponível. Validar também o caso em que o executável existe fora do PATH.

Retirar do rastreamento somente os dois `.pyc` identificados e manter regras de ignore. Preservar os arquivos locais quando apropriado, sem limpeza ampla nem reescrita de histórico. Documentar o padrão de instalação e execução efetivamente validado.

## 9. Validação e entrega incremental

Cada etapa começa com regressões reproduzíveis, aplica a correção e promove os testes relacionados à suíte regular. A suíte da auditoria permanece como evidência histórica; evitar duplicar testes permanentes depois da promoção.

Para OCR/filtro, montar amostra anotada com PDFs digitais, digitalizados, tabelas, colunas, numeração e casos operacionais negativos. Medir precisão e cobertura por categoria/página, comparando antes e depois na mesma amostra. Aceitar a melhoria somente se recuperar as omissões alvo sem piorar os controles negativos; registrar tamanho e limitações da amostra.

Para carga, fixar versões, máquina, número de processos, limites, conjunto de arquivos e perfil de requisições antes do ensaio. Medir latência, fila, memória e recuperação após saturação. A aceitação principal é respeitar os limites configurados e manter requisições leves responsivas; resultados devem incluir valores observados, não metas inventadas sem medição.

Validar no navegador filtro, ordenação, navegação vazia, cursor expirado, abertura do modal, falha de anexo, reprocessamento, teclado e apresentação dos indicadores. A consulta PNCP real será uma verificação limitada e separada; falha externa não pode ser confundida com aprovação ou reprovação dos testes determinísticos.

Entregar primeiro correções de extração/cache; depois operação e banco; em seguida snapshot e interface juntos; por fim consolidar CI, instalação e evidências. Uma entrega parcial deve identificar quais requisitos permanecem pendentes.
