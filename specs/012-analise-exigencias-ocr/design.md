# Design — Análise de exigências de editais por PDF/OCR

## 1. Decisões confirmadas e recomendações técnicas

### 1.1. Análise no clique, texto primeiro e OCR como fallback

Ao clicar no card, o modal deve abrir imediatamente com os dados já conhecidos da obra. A análise de habilitação começa de forma assíncrona na própria aba de detalhes. Se já houver resultado compatível em cache/persistência, o resumo deve aparecer sem novo processamento.

O pipeline deve tentar extrair texto antes de usar OCR:

```text
ObraCard / ObraDetailModal
        |
        v
GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias
        |
        v
serviço de análise de edital
        |
        +--> documentos PNCP e seleção de edital/anexos
        |
        +--> download seguro e hash
        |
        +--> pypdf/pdfplumber/pdfminer.six
        |
        +--> medição de qualidade por página
        |
        +--> OCR somente nas páginas necessárias
        |
        +--> localização de seções e classificação
        |
        +--> resultado com evidência, confiança e estado
```

PDF não é sinônimo de imagem. Muitos editais já possuem uma camada de texto pesquisável; nesses casos, OCR adicionaria custo e poderia introduzir erros. OCR deve ser reservado para páginas sem texto ou com extração insuficiente.

### 1.2. Bibliotecas já disponíveis

O plano aproveita o que já existe no ambiente:

| Necessidade | Biblioteca/Runtime disponível | Uso planejado |
|---|---|---|
| Texto e metadados | `pypdf` | fallback de leitura, páginas, metadados e validações |
| Texto/layout/tabelas | `pdfplumber` | extrair texto por página e preservar posições quando necessário |
| Parser usado pelo pdfplumber | `pdfminer.six` | suporte de parsing já presente no ambiente |
| Imagens | `Pillow` | preparar imagens para OCR e testes |
| Renderização | `pypdfium2` | converter páginas em imagens sem depender do browser |
| Diagnóstico/renderização | Poppler (`pdfinfo`, `pdftoppm`) | inspeção e fallback operacional |

O ambiente não possui motor de OCR. A estratégia local foi confirmada. A primeira tarefa técnica deve reconciliar as dependências já instaladas com `requirements.txt` e realizar um spike entre motores locais, tendo Tesseract com idioma português como recomendação inicial. Isso exige instalar/configurar o binário e o pacote de integração; não faz parte deste plano executado agora.

Uma alternativa futura é um serviço de OCR externo ou um modelo local, mas ela deve ser aprovada separadamente por causa de custo, privacidade, disponibilidade de rede e reprodutibilidade.

## 2. Pipeline detalhado

### Etapa A — Obter documentos

Reutilizar a consulta já implementada em `backend/services/pncp_service.py`. A análise não deve depender apenas do título: deve usar `tipo_documento_nome`, `titulo`, ordem e termos encontrados.

Prioridade recomendada:

1. edital ou instrumento convocatório;
2. anexos do edital;
3. documentos explicitamente nomeados como habilitação ou qualificação;
4. termo de referência/projeto básico, apenas quando o edital os referenciar para uma exigência de habilitação;
5. demais arquivos, marcados como documentos complementares e não analisados como habilitação automaticamente.

### Etapa B — Baixar com segurança

Criar um downloader isolado que:

- aceite somente `https` e hosts permitidos do PNCP;
- rejeite IPs privados, localhost e redirects para hosts desconhecidos;
- use timeout de conexão e leitura independentes;
- limite bytes e páginas antes de processar;
- valide `Content-Type`, assinatura `%PDF` e tamanho real;
- não registre conteúdo completo nos logs;
- gere hash SHA-256 do arquivo para cache e reprocessamento.

O downloader deve impedir que um link publicado no PNCP seja usado como entrada arbitrária para acessar recursos internos.

### Etapa C — Extrair texto

Executar por página para que o sistema consiga indicar exatamente onde houve falha. A primeira tentativa deve usar `pdfplumber`; `pypdf` e `pdfminer.six` servem como fallback e para diagnósticos.

Para cada página registrar internamente:

- número da página;
- quantidade de caracteres;
- proporção de caracteres imprimíveis;
- presença de palavras esperadas;
- erro de parsing, se houver;
- estado `texto_suficiente`, `texto_insuficiente` ou `sem_texto`.

O limiar de texto não deve ser fixado sem benchmark. Deve ser calibrado usando uma amostra de editais digitais e escaneados.

### Etapa D — Renderizar e fazer OCR

Somente páginas marcadas como `texto_insuficiente` ou `sem_texto` devem ser renderizadas. O plano deve testar inicialmente resolução entre 200 e 300 DPI e idioma português.

O adaptador de OCR deve devolver:

- texto reconhecido;
- idioma/configuração usada;
- confiança quando o motor fornecer;
- duração;
- número da página;
- estado de erro ou baixa qualidade.

Se o OCR falhar, o documento deve seguir como `analise_parcial`, com link para leitura manual. Não se deve transformar uma página ilegível em lista vazia.

### Etapa E — Localizar trechos relevantes

Aplicar primeiro regras determinísticas e tolerantes a variações de acentuação, caixa e numeração. Exemplos de âncoras:

- `habilitação`, `documentos de habilitação`;
- `qualificação técnica`, `atestado`, `registro profissional`, `acervo`;
- `regularidade fiscal`, `trabalhista`, `FGTS`, `CND`;
- `qualificação econômico-financeira`, `balanço`, `patrimônio`, `índices`;
- `declaração`, `declarações`;
- `documentos exigidos para habilitação`, `documentos do licitante`;
- referências a anexo, modelo ou item que complementem uma exigência de habilitação.

Termos de proposta, execução, garantia, ART/RRT e obrigações da contratada não entram no resultado da primeira versão; devem ser registrados como fora do escopo quando encontrados.

O algoritmo deve capturar o bloco da seção, respeitando títulos, numeração e mudança de seção. Referências para “Anexo”, “item”, “subitem” ou “conforme modelo” devem gerar relações para conferência, não uma falsa exigência isolada.

### Etapa F — Normalizar sem apagar a redação

O item normalizado pode conter um rótulo curto, mas deve preservar o texto original:

```json
{
  "categoria": "qualificacao_tecnica",
  "rotulo": "Atestado de capacidade técnica",
  "descricao_original": "apresentar atestado ... conforme item 8.4.1",
  "documento_id": 1,
  "titulo_documento": "Edital de Concorrência",
  "pagina": 18,
  "evidencia": "8.4.1 ... apresentar atestado ...",
  "confianca": 0.86,
  "origem_texto": "pdf_texto",
  "status": "identificado_no_edital"
}
```

Os valores `confianca` e `status` são da análise automática, não da validade jurídica. Caso o trecho seja ambíguo ou dependa de anexo não processado, usar `revisao_necessaria` ou `referenciado_em_outro_documento`.

### Etapa G — IA opcional

Uma IA pode ajudar a agrupar redações diferentes, mas não deve ser a primeira camada nem a única fonte. Se for aprovada, receberá apenas blocos já localizados e deverá devolver JSON validado, sempre com páginas e trechos presentes no texto de entrada.

O sistema deve rejeitar uma saída que:

- não aponte página/documento;
- invente item não presente no texto;
- transforme recomendação em obrigação;
- misture documento da Administração com documento exigido da empresa;
- não consiga ser validada pelo schema.

## 3. Contrato de backend proposto

### 3.1. Rota

```http
GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/exigencias
```

Parâmetro opcional futuro:

- `forcar=true`: ignorar cache e reprocessar;

O escopo de habilitação será fixo na primeira versão. Um escopo de execução somente poderá ser adicionado em uma especificação posterior.

### 3.2. Resposta

```json
{
  "status": "sucesso_parcial",
  "mensagem": "Exigências identificadas no edital; alguns anexos não puderam ser analisados.",
  "total_exigencias": 7,
  "categorias": {
    "habilitacao_juridica": 1,
    "qualificacao_tecnica": 3,
    "regularidade_fiscal_social_trabalhista": 2,
    "declaracoes": 1
  },
  "documentos_analisados": [
    {
      "documento_id": 1,
      "titulo": "Edital de Concorrência",
      "paginas": 42,
      "paginas_com_ocr": 0,
      "status": "analisado"
    }
  ],
  "exigencias": [
    {
      "categoria": "qualificacao_tecnica",
      "rotulo": "Atestado de capacidade técnica",
      "descricao_original": "...",
      "documento_id": 1,
      "pagina": 18,
      "evidencia": "...",
      "confianca": 0.86,
      "origem_texto": "pdf_texto",
      "status": "identificado_no_edital"
    }
  ],
  "analisador_versao": "ocr-edital-v1",
  "origem": "PNCP"
}
```

Estados mínimos: `nao_analisado`, `processando`, `sucesso`, `sucesso_parcial`, `sem_documento_analisavel` e `erro`.

## 4. Persistência e cache

Como OCR e parsing são mais caros que a listagem de documentos, o resultado deve ser associado a:

```text
id_pncp + hash dos documentos selecionados + versão do analisador
```

Para protótipo, o cache em memória existente pode ser usado durante o spike. Para o resumo persistir entre reinícios e aparecer de forma consistente nos cards, a recomendação é uma tabela de análise no SQLite/SQLAlchemy, com status, hash, versão, JSON normalizado e timestamps. O PDF bruto não precisa ser armazenado pelo sistema nessa fase; o link público e o hash são suficientes para reprocessamento.

## 5. Interface

### Card

O card deve mostrar somente um resumo, por exemplo:

```text
Exigências do edital
7 itens identificados · 4 categorias
Qualificação técnica · Regularidade fiscal
```

Estados visuais:

- `Ainda não analisado`, indicando que a análise será iniciada ao abrir o detalhe;
- `Analisando documentos`;
- resumo disponível;
- `Análise parcial`;
- `Não foi possível ler os anexos`.

O card não deve exibir uma lista longa nem sugerir que a análise seja parecer jurídico. A listagem inicial não deve fazer chamadas de OCR; o primeiro processamento acontece ao abrir o detalhe.

### Aba de detalhes

Adicionar seção separada da lista de documentos publicados:

```text
Exigências identificadas no edital

Habilitação técnica
  - Atestado de capacidade técnica
    Edital, página 18
    Ver trecho / abrir documento

Regularidade fiscal
  - Certidão ...
    Edital, página 21
```

Cada item deve permitir abrir a fonte original. Quando o navegador não conseguir abrir diretamente em uma página, mostrar o número da página e o trecho para localização manual.

## 6. Estrutura provável de arquivos

```text
backend/
├── schemas.py                              contratos da análise
├── main.py                                 rota e estados HTTP
├── config.py                               limites e flags do pipeline
├── models/edital_analysis_model.py         persistência da análise, se aprovada
└── services/
    ├── pdf_download_service.py             download e segurança
    ├── pdf_text_service.py                 texto, metadados e qualidade
    ├── ocr_service.py                      adaptador do motor OCR
    └── edital_analysis_service.py          regras, classificação e evidências

frontend/src/
├── api.js                                  cliente da análise
├── components/ObraCard.jsx                 resumo/cache/ação
└── components/ObraDetailModal.jsx          detalhe rastreável e estados

backend/tests/
├── unit/test_pdf_text_service.py
├── unit/test_ocr_service.py
├── unit/test_edital_analysis_service.py
└── integration/test_endpoints_exigencias.py
```

## 7. Qualidade e riscos

- PDF digital pode ter texto em ordem incorreta, colunas, tabelas ou caracteres quebrados;
- OCR pode confundir números, siglas, CNPJ, artigos e valores;
- editais podem dividir uma exigência entre edital e anexos;
- títulos de arquivos podem ser incompletos ou incorretos;
- uma mesma palavra pode descrever obrigação da Administração, do licitante ou da contratada;
- o PNCP pode retornar link indisponível ou documento substituído;
- processamento em massa pode provocar custo, lentidão e rate limit.

Por isso, o benchmark deve usar editais reais variados, com conferência manual de amostras. O objetivo da primeira versão é localizar e evidenciar, não prometer exaustividade jurídica.
