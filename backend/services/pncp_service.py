import asyncio
import base64
import binascii
import hashlib
import hmac
import inspect
import json
import logging
import re
import ssl
import time
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, AsyncIterator
from urllib.parse import quote, urlparse

import httpx
from cachetools import TTLCache
from sqlalchemy.exc import SQLAlchemyError

from backend.config import settings
from backend.exceptions import DatabaseServiceError, PNCPConnectionError, PNCPResponseError
from backend.services.document_snapshot_repository import (
    obter_snapshot_documentos,
    salvar_snapshot_documentos,
)
from backend.services.edital_analysis_repository import obter_resumos_contratacoes
from backend.services.query_snapshot_repository import (
    QuerySnapshot,
    obter_snapshot_consulta,
    salvar_snapshot_consulta,
)
from backend.models.obra_model import validar_modalidade
from backend.schemas import DocumentoOut, ExecucaoBusca, PaginacaoOut, ResultadoBusca, ResultadoDocumentos
from backend.services.circuit_breaker import CircuitBreaker
from backend.services.search_filter_service import (
    SEARCH_PARSER_VERSION,
    SearchExpression,
    aplicar_busca,
    parse_search_request,
)
from backend.services.tipo_contratacao import normalizar_campos_tipo_contratacao


logger = logging.getLogger(__name__)
PNCP_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
PNCP_DOCUMENTOS_URL = "https://pncp.gov.br/api/pncp/v1/orgaos"
MODALIDADES_PADRAO_TODAS = [4, 6, 8]
# O PNCP rejeita requisições com tamanhoPagina menor que 10.
PNCP_MIN_PAGE_SIZE = 10
# O PNCP rejeita requisições com tamanhoPagina maior que 50.
PNCP_MAX_PAGE_SIZE = 50
# A consulta aos arquivos é compartilhada pelos endpoints de documentos e de
# exigências. Duas tentativas absorvem uma oscilação momentânea sem criar uma
# sequência excessiva de requisições ao PNCP.
DOCUMENTOS_MAX_RETRIES = 2
_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(
    maxsize=settings.pncp_cache_maxsize,
    ttl=settings.pncp_cache_ttl_seconds,
)
_DOCUMENTOS_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(
    maxsize=settings.pncp_cache_maxsize,
    ttl=settings.pncp_cache_ttl_seconds,
)
# A consulta resumida de contratações não traz o critério de julgamento. Ele
# fica no primeiro item da contratação, que é consultado sob demanda apenas
# para os cards visíveis. O cache evita repetir essa chamada ao abrir o modal
# ou ao trocar um filtro local.
_TIPO_CONTRATACAO_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(
    maxsize=settings.pncp_cache_maxsize,
    ttl=settings.pncp_cache_ttl_seconds,
)
_TIPO_CONTRATACAO_INFLIGHT: dict[str, asyncio.Task[dict[str, Any]]] = {}
# A tela carrega a lista de arquivos e, em paralelo, inicia a análise de
# exigências. As duas operações precisam compartilhar a mesma consulta ao
# PNCP para não duplicar tráfego e agravar os timeouts intermitentes.
_DOCUMENTOS_INFLIGHT: dict[str, asyncio.Task[dict[str, Any]]] = {}
_PNCP_METRICS: Counter[str] = Counter()
_PNCP_CIRCUIT = CircuitBreaker(
    failure_threshold=settings.pncp_circuit_failure_threshold,
    recovery_timeout=settings.pncp_circuit_open_seconds,
)
_PNCP_HTTP_CLIENT: httpx.AsyncClient | Any | None = None
_PNCP_HTTP_CLIENT_LOOP: asyncio.AbstractEventLoop | None = None
# O limitador é compartilhado entre buscas: cancelar a requisição no browser
# não interrompe necessariamente uma chamada HTTP que já chegou ao servidor.
# Sem esse limite, mudanças rápidas nos filtros multiplicam as chamadas ao
# PNCP e provocam HTTP 429.
_PNCP_PAGE_SEMAPHORE: asyncio.Semaphore | None = None
_PNCP_PAGE_SEMAPHORE_LOOP: asyncio.AbstractEventLoop | None = None


class PaginationCursorError(ValueError):
    """Cursor adulterado, incompatível ou pertencente ao formato antigo."""

    code = "cursor_invalido"


class PaginationSnapshotExpiredError(ValueError):
    """O snapshot associado ao cursor já não está disponível."""

    code = "consulta_expirada"


def _pncp_client_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        settings.pncp_timeout_seconds,
        connect=settings.pncp_connect_timeout_seconds,
    )


async def obter_cliente_pncp() -> httpx.AsyncClient | Any:
    """Retorna um cliente HTTP reutilizável no loop atual da aplicação.

    Reutilizar conexões reduz a latência e a quantidade de handshakes TLS com
    o PNCP. O vínculo ao loop também mantém chamadas diretas dos testes
    isoladas, já que cada teste assíncrono pode possuir seu próprio loop.
    """

    global _PNCP_HTTP_CLIENT, _PNCP_HTTP_CLIENT_LOOP
    current_loop = asyncio.get_running_loop()
    client_is_closed = bool(getattr(_PNCP_HTTP_CLIENT, "is_closed", False))
    if (
        _PNCP_HTTP_CLIENT is None
        or _PNCP_HTTP_CLIENT_LOOP is not current_loop
        or client_is_closed
    ):
        _PNCP_HTTP_CLIENT = httpx.AsyncClient(
            timeout=_pncp_client_timeout(),
            verify=_tls_verify(),
            follow_redirects=True,
        )
        _PNCP_HTTP_CLIENT_LOOP = current_loop
    return _PNCP_HTTP_CLIENT


async def fechar_cliente_pncp() -> None:
    """Fecha o pool HTTP ao encerrar a aplicação."""

    global _PNCP_HTTP_CLIENT, _PNCP_HTTP_CLIENT_LOOP
    client = _PNCP_HTTP_CLIENT
    _PNCP_HTTP_CLIENT = None
    _PNCP_HTTP_CLIENT_LOOP = None
    close = getattr(client, "aclose", None)
    if callable(close):
        await close()


def obter_limitador_paginas_pncp() -> asyncio.Semaphore:
    """Retorna o limitador compartilhado de páginas para o loop em execução."""

    global _PNCP_PAGE_SEMAPHORE, _PNCP_PAGE_SEMAPHORE_LOOP
    current_loop = asyncio.get_running_loop()
    if _PNCP_PAGE_SEMAPHORE is None or _PNCP_PAGE_SEMAPHORE_LOOP is not current_loop:
        _PNCP_PAGE_SEMAPHORE = asyncio.Semaphore(settings.pncp_max_concurrent_requests)
        _PNCP_PAGE_SEMAPHORE_LOOP = current_loop
    return _PNCP_PAGE_SEMAPHORE


def obter_metricas_pncp() -> dict[str, Any]:
    """Resumo seguro para diagnóstico administrativo, sem payloads do PNCP."""
    return {
        "contadores": dict(_PNCP_METRICS),
        "cache_buscas": len(_CACHE),
        "cache_documentos": len(_DOCUMENTOS_CACHE),
        "cache_tipos_contratacao": len(_TIPO_CONTRATACAO_CACHE),
        "consultas_documentos_em_andamento": len(_DOCUMENTOS_INFLIGHT),
        "circuito_aberto": _PNCP_CIRCUIT.is_open,
        "falhas_consecutivas": _PNCP_CIRCUIT.consecutive_failures,
        "ultima_resposta_segundos": _PNCP_CIRCUIT.last_response_time,
    }


def get_mock_licitacoes() -> list[dict[str, Any]]:
    today = datetime.now(timezone.utc)
    d0 = today.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
    d1 = (today - timedelta(days=1)).replace(hour=14, minute=30, second=0, microsecond=0).isoformat()
    d2 = (today - timedelta(days=2)).replace(hour=9, minute=15, second=0, microsecond=0).isoformat()
    return [
        {
            "id_pncp": "MOCK-94309291000148-1-000130/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TRAMANDAI", "cnpj": "94309291000148"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Tramandai"},
            "objetoCompra": "CONTRATACAO DE EMPRESA ESPECIALIZADA EM ENGENHARIA PARA EXECUCAO DE OBRAS DE PAVIMENTACAO ASFALTICA E DRENAGEM PLUVIAL NA AV. BEIRA MAR.",
            "valorTotalEstimado": 1250000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrencia - Eletronica",
            "anoCompra": str(today.year),
            "sequencialCompra": "130",
            "fonte": "MOCK_LOCAL",
        },
        {
            "id_pncp": "MOCK-88309291000199-1-000045/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE TORRES", "cnpj": "88309291000199"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Torres"},
            "objetoCompra": "REFORMA E AMPLIACAO ESTRUTURAL DA ESCOLA MUNICIPAL DE ENSINO FUNDAMENTAL COM SUBSTITUICAO DE COBERTURA PREDIAL E RECONSTRUCAO DE MURO.",
            "valorTotalEstimado": 450000.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 4,
            "modalidadeNome": "Concorrencia - Eletronica",
            "anoCompra": str(today.year),
            "sequencialCompra": "45",
            "fonte": "MOCK_LOCAL",
        },
        {
            "id_pncp": "MOCK-77104212000188-1-000512/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE OSORIO", "cnpj": "77104212000188"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Osorio"},
            "objetoCompra": "EXECUCAO DE OBRAS DE PAVIMENTACAO E RECAPEAMENTO ASFALTICO EM DIVERSAS VIAS DO MUNICIPIO.",
            "valorTotalEstimado": 890000.00,
            "dataPublicacaoPncp": d0,
            "modalidadeId": 6,
            "modalidadeNome": "Pregao - Eletronico",
            "anoCompra": str(today.year),
            "sequencialCompra": "512",
            "fonte": "MOCK_LOCAL",
        },
        {
            "id_pncp": "MOCK-00509018000113-1-001422/2026",
            "orgaoEntidade": {"razaoSocial": "PREFEITURA MUNICIPAL DE CAPAO DA CANOA", "cnpj": "00509018000113"},
            "unidadeOrgao": {"ufSigla": "RS", "municipioNome": "Capao da Canoa"},
            "objetoCompra": "REFORMA DE PREDIO PUBLICO MUNICIPAL E DRENAGEM DE VIA PUBLICA.",
            "valorTotalEstimado": 27805.00,
            "dataPublicacaoPncp": d2,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitacao",
            "anoCompra": str(today.year),
            "sequencialCompra": "1422",
            "fonte": "MOCK_LOCAL",
        },
        {
            "id_pncp": "MOCK-82804212000196-1-000214/2026",
            "orgaoEntidade": {"razaoSocial": "MUNICIPIO DE AGUAS DE CHAPECO", "cnpj": "82804212000196"},
            "unidadeOrgao": {"ufSigla": "SC", "municipioNome": "Aguas de Chapeco"},
            "objetoCompra": "CONSTRUCAO DE COBERTURA E ESTRUTURA PARA A GARAGEM DO QUARTEL DA POLICIA MILITAR DE AGUAS DE CHAPECO.",
            "valorTotalEstimado": 8818.50,
            "dataPublicacaoPncp": d1,
            "modalidadeId": 8,
            "modalidadeNome": "Dispensa de Licitacao",
            "anoCompra": str(today.year),
            "sequencialCompra": "214",
            "fonte": "MOCK_LOCAL",
        },
    ]


def remover_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFD", texto or "")
    sem_acentos = "".join(char for char in normalizado if unicodedata.category(char) != "Mn")
    return sem_acentos.lower().strip()


TERMOS_POSITIVOS: dict[str, int] = {
    "construcao": 3,
    "reforma": 3,
    "pavimentacao": 3,
    "recapeamento": 3,
    "drenagem": 2,
    "saneamento": 2,
    "calcamento": 2,
    "edificacao": 2,
    "demolicao": 2,
    "contencao": 2,
    "muro de arrimo": 2,
    "muro de contencao": 2,
    "obra": 2,
    "obras": 2,
    "ponte": 3,
    "pontes": 3,
    "viaria": 2,
    "urbanizacao": 2,
    "canalizacao": 2,
    "terraplenagem": 2,
    "terraplanagem": 2,
    "enrocamento": 2,
    "desassoreamento": 2,
    "engenharia": 1,
    "hospitalar": 1,
    "instalacao": 1,
    "estrutura": 1,
    "cobertura": 1,
}

TERMOS_NEGATIVOS: dict[str, int] = {
    # Atas e registros de preço tratam de uma contratação futura, não de uma
    # oportunidade de obra com execução imediata. O objeto pode mencionar
    # pavimentação ou construção, por isso o peso precisa prevalecer sobre os
    # termos positivos.
    "registro de precos": -10,
    "aquisicao de material": -3,
    "aquisicao de materiais": -3,
    "compra de material": -3,
    "compra de materiais": -3,
    "fornecimento de material": -3,
    "material de construcao": -2,
    "cabo eletrico": -3,
    "consultoria": -1,
    "software": -4,
    "medicamento": -4,
    "limpeza de caixa": -3,
    "coleta de lixo": -3,
    "portaria": -3,
    "vigilancia": -3,
    "treinamento": -3,
    "curso": -3,
    "manutencao de veiculo": -4,
    "pecas": -3,
    "retroescavadeira": -3,
}

# Variações recorrentes no objeto das contratações de pavimentação. A lista
# fica separada dos termos positivos: ela permite incluir ou excluir essas
# obras sem alterar a classificação geral de construções.
TERMOS_PAVIMENTACAO = (
    "pavimentacao",
    "recapeamento",
    "calcamento",
    "asfalto",
    "pavimento",
)


def _contem_termo(texto: str, termo: str) -> bool:
    return re.search(rf"\b{re.escape(termo)}\b", texto) is not None


def pontuar_obra(descricao: str) -> int:
    texto = remover_acentos(descricao)
    score = sum(peso for termo, peso in TERMOS_POSITIVOS.items() if _contem_termo(texto, termo))
    score += sum(peso for termo, peso in TERMOS_NEGATIVOS.items() if _contem_termo(texto, termo))
    return score


def classificar_obra(descricao: str) -> str:
    score = pontuar_obra(descricao)
    if score >= 3:
        return "aprovado"
    if score >= 1:
        return "revisao_pendente"
    return "rejeitado"


def eh_obra_pavimentacao(descricao: str) -> bool:
    """Identifica obras viárias pavimentadas para o filtro opcional da busca."""
    texto = remover_acentos(descricao)
    return any(_contem_termo(texto, termo) for termo in TERMOS_PAVIMENTACAO)


def is_interesting_construction(objeto: str) -> bool:
    return classificar_obra(objeto) != "rejeitado"


def avaliar_filtro(casos: list[dict[str, str]]) -> dict[str, float | int]:
    resultados = [(classificar_obra(case["descricao"]), case["esperado"]) for case in casos]
    acertos = sum(predicted == expected for predicted, expected in resultados)
    verdadeiros_positivos = sum(
        predicted != "rejeitado" and expected != "rejeitado"
        for predicted, expected in resultados
    )
    falsos_positivos = sum(
        predicted != "rejeitado" and expected == "rejeitado"
        for predicted, expected in resultados
    )
    falsos_negativos = sum(
        predicted == "rejeitado" and expected != "rejeitado"
        for predicted, expected in resultados
    )
    return {
        "precisao": verdadeiros_positivos / (verdadeiros_positivos + falsos_positivos)
        if verdadeiros_positivos + falsos_positivos
        else 0.0,
        "cobertura": verdadeiros_positivos / (verdadeiros_positivos + falsos_negativos)
        if verdadeiros_positivos + falsos_negativos
        else 0.0,
        "acuracia": acertos / len(casos) if casos else 0.0,
        "total_casos": len(casos),
    }


def _nested(item: dict[str, Any], key: str) -> dict[str, Any]:
    value = item.get(key)
    return value if isinstance(value, dict) else {}


def _raw_pncp_identifier(item: Mapping[str, Any]) -> str:
    """Chave estável para unir repetições PNCP sem perder o registro rico."""

    return str(
        item.get("numeroControlePNCP")
        or item.get("numero_controle_pncp")
        or item.get("id_pncp")
        or f"{_nested(dict(item), 'orgaoEntidade').get('cnpj')}_{item.get('sequencialCompra')}"
    )


def _pncp_item_completeness(value: Any) -> int:
    """Pontua campos publicados para preferir duplicatas mais completas."""

    if isinstance(value, Mapping):
        return sum(_pncp_item_completeness(item) for item in value.values())
    if isinstance(value, list):
        return sum(_pncp_item_completeness(item) for item in value)
    return int(value not in (None, "", [], {}))


def _merge_pncp_values(preferred: Any, supplemental: Any) -> Any:
    if preferred in (None, "", [], {}):
        return supplemental
    if isinstance(preferred, Mapping) and isinstance(supplemental, Mapping):
        return {
            key: _merge_pncp_values(preferred.get(key), supplemental.get(key))
            for key in preferred.keys() | supplemental.keys()
        }
    if isinstance(preferred, list) and isinstance(supplemental, list):
        merged = list(preferred)
        serialized = {json.dumps(item, sort_keys=True, default=str) for item in merged}
        for item in supplemental:
            key = json.dumps(item, sort_keys=True, default=str)
            if key not in serialized:
                merged.append(item)
                serialized.add(key)
        return merged
    return preferred


def _merge_duplicate_pncp_item(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Mantém a versão mais completa e preenche lacunas da outra página."""

    preferred, supplemental = (
        (candidate, existing)
        if _pncp_item_completeness(candidate) > _pncp_item_completeness(existing)
        else (existing, candidate)
    )
    return _merge_pncp_values(preferred, supplemental)


def _date_is_in_range(value: Any, data_inicial: str | None, data_final: str | None) -> bool:
    if not value or not data_inicial or not data_final:
        return True
    date_clean = str(value)[:10].replace("-", "")
    return len(date_clean) != 8 or data_inicial <= date_clean <= data_final


def processar_itens_raw(
    items: list[dict[str, Any]],
    data_inicial: str | None = None,
    data_final: str | None = None,
    modalidade: int | None = None,
    uf: str | None = None,
) -> list[dict[str, Any]]:
    if modalidade is not None:
        modalidade = validar_modalidade(modalidade)
    uf_normalizada = uf.upper().strip() if uf else None
    resultados: list[dict[str, Any]] = []

    for item in items:
        publicacao = item.get("dataPublicacaoPncp") or item.get("data_publicacao") or ""
        if not _date_is_in_range(publicacao, data_inicial, data_final):
            continue

        item_mode = item.get("modalidadeId") or item.get("modalidade_codigo") or item.get("codigoModalidadeContratacao")
        if item_mode is not None:
            try:
                item_mode = int(item_mode)
            except (TypeError, ValueError):
                logger.warning("Registro PNCP descartado por modalidade inválida: %s", item_mode)
                continue
        if modalidade not in (None, 0) and item_mode is not None and int(item_mode) != modalidade:
            continue
        if modalidade not in (None, 0) and item_mode is None:
            continue

        unit = _nested(item, "unidadeOrgao")
        item_uf = str(unit.get("ufSigla") or item.get("uf") or "").upper().strip()
        if uf_normalizada and uf_normalizada != "TODOS" and item_uf != uf_normalizada:
            continue

        objeto = str(item.get("objetoCompra") or item.get("objeto") or "")
        status_classificacao = classificar_obra(objeto)
        if status_classificacao == "rejeitado":
            continue

        orgao = _nested(item, "orgaoEntidade")
        cnpj = str(orgao.get("cnpj") or item.get("cnpj") or "") or None
        ano = item.get("anoCompra") or item.get("ano")
        sequencial = item.get("sequencialCompra") or item.get("sequencialContratacao")
        numero_controle = item.get("numeroControlePNCP") or item.get("numero_controle_pncp")
        id_pncp = str(numero_controle or item.get("id_pncp") or "").strip()
        if not id_pncp:
            logger.warning("Registro PNCP descartado por ausência de identificador")
            continue

        link = item.get("link_pncp")
        if not link and cnpj and ano and sequencial:
            link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"

        campos_tipo = normalizar_campos_tipo_contratacao(item)
        # O filtro da rota já validou o código da modalidade. Preservamos esse
        # valor quando uma fonte PNCP antiga não o repete no payload.
        campos_tipo["modalidade"] = campos_tipo["modalidade"] or item.get("modalidadeNome") or item.get("modalidade")
        campos_tipo["modalidade_codigo"] = (
            campos_tipo["modalidade_codigo"]
            if campos_tipo["modalidade_codigo"] is not None
            else (int(item_mode) if item_mode is not None else None)
        )
        resultados.append(
            {
                "id_pncp": id_pncp,
                "numero_controle_pncp": str(numero_controle or id_pncp),
                "cnpj": cnpj,
                "ano": int(ano) if str(ano or "").isdigit() else None,
                "sequencial": int(sequencial) if str(sequencial or "").isdigit() else None,
                "orgao": orgao.get("razaoSocial") or item.get("orgao") or "Órgão não informado",
                "uf": item_uf or "BR",
                "municipio": unit.get("municipioNome") or item.get("municipio"),
                "objeto": objeto,
                "valor_estimado": item.get("valorTotalEstimado") or item.get("valor_estimado"),
                "data_publicacao": publicacao,
                **campos_tipo,
                "itens": item.get("itens") or item.get("itensCompra") or item.get("items") or item.get("descricaoItens"),
                "documentos": item.get("documentos") or item.get("documents"),
                "link_pncp": link,
                "fonte": item.get("fonte") or "PNCP_REAL",
                "status_classificacao": status_classificacao,
                "score_classificacao": pontuar_obra(objeto),
                "payload_original": item,
            }
        )
    return resultados


def _validate_date(value: str, field: str) -> str:
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{field} deve estar no formato YYYYMMDD e ser uma data válida") from exc
    return value


@dataclass
class PageFetchResult:
    page: int
    items: list[dict[str, Any]]
    total_registros: int | None = None
    error: PNCPConnectionError | PNCPResponseError | None = None
    rate_limited: bool = False
    terminal_error: bool = False


async def fetch_pagina(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    params: dict[str, Any],
    headers: dict[str, str],
    max_retries: int = 2,
    delay: float = 0.0,
    pace_requests: bool = False,
) -> PageFetchResult:
    if delay:
        await asyncio.sleep(delay)

    async with semaphore:
        for attempt in range(1, max_retries + 1):
            if pace_requests and settings.pncp_request_interval_seconds:
                await asyncio.sleep(settings.pncp_request_interval_seconds)
            try:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 204:
                    return PageFetchResult(
                        page=int(params["pagina"]),
                        items=[],
                        total_registros=0,
                    )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "desconhecido")
                    if attempt < max_retries:
                        delay_seconds = _rate_limit_retry_delay(retry_after, attempt)
                        logger.warning(
                            "Rate limit na página %s; aguardando %.1fs antes da tentativa %s",
                            params.get("pagina"),
                            delay_seconds,
                            attempt + 1,
                        )
                        await asyncio.sleep(delay_seconds)
                        continue
                    error = PNCPResponseError("PNCP limitou temporariamente a frequência de consultas")
                    logger.warning(
                        "Rate limit na página %s (Retry-After: %s); encerrando a busca atual",
                        params.get("pagina"),
                        retry_after,
                    )
                    return PageFetchResult(
                        page=int(params["pagina"]),
                        items=[],
                        error=error,
                        rate_limited=True,
                    )
                if response.status_code in {408, 425, 500, 502, 503, 504} and attempt < max_retries:
                    delay_seconds = _retry_delay("desconhecido", attempt)
                    logger.warning(
                        "PNCP respondeu HTTP %s na página %s; nova tentativa em %.1fs",
                        response.status_code,
                        params.get("pagina"),
                        delay_seconds,
                    )
                    await asyncio.sleep(delay_seconds)
                    continue
                response.raise_for_status()
                payload = response.json()
            except httpx.ConnectError as exc:
                error = PNCPConnectionError("Falha de conexão ou TLS com o PNCP")
                logger.warning("Falha TLS/conexão na página %s: %s", params.get("pagina"), exc)
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=error,
                    terminal_error=True,
                )
            except httpx.TimeoutException as exc:
                error = PNCPConnectionError("Timeout ao consultar o PNCP")
                logger.warning("Timeout na página %s: %s", params.get("pagina"), exc)
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=error,
                    terminal_error=True,
                )
            except httpx.HTTPStatusError as exc:
                error = PNCPResponseError(f"PNCP respondeu HTTP {exc.response.status_code}")
                logger.warning("Falha HTTP na página %s: %s", params.get("pagina"), exc)
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=error,
                    terminal_error=True,
                )
            except httpx.HTTPError as exc:
                error = PNCPConnectionError("Erro HTTP ao consultar o PNCP")
                logger.warning("Erro HTTP na página %s: %s", params.get("pagina"), exc)
                if attempt < max_retries:
                    await asyncio.sleep(0.4 * attempt)
                    continue
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=error,
                    terminal_error=True,
                )
            except ValueError as exc:
                error = PNCPResponseError("Payload JSON inválido retornado pelo PNCP")
                logger.warning("Payload inválido na página %s: %s", params.get("pagina"), exc)
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=error,
                    terminal_error=True,
                )

            if isinstance(payload, list):
                return PageFetchResult(page=int(params["pagina"]), items=payload)
            if not isinstance(payload, dict):
                return PageFetchResult(
                    page=int(params["pagina"]),
                    items=[],
                    error=PNCPResponseError("Formato de resposta inesperado do PNCP"),
                    terminal_error=True,
                )
            items = payload.get("data") or []
            total = payload.get("totalRegistros")
            return PageFetchResult(
                page=int(params["pagina"]),
                items=items if isinstance(items, list) else [],
                total_registros=int(total) if total is not None else None,
            )

    return PageFetchResult(
        page=int(params["pagina"]),
        items=[],
        error=PNCPConnectionError("Falha ao consultar o PNCP"),
        terminal_error=True,
    )


def _retry_delay(retry_after: str, attempt: int) -> float:
    try:
        return max(0.5, min(float(retry_after), 5.0))
    except (TypeError, ValueError):
        return min(0.5 * (2 ** (attempt - 1)), 2.0)


def _rate_limit_retry_delay(retry_after: str, attempt: int) -> float:
    """Prioriza Retry-After e evita repetir imediatamente uma resposta 429."""
    try:
        return max(0.5, min(float(retry_after), 30.0))
    except (TypeError, ValueError):
        return min(settings.pncp_rate_limit_retry_seconds * attempt, 30.0)


async def _execute_search(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    data_inicial: str,
    data_final: str,
    modalidade: int,
    tamanho_pagina: int,
    max_paginas: int,
    uf: str | None = None,
) -> tuple[list[dict[str, Any]], ExecucaoBusca]:
    semaphore = obter_limitador_paginas_pncp()
    modalidades = MODALIDADES_PADRAO_TODAS if modalidade == 0 else [modalidade]
    raw_items: list[dict[str, Any]] = []
    raw_index_by_id: dict[str, int] = {}
    paginas_consultadas = 0
    paginas_com_erro = 0
    parcial = False
    parar_por_rate_limit = False

    def append_unique_items(items: list[dict[str, Any]]) -> None:
        for item in items:
            item_id = _raw_pncp_identifier(item)
            previous_index = raw_index_by_id.get(item_id)
            if previous_index is None:
                raw_index_by_id[item_id] = len(raw_items)
                raw_items.append(item)
            else:
                raw_items[previous_index] = _merge_duplicate_pncp_item(
                    raw_items[previous_index], item
                )

    async def fetch_mode_page(current_mode: int) -> tuple[int, PageFetchResult]:
        params: dict[str, Any] = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": current_mode,
            "pagina": 1,
            "tamanhoPagina": tamanho_pagina,
        }
        if uf and uf != "TODOS":
            params["uf"] = uf
        result = await fetch_pagina(client, semaphore, url, params, headers, pace_requests=True)
        return current_mode, result

    # A busca padrão consulta uma página por modalidade. Essas chamadas são
    # independentes e precisam começar juntas para que o tempo de uma
    # modalidade lenta não seja somado ao das demais.
    if modalidade == 0 and max_paginas == 1:
        results = await asyncio.gather(*(fetch_mode_page(mode) for mode in modalidades))
        for _current_mode, result in results:
            paginas_consultadas += 1
            if result.error:
                paginas_com_erro += 1
                parcial = True
                continue
            append_unique_items(result.items)
            if result.total_registros is not None and len(result.items) < result.total_registros:
                parcial = True

        metadata = ExecucaoBusca(
            parcial=parcial,
            paginas_consultadas=paginas_consultadas,
            paginas_com_erro=paginas_com_erro,
            origem="PNCP",
        )
        return raw_items, metadata

    for current_mode in modalidades:
        collected_for_mode = 0
        total_for_mode: int | None = None
        for page in range(1, max_paginas + 1):
            params: dict[str, Any] = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": current_mode,
                "pagina": page,
                "tamanhoPagina": tamanho_pagina,
            }
            if uf and uf != "TODOS":
                params["uf"] = uf

            result = await fetch_pagina(client, semaphore, url, params, headers, pace_requests=True)
            paginas_consultadas += 1
            if result.error:
                paginas_com_erro += 1
                parcial = True
                if result.rate_limited:
                    parar_por_rate_limit = True
                # Um erro de uma modalidade não impede as demais modalidades.
                break

            if result.total_registros is not None:
                total_for_mode = result.total_registros
            collected_for_mode += len(result.items)
            append_unique_items(result.items)

            if total_for_mode is not None and collected_for_mode >= total_for_mode:
                break
            if total_for_mode is None and not result.items:
                break
        if total_for_mode is not None and collected_for_mode < total_for_mode:
            parcial = True
        if parar_por_rate_limit:
            break

    metadata = ExecucaoBusca(
        parcial=parcial,
        paginas_consultadas=paginas_consultadas,
        paginas_com_erro=paginas_com_erro,
        origem="PNCP",
    )
    return raw_items, metadata


def _tls_verify() -> bool | ssl.SSLContext:
    if settings.pncp_ca_bundle:
        return ssl.create_default_context(cafile=settings.pncp_ca_bundle)
    return True


def _result(
    *,
    status: str,
    mensagem: str,
    dados: list[dict[str, Any]],
    metadados: ExecucaoBusca,
    summaries: dict[str, dict[str, object]] | None = None,
) -> dict[str, Any]:
    keys = {
        f"{item['cnpj']}:{item['ano']}:{item['sequencial']}"
        for item in dados
        if item.get("cnpj") and item.get("ano") and item.get("sequencial")
    }
    if summaries is None:
        # Mantém compatibilidade com os consumidores síncronos e testes diretos
        # deste auxiliar. As rotas assíncronas usam _result_async.
        summaries = obter_resumos_contratacoes(keys)
    dados_com_resumo = [
        {
            **item,
            **(
                {"resumo_exigencias": summaries[key]}
                if (key := f"{item.get('cnpj')}:{item.get('ano')}:{item.get('sequencial')}") in summaries
                else {}
            ),
        }
        for item in dados
    ]
    result = ResultadoBusca(
        status=status,
        mensagem=mensagem,
        total_encontradas=len(dados_com_resumo),
        dados=dados_com_resumo,
        metadados=metadados,
    )
    return result.model_dump(mode="json")


async def _result_async(
    *,
    status: str,
    mensagem: str,
    dados: list[dict[str, Any]],
    metadados: ExecucaoBusca,
) -> dict[str, Any]:
    """Monta a resposta sem executar consultas SQL no loop da API."""

    keys = {
        f"{item['cnpj']}:{item['ano']}:{item['sequencial']}"
        for item in dados
        if item.get("cnpj") and item.get("ano") and item.get("sequencial")
    }


    summaries = await asyncio.to_thread(obter_resumos_contratacoes, keys)
    return _result(
        status=status,
        mensagem=mensagem,
        dados=dados,
        metadados=metadados,
        summaries=summaries,
    )


def _itens_tipo_payload(payload: Any) -> list[Mapping[str, Any]]:
    """Aceita os formatos de itens usados pelas versões do endpoint PNCP."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for field in ("data", "itens", "items"):
            value = payload.get(field)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, Mapping)]
    return []


def _criterio_mais_frequente(itens: list[Mapping[str, Any]]) -> tuple[str | None, str | None]:
    """Escolhe o critério mais publicado quando a contratação tem vários itens."""

    encontrados: list[tuple[str, str | None]] = []
    for item in itens:
        campos = normalizar_campos_tipo_contratacao(item)
        criterio = campos.get("criterio_julgamento")
        if criterio:
            origem = (campos.get("tipo_contratacao_origem") or {}).get("criterio_julgamento")
            encontrados.append((str(criterio), str(origem) if origem else None))
    if not encontrados:
        return None, None
    contagens = Counter(criterio for criterio, _origem in encontrados)
    criterio = contagens.most_common(1)[0][0]
    origem = next((origem for valor, origem in encontrados if valor == criterio and origem), None)
    return criterio, origem


async def _consultar_tipo_contratacao_pncp(
    cnpj: str,
    ano: int,
    sequencial: int,
    *,
    modalidade: str | None,
    tipo_instrumento: str | None,
) -> dict[str, Any]:
    """Busca o critério nos itens sem baixar o edital nem seus anexos."""

    url = f"{PNCP_DOCUMENTOS_URL}/{quote(cnpj, safe='')}/compras/{ano}/{sequencial}/itens"
    headers = {"User-Agent": "licitacoes-obras/1.0", "Accept": "application/json"}
    client = await obter_cliente_pncp()
    response = await client.get(
        url,
        params={"pagina": 1, "tamanhoPagina": 50},
        headers=headers,
    )
    if response.status_code == 204:
        return normalizar_campos_tipo_contratacao(
            {"modalidade": modalidade, "tipo_instrumento": tipo_instrumento}
        )
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as exc:
        raise PNCPResponseError("Payload JSON inválido retornado pelo PNCP") from exc

    criterio, criterio_field = _criterio_mais_frequente(_itens_tipo_payload(payload))
    campos = normalizar_campos_tipo_contratacao(
        {
            "modalidade": modalidade,
            "criterio_julgamento": criterio,
            "tipo_instrumento": tipo_instrumento,
        }
    )
    if criterio and criterio_field:
        origem = dict(campos.get("tipo_contratacao_origem") or {})
        origem["criterio_julgamento"] = criterio_field
        campos["tipo_contratacao_origem"] = origem
    return campos


def _clear_tipo_contratacao_inflight(cache_key: str, task: asyncio.Task[dict[str, Any]]) -> None:
    if _TIPO_CONTRATACAO_INFLIGHT.get(cache_key) is task:
        _TIPO_CONTRATACAO_INFLIGHT.pop(cache_key, None)


async def buscar_tipo_contratacao_pncp(
    cnpj: str,
    ano: int,
    sequencial: int,
    *,
    modalidade: str | None = None,
    tipo_instrumento: str | None = None,
) -> dict[str, Any]:
    """Retorna o tipo composto do card, enriquecendo-o com o primeiro item."""

    cnpj, ano, sequencial = _validar_identificadores_contratacao(cnpj, ano, sequencial)
    modalidade_normalizada = str(modalidade).strip() if modalidade else None
    instrumento_normalizado = str(tipo_instrumento).strip() if tipo_instrumento else None
    fallback = normalizar_campos_tipo_contratacao(
        {"modalidade": modalidade_normalizada, "tipo_instrumento": instrumento_normalizado}
    )
    cache_key = f"{cnpj}:{ano}:{sequencial}:{modalidade_normalizada or ''}:{instrumento_normalizado or ''}"
    cached = _TIPO_CONTRATACAO_CACHE.get(cache_key)
    if cached is not None:
        return dict(cached)

    task = _TIPO_CONTRATACAO_INFLIGHT.get(cache_key)
    if task is None:
        task = asyncio.create_task(
            _consultar_tipo_contratacao_pncp(
                cnpj,
                ano,
                sequencial,
                modalidade=modalidade_normalizada,
                tipo_instrumento=instrumento_normalizado,
            )
        )
        _TIPO_CONTRATACAO_INFLIGHT[cache_key] = task
        task.add_done_callback(
            lambda completed_task: _clear_tipo_contratacao_inflight(cache_key, completed_task)
        )
    try:
        result = await asyncio.shield(task)
    except (PNCPConnectionError, PNCPResponseError, httpx.HTTPError) as exc:
        logger.info("Não foi possível enriquecer o tipo da contratação %s: %s", cache_key, exc)
        return fallback
    _TIPO_CONTRATACAO_CACHE[cache_key] = dict(result)
    return dict(result)


def _validar_identificadores_contratacao(cnpj: str, ano: int, sequencial: int) -> tuple[str, int, int]:
    cnpj_normalizado = str(cnpj or "").strip()
    if re.fullmatch(r"[A-Za-z0-9]{14}", cnpj_normalizado) is None:
        raise ValueError("cnpj deve conter exatamente 14 caracteres alfanuméricos")
    if int(ano) < 1:
        raise ValueError("ano deve ser um inteiro positivo")
    if int(sequencial) < 1:
        raise ValueError("sequencial deve ser um inteiro positivo")
    return cnpj_normalizado, int(ano), int(sequencial)


def _document_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def normalizar_documentos_pncp(payload: Any) -> list[dict[str, Any]]:
    """Converte respostas possíveis do PNCP para o contrato do produto."""
    if isinstance(payload, list):
        raw_documents = payload
    elif isinstance(payload, dict):
        raw_documents = payload.get("documentos")
        if not isinstance(raw_documents, list):
            raw_documents = payload.get("data")
        if not isinstance(raw_documents, list):
            raw_documents = []
    else:
        raw_documents = []

    documents: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw_document in raw_documents:
        if not isinstance(raw_document, dict):
            continue

        raw_sequence = raw_document.get("sequencialDocumento") or raw_document.get("sequencial_documento")
        try:
            sequence = int(raw_sequence)
        except (TypeError, ValueError):
            logger.warning("Documento PNCP descartado por ausência de sequencial válido")
            continue
        if sequence < 1 or sequence in seen:
            continue

        raw_type_id = raw_document.get("tipoDocumentoId") or raw_document.get("tipo_documento_id")
        try:
            type_id = int(raw_type_id) if raw_type_id is not None else None
        except (TypeError, ValueError):
            type_id = None

        document = DocumentoOut(
            sequencial_documento=sequence,
            url=_document_url(raw_document.get("url")),
            tipo_documento_id=type_id,
            tipo_documento_nome=(
                str(raw_document.get("tipoDocumentoNome") or raw_document.get("tipo_documento_nome")).strip()
                if raw_document.get("tipoDocumentoNome") or raw_document.get("tipo_documento_nome")
                else None
            ),
            titulo=(
                str(raw_document.get("titulo")).strip()
                if raw_document.get("titulo")
                else None
            ),
            data_publicacao_pncp=(
                str(raw_document.get("dataPublicacaoPncp") or raw_document.get("data_publicacao_pncp")).strip()
                if raw_document.get("dataPublicacaoPncp") or raw_document.get("data_publicacao_pncp")
                else None
            ),
        )
        seen.add(sequence)
        documents.append(document.model_dump())
    return documents


def _documentos_result(
    documentos: list[dict[str, Any]],
    *,
    origem: str = "PNCP",
    desatualizado: bool = False,
    atualizado_em: datetime | str | None = None,
) -> dict[str, Any]:
    status = "sucesso_real" if documentos else "sucesso_vazio"
    if desatualizado:
        mensagem = (
            "Exibindo a última lista de documentos conhecida; o PNCP está indisponível no momento."
            if documentos
            else "A última consulta conhecida não encontrou documentos; o PNCP está indisponível no momento."
        )
    else:
        mensagem = (
            "Documentos da contratação carregados do PNCP."
            if documentos
            else "Nenhum documento foi disponibilizado para esta contratação no PNCP."
        )
    return ResultadoDocumentos(
        status=status,
        mensagem=mensagem,
        total=len(documentos),
        documentos=documentos,
        origem=origem,
        desatualizado=desatualizado,
        atualizado_em=(atualizado_em.isoformat() if isinstance(atualizado_em, datetime) else atualizado_em),
    ).model_dump(mode="json")


async def _registrar_documentos_reais(
    *,
    cache_key: str,
    documentos: list[dict[str, Any]],
) -> dict[str, Any]:
    atualizado_em = datetime.now(timezone.utc)
    result = _documentos_result(documentos, atualizado_em=atualizado_em)
    _DOCUMENTOS_CACHE[cache_key] = result
    try:
        await asyncio.to_thread(salvar_snapshot_documentos, cache_key, documentos)
    except Exception as exc:  # Persistência é auxiliar; não invalida uma resposta real do PNCP.
        logger.warning("Não foi possível salvar o snapshot de documentos: %s", exc)
        _PNCP_METRICS["documentos_falhas_persistencia"] += 1
    _PNCP_METRICS["documentos_sucesso_remoto"] += 1
    return result.copy()


async def _consultar_documentos_pncp(
    cnpj: str,
    ano: int,
    sequencial: int,
    *,
    cache_key: str,
) -> dict[str, Any]:
    """Consulta os arquivos remotos com retry limitado pelo orçamento.

    O timeout do cliente HTTP vale para cada tentativa, enquanto
    :func:`documentos_request_timeout_seconds` representa o orçamento total
    do endpoint. O deadline evita iniciar uma nova tentativa quando já não
    há tempo suficiente para ela.
    """
    url = (
        f"{PNCP_DOCUMENTOS_URL}/{quote(cnpj, safe='')}/compras/{ano}/{sequencial}/arquivos"
    )
    headers = {
        "User-Agent": "licitacoes-obras/1.0",
        "Accept": "application/json",
    }
    max_retries = DOCUMENTOS_MAX_RETRIES
    deadline = time.monotonic() + documentos_request_timeout_seconds()

    def _pode_repetir(attempt: int, delay_seconds: float) -> bool:
        if attempt >= max_retries:
            return False
        # Reserva o timeout de uma chamada completa antes de iniciar a
        # próxima. Isso mantém o retry dentro do orçamento mesmo quando a
        # falha de conexão acontece antes do timeout do httpx.
        remaining = deadline - time.monotonic()
        request_budget = max(
            settings.pncp_timeout_seconds,
            settings.pncp_connect_timeout_seconds,
        )
        return remaining > request_budget + delay_seconds

    async def _aguardar_retry(attempt: int, motivo: str, delay_seconds: float) -> None:
        remaining = max(0.0, deadline - time.monotonic())
        await asyncio.sleep(min(delay_seconds, remaining))
        logger.warning(
            "Falha transitória ao consultar documentos do PNCP (%s); "
            "nova tentativa %s/%s em %.1fs",
            motivo,
            attempt + 1,
            max_retries,
            delay_seconds,
        )

    try:
        client = await obter_cliente_pncp()
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.get(url, headers=headers)
            except httpx.TimeoutException as exc:
                delay_seconds = _retry_delay("desconhecido", attempt)
                if _pode_repetir(attempt, delay_seconds):
                    await _aguardar_retry(attempt, "timeout", delay_seconds)
                    continue
                raise PNCPConnectionError(
                    "Timeout ao consultar os documentos do PNCP"
                ) from exc
            except httpx.NetworkError as exc:
                delay_seconds = _retry_delay("desconhecido", attempt)
                if _pode_repetir(attempt, delay_seconds):
                    await _aguardar_retry(attempt, "conexão/TLS", delay_seconds)
                    continue
                raise PNCPConnectionError(
                    "Falha de conexão ou TLS ao consultar os documentos do PNCP"
                ) from exc

            if response.status_code == 204:
                return await _registrar_documentos_reais(cache_key=cache_key, documentos=[])

            if response.status_code == 429:
                delay_seconds = _retry_delay(response.headers.get("Retry-After", "desconhecido"), attempt)
                if _pode_repetir(attempt, delay_seconds):
                    await _aguardar_retry(attempt, "HTTP 429", delay_seconds)
                    continue
            elif response.status_code in {408, 425, 500, 502, 503, 504}:
                delay_seconds = _retry_delay("desconhecido", attempt)
                if _pode_repetir(attempt, delay_seconds):
                    await _aguardar_retry(attempt, f"HTTP {response.status_code}", delay_seconds)
                    continue

            if response.status_code == 429:
                raise PNCPResponseError("PNCP limitou temporariamente a consulta de documentos")
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise PNCPResponseError("Payload JSON inválido retornado pelo PNCP") from exc

            if not isinstance(payload, (list, dict)):
                raise PNCPResponseError("Formato de resposta inesperado do PNCP")
            return await _registrar_documentos_reais(
                cache_key=cache_key,
                documentos=normalizar_documentos_pncp(payload),
            )
    except PNCPResponseError:
        raise
    except httpx.TimeoutException as exc:
        raise PNCPConnectionError("Timeout ao consultar os documentos do PNCP") from exc
    except httpx.NetworkError as exc:
        raise PNCPConnectionError("Falha de conexão ou TLS ao consultar os documentos do PNCP") from exc
    except httpx.HTTPStatusError as exc:
        raise PNCPResponseError(f"PNCP respondeu HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise PNCPConnectionError("Erro HTTP ao consultar os documentos do PNCP") from exc

    raise PNCPConnectionError("Falha ao consultar os documentos do PNCP")


def _clear_documentos_inflight(cache_key: str, task: asyncio.Task[dict[str, Any]]) -> None:
    if _DOCUMENTOS_INFLIGHT.get(cache_key) is task:
        _DOCUMENTOS_INFLIGHT.pop(cache_key, None)


async def buscar_documentos_pncp(cnpj: str, ano: int, sequencial: int) -> dict[str, Any]:
    """Consulta os documentos publicados, com cache e deduplicação de chamadas simultâneas."""
    cnpj, ano, sequencial = _validar_identificadores_contratacao(cnpj, ano, sequencial)
    cache_key = f"{cnpj}:{ano}:{sequencial}"
    cached = _DOCUMENTOS_CACHE.get(cache_key)
    if cached is not None:
        _PNCP_METRICS["documentos_cache_memoria"] += 1
        return _documentos_result(
            list(cached.get("documentos", [])),
            origem="cache_memoria",
            atualizado_em=cached.get("atualizado_em"),
        )

    task = _DOCUMENTOS_INFLIGHT.get(cache_key)
    if task is None:
        _PNCP_METRICS["documentos_consultas_remotas"] += 1
        task = asyncio.create_task(
            _consultar_documentos_pncp(cnpj, ano, sequencial, cache_key=cache_key)
        )
        _DOCUMENTOS_INFLIGHT[cache_key] = task
        task.add_done_callback(lambda completed_task: _clear_documentos_inflight(cache_key, completed_task))

    # Um timeout ou fechamento do modal não deve cancelar a consulta que a
    # análise de exigências está aguardando para a mesma contratação.
    try:
        return await asyncio.shield(task)
    except (PNCPConnectionError, PNCPResponseError):
        _PNCP_METRICS["documentos_falhas_remotas"] += 1
        snapshot = await asyncio.to_thread(obter_snapshot_documentos, cache_key)
        if snapshot is not None:
            _PNCP_METRICS["documentos_cache_persistente"] += 1
            return _documentos_result(
                snapshot.documentos,
                origem="cache_persistente",
                desatualizado=True,
                atualizado_em=snapshot.updated_at,
            )
        raise


def documentos_request_timeout_seconds() -> float:
    """Orçamento do endpoint: duas tentativas do PNCP mais a espera de retry."""
    return max(5.0, (settings.pncp_timeout_seconds * 2) + _retry_delay("desconhecido", 1) + 1.0)


async def _fallback_local(
    *,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    uf: str | None,
    mensagem: str,
    paginas_consultadas: int = 0,
    paginas_com_erro: int = 0,
) -> dict[str, Any]:
    from backend.database import SessionLocal
    from backend.services.db_service import get_obras_from_db

    metadata = ExecucaoBusca(
        parcial=True,
        paginas_consultadas=paginas_consultadas,
        paginas_com_erro=paginas_com_erro,
        origem="banco_local",
    )
    def read_local() -> list[dict[str, Any]]:
        with SessionLocal() as db:
            return get_obras_from_db(
                db,
                uf=uf,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                include_payload=True,
            )

    try:
        dados = await asyncio.to_thread(read_local)
        if dados:
            return await _result_async(
                status="sucesso_offline_db",
                mensagem=mensagem,
                dados=dados,
                metadados=metadata,
            )
    except (DatabaseServiceError, SQLAlchemyError) as exc:
        logger.error("Falha ao consultar banco local durante fallback: %s", exc, exc_info=True)

    return await _result_async(
        status="erro",
        mensagem=f"{mensagem} Não há dados locais disponíveis para estes filtros.",
        dados=[],
        metadados=metadata,
    )


async def _fallback_cache_or_local(
    *,
    cache_key: str,
    modalidade: int,
    data_inicial: str,
    data_final: str,
    uf: str | None,
    mensagem: str,
    paginas_consultadas: int = 0,
    paginas_com_erro: int = 0,
) -> dict[str, Any]:
    """Usa cache somente depois de uma falha do PNCP; banco é o segundo fallback."""
    cached = _CACHE.get(cache_key)
    if cached is not None:
        result = cached.copy()
        cached_metadata = dict(result.get("metadados") or {})
        cached_metadata.update(
            {
                "origem": "cache",
                "parcial": True,
                "paginas_consultadas": paginas_consultadas or cached_metadata.get("paginas_consultadas", 0),
                "paginas_com_erro": paginas_com_erro or cached_metadata.get("paginas_com_erro", 0),
            }
        )
        result["status"] = "sucesso_offline_cache"
        result["mensagem"] = f"{mensagem} Exibindo o último resultado salvo em cache."
        result["metadados"] = cached_metadata
        return result
    fallback = _fallback_local(
        modalidade=modalidade,
        data_inicial=data_inicial,
        data_final=data_final,
        uf=uf,
        mensagem=mensagem,
        paginas_consultadas=paginas_consultadas,
        paginas_com_erro=paginas_com_erro,
    )
    return await fallback if inspect.isawaitable(fallback) else fallback


async def _resultado_local_disponivel(
    *,
    data_inicial: str,
    data_final: str,
    modalidade: int,
    uf: str | None,
) -> dict[str, Any] | None:
    """Retorna o snapshot local do período, sem iniciar uma chamada ao PNCP.

    A existência é verificada primeiro para todo o período. Assim, escolher
    uma UF, modalidade ou termo que não possua resultado não provoca uma nova
    coleta externa: apenas exibe uma lista vazia sobre o snapshot já salvo.
    """

    from backend.database import SessionLocal
    from backend.services.db_service import get_obras_from_db

    def read_local() -> list[dict[str, Any]]:
        with SessionLocal() as db:
            return get_obras_from_db(
                db,
                data_inicial=data_inicial,
                data_final=data_final,
                limit=1_000,
                include_payload=True,
            )

    try:
        dados_do_periodo = await asyncio.to_thread(read_local)
    except (DatabaseServiceError, SQLAlchemyError) as exc:
        logger.warning("Não foi possível consultar o snapshot local: %s", exc)
        return None

    if not dados_do_periodo:
        return None

    dados = dados_do_periodo
    if modalidade:
        dados = [item for item in dados if int(item.get("modalidade_codigo") or 0) == modalidade]
    if uf and uf.upper() != "TODOS":
        dados = [item for item in dados if str(item.get("uf") or "").upper() == uf.upper()]

    return await _result_async(
        status="sucesso_local",
        mensagem="Exibindo dados já armazenados para o período. Clique em Atualizar Dados para consultar o PNCP.",
        dados=dados,
        metadados=ExecucaoBusca(origem="banco_local"),
    )


def _timeout_message() -> str:
    return _timeout_message_for(settings.pncp_timeout_seconds)


def _timeout_message_for(timeout_seconds: float) -> str:
    return (
        f"A consulta ao PNCP excedeu {timeout_seconds:g} segundos; "
        "exibindo o último resultado local disponível."
    )


def _search_timeout_seconds(modalidade: int, max_paginas: int = 1) -> float:
    """Reserva tempo para páginas serializadas e um retry por rate limit."""
    modalidade_count = len(MODALIDADES_PADRAO_TODAS) if modalidade == 0 else 1
    page_count = max(1, max_paginas)
    requests = modalidade_count * page_count
    return (
        settings.pncp_timeout_seconds
        + settings.pncp_request_interval_seconds
        + settings.pncp_rate_limit_retry_seconds
    ) * requests


def search_request_timeout_seconds(modalidade: int, max_paginas: int) -> float:
    """Orçamento externo ligeiramente maior que o limite interno da busca."""
    return _search_timeout_seconds(modalidade, max_paginas) + 5.0


def _persistir_obras_consulta(dados: list[dict[str, Any]]) -> None:
    """Unidade de trabalho síncrona executada fora do loop da API."""

    from backend.database import SessionLocal
    from backend.services.db_service import cleanup_expired_obras, save_obras_batch

    with SessionLocal() as db:
        save_obras_batch(db, dados)
        cleanup_expired_obras(db, max_age_days=settings.retention_days)


def _pagination_fingerprint(
    *,
    data_inicial: str,
    data_final: str,
    modalidade: int,
    tamanho_pagina: int,
    max_paginas: int,
    uf: str | None,
    tamanho_resultado: int,
    termo: str | None = None,
    termos_inclusao: list[str] | None = None,
    termos_exclusao: list[str] | None = None,
    escopo_busca: str = "objeto_itens",
    modo_inclusao: str = "qualquer",
    ordenacao: str = "data_desc",
    incluir_pavimentacao: bool = True,
) -> str:
    query = {
        "data_inicial": data_inicial,
        "data_final": data_final,
        "modalidade": modalidade,
        "tamanho_pagina": tamanho_pagina,
        "max_paginas": max_paginas,
        "uf": uf or "TODOS",
        "tamanho_resultado": tamanho_resultado,
        # A forma canônica impede cursores diferentes para acentos/espaços e
        # inclui a versão do interpretador para não reutilizar snapshots com
        # outra semântica de exclusão.
        "termo": remover_acentos(termo or ""),
        "termos_inclusao": [remover_acentos(item) for item in (termos_inclusao or [])],
        "termos_exclusao": [remover_acentos(item) for item in (termos_exclusao or [])],
        "escopo_busca": escopo_busca,
        "modo_inclusao": modo_inclusao,
        "versao_parser": SEARCH_PARSER_VERSION,
        "ordenacao": ordenacao,
        "incluir_pavimentacao": incluir_pavimentacao,
    }
    return hashlib.sha256(json.dumps(query, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _encode_page_cursor(offset: int, fingerprint: str) -> str:
    payload = json.dumps({"offset": offset, "query": fingerprint}, separators=(",", ":")).encode()
    signature = hmac.new(settings.pagination_cursor_secret.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def _decode_page_cursor(cursor: str, fingerprint: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(f"{cursor}{'=' * (-len(cursor) % 4)}")
        payload, signature = raw[:-32], raw[-32:]
        expected = hmac.new(settings.pagination_cursor_secret.encode(), payload, hashlib.sha256).digest()
        parsed = json.loads(payload)
        offset = int(parsed["offset"])
    except (binascii.Error, KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("cursor de paginação inválido") from exc
    if not hmac.compare_digest(signature, expected) or parsed.get("query") != fingerprint or offset < 0:
        raise ValueError("cursor de paginação inválido")
    return offset


def _encode_snapshot_cursor(
    *,
    snapshot_id: str,
    offset: int,
    fingerprint: str,
    expires_at: datetime,
    tamanho_resultado: int,
) -> str:
    payload = json.dumps(
        {
            "v": 2,
            "snapshot": snapshot_id,
            "offset": offset,
            "query": fingerprint,
            "expires": int(expires_at.timestamp()),
            "size": tamanho_resultado,
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(settings.pagination_cursor_secret.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")


def _decode_snapshot_cursor(
    cursor: str,
    *,
    fingerprint: str,
    tamanho_resultado: int,
) -> tuple[str, int, datetime]:
    try:
        raw = base64.urlsafe_b64decode(f"{cursor}{'=' * (-len(cursor) % 4)}")
        payload, signature = raw[:-32], raw[-32:]
        expected = hmac.new(settings.pagination_cursor_secret.encode(), payload, hashlib.sha256).digest()
        parsed = json.loads(payload)
        snapshot_id = str(parsed["snapshot"])
        offset = int(parsed["offset"])
        expires_at = datetime.fromtimestamp(int(parsed["expires"]), tz=timezone.utc)
    except (binascii.Error, KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise PaginationCursorError("cursor de paginação inválido") from exc
    if (
        not hmac.compare_digest(signature, expected)
        or parsed.get("v") != 2
        or parsed.get("query") != fingerprint
        or parsed.get("size") != tamanho_resultado
        or offset < 0
        or not snapshot_id
    ):
        raise PaginationCursorError("cursor de paginação inválido")
    if expires_at <= datetime.now(timezone.utc):
        raise PaginationSnapshotExpiredError("A consulta anterior expirou; reinicie a busca.")
    return snapshot_id, offset, expires_at


def _decimal_value(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _ordenar_e_resumir_consulta(
    dados: list[dict[str, Any]],
    *,
    termo: str | None = None,
    ordenacao: str = "data_desc",
    incluir_pavimentacao: bool = True,
    expressao_busca: SearchExpression | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Aplica a mesma consulta global usada por indicadores e paginação."""

    allowed_orders = {"data_desc", "data_asc", "valor_desc", "valor_asc", "orgao"}
    if ordenacao not in allowed_orders:
        raise ValueError("ordenacao inválida")
    expression = expressao_busca or parse_search_request(termo)
    filtered_search = aplicar_busca(
        dados,
        expression,
        anexar_metadados=expression.possui_termos,
    )
    filtered = list(filtered_search.registros)
    if not incluir_pavimentacao:
        filtered = [
            item for item in filtered if not eh_obra_pavimentacao(str(item.get("objeto") or ""))
        ]
    ordered = sorted(filtered, key=lambda item: str(item.get("id_pncp") or item.get("numero_controle_pncp") or ""))
    if ordenacao == "data_desc":
        ordered.sort(key=lambda item: str(item.get("data_publicacao") or ""), reverse=True)
    elif ordenacao == "data_asc":
        ordered.sort(key=lambda item: (not bool(item.get("data_publicacao")), str(item.get("data_publicacao") or "")))
    elif ordenacao == "valor_desc":
        ordered.sort(
            key=lambda item: (
                _decimal_value(item.get("valor_estimado")) is None,
                -(_decimal_value(item.get("valor_estimado")) or Decimal("0")),
            )
        )
    elif ordenacao == "valor_asc":
        ordered.sort(
            key=lambda item: (
                _decimal_value(item.get("valor_estimado")) is None,
                _decimal_value(item.get("valor_estimado")) or Decimal("0"),
            )
        )
    else:
        ordered.sort(key=lambda item: remover_acentos(str(item.get("orgao") or "")))

    values = [_decimal_value(item.get("valor_estimado")) for item in ordered]
    known_values = [value for value in values if value is not None]

    def aggregate(field: str, fallback: str) -> dict[str, dict[str, Decimal | int]]:
        aggregates: dict[str, dict[str, Decimal | int]] = {}
        for item in ordered:
            key = str(item.get(field) or fallback)
            item_value = _decimal_value(item.get("valor_estimado")) or Decimal("0")
            current = aggregates.setdefault(key, {"quantidade": 0, "volume": Decimal("0")})
            current["quantidade"] = int(current["quantidade"]) + 1
            current["volume"] = Decimal(str(current["volume"])) + item_value
        return aggregates

    return ordered, {
        "total_coletado": len(dados),
        "total_filtrado": len(ordered),
        "volume_estimado": sum(known_values, Decimal("0")),
        "quantidade_sem_valor": len(ordered) - len(known_values),
        # Sobre o resultado inteiro, não só a página: o ERP mostra como indicador.
        "maior_valor": max(known_values, default=None),
        "agregados_uf": aggregate("uf", "BR"),
        "agregados_modalidade": aggregate("modalidade", "Não informada"),
        **filtered_search.metadados(expression),
    }


def _paginate_snapshot(
    snapshot: QuerySnapshot,
    *,
    offset: int,
    tamanho_resultado: int,
) -> dict[str, Any]:
    current_items = snapshot.dados[offset : offset + tamanho_resultado]
    next_offset = offset + len(current_items)
    has_more = next_offset < len(snapshot.dados)
    result = dict(snapshot.resultado)
    metadata = dict(result.get("metadados") or {})
    metadata.update(
        {
            "consulta_id": snapshot.id,
            "consulta_criada_em": snapshot.created_at.isoformat(),
            "consulta_expira_em": snapshot.expires_at.isoformat(),
        }
    )
    result.update(
        {
            "dados": current_items,
            "metadados": metadata,
            "paginacao": {
                "tamanho": tamanho_resultado,
                "total_carregado": len(snapshot.dados),
                "tem_mais": has_more,
                "proximo_cursor": (
                    _encode_snapshot_cursor(
                        snapshot_id=snapshot.id,
                        offset=next_offset,
                        fingerprint=snapshot.fingerprint,
                        expires_at=snapshot.expires_at,
                        tamanho_resultado=tamanho_resultado,
                    )
                    if has_more
                    else None
                ),
                "anterior_disponivel": offset > 0,
            },
        }
    )
    return result


async def _snapshot_and_paginate(
    result: dict[str, Any],
    *,
    fingerprint: str,
    tamanho_resultado: int,
) -> dict[str, Any]:
    if len(result.get("dados", [])) <= tamanho_resultado:
        # Não há continuidade a preservar. Evitar escrita temporária também
        # mantém testes unitários de respostas de página única independentes
        # de um banco já migrado.
        return _paginate_result(
            result,
            cursor=None,
            tamanho_resultado=tamanho_resultado,
            fingerprint=fingerprint,
        )
    # A agregação usa Decimal internamente. O modelo da resposta normalmente
    # faz essa conversão, mas aqui os metadados acabaram de ser recalculados e
    # ainda podem conter Decimal. Normalizar antes de gravar evita um cursor
    # apontando para um snapshot que o SQLite não conseguiria serializar.
    snapshot_dados = json.loads(json.dumps(list(result.get("dados", [])), ensure_ascii=False, default=str))
    snapshot_result = json.loads(
        json.dumps(
            {key: value for key, value in result.items() if key not in {"dados", "paginacao"}},
            ensure_ascii=False,
            default=str,
        )
    )
    snapshot = await asyncio.to_thread(
        salvar_snapshot_consulta,
        fingerprint=fingerprint,
        dados=snapshot_dados,
        resultado=snapshot_result,
    )
    return _paginate_snapshot(snapshot, offset=0, tamanho_resultado=tamanho_resultado)


async def _read_snapshot_page(
    *,
    cursor: str,
    fingerprint: str,
    tamanho_resultado: int,
) -> dict[str, Any]:
    snapshot_id, offset, _ = _decode_snapshot_cursor(
        cursor,
        fingerprint=fingerprint,
        tamanho_resultado=tamanho_resultado,
    )
    snapshot = await asyncio.to_thread(obter_snapshot_consulta, snapshot_id)
    if snapshot is None:
        raise PaginationSnapshotExpiredError("A consulta anterior expirou; reinicie a busca.")
    if snapshot.fingerprint != fingerprint:
        raise PaginationCursorError("cursor de paginação inválido")
    return _paginate_snapshot(snapshot, offset=offset, tamanho_resultado=tamanho_resultado)


def _paginate_result(
    result: dict[str, Any],
    *,
    cursor: str | None,
    tamanho_resultado: int,
    fingerprint: str,
) -> dict[str, Any]:
    offset = _decode_page_cursor(cursor, fingerprint) if cursor else 0
    loaded_items = list(result.get("dados", []))
    current_items = loaded_items[offset : offset + tamanho_resultado]
    next_offset = offset + len(current_items)
    has_more = next_offset < len(loaded_items)
    pagination = PaginacaoOut(
        tamanho=tamanho_resultado,
        total_carregado=len(loaded_items),
        tem_mais=has_more,
        proximo_cursor=_encode_page_cursor(next_offset, fingerprint) if has_more else None,
    ).model_dump()
    # O cursor de primeira geração continua usado apenas quando uma página
    # única não precisa de snapshot; mantenha o contrato histórico enxuto.
    pagination.pop("anterior_disponivel", None)
    paginated = {
        **result,
        "dados": current_items,
        "paginacao": pagination,
    }
    return paginated


async def search_licitacoes_construction(
    data_inicial: str,
    data_final: str,
    modalidade: int = 0,
    tamanho_pagina: int = 50,
    max_paginas: int = 10,
    uf: str | None = None,
    cursor: str | None = None,
    tamanho_resultado: int = 15,
    termo: str | None = None,
    termos_inclusao: list[str] | None = None,
    termos_exclusao: list[str] | None = None,
    escopo_busca: str = "objeto_itens",
    modo_inclusao: str = "qualquer",
    ordenacao: str = "data_desc",
    incluir_pavimentacao: bool = True,
    force_mock: bool = False,
    forcar_atualizacao: bool = False,
) -> dict[str, Any]:
    data_inicial = _validate_date(data_inicial, "data_inicial")
    data_final = _validate_date(data_final, "data_final")
    if data_inicial > data_final:
        raise ValueError("data_inicial não pode ser maior que data_final")
    modalidade = validar_modalidade(modalidade)
    if not PNCP_MIN_PAGE_SIZE <= tamanho_pagina <= PNCP_MAX_PAGE_SIZE:
        raise ValueError(
            f"tamanho_pagina deve estar entre {PNCP_MIN_PAGE_SIZE} e {PNCP_MAX_PAGE_SIZE}"
        )
    if not 1 <= max_paginas <= 100:
        raise ValueError("max_paginas deve estar entre 1 e 100")
    if not 1 <= tamanho_resultado <= 15:
        raise ValueError("tamanho_resultado deve estar entre 1 e 15")
    expressao_busca = parse_search_request(
        termo,
        termos_inclusao=termos_inclusao,
        termos_exclusao=termos_exclusao,
        escopo_busca=escopo_busca,
        modo_inclusao=modo_inclusao,
    )

    pagination_fingerprint = _pagination_fingerprint(
        data_inicial=data_inicial,
        data_final=data_final,
        modalidade=modalidade,
        tamanho_pagina=tamanho_pagina,
        max_paginas=max_paginas,
        uf=uf,
        tamanho_resultado=tamanho_resultado,
        termo=termo,
        termos_inclusao=[item.normalizado for item in expressao_busca.inclusoes],
        termos_exclusao=[item.normalizado for item in expressao_busca.exclusoes],
        escopo_busca=expressao_busca.escopo,
        modo_inclusao=expressao_busca.modo_inclusao,
        ordenacao=ordenacao,
        incluir_pavimentacao=incluir_pavimentacao,
    )

    if cursor:
        return await _read_snapshot_page(
            cursor=cursor,
            fingerprint=pagination_fingerprint,
            tamanho_resultado=tamanho_resultado,
        )

    async def paginate(result: dict[str, Any]) -> dict[str, Any]:
        dados_ordenados, resumo = _ordenar_e_resumir_consulta(
            list(result.get("dados", [])),
            termo=termo,
            ordenacao=ordenacao,
            incluir_pavimentacao=incluir_pavimentacao,
            expressao_busca=expressao_busca,
        )
        prepared = dict(result)
        prepared["dados"] = dados_ordenados
        prepared["total_encontradas"] = len(dados_ordenados)
        prepared["metadados"] = {**dict(result.get("metadados") or {}), **resumo}
        return await _snapshot_and_paginate(
            prepared,
            fingerprint=pagination_fingerprint,
            tamanho_resultado=tamanho_resultado,
        )

    if not forcar_atualizacao and not force_mock:
        resultado_local = await _resultado_local_disponivel(
            data_inicial=data_inicial,
            data_final=data_final,
            modalidade=modalidade,
            uf=uf,
        )
        if resultado_local is not None:
            return await paginate(resultado_local)

    _PNCP_METRICS["buscas_solicitadas"] += 1

    if force_mock:
        dados = processar_itens_raw(get_mock_licitacoes(), data_inicial, data_final, modalidade, uf)
        return await paginate(
            await _result_async(
                status="sucesso_mock",
                mensagem="Modo de teste: exibindo dados fictícios de desenvolvimento.",
                dados=dados,
                metadados=ExecucaoBusca(origem="mock"),
            )
        )

    cache_key = f"{data_inicial}:{data_final}:{modalidade}:{tamanho_pagina}:{max_paginas}:{uf or 'TODOS'}"
    if not _PNCP_CIRCUIT.allow_request():
        _PNCP_METRICS["buscas_circuito_aberto"] += 1
        logger.info("Circuit breaker do PNCP aberto; usando dados locais")
        return await paginate(
            await _fallback_cache_or_local(
                cache_key=cache_key,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                uf=uf,
                mensagem="O PNCP está temporariamente indisponível; exibindo dados locais.",
            )
        )

    headers = {
        "User-Agent": "licitacoes-obras/1.0",
        "Accept": "application/json",
    }
    search_timeout = _search_timeout_seconds(modalidade, max_paginas)
    started_at = time.monotonic()
    try:
        client = await obter_cliente_pncp()
        raw_items, metadata = await asyncio.wait_for(
            _execute_search(
                client,
                PNCP_URL,
                headers,
                data_inicial,
                data_final,
                modalidade,
                tamanho_pagina,
                max_paginas,
                uf,
            ),
            timeout=search_timeout,
        )
    except asyncio.TimeoutError:
        _PNCP_METRICS["buscas_timeout"] += 1
        response_time = time.monotonic() - started_at
        _PNCP_CIRCUIT.record_failure(response_time=response_time)
        logger.warning("Busca no PNCP excedeu o limite total de tempo (%.2fs)", response_time)
        return await paginate(
            await _fallback_cache_or_local(
                cache_key=cache_key,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                uf=uf,
                mensagem=_timeout_message_for(search_timeout),
                paginas_com_erro=1,
            )
        )
    except (httpx.TimeoutException, httpx.ConnectError, PNCPConnectionError, PNCPResponseError) as exc:
        _PNCP_METRICS["buscas_falha_remota"] += 1
        response_time = time.monotonic() - started_at
        _PNCP_CIRCUIT.record_failure(response_time=response_time)
        logger.error("PNCP indisponível após %.2fs: %s", response_time, exc, exc_info=True)
        return await paginate(
            await _fallback_cache_or_local(
                cache_key=cache_key,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                uf=uf,
                mensagem="O PNCP está temporariamente indisponível.",
            )
        )

    if metadata.paginas_com_erro:
        _PNCP_METRICS["buscas_parciais_com_erro"] += 1
        response_time = time.monotonic() - started_at
        _PNCP_CIRCUIT.record_failure(response_time=response_time)
        return await paginate(
            await _fallback_cache_or_local(
                cache_key=cache_key,
                modalidade=modalidade,
                data_inicial=data_inicial,
                data_final=data_final,
                uf=uf,
                mensagem="A consulta ao PNCP falhou; exibindo o último resultado local disponível.",
                paginas_consultadas=metadata.paginas_consultadas,
                paginas_com_erro=metadata.paginas_com_erro,
            )
        )

    pncp_response_time = time.monotonic() - started_at
    _PNCP_CIRCUIT.record_success(response_time=pncp_response_time)
    _PNCP_METRICS["buscas_sucesso_remoto"] += 1
    logger.info("Resposta do PNCP recebida em %.2fs", pncp_response_time)

    dados = processar_itens_raw(raw_items, data_inicial, data_final, modalidade, uf)
    if dados:
        try:
            await asyncio.to_thread(_persistir_obras_consulta, dados)
        except (ValueError, RuntimeError) as exc:
            logger.error("Falha de persistência após consulta PNCP: %s", exc, exc_info=True)

    status = "sucesso_parcial" if metadata.parcial else "sucesso_real"
    if metadata.parcial and metadata.paginas_com_erro:
        mensagem = "Resultado parcial: parte das páginas do PNCP não pôde ser consultada."
    elif metadata.parcial:
        mensagem = "Resultado parcial: o limite de páginas da consulta foi atingido."
    else:
        mensagem = "Consulta realizada com sucesso no PNCP."
    if not dados:
        status = "sucesso_vazio"
        mensagem = "Nenhuma licitação de obras encontrada para os filtros selecionados."

    result = await _result_async(status=status, mensagem=mensagem, dados=dados, metadados=metadata)
    _CACHE[cache_key] = result
    total_response_time = time.monotonic() - started_at
    logger.info(
        "Resultado pronto para o frontend em %.2fs (PNCP: %.2fs; registros: %s)",
        total_response_time,
        pncp_response_time,
        len(dados),
    )
    return await paginate(result)


async def stream_licitacoes_construction(
    data_inicial: str,
    data_final: str,
    modalidade: int = 0,
    tamanho_pagina: int = 50,
    max_paginas: int = 1,
    uf: str | None = None,
    termo: str | None = None,
    termos_inclusao: list[str] | None = None,
    termos_exclusao: list[str] | None = None,
    escopo_busca: str = "objeto_itens",
    modo_inclusao: str = "qualquer",
    ordenacao: str = "data_desc",
    incluir_pavimentacao: bool = True,
    forcar_atualizacao: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Produz resultados incrementais sem esperar o término de toda a consulta.

    A rota JSON continua disponível para consumidores que precisam do snapshot
    paginado. Esta variante é destinada à tela: a cada página recebida do
    PNCP, devolve o conjunto já filtrado para que os cards possam aparecer.
    """

    data_inicial = _validate_date(data_inicial, "data_inicial")
    data_final = _validate_date(data_final, "data_final")
    if data_inicial > data_final:
        raise ValueError("data_inicial não pode ser maior que data_final")
    modalidade = validar_modalidade(modalidade)
    if not PNCP_MIN_PAGE_SIZE <= tamanho_pagina <= PNCP_MAX_PAGE_SIZE:
        raise ValueError(
            f"tamanho_pagina deve estar entre {PNCP_MIN_PAGE_SIZE} e {PNCP_MAX_PAGE_SIZE}"
        )
    if not 1 <= max_paginas <= 100:
        raise ValueError("max_paginas deve estar entre 1 e 100")
    expressao_busca = parse_search_request(
        termo,
        termos_inclusao=termos_inclusao,
        termos_exclusao=termos_exclusao,
        escopo_busca=escopo_busca,
        modo_inclusao=modo_inclusao,
    )

    if not forcar_atualizacao:
        resultado_local = await _resultado_local_disponivel(
            data_inicial=data_inicial,
            data_final=data_final,
            modalidade=modalidade,
            uf=uf,
        )
        if resultado_local is not None:
            dados, resumo = _ordenar_e_resumir_consulta(
                list(resultado_local.get("dados") or []),
                termo=termo,
                ordenacao=ordenacao,
                incluir_pavimentacao=incluir_pavimentacao,
                expressao_busca=expressao_busca,
            )
            resultado_local["dados"] = dados
            resultado_local["total_encontradas"] = len(dados)
            resultado_local["metadados"] = {**dict(resultado_local.get("metadados") or {}), **resumo}
            yield {"tipo": "concluido", **resultado_local}
            return

    cache_key = f"{data_inicial}:{data_final}:{modalidade}:{tamanho_pagina}:{max_paginas}:{uf or 'TODOS'}"

    async def fallback_event(mensagem: str, paginas: int, erros: int) -> dict[str, Any]:
        fallback = await _fallback_cache_or_local(
            cache_key=cache_key,
            modalidade=modalidade,
            data_inicial=data_inicial,
            data_final=data_final,
            uf=uf,
            mensagem=mensagem,
            paginas_consultadas=paginas,
            paginas_com_erro=erros,
        )
        dados, resumo = _ordenar_e_resumir_consulta(
            list(fallback.get("dados") or []),
            termo=termo,
            ordenacao=ordenacao,
            incluir_pavimentacao=incluir_pavimentacao,
            expressao_busca=expressao_busca,
        )
        fallback["dados"] = dados
        fallback["total_encontradas"] = len(dados)
        fallback["metadados"] = {**dict(fallback.get("metadados") or {}), **resumo}
        return {"tipo": "concluido", **fallback}

    _PNCP_METRICS["buscas_solicitadas"] += 1
    if not _PNCP_CIRCUIT.allow_request():
        _PNCP_METRICS["buscas_circuito_aberto"] += 1
        yield await fallback_event("O PNCP está temporariamente indisponível; exibindo dados locais.", 0, 0)
        return

    modalidades = MODALIDADES_PADRAO_TODAS if modalidade == 0 else [modalidade]
    semaphore = obter_limitador_paginas_pncp()
    headers = {"User-Agent": "licitacoes-obras/1.0", "Accept": "application/json"}
    raw_items: list[dict[str, Any]] = []
    raw_index_by_id: dict[str, int] = {}
    paginas_consultadas = 0
    paginas_com_erro = 0
    parcial = False
    parar_por_rate_limit = False
    started_at = time.monotonic()

    def append_unique_items(items: list[dict[str, Any]]) -> None:
        for item in items:
            item_id = _raw_pncp_identifier(item)
            previous_index = raw_index_by_id.get(item_id)
            if previous_index is None:
                raw_index_by_id[item_id] = len(raw_items)
                raw_items.append(item)
            else:
                raw_items[previous_index] = _merge_duplicate_pncp_item(
                    raw_items[previous_index], item
                )

    def current_payload(*, final: bool) -> dict[str, Any]:
        dados = processar_itens_raw(raw_items, data_inicial, data_final, modalidade, uf)
        ordered, resumo = _ordenar_e_resumir_consulta(
            dados,
            termo=termo,
            ordenacao=ordenacao,
            incluir_pavimentacao=incluir_pavimentacao,
            expressao_busca=expressao_busca,
        )
        metadata = ExecucaoBusca(
            parcial=parcial if final else False,
            paginas_consultadas=paginas_consultadas,
            paginas_com_erro=paginas_com_erro,
            origem="PNCP",
        ).model_dump(mode="json")
        metadata.update(resumo)
        if final:
            if paginas_com_erro:
                status = "sucesso_parcial"
                mensagem = "Resultado parcial: parte das páginas do PNCP não pôde ser consultada."
            elif parcial:
                status = "sucesso_parcial"
                mensagem = "Resultado parcial: o limite de páginas da consulta foi atingido."
            elif ordered:
                status = "sucesso_real"
                mensagem = "Consulta realizada com sucesso no PNCP."
            else:
                status = "sucesso_vazio"
                mensagem = "Nenhuma licitação de obras encontrada para os filtros selecionados."
            return {
                "tipo": "concluido",
                "status": status,
                "mensagem": mensagem,
                "total_encontradas": len(ordered),
                "dados": ordered,
                "metadados": metadata,
            }
        return {
            "tipo": "progresso",
            "status": "carregando",
            "mensagem": f"Carregadas {paginas_consultadas} página(s) do PNCP.",
            "total_encontradas": len(ordered),
            "dados": ordered,
            "metadados": metadata,
        }

    try:
        client = await obter_cliente_pncp()
        for current_mode in modalidades:
            collected_for_mode = 0
            total_for_mode: int | None = None
            for page in range(1, max_paginas + 1):
                params: dict[str, Any] = {
                    "dataInicial": data_inicial,
                    "dataFinal": data_final,
                    "codigoModalidadeContratacao": current_mode,
                    "pagina": page,
                    "tamanhoPagina": tamanho_pagina,
                }
                if uf and uf != "TODOS":
                    params["uf"] = uf
                result = await fetch_pagina(
                    client,
                    semaphore,
                    PNCP_URL,
                    params,
                    headers,
                    pace_requests=True,
                )
                paginas_consultadas += 1
                if result.error:
                    paginas_com_erro += 1
                    parcial = True
                    parar_por_rate_limit = result.rate_limited
                    break
                total_for_mode = result.total_registros if result.total_registros is not None else total_for_mode
                collected_for_mode += len(result.items)
                append_unique_items(result.items)
                yield current_payload(final=False)
                if total_for_mode is not None and collected_for_mode >= total_for_mode:
                    break
                if total_for_mode is None and not result.items:
                    break
            if total_for_mode is not None and collected_for_mode < total_for_mode:
                parcial = True
            if parar_por_rate_limit:
                break
    except (httpx.TimeoutException, httpx.ConnectError, PNCPConnectionError, PNCPResponseError) as exc:
        _PNCP_METRICS["buscas_falha_remota"] += 1
        _PNCP_CIRCUIT.record_failure(response_time=time.monotonic() - started_at)
        logger.error("PNCP indisponível durante busca progressiva: %s", exc, exc_info=True)
        if not raw_items:
            yield await fallback_event("O PNCP está temporariamente indisponível.", paginas_consultadas, paginas_com_erro + 1)
            return
        paginas_com_erro += 1
        parcial = True

    if paginas_com_erro:
        _PNCP_METRICS["buscas_parciais_com_erro"] += 1
        _PNCP_CIRCUIT.record_failure(response_time=time.monotonic() - started_at)
        # fetch_pagina transforma falhas HTTP em PageFetchResult. Sem este
        # retorno explícito a rota SSE concluía com uma lista parcial, sem
        # consultar o cache ou o banco local, diferentemente da rota JSON.
        yield await fallback_event(
            "A consulta ao PNCP falhou; exibindo o último resultado local disponível.",
            paginas_consultadas,
            paginas_com_erro,
        )
        return

    _PNCP_CIRCUIT.record_success(response_time=time.monotonic() - started_at)
    _PNCP_METRICS["buscas_sucesso_remoto"] += 1

    dados = processar_itens_raw(raw_items, data_inicial, data_final, modalidade, uf)
    if dados:
        try:
            await asyncio.to_thread(_persistir_obras_consulta, dados)
        except (ValueError, RuntimeError) as exc:
            logger.error("Falha de persistência após busca progressiva: %s", exc, exc_info=True)

    # O fluxo SSE também precisa abastecer o cache. Caso o PNCP falhe na
    # próxima atualização, o fallback poderá retornar este snapshot completo,
    # ainda que a falha ocorra antes da primeira página nova.
    cache_status = "sucesso_parcial" if parcial else "sucesso_real"
    cache_message = "Resultado parcial: o limite de páginas da consulta foi atingido." if parcial else "Consulta realizada com sucesso no PNCP."
    if not dados:
        cache_status = "sucesso_vazio"
        cache_message = "Nenhuma licitação de obras encontrada para os filtros selecionados."
    cache_metadata = ExecucaoBusca(
        parcial=parcial,
        paginas_consultadas=paginas_consultadas,
        paginas_com_erro=paginas_com_erro,
        origem="PNCP",
    )
    _CACHE[cache_key] = await _result_async(
        status=cache_status,
        mensagem=cache_message,
        dados=dados,
        metadados=cache_metadata,
    )
    yield current_payload(final=True)
