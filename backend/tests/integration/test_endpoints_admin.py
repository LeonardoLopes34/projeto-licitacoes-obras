import backend.admin as admin_module
import backend.main as main_module
from backend.config import settings
from backend.main import app
from backend.tests.asgi_client import get


def test_endpoint_admin_rejeita_sem_credencial():
    settings.admin_api_key = "secret-test"
    response = get(app, "/admin/database/stats")
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
    response = get(app, "/admin/database/stats", headers={"X-Admin-Key": "secret-test"})
    assert response.status_code == 200


def test_metricas_operacionais_exigem_credencial_e_nao_expoem_payloads(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "secret-test")
    monkeypatch.setattr(main_module, "obter_metricas_pncp", lambda: {"contadores": {"buscas_sucesso_remoto": 2}})

    denied = get(app, "/admin/operations/metrics")
    accepted = get(app, "/admin/operations/metrics", headers={"X-Admin-Key": "secret-test"})

    assert denied.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["pncp"] == {"contadores": {"buscas_sucesso_remoto": 2}}
    assert "pdf" not in str(accepted.json()).lower()


def test_api_v1_exige_chave_quando_configurada(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "erp-secret")

    sem_chave = get(app, "/api/v1/obras?inicial_date=invalida")
    chave_errada = get(app, "/api/v1/obras?inicial_date=invalida", headers={"X-API-Key": "outra"})
    # Data inválida dá 422 sem chamar o PNCP: prova que a chave passou.
    com_chave = get(app, "/api/v1/obras?inicial_date=invalida", headers={"X-API-Key": "erp-secret"})

    assert sem_chave.status_code == 401
    assert chave_errada.status_code == 401
    assert com_chave.status_code == 422
    assert get(app, "/health").status_code == 200
