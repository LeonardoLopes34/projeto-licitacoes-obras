# Spec 014 — Busca PNCP, palavras excluídas e enriquecimento dos cards

**Origem:** exploração do portal PNCP em 14/09/2026, comparação com a tela de editais/atas/contratos e lacunas observadas no filtro atual do projeto.
**Fase:** 3 — Qualidade funcional e descoberta de oportunidades · **Bloqueia produção:** Não (recomendado antes da próxima evolução do filtro)

## Contexto

O portal PNCP oferece filtros estruturais, busca textual, itens, documentos, histórico, atas e contratos relacionados. A busca textual do portal não deve ser tratada como uma linguagem de exclusão: a consulta `pavimentacao -drenagem` continuou retornando objetos que mencionavam drenagem.

No projeto, o classificador atual usa termos positivos/negativos para pontuar uma obra, enquanto a pesquisa textual do frontend é aplicada localmente por substring em vários campos. Isso mistura classificação, pesquisa e exclusão definida pelo usuário. Também existe apenas a modalidade no card, embora o usuário precise visualizar o tipo da contratação de forma próxima ao PNCP, por exemplo:

```text
Tipo
Concorrência por Menor Preço - Menor Preço
```

O plano separa esses conceitos e preserva compatibilidade com os contratos existentes.

## Requisitos

| ID | Requisito |
|---|---|
| R014-1 | O sistema DEVE aceitar termos de inclusão e exclusão na mesma pesquisa, por exemplo `pavimentação -drenagem`. |
| R014-2 | O sistema DEVE excluir um resultado quando um termo negativo corresponder ao campo de busca configurado, usando normalização de caixa, acentos, pontuação e limites de palavra. |
| R014-3 | O sistema DEVE diferenciar termos digitados pelo usuário das listas internas de pontuação/classificação de obras. |
| R014-4 | O sistema DEVE pesquisar por padrão no objeto e nas descrições dos itens, sem considerar órgão, município ou fonte como correspondência textual automática. |
| R014-5 | O sistema DEVE permitir que o usuário escolha o escopo textual adicional, incluindo órgão, município, modalidade, fonte e documentos quando esses dados estiverem disponíveis. |
| R014-6 | O sistema DEVE aplicar inclusão, exclusão, ordenação e contagens antes da paginação apresentada ao usuário. |
| R014-7 | O sistema DEVE informar os termos encontrados, o campo correspondente e o motivo de exclusão ou inclusão de cada resultado quando houver filtragem textual. |
| R014-8 | O backend DEVE expor um campo normalizado `tipo_contratacao`, preservando separadamente modalidade e critério de julgamento quando disponíveis. |
| R014-9 | O card DEVE exibir uma seção `Tipo` com o tipo normalizado, incluindo combinações como `Concorrência por Menor Preço - Menor Preço`, sem inventar informação quando o PNCP não a publicar. |
| R014-10 | O card DEVE manter modalidade, localidade, órgão, objeto, valor e data, com fallback acessível para campos ausentes. |
| R014-11 | O sistema DEVE deduplicar resultados por identificador PNCP e manter os vínculos de edital, ata, contrato e documentos quando existirem. |
| R014-12 | O sistema DEVE manter uma base de casos de busca anotados para validar falsos positivos, falsos negativos, exclusões e a montagem do tipo exibido no card. |

## Critérios de aceitação

- [x] `pavimentação -drenagem` retorna resultados com pavimentação e não retorna resultado cujo objeto/itens contenham drenagem, respeitando o escopo selecionado.
- [x] Termos com acento e sem acento têm o mesmo comportamento; `pavimentacao` e `pavimentação` são equivalentes.
- [x] Uma correspondência em órgão ou município não é suficiente para aprovar um resultado quando o escopo padrão estiver configurado como objeto/itens.
- [x] O sistema encontra um termo que só aparece depois do primeiro item coletado e as contagens não mudam somente por trocar de página.
- [x] A resposta preserva a pesquisa legada com `termo` sem termos negativos e não altera silenciosamente a semântica dos endpoints existentes.
- [x] Um card com modalidade/critério disponíveis exibe `Tipo: Concorrência por Menor Preço - Menor Preço` ou a combinação equivalente retornada pelo PNCP.
- [x] Um card sem tipo publicado exibe `Tipo não informado` ou fallback equivalente, sem usar modalidade inventada como critério de julgamento.
- [x] O leitor de tela encontra o rótulo `Tipo` e o valor completo; textos longos não quebram o layout nem escondem o objeto.
- [x] Os casos anotados cobrem pelo menos: termo positivo com negativo, frase negativa, acentos, falsa correspondência no órgão, descrição de item e tipo ausente.
