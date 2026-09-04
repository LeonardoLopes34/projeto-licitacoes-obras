from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OrigemDados = Literal["PNCP", "banco_local", "cache", "cache_memoria", "cache_persistente", "mock"]
CategoriaExigencia = Literal[
    "habilitacao_juridica",
    "qualificacao_tecnica",
    "regularidade_fiscal_social_trabalhista",
    "qualificacao_economico_financeira",
    "declaracoes",
    "documento_referenciado",
    "nao_classificado",
]
StatusAnaliseExigencias = Literal[
    "nao_analisado",
    "processando",
    "sucesso",
    "sucesso_parcial",
    "sem_documento_analisavel",
    "erro",
]
StatusExigencia = Literal[
    "identificado_no_edital",
    "referenciado_em_outro_documento",
    "revisao_necessaria",
]
OrigemTextoExigencia = Literal["pdf_texto", "ocr"]


class ResumoExigenciasOut(BaseModel):
    status: StatusAnaliseExigencias
    total_exigencias: int = Field(default=0, ge=0)
    categorias: dict[CategoriaExigencia, int] = Field(default_factory=dict)
    analisador_versao: str


class ExecucaoBusca(BaseModel):
    parcial: bool = False
    paginas_consultadas: int = Field(default=0, ge=0)
    paginas_com_erro: int = Field(default=0, ge=0)
    origem: OrigemDados = "PNCP"


class PaginacaoOut(BaseModel):
    tamanho: int = Field(default=15, ge=1, le=50)
    total_carregado: int = Field(default=0, ge=0)
    tem_mais: bool = False
    proximo_cursor: str | None = None


class ObraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_pncp: str
    numero_controle_pncp: str | None = None
    cnpj: str | None = None
    ano: int | None = None
    sequencial: int | None = None
    orgao: str
    municipio: str | None = None
    uf: str
    objeto: str
    valor_estimado: Decimal | None = None
    data_publicacao: str
    modalidade: str | None = None
    modalidade_codigo: int | None = None
    link_pncp: str | None = None
    fonte: str = "PNCP_REAL"
    status_classificacao: str = "aprovado"
    score_classificacao: int = 0
    resumo_exigencias: ResumoExigenciasOut | None = None


class DocumentoOut(BaseModel):
    sequencial_documento: int = Field(ge=1)
    url: str | None = None
    tipo_documento_id: int | None = None
    tipo_documento_nome: str | None = None
    titulo: str | None = None
    data_publicacao_pncp: str | None = None


class ResultadoDocumentos(BaseModel):
    status: str
    mensagem: str
    total: int = Field(ge=0)
    documentos: list[DocumentoOut] = Field(default_factory=list)
    origem: OrigemDados = "PNCP"
    desatualizado: bool = False
    atualizado_em: str | None = None


class DocumentoAnalisadoOut(BaseModel):
    documento_id: int = Field(ge=1)
    titulo: str
    url: str | None = None
    paginas: int = Field(default=0, ge=0)
    paginas_com_ocr: int = Field(default=0, ge=0)
    status: str
    mensagem: str | None = None


class ExigenciaOut(BaseModel):
    categoria: CategoriaExigencia
    rotulo: str
    descricao_resumida: str = ""
    descricao_original: str
    documento_id: int = Field(ge=1)
    titulo_documento: str
    url_documento: str | None = None
    pagina: int = Field(ge=1)
    evidencia: str = Field(min_length=1)
    confianca: float = Field(ge=0, le=1)
    origem_texto: OrigemTextoExigencia
    status: StatusExigencia


class ResultadoExigencias(BaseModel):
    status: StatusAnaliseExigencias
    mensagem: str
    total_exigencias: int = Field(default=0, ge=0)
    categorias: dict[CategoriaExigencia, int] = Field(default_factory=dict)
    documentos_analisados: list[DocumentoAnalisadoOut] = Field(default_factory=list)
    exigencias: list[ExigenciaOut] = Field(default_factory=list)
    analisador_versao: str
    origem: OrigemDados = "PNCP"
    desatualizado: bool = False
    atualizado_em: str | None = None


class ResultadoBusca(BaseModel):
    status: str
    mensagem: str
    total_encontradas: int = Field(ge=0)
    dados: list[ObraOut] = Field(default_factory=list)
    metadados: ExecucaoBusca
    paginacao: PaginacaoOut = Field(default_factory=PaginacaoOut)
