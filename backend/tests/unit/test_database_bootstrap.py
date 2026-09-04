from backend.config import settings
from backend.database import _schema_bootstrap_permitted


def test_bootstrap_de_schema_eh_restrito_a_ambientes_nao_produtivos(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    assert _schema_bootstrap_permitted() is True

    monkeypatch.setattr(settings, "app_env", "production")
    assert _schema_bootstrap_permitted() is False
