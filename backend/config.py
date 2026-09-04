from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuração centralizada do backend, carregada do ambiente."""

    app_env: str = "development"
    database_url: str | None = None
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    admin_api_key: str = ""
    pncp_ca_bundle: str | None = None
    # Limite por modalidade; a consulta padrão dispara as modalidades em paralelo.
    pncp_timeout_seconds: float = 3.0
    pncp_connect_timeout_seconds: float = 2.0
    # Uma página por modalidade evita rajadas que ativam o rate limit do PNCP.
    # Consultas aprofundadas podem informar max_paginas explicitamente.
    pncp_max_paginas: int = 1
    pncp_cache_ttl_seconds: int = 180
    pncp_cache_maxsize: int = 256
    pncp_circuit_failure_threshold: int = 3
    pncp_circuit_open_seconds: float = 30.0
    pagination_cursor_secret: str = "development-pagination-secret"
    retention_days: int = 2

    # Análise sob demanda de editais. O binário Tesseract é um pré-requisito
    # externo configurável por TESSERACT_CMD; o pipeline continua retornando
    # um resultado parcial quando ele não estiver disponível.
    edital_download_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    edital_download_timeout_seconds: float = Field(default=20.0, gt=0)
    edital_pdf_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1)
    edital_pdf_max_pages: int = Field(default=150, ge=1)
    # ZIPs são comuns nos editais, mas são tratados como conteúdo não confiável.
    # Os limites cobrem metadados, arquivos PDF e o total descompactado.
    edital_zip_max_entries: int = Field(default=100, ge=1, le=1000)
    edital_zip_max_pdfs: int = Field(default=10, ge=1, le=100)
    edital_zip_max_uncompressed_bytes: int = Field(default=60 * 1024 * 1024, ge=1)
    edital_zip_max_compression_ratio: float = Field(default=100.0, ge=1, le=1000)
    edital_zip_max_total_pages: int = Field(default=150, ge=1)
    edital_text_min_characters: int = Field(default=80, ge=1)
    edital_ocr_dpi: int = Field(default=250, ge=150, le=400)
    edital_ocr_language: str = "por"
    edital_ocr_timeout_seconds: float = Field(default=45.0, gt=0)
    tesseract_cmd: str | None = None
    edital_analysis_concurrency: int = Field(default=2, ge=1)
    edital_analysis_cache_ttl_seconds: int = Field(default=24 * 60 * 60, ge=1)
    edital_analysis_cache_maxsize: int = Field(default=128, ge=1)
    edital_analysis_timeout_seconds: float = Field(default=180.0, gt=0)
    edital_analyzer_version: str = "ocr-edital-v1"
    pncp_document_hosts: list[str] = Field(
        default_factory=lambda: ["pncp.gov.br", "www.pncp.gov.br"]
    )

    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env",),
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return list(value)

    @field_validator("pncp_document_hosts", mode="before")
    @classmethod
    def parse_pncp_document_hosts(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["pncp.gov.br", "www.pncp.gov.br"]
        if isinstance(value, str):
            return [host.strip().lower() for host in value.split(",") if host.strip()]
        return [str(host).strip().lower() for host in value if str(host).strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
