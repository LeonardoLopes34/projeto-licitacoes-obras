# Design — Spec 008: Classificador/Filtro de Obras por Palavras-Chave

## Abordagem

1. Tokenização com word boundary (`\bpalavra\b`), evitando dependência pesada de NLP nesta fase — regex puro é suficiente para o problema descrito.
2. Sistema de pontuação: termos positivos somam peso, termos negativos subtraem peso; limiares definem `aprovado / revisão manual / rejeitado`.
3. Base de casos versionada como fixture de teste, usada tanto para regressão automatizada quanto para medir precisão/cobertura.

## Trecho ilustrativo

```python
import re

TERMOS_POSITIVOS = {
    "construção": 3, "reforma": 3, "obra": 2, "pavimentação": 3,
    "edificação": 2, "hospitalar": 2,  # positivo — "hospitalar" não deve mais ser negativo por engano
}
TERMOS_NEGATIVOS = {
    "consultoria": -2, "serviço de limpeza": -2, "software": -3,
}
LIMIAR_APROVADO = 3
LIMIAR_REVISAO = 1  # entre LIMIAR_REVISAO e LIMIAR_APROVADO => revisão manual

def _contem_termo(texto: str, termo: str) -> bool:
    padrao = r"\b" + re.escape(termo) + r"\b"
    return re.search(padrao, texto, flags=re.IGNORECASE) is not None

def pontuar_obra(descricao: str) -> int:
    score = 0
    for termo, peso in TERMOS_POSITIVOS.items():
        if _contem_termo(descricao, termo):
            score += peso
    for termo, peso in TERMOS_NEGATIVOS.items():
        if _contem_termo(descricao, termo):
            score += peso  # peso já é negativo
    return score

def classificar_obra(descricao: str) -> str:
    score = pontuar_obra(descricao)
    if score >= LIMIAR_APROVADO:
        return "aprovado"
    if score >= LIMIAR_REVISAO:
        return "revisao_pendente"
    return "rejeitado"
```

## Base de casos (fixture de teste)

```json
// tests/fixtures/casos_filtro.json
[
  {"descricao": "Reforma de ala hospitalar do Hospital Municipal", "esperado": "aprovado"},
  {"descricao": "Aquisição de cabo elétrico para manutenção predial", "esperado": "rejeitado"},
  {"descricao": "Construção de UBS com instalação elétrica completa", "esperado": "aprovado"},
  {"descricao": "Contratação de consultoria em engenharia de obras", "esperado": "revisao_pendente"}
]
```

## Métrica de precisão/cobertura

```python
def avaliar_filtro(casos: list[dict]) -> dict:
    acertos = sum(1 for c in casos if classificar_obra(c["descricao"]) == c["esperado"])
    return {"precisao": acertos / len(casos), "total_casos": len(casos)}
```

## Impacto em outras specs

- Spec 007: itens com status `revisao_pendente` precisam de uma coluna/estado persistido no modelo `Obra`.
- Spec 009: itens pendentes de revisão devem ter uma seção própria na UI.
