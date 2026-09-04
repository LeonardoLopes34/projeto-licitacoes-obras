from fastapi.testclient import TestClient

import backend.admin as admin_module
import backend.main as main_module
from backend.config import settings
from backend.main import app


def test_endpoint_admin_rejeita_sem_credencial():
    settings.admin_api_key = "secret-test"
    client = TestClient(app)
    response = client.get("/admin/database/stats")
    assert response.status_code == 401


def test_endpoint_admin_aceita_credencial(monkeypatch):
    settings.admin_api_key = "secret-test"

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(admin_module, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(admin_module, "get_db_stats", lambda db: {"total_obras_armazenadas": 0})
    client = TestClient(app)
    response = client.get("/admin/database/stats", headers={"X-Admin-Key": "secret-test"})
    assert response.status_code == 200


def test_metricas_operacionais_exigem_credencial_e_nao_expoem_payloads(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "secret-test")
    monkeypatch.setattr(main_module, "obter_metricas_pncp", lambda: {"contadores": {"buscas_sucesso_remoto": 2}})

    client = TestClient(app)
    denied = client.get("/admin/operations/metrics")
    accepted = client.get("/admin/operations/metrics", headers={"X-Admin-Key": "secret-test"})

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["pncp"] == {"contadores": {"buscas_sucesso_remoto": 2}}
    assert "pdf" not in str(accepted.json()).lower()
