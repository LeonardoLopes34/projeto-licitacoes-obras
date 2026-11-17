# Design — Spec 004: CORS e Endpoints Administrativos

## Abordagem

1. Configurar CORS via `Settings` (Pydantic `BaseSettings`), lendo `ALLOWED_ORIGINS` como lista separada por vírgula a partir de variável de ambiente, diferente por ambiente (dev permite `localhost`, prod só domínios reais).
2. Extrair endpoints administrativos (`/stats`, `/admin/limpar-banco`, `/admin/mocks`) para um `APIRouter` próprio (`admin_router`), protegido por uma dependência comum de autenticação.
3. Autenticação mínima viável: API key estática via header (`X-Admin-Key`), validada contra variável de ambiente — evolutivo para OAuth/JWT se necessário depois.

## Trecho ilustrativo

```python
# config.py
class Settings(BaseSettings):
    allowed_origins: list[str] = []
    admin_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

```python
# admin/deps.py
def verificar_admin(x_admin_key: str = Header(...)):
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Credencial administrativa inválida")

# admin/router.py
admin_router = APIRouter(prefix="/admin", dependencies=[Depends(verificar_admin)])

@admin_router.post("/limpar-banco")
def limpar_banco(...): ...

@admin_router.post("/mocks/ativar")
def ativar_mocks(...): ...
```

## Impacto em outras specs

- Spec 006 (higiene do Git) deve garantir que `.env` com `ADMIN_API_KEY` nunca seja versionado.
