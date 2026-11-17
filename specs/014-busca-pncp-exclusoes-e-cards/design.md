# Design — Spec 014: Busca PNCP, palavras excluídas e enriquecimento dos cards

## 1. Direção de implementação

Usar a arquitetura atual — FastAPI, Pydantic, serviço de consulta PNCP, snapshots de consulta e React/Vite — sem criar um mecanismo externo de busca nesta etapa. O filtro deve ser determinístico, auditável e compatível com o endpoint GET existente.

O plano tem três entregas relacionadas:

1. interpretar inclusão e exclusão como uma expressão de busca própria;
2. filtrar o conjunto coletado no backend antes da paginação;
3. enriquecer o contrato e o card com o tipo da contratação.

Atas e contratos permanecem entidades relacionadas, não devem ser misturados automaticamente à lista de editais de obras. Seus identificadores poderão ser preservados para navegação e enriquecimento posterior.

## 2. Modelo de busca

### 2.1. Expressão compatível

Manter `termo` como parâmetro de entrada para compatibilidade e interpretar:

```text
pavimentação -drenagem -"registro de preços"
```

como:

```json
{
  "incluir": ["pavimentação"],
  "excluir": ["drenagem", "registro de preços"],
  "frases_exatas": ["registro de preços"]
}
```

O parser deve aceitar aspas, espaços repetidos e hífen somente no início de um token ou frase. Um hífen interno de uma palavra não deve criar exclusão. Limitar quantidade, tamanho e caracteres de cada termo para evitar expressões abusivas.

Em uma etapa aditiva, o contrato pode expor também listas estruturadas:

| Parâmetro | Uso |
|---|---|
| `termo` | Expressão legada e compatível com a interface atual |
| `termos_inclusao` | Lista normalizada de termos positivos |
| `termos_exclusao` | Lista normalizada de termos negativos |
| `escopo_busca` | `objeto_itens`, `objeto_itens_orgao`, `todos_metadados` ou enumeração equivalente |
| `modo_inclusao` | `qualquer` por padrão; `todos` como opção explícita |

Se listas estruturadas e `termo` forem enviados juntos, documentar a precedência e rejeitar combinações ambíguas em vez de duplicar silenciosamente os termos.

### 2.2. Normalização e correspondência

Reutilizar `remover_acentos` e a correspondência por palavra inteira já introduzida na Spec 008, evoluindo-a para:

- normalizar caixa, acentos, Unicode, pontuação e espaços;
- comparar frases contíguas depois da normalização;
- preservar o texto original para evidência e apresentação;
- aplicar aliases/sinônimos versionados apenas quando explicitamente cadastrados;
- não usar substring simples como regra de exclusão;
- registrar o campo no qual houve correspondência.

O objeto e os itens são o escopo padrão. O órgão pode conter “engenharia” ou um curso de engenharia sem que o objeto seja uma obra; isso deve ser uma correspondência opcional, não um falso positivo padrão.

### 2.3. Resultado auditável

Adicionar metadados opcionais ao resultado filtrado, sem obrigar o frontend a exibi-los em todos os cards:

```json
{
  "termos_correspondentes": ["pavimentação"],
  "campos_correspondentes": ["objeto"],
  "termos_excluidos": [],
  "motivo_filtro": "incluido_por_termo",
  "score_classificacao": 8
}
```

Para itens removidos antes da paginação, contabilizar o motivo nos metadados da consulta ou em modo de diagnóstico, sem expor resultados excluídos como se fossem oportunidades.

## 3. Fluxo backend e paginação

O fluxo proposto é:

```text
PNCP → normalização do edital → deduplicação por id PNCP
     → busca de itens quando necessário
     → classificação de obra
     → inclusão/exclusão textual
     → ordenação estável
     → totais e agregados
     → snapshot/cursor
     → página retornada
```

O limite de páginas do PNCP continua sendo um limite de alcance da coleta. Os metadados devem distinguir:

- universo estimado no portal;
- registros coletados pela consulta;
- registros aprovados pela classificação;
- registros restantes após inclusão/exclusão;
- registros presentes na página atual.

O identificador PNCP é a chave de deduplicação. Quando o mesmo objeto vier de mais de uma página ou origem, manter o registro mais completo e registrar a origem/atualização.

O termo, o escopo, as listas de inclusão/exclusão, a ordenação e a versão do parser devem fazer parte da assinatura do snapshot/cursor. Alterar qualquer um deles reinicia a consulta.

## 4. Contrato normalizado do tipo da contratação

### 4.1. Campos do backend

Adicionar a `ObraOut` e ao registro normalizado:

| Campo | Semântica |
|---|---|
| `tipo_contratacao` | Texto pronto para exibição no card; pode ser nulo |
| `modalidade` | Nome da modalidade retornado pelo PNCP |
| `modalidade_codigo` | Código da modalidade |
| `criterio_julgamento` | Critério, quando disponível no edital ou item |
| `tipo_instrumento` | Tipo do instrumento convocatório, quando disponível |
| `tipo_contratacao_origem` | Campos usados para montar o texto, para auditoria |

### 4.2. Regra de composição

Priorizar o texto específico publicado pela origem. Quando o PNCP retornar modalidade e critério separados, compor:

```text
{modalidade} por {criterio_julgamento} - {criterio_julgamento}
```

somente se essa for a convenção confirmada pelos dados de origem e não houver um texto específico já pronto. A implementação não deve concatenar cegamente palavras duplicadas. Exemplos esperados:

| Dados disponíveis | `tipo_contratacao` |
|---|---|
| `Concorrência por Menor Preço`, critério `Menor Preço` | `Concorrência por Menor Preço - Menor Preço` |
| `Concorrência - Eletrônica`, sem critério | `Concorrência - Eletrônica` |
| somente modalidade `Pregão - Eletrônico` | `Pregão - Eletrônico` |
| nenhum campo de tipo | nulo, com fallback visual `Tipo não informado` |

Preservar os campos atômicos para filtros e análises. O campo composto é apresentação, não deve ser usado como única fonte para filtragem.

## 5. Card do edital

Atualizar `frontend/src/components/ObraCard.jsx` para exibir, próximo à localidade e antes do objeto:

```text
Localização  [UF]

Tipo
Concorrência por Menor Preço - Menor Preço

Órgão
...
```

O card deve:

- usar `tipo_contratacao` primeiro;
- cair para `modalidade` somente quando o tipo composto não existir;
- mostrar `Tipo não informado` quando ambos estiverem ausentes;
- preservar o badge de modalidade sem duplicar o texto caso o layout fique redundante;
- usar `title`/tooltip ou expansão acessível para tipos longos;
- testar mobile, zoom, teclado e leitor de tela.

O detalhe da contratação deve exibir os campos atômicos — modalidade, critério, tipo de instrumento — para que o usuário consiga auditar o texto resumido do card.

## 6. Interface do filtro

Substituir a dependência de uma única caixa ambígua por uma experiência progressiva:

- caixa de busca compatível com a expressão rápida;
- chips separados `Incluir` e `Excluir` após a interpretação;
- opção de editar/remover cada chip;
- seletor de escopo, com `Objeto e itens` como padrão;
- ajuda curta: `Use - para excluir e aspas para frases`;
- resumo dos filtros ativos e contagem após o filtro;
- estado vazio informando se não houve correspondência ou se todos os resultados foram excluídos.

Não usar o operador negativo do PNCP como implementação. A aplicação deve interpretar e aplicar sua própria semântica.

## 7. Testes e observabilidade

Criar fixture versionada com:

- `pavimentação de vias com drenagem` → excluído por `-drenagem`;
- aquisição de material com “engenharia” apenas no órgão → não correspondente no escopo padrão;
- serviço de engenharia com “engenharia” no objeto → correspondente;
- descrição de item contendo o termo, mas objeto genérico → correspondente;
- texto com acento e sem acento;
- frase negativa com aspas;
- tipo composto, modalidade sem critério e tipo ausente;
- duplicidade do mesmo identificador PNCP em páginas diferentes.

Medir, quando houver consulta textual:

- total coletado;
- positivos antes da exclusão;
- excluídos por termo;
- resultados finais;
- campos que mais geraram correspondência;
- consulta parcial ou completa.

## 8. Impacto em outras specs

- **Spec 008:** reutilizar o classificador, mas não confundir `TERMOS_NEGATIVOS` com exclusões do usuário.
- **Spec 009:** atualizar acessibilidade, chips, estados vazios e card responsivo.
- **Spec 010:** incluir fixtures e regressões no CI.
- **Spec 011:** documentos podem ser escopo opcional; não devem entrar na busca padrão sem metadados de cobertura.
- **Spec 013:** incorporar expressão, escopo, tipo composto e versão do parser na assinatura do snapshot e nos agregados.

