# Spec 015 — Indexação vetorial de editais

**Origem:** decisão de produto de 16/09/2026 para preparar o acervo de editais do PNCP com PostgreSQL/`pgvector` e OpenAI, começando pela identificação de documentos exigidos nos cards atuais.
**Fase:** 6 — Evolução de dados, análise assistida e recuperação semântica · **Bloqueia produção:** Não nesta etapa; a ativação depende de validação de custo, segurança, qualidade e revisão humana.

## Contexto

O sistema já baixa PDFs e ZIPs autorizados do PNCP, extrai texto por página e aplica OCR seletivo. O processamento atual é transitório: os PDFs não são gravados e somente o resultado normalizado da análise de exigências é persistido.

Isso é adequado para a funcionalidade atual, mas não forma um acervo pesquisável nem permite enriquecer de modo consistente o resumo de cada card. Esta spec introduz uma camada de indexação vetorial rastreável e uma análise estruturada assistida pela API da OpenAI para identificar documentos necessários no edital. O resultado será adaptado ao contrato atual de `resumo_exigencias`; não será construído ainda um agente conversacional, chat, endpoint público de perguntas ou interface de busca semântica.

## Escopo

Incluído:

- transformar texto extraído de PDFs em trechos e embeddings;
- persistir vetores, texto e metadados de origem em banco vetorial integrado ao banco da aplicação;
- usar a API da OpenAI para gerar embeddings e analisar, em formato estruturado, documentos exigidos, evidências, páginas e categorias;
- persistir o resultado versionado da análise e projetar um resumo compatível com os cards atuais;
- processar documentos sob demanda e em lote de forma resiliente;
- manter versões, proveniência, retenção, métricas e testes.

Fora do escopo:

- agente conversacional, ferramenta de agente ou acesso livre ao banco;
- endpoint público de pergunta/resposta, nova tela de chat ou chatbot;
- persistência de PDFs ou ZIPs brutos;
- interpretar juridicamente os documentos recuperados ou afirmar que a exigência é juridicamente válida.

## Requisitos

| ID | Requisito |
|---|---|
| R015-1 | O sistema DEVE reutilizar o download validado, a extração de texto e o OCR existentes, sem gravar o PDF ou ZIP bruto no disco ou no banco. |
| R015-2 | QUANDO um PDF for processado com texto aproveitável, ENTÃO o sistema DEVE dividi-lo em trechos estáveis, preservando documento, página, ordem e texto original do trecho. |
| R015-3 | O sistema DEVE persistir, para cada trecho, seu vetor, hash, versão de extração/chunking, modelo de embedding, origem do texto e metadados suficientes para citar a fonte posteriormente. |
| R015-4 | QUANDO o mesmo conteúdo de PDF, versão de processamento e modelo de embedding forem recebidos novamente, ENTÃO o sistema DEVE reaproveitar a indexação existente sem gerar vetores duplicados. |
| R015-5 | QUANDO o conteúdo de um documento ou a configuração de processamento mudar, ENTÃO o sistema DEVE criar ou ativar a versão nova e impedir que trechos obsoletos sejam considerados ativos. |
| R015-6 | ENQUANTO a geração de embeddings estiver indisponível, limitada ou atingir seu orçamento, o sistema DEVE registrar o estado do documento, aplicar retentativas controladas e não bloquear as rotas atuais de obras ou exigências. |
| R015-7 | O sistema DEVE limitar concorrência, tamanho, páginas, quantidade de trechos, tentativas e custo estimado por processamento, respeitando também os limites já aplicados ao download e OCR. |
| R015-8 | O sistema DEVE usar uma implementação de armazenamento vetorial compatível com PostgreSQL e a extensão `pgvector`; em SQLite, a indexação real não DEVE ser ativada silenciosamente. |
| R015-9 | O sistema DEVE manter filtros de proveniência por contratação, documento, página, UF e estado de indexação, mesmo que a consulta semântica para usuários ainda não seja exposta. |
| R015-10 | O sistema DEVE registrar métricas e falhas por etapa — seleção, download, extração, OCR, chunking, embedding e persistência — sem expor conteúdo de edital, URLs privadas ou credenciais em logs. |
| R015-11 | A geração de embeddings DEVE usar a API da OpenAI por meio de um adaptador versionado, com `OPENAI_API_KEY` já padronizada, `text-embedding-3-small` como modelo inicial e dimensão configurável, sem expor a chave em logs ou respostas. |
| R015-12 | O sistema DEVE aplicar retenção e remoção lógica ou física aos vetores e textos derivados quando a contratação, documento ou versão deixar de ser elegível, preservando somente os metadados operacionais necessários. |
| R015-13 | O sistema NÃO DEVE adicionar nesta spec agente conversacional, chat, endpoint público de recuperação semântica ou interface de pergunta/resposta; a API da OpenAI será usada somente no processamento interno. |
| R015-14 | QUANDO houver texto elegível de um edital, ENTÃO o analisador da OpenAI DEVE receber contexto delimitado e instruções que tratem o conteúdo do edital como dado não confiável, retornando somente JSON validável pelo schema da aplicação. |
| R015-15 | O resultado da análise DEVE identificar o documento exigido, categoria, resumo curto, página, trecho de evidência, confiança e estado (`identificado`, `incerto` ou `não_identificado`) sem inventar exigências ausentes no texto fornecido. |
| R015-16 | O backend DEVE converter uma análise válida para o contrato atual de `resumo_exigencias`, mantendo `status`, `total_exigencias`, `categorias` e `analisador_versao` usados pelos cards atuais. |
| R015-17 | A análise assistida DEVE ser versionada por hashes dos PDFs/chunks, modelo OpenAI, versão do prompt e schema; uma mudança nesses elementos DEVE permitir reprocessamento sem sobrescrever silenciosamente a evidência anterior. |
| R015-18 | SE a API da OpenAI falhar, exceder limite, retornar JSON inválido ou não houver contexto suficiente, ENTÃO o sistema DEVE preservar a análise local/fallback existente, marcar o resultado como parcial ou indisponível e não bloquear a listagem de obras. |
| R015-19 | O card atual DEVE exibir uma lista compacta dos documentos exigidos identificados, deixar distinguível que o resultado veio de análise assistida e manter acesso ao detalhe com fonte, página e trecho; o resultado NÃO DEVE ser apresentado como parecer jurídico. |
| R015-20 | O sistema DEVE registrar tokens, latência, custo estimado, modelo, versão do prompt, taxa de falha e quantidade de itens aceitos/rejeitados, sem armazenar prompts completos ou respostas sensíveis em logs operacionais. |
| R015-21 | QUANDO o usuário abrir uma contratação sem análise compatível, ENTÃO o sistema DEVE iniciar ou reutilizar um job exclusivo daquela contratação, sem executar preenchimento histórico automático nesta fase. |
| R015-22 | O card atual DEVE exibir os documentos exigidos identificados em lista compacta, com indicação de análise assistida e estado de incerteza/falha quando aplicável. |

## Critérios de aceitação

- [ ] **CA015-1:** um PDF digital, um PDF digitalizado e um ZIP com PDFs passam pelo mesmo pipeline seguro; somente as páginas que precisarem usam OCR e nenhum arquivo bruto é escrito ou persistido.
- [ ] **CA015-2:** cada chunk salvo contém texto original, página, ordem, contratação, título/identificador do documento, URL de origem, hash do conteúdo, origem do texto e versões de processamento.
- [ ] **CA015-3:** reprocessar o mesmo PDF com a mesma configuração não chama o provedor novamente nem cria linhas duplicadas.
- [ ] **CA015-4:** modificar o hash do PDF, a estratégia de chunking ou o modelo cria uma versão distinta; somente a versão ativa é elegível para recuperação futura.
- [ ] **CA015-5:** uma falha de provedor, timeout, documento ilegível ou limite de custo deixa diagnóstico recuperável e não degrada a resposta dos endpoints existentes de obras e exigências.
- [ ] **CA015-6:** o banco PostgreSQL descartável com `pgvector` aplica as migrações e executa uma busca de vizinhos mais próximos restrita a uma contratação; SQLite não tenta executar SQL vetorial.
- [ ] **CA015-7:** a fila persiste estados pendente, em execução, concluído, falho e esgotado; reinício do processo não perde trabalho nem processa a mesma unidade simultaneamente.
- [ ] **CA015-8:** limites de bytes, páginas, chunks, lotes, concorrência e tentativas são cobertos por testes e produzem estados/métricas explícitos.
- [ ] **CA015-9:** a amostra anotada em português recupera os trechos-fonte esperados entre os primeiros resultados para consultas de validação definidas antes da escolha do modelo.
- [ ] **CA015-10:** não existe agente conversacional, chat ou endpoint público de pergunta adicionado como parte desta entrega.
- [ ] **CA015-11:** a análise OpenAI recebe apenas chunks/contexto delimitado, retorna JSON conforme schema e rejeita resposta inválida sem gravar resultado como sucesso.
- [ ] **CA015-12:** um edital com “apresentar atestado de capacidade técnica” produz item com documento, categoria, página/evidência e confiança; texto sem exigência não gera item inventado.
- [ ] **CA015-13:** uma análise válida aparece nos campos usados pelos cards (`resumo_exigencias`, total, categorias e documentos exigidos), sem quebrar o fallback local nem a abertura do detalhe.
- [ ] **CA015-14:** reprocessar com novo PDF, modelo, prompt ou schema cria versão nova e mantém a anterior auditável/inativa.
- [ ] **CA015-15:** indisponibilidade, limite ou custo excedido da OpenAI mantém a consulta de obras disponível e exibe estado parcial/indisponível no resumo.
- [ ] **CA015-16:** métricas e logs permitem distinguir tokens/custo/latência por embeddings e análise estruturada, sem expor chave, prompt completo ou conteúdo integral do edital.
- [ ] **CA015-17:** ao abrir uma contratação sem análise compatível, o sistema inicia a análise daquela contratação; quando concluída, o card atual pode ser atualizado/recarregado para mostrar os documentos exigidos.
- [ ] **CA015-18:** o card mostra os documentos exigidos com rótulo de análise assistida e estado compreensível quando houver incerteza, ausência de documento analisável ou falha da OpenAI.

## Decisões aprovadas para a primeira fase

1. **Modelos:** usar OpenAI; iniciar embeddings com `text-embedding-3-small` (1.536 dimensões) e análise estruturada com `gpt-5-mini`, ambos configuráveis por ambiente e versionados nos resultados.
2. **Tratamento de dados:** está aprovado o envio dos trechos necessários à OpenAI, mantendo chave, prompts e respostas protegidos e registrando somente métricas/IDs nos logs.
3. **Banco e ambiente:** usar PostgreSQL com `pgvector`; no desenvolvimento, o compose expõe o banco em `localhost:55432` e o backend usa `DATABASE_URL` com essa porta. SQLite não será usado para a indexação real.
4. **Disparo inicial:** iniciar a análise quando o usuário abrir cada contratação/detalhe e não houver análise compatível. Não haverá preenchimento histórico automático nesta primeira fase.
5. **Cards:** exibir documentos exigidos em lista compacta no card atual, junto com indicação de análise assistida e estado de incerteza/falha quando aplicável. A evidência completa permanece no detalhe.
