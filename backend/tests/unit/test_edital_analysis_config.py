import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_configuracoes_do_pipeline_rejeitam_limites_inseguros():
    with pytest.raises(ValidationError):
        Settings(pncp_timeout_seconds=0)

    with pytest.raises(ValidationError):
        Settings(pncp_connect_timeout_seconds=0)

    with pytest.raises(ValidationError):
        Settings(edital_pdf_max_pages=0)

    with pytest.raises(ValidationError):
        Settings(edital_ocr_dpi=90)

    with pytest.raises(ValidationError):
        Settings(edital_zip_max_total_pages=0)


def test_producao_exige_segredo_proprio_para_cursor():
    with pytest.raises(ValidationError, match="PAGINATION_CURSOR_SECRET"):
        Settings(app_env="production")

    with pytest.raises(ValidationError, match="API_KEY"):
        Settings(app_env="production", pagination_cursor_secret="segredo-longo-de-producao")

    settings = Settings(app_env="production", pagination_cursor_secret="segredo-longo-de-producao", api_key="chave-erp")
    assert settings.pagination_cursor_secret == "segredo-longo-de-producao"


def test_indexacao_vetorial_exige_postgresql_e_credencial():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(vector_indexing_enabled=True, database_url="sqlite:///./test.db", openai_api_key="chave")

    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(vector_indexing_enabled=True, database_url="postgresql://localhost/licitacoes", openai_api_key="")

    configured = Settings(
        vector_indexing_enabled=True,
        database_url="postgresql+psycopg2://localhost/licitacoes",
        openai_api_key="chave-de-teste",
    )
    assert configured.openai_embedding_model == "text-embedding-3-small"
    assert configured.openai_embedding_dimensions == 1536
    assert configured.openai_analysis_max_output_tokens == 4_096
