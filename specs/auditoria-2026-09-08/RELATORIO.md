# Auditoria do projeto — 08/09/2026

O projeto possui uma base organizada: separação entre API, integração PNCP, persistência, download, OCR e interface; validação de entrada; proteção administrativa; limites de arquivos e tratamento de falhas externas. Entretanto, os testes atuais não cobrem alguns cenários importantes de extração de exigências, cache e navegação.

Foram confirmados **sete problemas**: seis por novos testes de regressão e um pela comparação do banco migrado com os modelos.

## Resultados das verificações

| Verificação | Resultado |
| --- | --- |
| Testes existentes do backend | 109 passaram, 1 ignorado, 1 aviso de depreciação do TestClient/httpx |
| Testes existentes do frontend | 6 passaram, em 2 arquivos |
| Ruff do backend | Passou |
| Lint do frontend | Passou |
| Compilação de produção do frontend | Passou |
| Compatibilidade das dependências Python instaladas (`pip check`) | Passou |
| Migrações em SQLite novo (`alembic upgrade head`) | Passaram até `0003_document_snapshots` |
| Correspondência entre migrações e modelos (`alembic check`) | Falhou: 9 índices ausentes e divergência em `created_at` |
| Novos testes de diagnóstico do backend | 5 falharam, confirmando os comportamentos descritos abaixo |
| Novo teste de diagnóstico do frontend | 1 falhou, confirmando perda de navegação |
| Disponibilidade do OCR pela configuração da aplicação | Tesseract disponível, idioma `por` |
| OCR real sobre imagem sintética | Reconheceu corretamente “A licitante devera apresentar contrato social atualizado.” |

O teste existente de ambiente do Tesseract foi ignorado porque verifica somente o PATH. A aplicação encontra o executável pelo caminho configurado; portanto, o teste ignorado não significa ausência de OCR.

## Problemas confirmados e correções sugeridas

### 1. Alta prioridade: exigências diferentes da mesma categoria são omitidas

Em [edital_analysis_service.py:205](S:/Leo/projeto-licitacoes-obras/backend/services/edital_analysis_service.py:205), a extração procura apenas a primeira ocorrência de cada palavra e interrompe a categoria depois do primeiro item aceito. Na mesma página, “apresentar atestado de capacidade técnica” e “apresentar registro profissional no CREA” produzem **um item**, embora cada frase isolada seja reconhecida.

**Impacto:** a lista de documentos fica incompleta mesmo quando o texto está legível. **Correção:** percorrer todas as ocorrências e frases relevantes, deixando a deduplicação remover apenas repetições do mesmo requisito. O diagnóstico exige dois itens e recebe um.

### 2. Alta prioridade: a posição encontrada no texto normalizado é aplicada ao texto original

Em [edital_analysis_service.py:208](S:/Leo/projeto-licitacoes-obras/backend/services/edital_analysis_service.py:208), `match.start()` vem de um texto cujos espaços e quebras foram reduzidos. Esse deslocamento é usado para recortar o original, que tem outro comprimento.

**Reprodução:** acrescentar uma introdução, espaços de diagramação e outra frase antes de uma obrigação reconhecida faz o resultado cair de um item para zero. **Correção:** normalizar cada trecho já separado do original ou manter um mapa entre posições normalizadas e originais. Preservar sempre a evidência literal.

### 3. Alta prioridade: o cache pode esconder um novo anexo que falhou no download

Em [edital_analysis_service.py:360](S:/Leo/projeto-licitacoes-obras/backend/services/edital_analysis_service.py:360), o hash considera somente downloads bem-sucedidos. Depois de analisar um edital, a inclusão de um anexo cujo download falha gera a mesma chave. O retorno antecipado do cache reutiliza o resultado anterior e omite o novo anexo e sua falha.

**Reprodução:** primeiro consultar apenas o documento 1; depois consultar 1 e 2, simulando falha no 2. O resultado continua listando apenas o 1. **Correção:** considerar a lista completa de documentos selecionados e seus estados na compatibilidade do cache; reaproveitar análises individuais sem esconder falhas atuais.

### 4. Média prioridade: páginas podem repetir ou perder registros quando o PNCP muda

O cursor em [pncp_service.py:1130](S:/Leo/projeto-licitacoes-obras/backend/services/pncp_service.py:1130) contém posição e assinatura dos filtros. Cada navegação consulta novamente a fonte, e [pncp_service.py:1158](S:/Leo/projeto-licitacoes-obras/backend/services/pncp_service.py:1158) aplica a posição à nova lista.

**Reprodução:** carregar os primeiros 15 de 30 registros; inserir uma publicação no início; pedir a segunda página. O registro 14 aparece nas duas páginas. **Correção:** vincular o cursor a um snapshot com validade explícita e ordenação estável, ou adotar paginação por uma chave estável adequada à fonte. A primeira busca pode continuar consultando o PNCP normalmente.

### 5. Média prioridade: filtrar uma página sem correspondências remove a navegação

[ObrasList.jsx:69](S:/Leo/projeto-licitacoes-obras/frontend/src/components/ObrasList.jsx:69) retorna a tela vazia antes de renderizar os botões. Como a busca textual em [App.jsx:229](S:/Leo/projeto-licitacoes-obras/frontend/src/App.jsx:229) trabalha apenas sobre os cards da página atual, não encontrar o termo nessa página esconde “Anterior” e “Próxima”, mesmo com outros resultados disponíveis.

**Correção:** manter a navegação no estado vazio. Definir também o alcance da busca textual: se deve pesquisar toda a consulta, aplicar o filtro antes da paginação no backend; caso seja local, identificar explicitamente “filtrar esta página”. O teste renderiza uma página 2 vazia com ambos os sentidos disponíveis e não encontra o botão “Próxima”.

### 6. Média prioridade: tarefas concluídas após timeout permanecem registradas

Em [edital_analysis_service.py:346](S:/Leo/projeto-licitacoes-obras/backend/services/edital_analysis_service.py:346), `shield` mantém a análise em execução após cancelar a espera. A limpeza só ocorre se a tarefa já terminou quando o `finally` é executado. Se terminar depois, permanece em `_inflight` até outra consulta da mesma contratação.

**Impacto:** retenção de resultados em memória sem o limite do cache; a primeira consulta posterior pode receber o resultado antigo, inclusive com `forcar=true`. **Correção:** remover a entrada em callback de conclusão, verificando a identidade da tarefa, e tratar suas exceções. Aplicar um orçamento ao processamento compartilhado, além do timeout de quem espera. O diagnóstico simula timeout, conclui o processamento e confirma a entrada remanescente.

### 7. Média prioridade: as migrações não reproduzem o modelo de obras

Em [0001_modelo_obras.py:15](S:/Leo/projeto-licitacoes-obras/alembic/versions/0001_modelo_obras.py:15), a tabela é criada sem os índices definidos no modelo e com `created_at` aceitando nulos. Após aplicar todas as migrações em SQLite vazio, `alembic check` identificou ausência de índices em: `ano`, `cnpj`, `created_at`, `data_publicacao`, `modalidade_codigo`, `numero_controle_pncp`, `status_classificacao`, `uf` e `valor_estimado`.

**Impacto:** instalações por migração e por criação automática de tabelas têm estruturas diferentes; consultas e limpeza podem sofrer com crescimento do banco. **Correção:** criar uma nova migração que alinhe índices e nulabilidade, tratando registros antigos antes de impor a restrição. Acrescentar a comparação de modelos ao CI. Não reescrever uma migração já aplicada.

## Melhorias adicionais identificadas por leitura do código

- **Cobertura no CI:** o fluxo do frontend em [.github/workflows/ci.yml](S:/Leo/projeto-licitacoes-obras/.github/workflows/ci.yml) executa lint e build, mas não `npm run test`. Incluir testes de integração da tela principal, filtros, erros e navegação.
- **Indicadores e ordenação:** [App.jsx:253](S:/Leo/projeto-licitacoes-obras/frontend/src/App.jsx:253) ordena apenas a página; a soma em linha 273 também abrange apenas esses cards, embora a interface diga “Volume Total Estimado”. Calcular estatísticas globais no backend ou informar claramente que são da página.
- **Concorrência e memória:** o semáforo em [edital_analysis_service.py:386](S:/Leo/projeto-licitacoes-obras/backend/services/edital_analysis_service.py:386) limita downloads dentro de uma contratação. Diferentes contratações possuem limites independentes e os arquivos são acumulados antes da análise. Definir limite compartilhado, fila e orçamento de bytes por análise; validar com teste de carga. Não foi realizado teste de carga nesta auditoria.
- **Banco em rotas assíncronas:** a persistência em [pncp_service.py:1327](S:/Leo/projeto-licitacoes-obras/backend/services/pncp_service.py:1327) é síncrona dentro da consulta assíncrona. Transferir a unidade de trabalho para uma thread com sua própria sessão, ou adotar acesso assíncrono. Medir a latência com banco lento.
- **Ambiente reproduzível:** as dependências Python possuem apenas limites mínimos; o Ruff aponta Python 3.14 e o CI usa 3.12. Definir versões suportadas e uma resolução reproduzível das dependências. Há também dois arquivos `.pyc` ainda rastreados pelo Git, apesar do `.gitignore`.
- **Teste do Tesseract:** usar a mesma configuração da aplicação na verificação de disponibilidade, evitando ignorar um OCR funcional.

## Reproduzir os diagnósticos

Os novos casos afirmam o comportamento desejado e **devem falhar no código auditado**. Foram mantidos fora da descoberta padrão para não confundir o resultado da suíte existente. As falhas foram reproduzidas com dados sintéticos, sem chamadas ao PNCP e sem gravar no banco do projeto.

Na raiz do projeto, usando um terminal dedicado:

```powershell
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:APP_ENV = 'test'
$env:PYTHONDONTWRITEBYTECODE = '1'
./.venv/Scripts/python.exe -m pytest specs/auditoria-2026-09-08/test_regressoes.py -q --tb=short
```

No diretório `frontend`:

```powershell
npm.cmd exec vitest run -- --config audit/vitest.config.js
```

Para verificar migrações, usar um arquivo novo em diretório temporário; não usar `:memory:`, pois os comandos são processos diferentes:

```powershell
$auditDb = Join-Path ([System.IO.Path]::GetTempPath()) ('licitacoes-audit-' + [guid]::NewGuid().ToString('N') + '.db')
$env:DATABASE_URL = 'sqlite:///' + $auditDb.Replace('\', '/')
./.venv/Scripts/python.exe -m alembic upgrade head
./.venv/Scripts/python.exe -m alembic check
```

## Escopo e ordem sugerida

Priorizar a extração e a compatibilidade do cache (itens 1–3), depois navegação (4–5), tarefas após timeout e migrações (6–7). Incorporar os diagnósticos à suíte regular conforme cada correção for implementada.

A auditoria considerou o estado local, incluindo alterações já existentes. Foram adicionados apenas este relatório e os arquivos de diagnóstico; o código da aplicação e o banco original foram preservados. A API real do PNCP, PostgreSQL, navegação visual em navegador e comportamento sob carga não foram validados. O OCR real foi testado com imagem sintética, não com uma amostra representativa de editais digitalizados.
