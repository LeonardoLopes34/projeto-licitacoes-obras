# Design — Spec 005: Configuração de Ambiente do Frontend (Vite)

## Abordagem

Duas opções equivalentes — escolher uma:

**Opção A (recomendada): mover os arquivos de ambiente para dentro de `frontend/`**
- Criar `frontend/.env.development` com `VITE_API_URL=http://127.0.0.1:8000/api/v1`
- Criar `frontend/.env.production` com `VITE_API_URL=https://<dominio-real-da-api>/api/v1`
- Remover `.env` da raiz (ou mantê-lo apenas para variáveis do backend, sem relação com o Vite).

**Opção B: manter `.env` na raiz e configurar `envDir` no Vite**
```js
// vite.config.js
export default defineConfig({
  envDir: "../", // aponta para a raiz do monorepo
  // ...
});
```

## Validação fail-fast

```js
// src/config.js
const apiUrl = import.meta.env.VITE_API_URL;
if (!apiUrl) {
  throw new Error(
    "VITE_API_URL não definida. Configure frontend/.env.production antes de buildar."
  );
}
export const API_URL = apiUrl;
```

```js
// App.jsx
import { API_URL } from "./config";
// remover qualquer fallback tipo `|| "http://127.0.0.1:8000/api/v1/obras"`
fetch(`${API_URL}/obras`);
```

## Impacto em outras specs

- Spec 009 (fetch client centralizado) deve importar `API_URL` deste módulo único, evitando URLs espalhadas pelo código.
