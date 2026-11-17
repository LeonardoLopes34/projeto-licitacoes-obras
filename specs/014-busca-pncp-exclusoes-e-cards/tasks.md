# Tasks — Spec 014: Busca PNCP, palavras excluídas e enriquecimento dos cards

**Status:** implementada e validada localmente em 14/09/2026. A verificação
operacional contra o PNCP real (T014-16) permanece pendente por depender da
disponibilidade externa.
**Regra de conclusão:** marcar uma tarefa somente depois de verificar os critérios de aceitação em `requirements.md` e registrar a evidência.

## Fase 0 — Linha de base e contrato

- [x] **T014-01 — Registrar a linha de base da busca atual** (R014-3, R014-6, R014-11)
  - Reproduzir buscas sem termo, com `pavimentacao`, com `pavimentacao -drenagem` e com filtro de UF/modalidade.
  - Registrar a diferença entre total coletado, total filtrado e página exibida.
  - Confirmar que o frontend atual aplica parte dos filtros localmente e não envia o termo no conjunto-base.
  - **Aceite:** evidência versionada sem alterar dados reais ou marcar uma consulta parcial como universo PNCP.

- [x] **T014-02 — Definir o contrato de busca e compatibilidade** (R014-1, R014-3, R014-5, R014-6)
  - Documentar `termo`, listas estruturadas, escopo e modo de inclusão.
  - Definir limites, precedência e mensagens de erro para expressões ambíguas.
  - Manter chamadas legadas sem exclusões funcionando.
  - **Aceite:** contrato aprovado em testes de validação e documentado no endpoint.

- [x] **T014-03 — Criar fixture anotada de busca e card** (R014-2, R014-7, R014-8, R014-9, R014-12)
  - Adicionar casos de acento, frase, órgão falso positivo, item, duplicidade e tipos compostos.
  - Registrar resultado esperado, campo correspondente e motivo de exclusão.
  - **Aceite:** fixture cobre todos os cenários dos critérios de aceitação.

## Fase 1 — Parser e correspondência

- [x] **T014-04 — Implementar parser de inclusão/exclusão** (R014-1, R014-2, R014-3)
  - Interpretar tokens, aspas e prefixo `-` sem tratar hífen interno como exclusão.
  - Normalizar acentos, caixa, pontuação e espaços.
  - Validar quantidade e tamanho dos termos.
  - **Aceite:** testes unitários cobrem expressões válidas, vazias e inválidas.

- [x] **T014-05 — Implementar correspondência por escopo** (R014-2, R014-4, R014-5, R014-7)
  - Criar avaliador com campos `objeto`, `itens`, `orgao`, `municipio`, `modalidade`, `fonte` e documentos quando disponíveis.
  - Usar objeto/itens como padrão e palavra inteira/frase normalizada.
  - Retornar campo, trecho ou termo correspondente sem substituir o texto original.
  - **Aceite:** “engenharia” apenas no órgão não aprova o resultado no escopo padrão; “engenharia” no objeto ou item aprova quando configurado.

- [x] **T014-06 — Separar exclusão do usuário e classificação de obra** (R014-3, R014-12)
  - Manter `TERMOS_POSITIVOS`/`TERMOS_NEGATIVOS` para score/classificação.
  - Aplicar termos do usuário como predicado explícito posterior à classificação elegível.
  - Retornar motivo distinto para `rejeitado`, `excluído_por_termo` e `revisao_pendente`.
  - **Aceite:** alterar a lista interna de pesos não muda a semântica de uma exclusão explícita do usuário.

## Fase 2 — Dados PNCP e backend

- [x] **T014-07 — Normalizar tipo, modalidade e critério** (R014-8, R014-9, R014-10)
  - Mapear campos disponíveis do PNCP sem sobrescrever os valores atômicos.
  - Criar compositor determinístico para `tipo_contratacao` e evitar duplicação de palavras.
  - Preservar `tipo_contratacao_origem` para diagnóstico.
  - **Aceite:** casos “Concorrência por Menor Preço - Menor Preço”, somente modalidade e ausente passam na fixture.

- [x] **T014-08 — Acrescentar contrato Pydantic e normalização da obra** (R014-7 a R014-11)
  - Adicionar campos de tipo, critério, correspondências e motivo ao schema de saída.
  - Preservar compatibilidade de serialização e campos existentes.
  - Deduplicar por `id_pncp` antes de calcular totais.
  - **Aceite:** respostas antigas continuam válidas e respostas novas carregam o tipo quando a origem o fornecer.

- [x] **T014-09 — Aplicar busca antes da paginação e do snapshot** (R014-2, R014-6, R014-11)
  - Integrar parser, escopo e predicado à consulta de obras.
  - Calcular totais, agregados e volume sobre o mesmo conjunto que gera os cards.
  - Incorporar expressão, escopo e versão do parser ao snapshot/cursor.
  - **Aceite:** termo encontrado após a primeira página do PNCP aparece quando coletado; mudar termo, escopo ou exclusão reinicia o cursor.

- [x] **T014-10 — Expor metadados de auditoria da filtragem** (R014-7, R014-12)
  - Incluir termos correspondentes, campos, motivos e contagens nos metadados da consulta.
  - Não expor registros excluídos na lista normal nem somá-los ao volume final.
  - **Aceite:** uma consulta permite explicar por que um resultado entrou ou saiu sem consultar logs internos.

## Fase 3 — Interface e card

- [x] **T014-11 — Criar controles de inclusão, exclusão e escopo** (R014-1, R014-4, R014-5)
  - Atualizar `FilterPanel` com interpretação visual, chips, remoção individual e ajuda de sintaxe.
  - Preservar atalhos de busca, teclado e limpeza de filtros.
  - **Aceite:** usuário consegue representar `pavimentação -drenagem` sem editar uma expressão opaca depois de adicioná-la.

- [x] **T014-12 — Exibir tipo da contratação no `ObraCard`** (R014-9, R014-10)
  - Adicionar bloco `Tipo` antes do objeto, usando `tipo_contratacao` e fallback documentado.
  - Preservar modalidade como badge/filtro sem duplicação desnecessária.
  - Testar textos longos, mobile, zoom, teclado e leitor de tela.
  - **Aceite:** card renderiza o exemplo `Concorrência por Menor Preço - Menor Preço` quando esse valor estiver no contrato normalizado.

- [x] **T014-13 — Exibir resumo da busca e motivos de filtragem** (R014-6, R014-7)
  - Mostrar inclusão, exclusão, escopo, quantidade final e indicação de consulta parcial.
  - Diferenciar “nenhum resultado encontrado” de “todos os resultados foram excluídos”.
  - **Aceite:** a troca de página não altera o total da consulta e o estado vazio orienta a remoção de exclusões.

- [x] **T014-14 — Atualizar o detalhe para auditar o card** (R014-8, R014-10, R014-11)
  - Mostrar modalidade, critério, tipo de instrumento, tipo composto e origem dos dados.
  - Manter links para edital, ata, contrato e documentos quando publicados.
  - **Aceite:** usuário consegue identificar quais campos formaram o `Tipo` exibido no card.

## Fase 4 — Qualidade e entrega

- [x] **T014-15 — Criar regressões backend e frontend** (R014-1 a R014-12)
  - Cobrir parser, normalização, escopo, paginação, deduplicação, schema e renderização do card.
  - Incluir casos negativos e campos ausentes.
  - **Aceite:** suíte determinística passa sem depender da disponibilidade do PNCP.

- [ ] **T014-16 — Validar consulta PNCP real limitada** (R014-2, R014-6, R014-11)
  - Comparar uma consulta sem filtro, uma filtrada por UF/modalidade, uma com exclusão e uma com edital detalhado.
  - Separar falha externa, dado ausente no órgão e falha de aplicação.
  - **Aceite:** relatório registra alcance, parcialidade e divergências sem tratar contadores do portal como verdade absoluta.

- [x] **T014-17 — Atualizar documentação e matriz de rastreabilidade** (R014-1 a R014-12)
  - Atualizar `specs/README.md`, contrato da API, manual do usuário e limites da busca.
  - Registrar eventual divergência entre a composição planejada e o campo efetivamente publicado pelo PNCP.
  - **Aceite:** documentação descreve a semântica de inclusão/exclusão, o tipo do card e os estados de dados ausentes.

## Matriz de cobertura do plano

| Requisito | Tarefas principais |
|---|---|
| R014-1 a R014-3 | T014-02, T014-04, T014-06, T014-11, T014-15 |
| R014-4 e R014-5 | T014-05, T014-11, T014-15 |
| R014-6 e R014-7 | T014-09, T014-10, T014-13, T014-15 |
| R014-8 a R014-10 | T014-07, T014-08, T014-12, T014-14, T014-15 |
| R014-11 | T014-08, T014-09, T014-14, T014-16 |
| R014-12 | T014-03, T014-06, T014-15, T014-17 |
