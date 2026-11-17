# Requisitos — Análise de exigências do edital por PDF/OCR

## 1. Origem e interpretação

Esta especificação transforma a solicitação de identificar, nos editais, a documentação que a empresa participante ou executora precisa apresentar em um plano incremental para o sistema de Captação de Obras Públicas.

O arquivo `SINAPI_EXCEL_ADDIN_SPEC.md` continua sendo somente referência de organização. As decisões abaixo são específicas deste projeto e não importam regras de Excel, SINAPI, Office.js, Kotlin ou Spring Boot.

## 2. Situação atual do projeto

O projeto já possui:

- backend Python/FastAPI com integração ao PNCP;
- frontend React/Vite;
- rota de documentos publicados da contratação: `GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos`;
- cache curto em memória para consultas PNCP;
- `pypdf`, `pdfplumber`, `pdfminer.six`, `Pillow` e `pypdfium2` disponíveis no ambiente virtual local;
- executáveis `pdfinfo` e `pdftoppm` do Poppler disponíveis no runtime do ambiente;
- testes unitários e de integração no backend.

O ambiente não possui atualmente um motor de OCR configurado. Não foram encontrados Tesseract, `pytesseract`, `ocrmypdf`, OpenCV ou uma biblioteca de modelos de visão/NLP. As bibliotecas de PDF atualmente disponíveis no ambiente também precisam ser reconciliadas com `requirements.txt` antes de uma implementação reproduzível em outra máquina.

## 3. Objetivo

Permitir que o sistema localize, nos editais e anexos publicados no PNCP, as exigências documentais dirigidas à empresa licitante ou contratada e apresente:

1. um resumo compacto no card da obra quando houver análise disponível;
2. uma lista detalhada na aba de detalhes;
3. a fonte de cada item, com documento, página e trecho de evidência;
4. o estado da análise, sua cobertura e eventuais limitações.

O produto deve dizer **exigências identificadas no edital**. Não deve afirmar que uma empresa está habilitada, que um documento é juridicamente suficiente ou que a lista automática substitui a leitura do edital.

## 4. Decisões confirmadas

“Documentação que a empresa que vai executar precisa” pode significar duas coisas diferentes:

- documentação de habilitação para participar da licitação;
- documentos e obrigações da empresa vencedora durante a execução ou assinatura do contrato.

Foram confirmadas para a primeira versão as seguintes decisões:

- analisar somente a **documentação de habilitação do licitante**;
- iniciar a análise quando o usuário clicar no card e abrir os detalhes da obra;
- abrir o modal imediatamente com os dados já disponíveis, executando a análise em estado separado de carregamento;
- usar um **motor de OCR local** como primeira opção;
- deixar obrigações da contratada, documentos de assinatura, proposta e documentos de execução para uma etapa futura separada.

Não se deve misturar habilitação, proposta, obrigações da contratada, documentos para assinatura e medições em uma única lista.

## 5. Escopo incluído

- selecionar o edital e anexos relevantes entre os documentos publicados da contratação;
- baixar os arquivos públicos do PNCP sob limites de tamanho, páginas e tempo;
- extrair texto de PDFs digitais;
- detectar páginas com pouco ou nenhum texto;
- aplicar OCR somente nas páginas que precisarem;
- localizar seções e expressões relacionadas a habilitação e documentação;
- classificar itens nas categorias do domínio;
- preservar página, documento e trecho de evidência;
- devolver análise parcial quando algum PDF não puder ser lido;
- apresentar resumo no card quando o resultado estiver disponível em cache/persistência, sem iniciar análise em massa;
- apresentar a análise completa na aba de detalhes;
- permitir reprocessamento quando a versão do documento ou do analisador mudar.

## 6. Fora do escopo inicial

- verificar se uma empresa específica possui os documentos;
- validar autenticidade, validade, assinatura, regularidade ou suficiência jurídica;
- afirmar que a lista automática é uma checklist completa;
- interpretar documentos manuscritos ou imagens complexas sem uma etapa específica;
- analisar automaticamente todos os cards durante o carregamento inicial;
- resumir contratos, atas, aditivos ou medições posteriores;
- enviar, alterar, excluir ou armazenar documentos no PNCP;
- usar IA generativa como única fonte sem evidência textual rastreável.

## 7. Categorias de análise

Os itens identificados devem ser classificados, quando possível, em:

- `habilitacao_juridica`;
- `qualificacao_tecnica`;
- `regularidade_fiscal_social_trabalhista`;
- `qualificacao_economico_financeira`;
- `declaracoes`;
- `documento_referenciado`;
- `nao_classificado`.

`proposta_e_precificacao` e `obrigacoes_da_contratada` ficam reservadas para fases futuras e não devem ser analisadas na primeira versão.

As quatro primeiras categorias correspondem à divisão geral de habilitação da Lei nº 14.133/2021. A classificação é informativa e deve preservar a redação e a fonte do edital.

## 8. Requisitos funcionais

**RF-001 — Seleção de documentos**  
O sistema DEVE priorizar documentos cujo tipo ou título contenha termos como `edital`, `instrumento convocatório`, `habilitação`, `qualificação`, `anexo`, `termo de referência` ou `projeto básico`, sem descartar silenciosamente outros arquivos relacionados.

**RF-002 — Download controlado**  
QUANDO um documento for selecionado para análise, o backend DEVE baixá-lo somente de origem autorizada, respeitando timeout, limite de bytes, limite de páginas e redirects seguros.

**RF-003 — Extração sem OCR**  
O sistema DEVE tentar primeiro extrair texto e metadados com as bibliotecas de PDF já disponíveis, registrando quantidade de caracteres, páginas processadas e qualidade estimada.

**RF-004 — OCR condicional**  
SE uma página for escaneada ou tiver texto insuficiente, ENTÃO o sistema DEVE encaminhá-la a um adaptador de OCR configurado, sem rasterizar desnecessariamente todas as páginas.

**RF-005 — Localização de seções**  
O sistema DEVE identificar ocorrências de seções e termos relacionados somente à habilitação, documentação, qualificação técnica, regularidade e declarações. Referências a proposta e execução contratual devem ficar fora do resultado da primeira versão.

**RF-006 — Extração de itens**  
Cada exigência identificada DEVE preservar a descrição original ou uma normalização claramente marcada, a categoria, o documento de origem, a página e o trecho de evidência.

**RF-007 — Confiança e análise parcial**  
O sistema DEVE indicar quando um item foi identificado com baixa confiança, quando houve OCR ou quando parte dos anexos não pôde ser processada.

**RF-008 — Resumo no card**  
QUANDO o usuário clicar no card, o sistema DEVE abrir os detalhes da obra e iniciar a análise de habilitação em segundo plano. QUANDO houver análise concluída ou parcial disponível, o card DEVE poder mostrar quantidade de itens e categorias encontradas. Sem análise, deve mostrar estado “Ainda não analisado”.

**RF-009 — Detalhe rastreável**  
Na aba de detalhes, o sistema DEVE exibir os itens agrupados e oferecer link para o arquivo de origem, página e evidência textual sempre que disponível.

**RF-010 — Reprocessamento**  
O sistema DEVE invalidar ou reprocessar o resultado quando mudar o hash do documento, a versão do analisador, as regras de classificação ou o motor de OCR.

## 9. Requisitos não funcionais

**RNF-001 — Desempenho**  
A abertura da listagem de obras NÃO DEVE iniciar download ou OCR em massa. O clique no card deve abrir o modal sem aguardar o OCR; a análise ocorre sob demanda, com carregamento independente, cache e possibilidade de resultado parcial.

**RNF-002 — Segurança de rede**  
O backend DEVE aceitar somente URLs derivadas dos documentos do PNCP e de hosts permitidos, validar o host após redirects e impedir SSRF, esquemas não HTTP/HTTPS e downloads ilimitados.

**RNF-003 — Reprodutibilidade**  
As dependências de PDF/OCR e suas versões DEVEM estar declaradas no projeto antes da implementação, para que o fluxo funcione em ambiente limpo.

**RNF-004 — Auditabilidade**  
Nenhum item deve ser devolvido como exigência sem documento e página de origem, salvo quando o estado for explicitamente “não rastreável” ou “revisão necessária”.

**RNF-005 — Segurança jurídica**  
A interface DEVE diferenciar “identificado no edital”, “referenciado em outro anexo”, “não localizado” e “não foi possível analisar”.

**RNF-006 — Compatibilidade**  
A solução DEVE preservar a resposta e o comportamento atuais de busca de obras e de listagem de documentos publicados.

**RNF-007 — Observabilidade**  
O backend DEVE registrar métricas resumidas de processamento, como documentos selecionados, páginas com OCR, duração, estado e versão do analisador, sem registrar o PDF inteiro ou dados desnecessários.

## 10. Critérios de aceitação do plano

- [x] O escopo inicial foi confirmado como documentação de habilitação do licitante.
- [x] O gatilho foi confirmado como o clique no card, com análise dentro da aba de detalhes.
- [x] A primeira opção de OCR foi confirmada como motor local.
- [ ] Uma amostra de editais reais, digitais e escaneados, foi escolhida para benchmark.
- [ ] O motor de OCR foi escolhido com base em precisão, instalação, idioma português e custo operacional.
- [ ] O resultado de cada item possui documento, página e evidência.
- [ ] Um PDF digital é processado sem OCR quando seu texto é suficiente.
- [ ] Um PDF escaneado dispara OCR somente nas páginas necessárias.
- [ ] PDF inválido, protegido, vazio ou excedente retorna estado parcial/erro compreensível.
- [ ] Nenhum documento é analisado em massa durante o carregamento inicial dos cards.
- [ ] O card exibe resumo sem afirmar validação jurídica.
- [ ] O detalhe permite conferir a fonte original de cada exigência.
- [ ] Existe conjunto de testes com PDFs reais anonimizados ou fixtures controladas.
- [ ] A análise não classifica automaticamente uma empresa como habilitada, inabilitada ou irregular.

## 11. Definição de pronto

A funcionalidade estará pronta quando o pipeline texto/OCR, a classificação por evidência, os estados parciais, o contrato backend, o resumo do card e o detalhe tiverem sido implementados e validados com amostra variada de editais. A primeira entrega deve declarar suas limitações e nunca apresentar a extração automática como parecer jurídico.
