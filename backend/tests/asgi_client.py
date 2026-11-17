"""Cliente mínimo para testes HTTP sem depender do TestClient descontinuado."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


def get(app: Any, url: str, **kwargs: Any) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(url, **kwargs)

    return asyncio.run(request())
