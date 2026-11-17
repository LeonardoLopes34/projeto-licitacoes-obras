# Tasks — Spec 013: Confiabilidade e melhorias após auditoria

**Status:** plano de execução futuro. Todas as tarefas estão pendentes.  
**Restrição desta etapa:** criar somente documentação; não executar nenhuma tarefa de implementação abaixo.  
**Regra de conclusão:** marcar uma tarefa somente depois de verificar os critérios CA013 correspondentes em `requirements.md` e registrar a evidência.

## Fase 0 — Preparação e referência de testes

- [ ] **T013-01 — Registrar linha de base e promover os diagnósticos por etapa** (R013-1 a R013-8, R013-15)
  - Reproduzir os cinco casos Python e o caso frontend da auditoria em ambiente isolado.
  - Registrar estado da suíte regular e divergências das migrações sem alterar o banco local.
  - Preparar a incorporação de cada regressão à suíte regular junto com sua correção; não mascarar falhas com skips permanentes.
  - **Aceite:** evidências históricas e novas separadas; nenhum teste usa dados reais da instalação.

- [ ] **T013-02 — Definir e validar ambiente reproduzível** (R013-12)
  - Inventariar dependências diretas/transitivas; definir lock/constraints e versões de Python, Node e gerenciador de pacotes.
  - Validar a proposta de matriz Python 3.12/3.14; alinhar lint, instalação e documentação às versões que forem suportadas.
  - Executar instalação limpa e `pip check`, sem atualizar pacotes indiscriminadamente.
  - **Aceite:** CA013-12 quanto à instalação e matriz; o aviso do cliente de testes é tratado em T013-18.

- [ ] **T013-03 — Alinhar o teste de OCR à configuração real** (R013-14)
  - Reutilizar resolução de executável e idioma da aplicação.
  - Cobrir executável fora do PATH, ausência do binário, ausência do idioma e imagem sintética.
  - Separar testes simulados dos testes de integração com OCR obrigatório.
  - **Aceite:** CA013-14; registrar a configuração efetivamente usada sem expor segredos.

## Fase 1 — Exigências e cobertura documental (prioridade alta)

- [ ] **T013-04 — Preservar evidências ao normalizar texto** (R013-2; depende de T013-01)
  - Separar trechos originais com origem e limites, tratando numeração e quebras de linha.
  - Normalizar para comparação sem recortar o original com deslocamentos incompatíveis.
  - **Aceite:** CA013-2 e regressão de diagramação aprovada.

- [ ] **T013-05 — Extrair várias exigências por categoria e página** (R013-1; depende de T013-04)
  - Percorrer ocorrências posteriores a cabeçalhos e menções rejeitadas.
  - Preservar documentos distintos e deduplicar somente equivalentes.
  - Reexecutar controles de menções operacionais e versionar as novas regras.
  - **Aceite:** CA013-1, sem regressão nos casos negativos existentes.

- [ ] **T013-06 — Corrigir compatibilidade e cobertura do cache** (R013-3; depende de T013-05)
  - Construir manifesto completo e invalidar agregados incompatíveis.
  - Manter visíveis anexos com falha, documentos removidos/alterados e estados parciais.
  - Testar cache em memória, persistente, recuperação e versão do analisador.
  - **Aceite:** CA013-3; o novo anexo indisponível aparece junto com sua falha.

## Fase 2 — Execução, capacidade e banco

- [ ] **T013-07 — Corrigir conclusão e reprocessamento das análises** (R013-6; depende de T013-01)
  - Limpar registros na conclusão real com verificação da identidade da tarefa.
  - Consumir exceções e definir o comportamento de solicitações forçadas concorrentes.
  - Cobrir consumidor cancelado, timeout, erro e tarefa finalizada sem consumidores.
  - **Aceite:** CA013-6; nenhuma tarefa antiga concluída é devolvida como reprocessamento.

- [ ] **T013-08 — Limitar fila, processamento e memória** (R013-10; depende de T013-07)
  - Compartilhar limites entre contratações; limitar documentos, bytes, páginas e tempo.
  - Processar e liberar arquivos gradualmente; contabilizar trabalho que continua após timeout.
  - Definir capacidade por processo e orçamento da instalação; registrar métricas de saturação.
  - **Aceite:** CA013-10 em ensaio determinístico; benchmark consolidado em T013-20.

- [ ] **T013-09 — Isolar persistência síncrona das rotas assíncronas** (R013-11; depende de T013-01)
  - Identificar gravação, resumos, fallback e demais consultas síncronas usadas por rotas assíncronas.
  - Executar unidades de trabalho com sessão própria e pool/executor dimensionados.
  - Cobrir erro, rollback, fechamento e banco deliberadamente suspenso por barreira.
  - **Aceite:** CA013-11; a requisição leve conclui sem esperar o banco bloqueado.

- [ ] **T013-10 — Criar migração de alinhamento da tabela de obras** (R013-7; depende de T013-01)
  - Criar os nove índices ausentes sem duplicar os já existentes.
  - Tratar somente valores nulos de `created_at`, documentar backfill e impor não nulidade.
  - Preservar dados e revisões antigas; não executar limpeza por retenção como parte da migração.
  - **Aceite:** banco legado mantém linhas e valores válidos; revisão nova aplicada em ambiente descartável.

- [ ] **T013-11 — Verificar migrações nos bancos suportados** (R013-7, R013-15; depende de T013-10)
  - Testar SQLite/PostgreSQL vazios, migrados e criados por bootstrap.
  - Conferir índices, nulabilidade, preservação de registros e `alembic check`.
  - **Aceite:** CA013-7 com evidências dos dois bancos; sem uso do banco original.

## Fase 3 — Consulta estável e interface coerente

- [ ] **T013-12 — Adicionar persistência temporária de snapshots** (R013-4; depende de T013-09, T013-11)
  - Definir modelo, nova migração, TTL, limites de tamanho/volume e limpeza de expirados.
  - Persistir lista normalizada e metadados; validar leitura entre processos ligados ao mesmo banco.
  - **Aceite:** snapshot imutável e limitado; falha de gravação não gera cursor inutilizável.

- [ ] **T013-13 — Vincular cursores ao snapshot e aos filtros** (R013-4; depende de T013-12)
  - Assinar versão, expiração, posição, tamanho e contexto da consulta.
  - Validar adulteração, incompatibilidade, expiração, remoção e transição de formato.
  - Preservar primeira consulta/atualização remota e continuidade sem nova coleta.
  - **Aceite:** CA013-4, incluindo inserção, remoção e reordenação da fonte entre páginas.

- [ ] **T013-14 — Centralizar filtros, ordenação e indicadores** (R013-9; depende de T013-12)
  - Definir contrato aditivo, busca textual normalizada, enumeração de ordenação e desempate estável.
  - Calcular totais, volume conhecido e agregados antes de paginar, usando Decimal para valores.
  - Documentar diferenças entre universo PNCP, conjunto coletado, filtrado e página.
  - **Aceite:** CA013-9 no backend, com termo presente somente depois do 15º registro e valores ausentes.

- [ ] **T013-15 — Atualizar navegação, estados e indicadores da interface** (R013-5, R013-9; depende de T013-13, T013-14)
  - Preservar paginação no estado vazio e permitir reinício de consulta expirada.
  - Consumir filtros e resumos globais da consulta; identificar parcialidade e origem.
  - Reiniciar página ao mudar filtros/ordenação; descartar respostas antigas; manter acessibilidade.
  - **Aceite:** CA013-5 e CA013-9 na interface; totais não mudam por trocar apenas a página.

- [ ] **T013-16 — Cobrir o fluxo completo do frontend** (R013-5, R013-8, R013-9; depende de T013-15)
  - Testar tela principal, filtros, ordenação, próximos/anteriores, vazio, erro, expiração e cancelamento.
  - Cobrir abertura de detalhes, anexo com falha e reprocessamento sem bloquear o modal.
  - Incorporar o diagnóstico da navegação vazia à suíte regular.
  - **Aceite:** testes de integração aprovados e fluxo preparado para inspeção no navegador.

## Fase 4 — CI, dependências e higiene

- [ ] **T013-17 — Consolidar verificações no CI** (R013-8; depende de T013-02, T013-03, T013-11, T013-16)
  - Incluir `npm run test`, testes backend, lint, build, migrações e ambiente OCR obrigatório.
  - Usar bancos descartáveis e simulações PNCP nos testes determinísticos.
  - Confirmar propagação de falha com ensaio temporário controlado e depois restaurá-lo.
  - **Aceite:** CA013-8; nenhuma regressão fica escondida fora da descoberta de testes.

- [ ] **T013-18 — Resolver o aviso de depreciação do cliente de testes** (R013-12; depende de T013-02)
  - Verificar combinação suportada de FastAPI, Starlette e cliente HTTP.
  - Atualizar somente o necessário e registrar a resolução no mecanismo de dependências escolhido.
  - **Aceite:** CA013-12 completo; sem silenciamento global de avisos.

- [ ] **T013-19 — Remover artefatos gerados do rastreamento Git** (R013-13)
  - Retirar do índice os dois `.pyc` identificados pela auditoria, preservando fontes e alterações locais.
  - Manter ignore e acrescentar verificação de reintrodução ao CI.
  - **Aceite:** CA013-13; executar testes não suja o Git com bytecode rastreado.

## Fase 5 — Aceite e documentação

- [ ] **T013-20 — Validar qualidade, carga e integração real** (R013-10, R013-14, R013-15; depende de T013-06, T013-08, T013-16)
  - Montar amostra anotada de PDFs digitais e digitalizados, incluindo tabelas, colunas e controles negativos.
  - Comparar precisão/cobertura antes e depois; registrar falsos positivos e omissões.
  - Executar ensaio de carga com máquina, processos, limites e conjunto de arquivos registrados.
  - Inspecionar navegador e fazer consulta PNCP real limitada, separada da suíte determinística.
  - **Aceite:** CA013-10 e CA013-15; resultados externos inconclusivos permanecem declarados como tal.

- [ ] **T013-21 — Atualizar documentação operacional** (R013-4, R013-9, R013-10, R013-12, R013-14, R013-15; depende de T013-17, T013-18, T013-20)
  - Documentar instalação validada, versões, migrações, expiração de consultas, indicadores, OCR e capacidade por processo.
  - Registrar mudanças de contrato, transição de cursores e configuração de segredo em produção.
  - Atualizar esta spec se decisões de implementação divergirem da proposta, com justificativa.
  - **Aceite:** documentação reproduz o comportamento final e não apresenta limitações como resolvidas.

- [ ] **T013-22 — Fechar o aceite da spec** (R013-1 a R013-15; depende das tarefas anteriores)
  - Conferir todos os CA013 e associar testes/relatórios às tarefas.
  - Executar a suíte completa, lint, build, instalação limpa e verificação de migrações nos ambientes suportados.
  - Confirmar que arquivos de teste, banco real, segredos e alterações locais foram tratados corretamente.
  - **Aceite:** nenhum requisito pendente; caso haja entrega parcial, manter esta tarefa aberta e listar o restante.

## Matriz de cobertura do plano

| Origem na auditoria | Requisito | Tarefas principais |
| --- | --- | --- |
| Problema 1 — uma exigência por categoria/página | R013-1 | T013-04, T013-05 |
| Problema 2 — posição normalizada incorreta | R013-2 | T013-04 |
| Problema 3 — cache oculta anexo com falha | R013-3 | T013-06 |
| Problema 4 — paginação sobre fonte mutável | R013-4 | T013-12, T013-13 |
| Problema 5 — navegação desaparece no vazio | R013-5 | T013-15, T013-16 |
| Problema 6 — tarefas após timeout | R013-6 | T013-07 |
| Problema 7 — divergência das migrações | R013-7 | T013-10, T013-11 |
| Melhoria — cobertura frontend e CI | R013-8 | T013-16, T013-17 |
| Melhoria — indicadores e ordenação da consulta | R013-9 | T013-14, T013-15 |
| Melhoria — concorrência, fila e memória | R013-10 | T013-08, T013-20 |
| Melhoria — banco síncrono em rotas assíncronas | R013-11 | T013-09 |
| Melhoria — versões/dependências e aviso observado | R013-12 | T013-02, T013-18 |
| Melhoria — bytecode rastreado | R013-13 | T013-19 |
| Melhoria — teste do OCR fora do PATH | R013-14 | T013-03, T013-17 |
| Lacunas — dados reais, PostgreSQL, navegador e carga | R013-15 | T013-11, T013-20, T013-21, T013-22 |
