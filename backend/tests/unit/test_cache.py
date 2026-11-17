import time

from cachetools import TTLCache

from backend.services import pncp_service


def test_cache_tem_ttl_e_limite(monkeypatch):
    cache = TTLCache(maxsize=1, ttl=0.01)
    cache["a"] = {"ok": True}
    monkeypatch.setattr(pncp_service, "_CACHE", cache)
    assert "a" in pncp_service._CACHE
    time.sleep(0.02)
    assert "a" not in pncp_service._CACHE
