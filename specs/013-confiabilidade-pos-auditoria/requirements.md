# Spec 013 — Confiabilidade e melhorias após auditoria

**Status:** planejado — implementação não iniciada nesta etapa.  
**Origem:** auditoria local de 08/09/2026, com sete problemas confirmados e melhorias adicionais.  
**Fase:** evolução transversal de confiabilidade, dados, frontend e qualidade.  
**Relacionada às specs:** 002, 003, 006, 007, 009, 010, 011 e 012.  
**Prioridade:** alta para omissões de exigências e cobertura documental; média para navegação, operação, migrações e qualidade.  
**Condição de entrega:** não considerar esta spec concluída enquanto seus critérios de aceitação estiverem pendentes.

## 1. Objetivo e referências

Corrigir as falhas reproduzidas na auditoria, tornar busca e indicadores coerentes com a paginação e fortalecer execução, testes e instalação do projeto. Esta spec segue a organização EARS, design técnico e checklist adotada nas specs existentes.

Referências:

- [Relatório da auditoria](S:/Leo/projeto-licitacoes-obras/specs/auditoria-2026-09-08/RELATORIO.md).
- [Diagnósticos do backend](S:/Leo/projeto-licitacoes-obras/specs/auditoria-2026-09-08/test_regressoes.py).
- [Diagnóstico do frontend](S:/Leo/projeto-licitacoes-obras/frontend/audit/casos.jsx).

As specs anteriores servem como histórico e referência de organização. Afirmações históricas sobre ausência de OCR, ausência de testes ou exemplos antigos de modalidade não descrevem necessariamente o estado atual. Preservar os códigos atualmente usados pelo domínio: `0` para todas as modalidades suportadas, `4`, `6` e `8`.

## 2. Estado observado

| Verificação em 08/09/2026 | Evidência |
| --- | --- |
| Suíte regular | 109 testes Python aprovados, 1 ignorado; 6 testes frontend aprovados |
| Qualidade básica | Lint, build e compatibilidade das dependências instaladas aprovados |
| Diagnósticos adicionais | 5 casos backend e 1 frontend reproduziram falhas |
| Migrações SQLite | Upgrade executou; comparação com os modelos apontou 9 índices ausentes e divergência de nulabilidade |
| OCR | Disponível pela configuração da aplicação; imagem sintética reconhecida corretamente |
| Lacunas de validação | PNCP real, PostgreSQL, navegação visual, carga e amostra representativa de editais não foram validados |

Esses números são a linha de base histórica, não a meta de cobertura nem evidência de implementação desta spec.

## 3. Escopo

Inclui todas as correções e melhorias do relatório: extração, evidências, cache, paginação, filtros, ordenação, indicadores, ciclo de vida das análises, concorrência, memória, banco assíncrono, migrações, CI, dependências, versões de execução, higiene do Git e teste real do OCR.

A criação desta spec modifica somente documentação. As mudanças de código, testes, configurações, dependências, migrações e índice Git descritas nas tarefas são trabalho futuro.

Continuam fora do escopo: validação jurídica da habilitação de empresas, análise de obrigações da contratada, OCR em massa na abertura da listagem, contratação de serviços externos e publicação/deploy como parte deste planejamento.

## 4. Requisitos em formato EARS

| ID | Prioridade | Requisito |
| --- | --- | --- |
| R013-1 | Alta | QUANDO uma página contiver exigências documentais distintas da mesma categoria, ENTÃO o sistema DEVE preservar todas as ocorrências aceitas pelas regras, deduplicando somente repetições equivalentes. |
| R013-2 | Alta | QUANDO a normalização alterar espaços, acentos ou quebras de linha, ENTÃO o sistema DEVE manter a associação correta com o texto original, documento e página, sem usar posições incompatíveis para recortar evidências. |
| R013-3 | Alta | SE um documento selecionado for incluído, removido, alterado ou falhar na análise atual, ENTÃO o cache DEVE refletir a cobertura atual e explicitar falhas; um resultado anterior não pode ocultar anexos nem apresentar cobertura completa indevida. |
| R013-4 | Média | ENQUANTO o usuário navegar por uma mesma consulta válida, o sistema DEVE usar um conjunto estável e ordenado de resultados; SE o cursor expirar ou for incompatível, ENTÃO DEVE informar a condição sem aplicar a posição a outra consulta. |
| R013-5 | Média | QUANDO uma página ficar vazia e houver navegação válida, ENTÃO a interface DEVE preservar os controles aplicáveis; SE a consulta expirar, ENTÃO DEVE oferecer reinício explícito, mantendo os filtros. |
| R013-6 | Média | QUANDO uma análise terminar, falhar ou for cancelada, ENTÃO o registro de processamento em andamento DEVE ser limpo, mesmo sem consumidores; uma consulta forçada não pode receber uma tarefa antiga concluída como se fosse novo processamento. |
| R013-7 | Média | O banco atualizado pelas migrações DEVE corresponder aos modelos suportados, incluindo índices e nulabilidade; atualizações DEVEM preservar os registros existentes e tratar dados legados antes de impor novas restrições. |
| R013-8 | Média | QUANDO um pull request for validado, ENTÃO o CI DEVE executar testes backend e frontend, lint, build e verificação de migrações em bancos isolados, falhando quando uma etapa obrigatória falhar. |
| R013-9 | Média | O sistema DEVE aplicar busca textual, ordenação e indicadores ao mesmo conjunto filtrado da consulta antes de paginar; QUANDO a coleta PNCP for parcial ou usar dados anteriores, ENTÃO a interface DEVE informar esse alcance. |
| R013-10 | Média | ENQUANTO houver análises simultâneas, o serviço DEVE impor limites compartilhados de processamento, fila e recursos; SE atingir capacidade ou orçamento, ENTÃO DEVE devolver estado explícito e liberar recursos ao término real do trabalho. |
| R013-11 | Média | QUANDO uma rota assíncrona acessar persistência síncrona, ENTÃO o acesso DEVE ocorrer sem bloquear o processamento das demais requisições, com sessão própria, transação delimitada e tratamento de erro. |
| R013-12 | Média | O projeto DEVE declarar versões suportadas de Python e Node, manter resolução reproduzível de dependências e alinhar ambiente local, lint e CI; avisos de depreciação do cliente de testes DEVEM ser resolvidos por compatibilidade validada. |
| R013-13 | Média | O repositório DEVE deixar de rastrear artefatos Python gerados e impedir sua reintrodução, preservando arquivos-fonte e alterações locais legítimas. |
| R013-14 | Média | QUANDO o teste de OCR verificar disponibilidade, ENTÃO DEVE usar a mesma resolução de executável e idioma da aplicação; no ambiente de integração que exige OCR, sua ausência DEVE provocar falha, e não skip silencioso. |
| R013-15 | Média | A entrega DEVE registrar evidências de regressão, integração, desempenho e qualidade de extração, distinguindo simulações locais, validação com dados reais e limitações ainda não verificadas. |

## 5. Critérios de aceitação rastreáveis

- [ ] **CA013-1 / R013-1:** atestado de capacidade técnica e registro profissional na mesma página geram dois itens; variações equivalentes não geram duplicatas; cabeçalho ou primeira menção irrelevante não impede analisar menção posterior válida.
- [ ] **CA013-2 / R013-2:** introdução com espaços repetidos, quebras de linha, acentos e numeração mantém a obrigação e sua evidência literal correta; o caso da auditoria passa de zero para um item.
- [ ] **CA013-3 / R013-3:** após analisar o documento 1, uma nova consulta com 1 e 2, falhando o download do 2, exibe ambos e indica cobertura parcial; remoção, mudança de conteúdo, recuperação do download e alteração da versão do analisador invalidam os resultados afetados.
- [ ] **CA013-4 / R013-4:** inserção, remoção ou reordenação da fonte entre páginas não repete nem omite itens do snapshot; cursores adulterados, expirados e de outros filtros são tratados explicitamente; navegação funciona entre processos conectados ao mesmo banco.
- [ ] **CA013-5 / R013-5:** o estado vazio mantém Anterior/Próxima quando aplicáveis; cursor expirado oferece atualizar a consulta; alterar filtros reinicia a página e não mistura respostas concorrentes.
- [ ] **CA013-6 / R013-6:** após timeout do consumidor, a tarefa termina e sai do registro; falha e cancelamento também limpam; reprocessamento forçado respeita a política definida no design sem reutilizar uma tarefa antiga finalizada.
- [ ] **CA013-7 / R013-7:** banco novo e banco legado com `created_at` nulo são migrados preservando linhas; os nove índices existem; `created_at` não aceita nulos; `alembic check` passa em SQLite e PostgreSQL isolados.
- [ ] **CA013-8 / R013-8:** um teste frontend propositalmente inválido em ensaio temporário faz o CI falhar; o fluxo regular inclui as regressões corrigidas, verificação do schema e bancos de teste separados da instalação local.
- [ ] **CA013-9 / R013-9:** em uma consulta com mais de 15 itens, um termo presente apenas depois da primeira página é encontrado; ordenar por valor considera todos os itens coletados; totais e gráficos permanecem iguais ao trocar apenas de página; resultados parciais e valores ausentes são identificados.
- [ ] **CA013-10 / R013-10:** com limite L e mais de L contratações distintas, a simultaneidade real não excede L; fila, bytes de arquivos e páginas em processamento são limitados; timeout não libera uma vaga enquanto trabalho não cancelável continua ativo; o orçamento total considera a quantidade de processos configurados.
- [ ] **CA013-11 / R013-11:** em teste com operação de banco deliberadamente suspensa por uma barreira, outra requisição leve conclui antes da liberação dessa barreira; commit, rollback e fechamento de sessão funcionam em sucesso e erro.
- [ ] **CA013-12 / R013-12:** instalação limpa a partir dos arquivos de dependências reproduz a resolução registrada para cada plataforma suportada; teste, lint, build e `pip check` passam; o aviso observado de TestClient/httpx deixa de ocorrer sem silenciamento genérico de warnings.
- [ ] **CA013-13 / R013-13:** a lista de arquivos rastreados não contém `.pyc` nem `__pycache__`; rodar testes não gera novas alterações rastreadas desses artefatos; fontes e mudanças anteriores permanecem preservadas.
- [ ] **CA013-14 / R013-14:** executável configurado fora do PATH é reconhecido pelo teste; executável ou idioma ausente tem diagnóstico específico; o CI com OCR obrigatório reconhece texto conhecido de imagem sintética.
- [ ] **CA013-15 / R013-15:** relatório de aceite contém os seis diagnósticos convertidos em regressões aprovadas, inspeção do fluxo completo no navegador, testes PostgreSQL, amostra anotada de editais e ensaio de carga com limites e medições; consulta PNCP real é registrada separadamente, com data e resultado, sem determinar o sucesso dos testes unitários.

## 6. Definição de pronto

Todos os requisitos devem ter testes ou evidências vinculados, com as tarefas concluídas somente após verificação. Os testes que hoje reproduzem falhas devem entrar na suíte regular com expectativas de sucesso, sem `skip` ou `xfail` permanente para esconder regressões.

Reavaliar a precisão do filtro documental com a amostra anotada antes de divulgar melhora de cobertura. A correção de falsos negativos não deve reintroduzir as menções operacionais excluídas pelo filtro atual. Registrar limitações quantitativas, especialmente em PDFs digitalizados, em vez de prometer extração completa.
