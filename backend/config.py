from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuração centralizada do backend, carregada do ambiente."""

    app_env: str = "development"
    database_url: str | None = None
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    admin_api_key: str = ""
    # Chave que integrações (ERP) enviam em X-API-Key; obrigatória em produção.
    api_key: str = ""
    pncp_ca_bundle: str | None = None
    # Limite por modalidade; a consulta padrão dispara as modalidades em paralelo.
    # O endpoint de documentos pode responder mais lentamente que a busca
    # resumida de licitações; estes valores deixam margem para os retries.
    pncp_timeout_seconds: float = Field(default=8.0, gt=0)
    pncp_connect_timeout_seconds: float = Field(default=3.0, gt=0)
    # O PNCP limita rajadas de consultas. Uma página por vez reduz respostas
    # 429 quando a tela consulta as modalidades padrão.
    pncp_max_concurrent_requests: int = Field(default=1, ge=1, le=5)
    # A tela recebe cada página por streaming. Um intervalo moderado preserva
    # essa atualização progressiva e evita que o PNCP interrompa a coleta com
    # HTTP 429 no meio de uma consulta de várias páginas.
    pncp_request_interval_seconds: float = Field(default=2.0, ge=0.0, le=30.0)
    pncp_rate_limit_retry_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    # Uma página por modalidade evita rajadas que ativam o rate limit do PNCP.
    # Consultas aprofundadas podem informar max_paginas explicitamente.
    pncp_max_paginas: int = 1
    pncp_cache_ttl_seconds: int = 180
    pncp_cache_maxsize: int = 256
    pncp_circuit_failure_threshold: int = 3
    pncp_circuit_open_seconds: float = 30.0
    pagination_cursor_secret: str = "development-pagination-secret"
    query_snapshot_ttl_seconds: int = Field(default=15 * 60, ge=60, le=24 * 60 * 60)
    query_snapshot_max_records: int = Field(default=1_000, ge=1, le=10_000)
    query_snapshot_max_bytes: int = Field(default=2 * 1024 * 1024, ge=1_024)
    query_snapshot_max_count: int = Field(default=256, ge=1, le=10_000)
    retention_days: int = 2

    # Análise sob demanda de editais. O binário Tesseract é um pré-requisito
    # externo configurável por TESSERACT_CMD; o pipeline continua retornando
    # um resultado parcial quando ele não estiver disponível. A chave abaixo
    # permite desligar o OCR sem simular uma falha do binário, por exemplo para
    # validar a análise assistida somente com texto digital do PDF.
    edital_download_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    edital_download_timeout_seconds: float = Field(default=30.0, gt=0)
    edital_download_retries: int = Field(default=2, ge=0, le=5)
    edital_download_retry_delay_seconds: float = Field(default=1.0, ge=0, le=30)
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
    edital_ocr_enabled: bool = True
    edital_ocr_dpi: int = Field(default=250, ge=150, le=400)
    edital_ocr_language: str = "por"
    edital_ocr_timeout_seconds: float = Field(default=45.0, gt=0)
    tesseract_cmd: str | None = None
    # "openai" transcreve páginas escaneadas com modelo de visão e recorre ao
    # Tesseract quando a chamada falha; "tesseract" mantém o OCR só local.
    edital_ocr_provider: Literal["tesseract", "openai"] = "tesseract"
    openai_ocr_model: str = "gpt-5-mini"
    # Vazio para modelos sem raciocínio; "minimal" evita gastar tokens na transcrição.
    openai_ocr_reasoning_effort: str = "minimal"
    openai_ocr_max_output_tokens: int = Field(default=8_000, ge=256, le=32_000)
    edital_analysis_concurrency: int = Field(default=2, ge=1)
    edital_analysis_queue_maxsize: int = Field(default=8, ge=0, le=256)
    edital_analysis_max_documents: int = Field(default=20, ge=1, le=200)
    edital_analysis_max_total_bytes: int = Field(default=50 * 1024 * 1024, ge=1_024)
    edital_analysis_max_total_pages: int = Field(default=300, ge=1, le=5_000)
    edital_analysis_cache_ttl_seconds: int = Field(default=24 * 60 * 60, ge=1)
    edital_analysis_cache_maxsize: int = Field(default=128, ge=1)
    edital_analysis_timeout_seconds: float = Field(default=180.0, gt=0)
    edital_analyzer_version: str = "ocr-edital-v3"

    # Indexação e análise assistida de editais (Spec 015). A capacidade nasce
    # desativada: ativá-la requer PostgreSQL/pgvector e uma chave OpenAI apenas
    # no ambiente de execução, nunca em fixtures ou código.
    vector_indexing_enabled: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, ge=1, le=1536)
    openai_analysis_model: str = "gpt-5-mini"
    openai_request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openai_embedding_batch_size: int = Field(default=32, ge=1, le=256)
    openai_analysis_max_chunks: int = Field(default=48, ge=1, le=256)
    openai_analysis_max_input_characters: int = Field(default=48_000, ge=1_000, le=500_000)
    # O teto inclui tokens visíveis e de raciocínio da Responses API. Um
    # limite baixo pode encerrar a resposta antes do JSON estruturado.
    openai_analysis_max_output_tokens: int = Field(default=4_096, ge=64, le=16_000)
    openai_analysis_max_items: int = Field(default=50, ge=1, le=500)
    vector_chunk_max_characters: int = Field(default=1_400, ge=200, le=20_000)
    vector_chunk_overlap_characters: int = Field(default=160, ge=0, le=2_000)
    vector_index_max_chunks_per_document: int = Field(default=300, ge=1, le=5_000)
    vector_index_max_chunks_per_job: int = Field(default=800, ge=1, le=10_000)
    vector_index_max_documents: int = Field(default=20, ge=1, le=200)
    vector_index_max_attempts: int = Field(default=3, ge=1, le=10)
    vector_index_lease_seconds: int = Field(default=300, ge=30, le=3_600)
    vector_index_worker_concurrency: int = Field(default=1, ge=1, le=8)
    vector_index_max_cost_usd_per_job: float = Field(default=0.50, ge=0.001, le=100.0)
    vector_index_retention_days: int = Field(default=90, ge=1, le=3_650)
    openai_embedding_cost_per_million_tokens: float = Field(default=0.02, ge=0)
    openai_analysis_input_cost_per_million_tokens: float = Field(default=0.25, ge=0)
    openai_analysis_output_cost_per_million_tokens: float = Field(default=2.00, ge=0)
    vector_chunking_version: str = "chunking-v1"
    vector_extraction_version: str = "pdf-ocr-v1"
    openai_analysis_prompt_version: str = "requirements-v1"
    openai_analysis_schema_version: str = "requirements-schema-v1"
    pncp_document_hosts: Annotated[list[str], NoDecode] = Field(
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

    @model_validator(mode="after")
    def require_cursor_secret_in_production(self) -> "Settings":
        if (
            self.app_env.strip().lower() in {"production", "prod"}
            and self.pagination_cursor_secret == "development-pagination-secret"
        ):
            raise ValueError("PAGINATION_CURSOR_SECRET deve ser configurado em produção")
        if self.app_env.strip().lower() in {"production", "prod"} and not self.api_key.strip():
            raise ValueError("API_KEY deve ser configurada em produção")
        if self.edital_ocr_provider == "openai" and not self.openai_api_key.strip():
            raise ValueError("OPENAI_API_KEY deve ser configurada para EDITAL_OCR_PROVIDER=openai")
        if self.vector_indexing_enabled:
            database_url = (self.database_url or "").strip().lower()
            if not database_url or database_url.startswith("sqlite"):
                raise ValueError("VECTOR_INDEXING_ENABLED exige DATABASE_URL PostgreSQL com pgvector")
            if not self.openai_api_key.strip():
                raise ValueError("OPENAI_API_KEY deve ser configurada para ativar a indexação vetorial")
            if self.openai_embedding_model != "text-embedding-3-small":
                raise ValueError("OPENAI_EMBEDDING_MODEL inicial deve ser text-embedding-3-small")
            if self.openai_embedding_dimensions != 1536:
                raise ValueError("OPENAI_EMBEDDING_DIMENSIONS inicial deve ser 1536")
            if not self.openai_analysis_model.strip():
                raise ValueError("OPENAI_ANALYSIS_MODEL deve ser configurado para ativar a indexação vetorial")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
