# Design — Documentos de uma Licitação PNCP

## 1. Decisões de design

### 1.1. Backend como proxy de integração

O navegador não deve chamar o PNCP diretamente. O backend fará a consulta porque já concentra timeout, TLS, tratamento de falhas e configuração da integração externa.

Fluxo:

```text
ObraCard
   ↓ seleciona obra
ObraDetailModal
   ↓ carrega sob demanda
frontend/src/api.js
   ↓ GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos
FastAPI
   ↓ valida e normaliza
PNCP service
   ↓ GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
PNCP
```

### 1.2. Consulta sob demanda

Os documentos não serão adicionados à consulta geral de obras. Isso evita uma chamada por card, reduz latência e evita atingir limites do PNCP quando o usuário apenas navega pela listagem.

### 1.3. Sem persistência inicial

O banco continuará armazenando a obra como já faz hoje. Os documentos serão buscados sob demanda e mantidos apenas no cache em memória pelo TTL configurado. Persistência futura exigiria uma decisão específica sobre retenção, atualização e armazenamento de links externos.

## 2. Contrato interno do backend

### 2.1. Rota

```http
GET /api/v1/obras/{cnpj}/{ano}/{sequencial}/documentos
```

Parâmetros:

| Parâmetro | Regra |
|---|---|
| `cnpj` | 14 caracteres alfanuméricos, sem `/`, espaços ou pontuação |
| `ano` | inteiro positivo |
| `sequencial` | inteiro positivo |

### 2.2. Sucesso

```json
{
  "status": "sucesso_real",
  "mensagem": "Documentos da contratação carregados do PNCP.",
  "total": 2,
  "documentos": [
    {
      "sequencial_documento": 1,
      "url": "https://pncp.gov.br/.../arquivo.pdf",
      "tipo_documento_id": 1,
      "tipo_documento_nome": "Edital",
      "titulo": "Edital de Concorrência",
      "data_publicacao_pncp": "2026-09-02"
    }
  ],
  "origem": "PNCP"
}
```

### 2.3. Estados de resposta

| Situação | HTTP | `status` | Comportamento |
|---|---:|---|---|
| Documentos carregados | 200 | `sucesso_real` | exibir a lista |
| Nenhum documento | 200 | `sucesso_vazio` | exibir estado vazio |
| Parâmetro inválido | 422 | — | não chamar PNCP |
| PNCP indisponível/timeout | 503 | — | erro apenas na seção de documentos |
| PNCP respondeu formato inválido | 502 | — | erro seguro |

Erros seguirão o formato simples já usado pelo FastAPI no projeto (`detail`), sem criar uma camada de exceções incompatível com a base atual.

## 3. Contrato com o PNCP

O serviço externo será chamado com:

```text
https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
```

O endpoint real respondeu uma lista direta. O módulo também aceita um objeto com a chave `documentos` ou `data` para tolerar variações compatíveis sem expor o payload externo. A saída interna será sempre `list[DocumentoOut]`.

O prefixo da rota fica centralizado em uma constante do serviço. A busca geral de contratações permanece no prefixo `/api/consulta` porque são serviços distintos.

## 4. Normalização

Mapeamento:

```text
PNCP                         Produto
──────────────────────       ─────────────────────────
sequencialDocumento          sequencial_documento
url                          url
tipoDocumentoId              tipo_documento_id
tipoDocumentoNome            tipo_documento_nome
titulo                       titulo
dataPublicacaoPncp           data_publicacao_pncp
```

Regras:

- `sequencialDocumento` é obrigatório para identificar o documento;
- `url` pode ser nula internamente quando o PNCP não a fornecer, mas não haverá link clicável sem URL HTTP/HTTPS válida;
- campos textuais vazios devem ser convertidos para `null` ou para o fallback visual apropriado;
- documentos sem identificador devem ser descartados e registrados em log como payload incompatível;
- a ordem retornada pelo PNCP deve ser preservada;
- documentos duplicados pelo sequencial devem aparecer somente uma vez.

## 5. Cache e resiliência

Será criado um cache separado do cache da busca de obras:

```text
chave = cnpj:ano:sequencial
TTL    = configuração curta, inicialmente 180 segundos
```

O cache evita repetição ao fechar e reabrir o mesmo detalhe. A consulta de documentos não deve reutilizar o fallback de obras, porque uma obra salva localmente não significa que seus documentos estejam salvos.

O cliente HTTP deve:

- usar o mesmo mecanismo de verificação TLS do serviço existente;
- enviar `Accept: application/json` e um `User-Agent` do produto;
- respeitar timeout configurável;
- tratar `204` como lista vazia;
- tratar `429`, `5xx`, conexão e timeout como falha controlada;
- não registrar payload completo ou URL sensível em logs.

## 6. Design da interface

Dentro do corpo de `ObraDetailModal`, após o objeto da licitação, será incluída a seção:

```text
Documentos publicados no PNCP

[carregando...]                    (loading)

┌────────────────────────────────┐
│ Edital                          │
│ Tipo: Edital                    │
│ Publicado em: 02/09/2026        │
│                         Abrir ↗ │
└────────────────────────────────┘
```

Estados:

1. **Carregando:** spinner ou texto acessível.
2. **Sucesso:** lista de documentos com links em nova aba.
3. **Vazio:** “Nenhum documento foi disponibilizado para esta contratação no PNCP.”
4. **Erro:** “Não foi possível carregar os documentos agora.” e botão “Tentar novamente”.
5. **Sem identificadores:** “Documentos indisponíveis para este registro.”
6. **Mock:** “Documentos reais não estão disponíveis no modo de demonstração.”

O título “Documentos publicados no PNCP” deve permanecer explícito para não sugerir validação jurídica.

## 7. Arquivos e responsabilidades

```text
backend/
├── schemas.py                         contrato DocumentoOut/ResultadoDocumentos
├── main.py                            rota HTTP e mapeamento de erros
└── services/pncp_service.py           chamada, cache e normalização PNCP

frontend/src/
├── api.js                              cliente HTTP do backend
└── components/ObraDetailModal.jsx     estado e apresentação dos documentos

backend/tests/
├── unit/test_documentos_pncp.py        normalização e serviço
└── integration/test_endpoints_obras.py contrato da rota
```

## 8. Segurança e limites

- não receber URL do PNCP como parâmetro do frontend;
- não permitir que o frontend monte a URL externa;
- validar CNPJ como identificador de caminho, incluindo compatibilidade com CNPJ alfanumérico de 14 caracteres;
- filtrar esquemas de URL antes de retorná-los como links;
- não baixar o arquivo no backend nesta primeira versão;
- não interpretar o conteúdo do PDF como se fosse uma decisão jurídica;
- tratar links externos como conteúdo não confiável para exibição, usando `target="_blank"` e `rel="noopener noreferrer"`.

## 9. Validação manual

Após os testes automatizados, validar:

1. abrir a aplicação;
2. abrir uma obra real com `cnpj`, `ano` e `sequencial`;
3. verificar uma chamada única ao backend;
4. conferir título, tipo, data e abertura do link;
5. fechar e reabrir para verificar o cache;
6. simular resposta vazia e erro;
7. abrir um registro mockado e confirmar que não há chamada externa inválida.
