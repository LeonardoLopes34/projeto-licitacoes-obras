# Design — Spec 003: Erros Não Devem Virar Sucesso Silencioso

## Abordagem

1. Definir um schema Pydantic de resposta padrão para toda busca de obras, incluindo o bloco de metadados de execução.
2. Tratar exceções por camada e tipo, em vez de um `except Exception` genérico:
   - `httpx.HTTPError` / `requests.exceptions.RequestException` → falha de rede/timeout.
   - `pydantic.ValidationError` → falha de parsing/formato inesperado da API.
   - `sqlalchemy.exc.SQLAlchemyError` → falha de banco local.
3. Cada falha é logada com nível apropriado (`WARNING` para falha pontual de página, `ERROR` para falha que compromete toda a busca) e contabilizada nos metadados.

## Schema de resposta

```python
from typing import Literal
from pydantic import BaseModel

class ResultadoBusca(BaseModel):
    obras: list[ObraOut]
    parcial: bool
    paginas_consultadas: int
    paginas_com_erro: int
    origem: Literal["PNCP", "banco_local"]
```

## Trecho ilustrativo (endpoint)

```python
@router.get("/obras", response_model=ResultadoBusca)
async def listar_obras(intervalo_dias: int = 30):
    try:
        registros, metadados = buscar_obras_pncp(intervalo_dias)
        origem = "PNCP"
    except PNCPConnectionError as e:
        logger.error("PNCP indisponível, usando fallback local: %s", e)
        registros = obter_obras_banco_local()
        metadados = {"parcial": True, "paginas_consultadas": 0, "paginas_com_erro": 0}
        origem = "banco_local"

    return ResultadoBusca(obras=registros, origem=origem, **metadados)
```

## Impacto em outras specs

- Spec 002 fornece os campos `parcial`, `paginas_consultadas`, `paginas_com_erro` consumidos aqui.
- Spec 009 (frontend) exibe `parcial`/`origem` na interface (`StatusBanner`).
