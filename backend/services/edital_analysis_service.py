"""Regras determinísticas para localizar exigências de habilitação em editais."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from cachetools import TTLCache

from backend.config import settings
from backend.exceptions import PNCPConnectionError, PNCPResponseError
from backend.schemas import ResultadoExigencias
from backend.services.ocr_service import OpenAIVisionOcrService, TesseractOcrService, criar_servico_ocr
from backend.services.edital_analysis_repository import (
    obter_analise,
    obter_ultima_analise_com_atualizacao,
    salvar_analise,
)
from backend.services.pdf_download_service import (
    DownloadedDocument,
    DownloadedPdf,
    DownloadedZip,
    PdfDownloadError,
    baixar_pdf_pncp,
)
from backend.services.pdf_text_service import (
    PageText,
    PdfPageLimitError,
    PdfTextError,
    extrair_texto_pdf,
    renderizar_pagina_para_ocr,
)
from backend.services.pncp_service import buscar_documentos_pncp
from backend.services.semantic_summary_service import gerar_descricao_resumida
from backend.services.document_requirement_filter import (
    DocumentRequirementFilterResult,
    avaliar_candidato_documental,
    chave_requisito_documental,
    filtrar_exigencias_documentais,
)


logger = logging.getLogger(__name__)


class AnalysisCapacityError(RuntimeError):
    """A capacidade compartilhada de análise foi atingida."""

PRIORITY_TERMS = (
    (0, ("edital", "instrumento convocatorio")),
    (1, ("habilitacao", "qualificacao")),
    (2, ("anexo",)),
    (3, ("termo de referencia", "projeto basico")),
)
EXCLUDED_TERMS = (
    "proposta",
    "precificacao",
    "execucao contratual",
    "da contratada",
    "contratada devera",
    "garantia contratual",
    "medicao",
    "art/rrt",
    "declaracao do vencedor",
    "interpor recurso",
    "firmo a presente",
    "art ",
    "rrt ",
)
CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "habilitacao_juridica",
        "Documento de habilitação jurídica",
        ("contrato social", "ato constitutivo", "estatuto", "registro comercial", "inscricao no registro"),
    ),
    (
        "qualificacao_tecnica",
        "Comprovação de qualificação técnica",
        ("atestado", "capacidade tecnica", "acervo tecnico", "registro profissional", "crea", "cau"),
    ),
    (
        "regularidade_fiscal_social_trabalhista",
        "Comprovação de regularidade fiscal, social ou trabalhista",
        ("regularidade fiscal", "fgts", "cnd", "certidao negativa", "receita federal"),
    ),
    (
        "qualificacao_economico_financeira",
        "Comprovação de qualificação econômico-financeira",
        ("balanco patrimonial", "patrimonio liquido", "indice de liquidez", "indices de liquidez"),
    ),
    ("declaracoes", "Declaração exigida", ("declaracao", "declaracoes")),
)

# Documento concreto pedido no trecho: (família, chave, nome, descrição, alternativas).
# Cada alternativa é um grupo de termos que precisam aparecer juntos. Dentro de
# uma família vale o primeiro que casar, então os mais específicos vêm antes.
# Descrição None usa o resumo semântico existente.
_Tipo = tuple[str, str, str, str | None, tuple[tuple[str, ...], ...]]
DOCUMENT_TYPES: dict[str, tuple[_Tipo, ...]] = {
    "habilitacao_juridica": (
        ("constituicao", "contrato_social", "Ato constitutivo, estatuto ou contrato social",
         "Contrato social ou estatuto em vigor, com as alterações ou a consolidação, registrado no órgão competente.",
         (("contrato social",), ("ato constitutivo",), ("estatuto",))),
        ("constituicao", "registro_comercial", "Registro comercial",
         "Inscrição do empresário individual ou da empresa na Junta Comercial.",
         (("registro comercial",), ("junta comercial",), ("inscricao no registro",))),
    ),
    "qualificacao_tecnica": (
        ("acervo", "certidao_acervo_tecnico", "Certidão de Acervo Técnico (CAT)",
         "CAT emitida pelo CREA/CAU em nome do responsável técnico, comprovando a execução de serviço similar.",
         (("acervo tecnico",), ("cat",))),
        ("atestado", "atestado_tecnico_profissional", "Atestado de capacidade técnico-profissional",
         "Atestado em nome do responsável técnico, comprovando que ele já executou serviço similar ao objeto.",
         (("atestado", "profissional"), ("capacidade tecnico profissional",), ("tecnico-profissional",))),
        ("atestado", "atestado_tecnico_operacional", "Atestado de capacidade técnico-operacional",
         "Atestado em nome da empresa, comprovando que ela já executou serviço similar ao objeto.",
         (("atestado", "operacional"), ("capacidade tecnico operacional",), ("tecnico-operacional",))),
        ("atestado", "atestado_capacidade_tecnica", "Atestado de capacidade técnica",
         "Atestado emitido por pessoa jurídica de direito público ou privado, comprovando a execução anterior "
         "de serviço com características similares ao objeto.",
         (("atestado",), ("capacidade tecnica",))),
        ("registro", "registro_profissional", "Registro no CREA/CAU",
         "Certidão de registro da empresa e/ou do responsável técnico no conselho profissional (CREA ou CAU).",
         (("crea",), ("cau",), ("registro profissional",), ("conselho regional",))),
        ("vinculo", "vinculo_responsavel_tecnico", "Comprovação de vínculo do responsável técnico",
         "Carteira de trabalho, contrato social, contrato de prestação de serviço ou declaração de compromisso "
         "que ligue o responsável técnico à empresa.",
         (("vinculo",), ("vinculacao",), ("quadro permanente",))),
    ),
    "regularidade_fiscal_social_trabalhista": (
        ("federal", "regularidade_federal", "Certidão de regularidade com a Fazenda Federal",
         "Certidão conjunta da Receita Federal e da PGFN (tributos federais e dívida ativa da União).",
         (("receita federal",), ("fazenda federal",), ("divida ativa da uniao",), ("tributos federais",), ("pgfn",))),
        ("estadual", "regularidade_estadual", "Certidão de regularidade com a Fazenda Estadual",
         "Certidão negativa de débitos estaduais emitida pela Secretaria da Fazenda do estado da sede da empresa.",
         (("fazenda estadual",), ("fazenda publica estadual",), ("tributos estaduais",), ("debitos estaduais",))),
        ("municipal", "regularidade_municipal", "Certidão de regularidade com a Fazenda Municipal",
         "Certidão negativa de débitos municipais emitida pela prefeitura da sede da empresa.",
         (("fazenda municipal",), ("fazenda publica municipal",), ("tributos municipais",), ("debitos municipais",))),
        ("fgts", "regularidade_fgts", "Certificado de Regularidade do FGTS (CRF)",
         "Certificado de regularidade com o FGTS emitido pela Caixa Econômica Federal.",
         (("fgts",),)),
        ("trabalhista", "regularidade_trabalhista", "Certidão Negativa de Débitos Trabalhistas (CNDT)",
         "Certidão emitida pela Justiça do Trabalho comprovando a inexistência de débitos trabalhistas.",
         (("debitos trabalhistas",), ("cndt",), ("justica do trabalho",), ("regularidade trabalhista",))),
        ("fiscal", "regularidade_fiscal", "Certidão de regularidade fiscal", None,
         (("regularidade fiscal",), ("certidao negativa",), ("cnd",))),
    ),
    "qualificacao_economico_financeira": (
        ("balanco", "balanco_patrimonial", "Balanço patrimonial e demonstrações contábeis",
         "Balanço patrimonial e demonstrações contábeis do último exercício social, na forma da lei.",
         (("balanco patrimonial",), ("demonstracoes contabeis",))),
        ("falencia", "certidao_falencia", "Certidão negativa de falência e recuperação judicial",
         "Certidão emitida pelo distribuidor judicial da sede da empresa.",
         (("falencia",), ("recuperacao judicial",))),
        ("indices", "indices_liquidez", "Comprovação dos índices de liquidez",
         "Índices como Liquidez Geral, Liquidez Corrente e Solvência Geral, calculados a partir do balanço.",
         (("indice de liquidez",), ("indices de liquidez",), ("liquidez geral",), ("liquidez corrente",))),
        ("patrimonio", "patrimonio_liquido", "Comprovação de patrimônio líquido ou capital mínimo",
         "Patrimônio líquido ou capital social mínimo exigido no edital, comprovado pelo balanço.",
         (("patrimonio liquido",), ("capital social minimo",), ("capital minimo",))),
    ),
    "declaracoes": (
        ("declaracao", "declaracao_menor", "Declaração de não emprego de menor",
         "Declaração de que a empresa não emprega menor de 18 anos em trabalho noturno, perigoso ou insalubre, "
         "nem menor de 16, salvo aprendiz.",
         (("menor",), ("menores",), ("xxxiii",))),
        ("declaracao", "declaracao_trabalho_degradante", "Declaração de inexistência de trabalho degradante ou forçado",
         None, (("degradante",), ("trabalho forcado",), ("analoga a de escravo",))),
        ("declaracao", "declaracao_reserva_cargos", "Declaração de reserva de cargos (PcD e reabilitados)",
         "Declaração de cumprimento da reserva de cargos para pessoas com deficiência e reabilitados da Previdência.",
         (("reserva de cargos",), ("pessoa com deficiencia",), ("pessoas com deficiencia",), ("reabilitado",))),
        ("declaracao", "declaracao_me_epp", "Declaração de enquadramento como ME/EPP",
         "Declaração de que a empresa se enquadra como microempresa ou empresa de pequeno porte.",
         (("microempresa",), ("pequeno porte",), ("epp",), ("regime diferenciado",), ("enquadramento",))),
        ("declaracao", "declaracao_cumprimento_habilitacao", "Declaração de cumprimento dos requisitos de habilitação",
         None, (("requisitos de habilitacao",), ("cumpre plenamente",))),
        ("declaracao", "declaracao_vistoria", "Declaração de vistoria técnica ou de conhecimento do local",
         "Declaração de que a empresa visitou o local da obra ou conhece plenamente as condições locais.",
         (("vistoria",), ("conhecimento do local",), ("condicoes locais",))),
        ("declaracao", "declaracao_equipamentos_pessoal", "Declaração de disponibilidade de equipamentos e pessoal técnico",
         "Declaração de que a empresa dispõe dos equipamentos e da equipe técnica necessários à execução.",
         (("disponibilidade de equipamentos",), ("equipamentos", "pessoal tecnico"))),
        ("declaracao", "declaracao_execucao_projetos", "Declaração de execução conforme projetos e especificações",
         "Declaração de que a obra será executada conforme os projetos e especificações do contratante.",
         (("executar a obra", "projetos"),)),
        ("declaracao", "declaracao_conformidade", "Declaração geral de conformidade e responsabilidade", None,
         (("conformidade e responsabilidade",),)),
        ("declaracao", "declaracao_veracidade", "Declaração de veracidade das informações", None,
         (("veracidade",), ("declaracao falsa",), ("documentacao falsa",))),
        ("declaracao", "declaracao_inidoneidade", "Declaração de idoneidade", None, (("inidoneidade",), ("inidonea",))),
        ("declaracao", "declaracao_impedimento", "Declaração de inexistência de impedimento", None,
         (("impedimento",), ("fato impeditivo",))),
    ),
}


def _identificar_documentos(category: str, normalized: str) -> list[tuple[str, str, str | None]]:
    """Devolve (chave, nome, descrição) dos documentos concretos citados no trecho."""

    found: list[tuple[str, str, str | None]] = []
    families: set[str] = set()
    for family, key, name, description, alternatives in DOCUMENT_TYPES.get(category, ()):
        if family in families:
            continue
        if any(all(re.search(rf"\b{re.escape(term)}\b", normalized) for term in group) for group in alternatives):
            families.add(family)
            found.append((key, name, description))
    return found


@dataclass(frozen=True)
class SelectedDocument:
    documento_id: int
    titulo: str
    url: str | None
    prioridade: int | None
    selecionado: bool


@dataclass(frozen=True)
class _DownloadedDocument:
    document: SelectedDocument
    arquivo: DownloadedDocument | None
    error: str | None = None

    @property
    def pdfs(self) -> tuple[DownloadedPdf, ...]:
        if self.arquivo is None:
            return ()
        if isinstance(self.arquivo, DownloadedZip):
            return self.arquivo.pdfs
        return (self.arquivo,)


def normalizar_texto(texto: str) -> str:
    normalized = unicodedata.normalize("NFD", texto or "")
    without_accents = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _document_dict(document: Any) -> dict[str, Any]:
    return document.model_dump() if hasattr(document, "model_dump") else dict(document)


def selecionar_documentos_para_analise(documentos: list[Any]) -> list[SelectedDocument]:
    """Prioriza edital/anexos e explicita, em vez de ocultar, o que ficou fora."""
    selected: list[SelectedDocument] = []
    for raw_document in documentos:
        document = _document_dict(raw_document)
        try:
            document_id = int(document.get("sequencial_documento"))
        except (TypeError, ValueError):
            continue
        title = str(document.get("titulo") or document.get("tipo_documento_nome") or f"Documento {document_id}")
        index_text = normalizar_texto(f"{document.get('tipo_documento_nome') or ''} {title}")
        priority = next(
            (candidate_priority for candidate_priority, terms in PRIORITY_TERMS if any(term in index_text for term in terms)),
            None,
        )
        selected.append(
            SelectedDocument(
                documento_id=document_id,
                titulo=title,
                url=str(document.get("url")).strip() if document.get("url") else None,
                prioridade=priority,
                selecionado=priority is not None and priority < 3,
            )
        )
    return sorted(
        selected,
        key=lambda item: (
            not item.selecionado,
            item.prioridade if item.prioridade is not None else 99,
            item.documento_id,
        ),
    )


def _sentence_around(texto: str, start: int) -> str:
    left = max(texto.rfind("\n", 0, start), texto.rfind(".", 0, start), texto.rfind(";", 0, start)) + 1
    right_candidates = [
        position
        for position in (texto.find("\n", start), texto.find(".", start), texto.find(";", start))
        if position != -1
    ]
    right = min(right_candidates) + 1 if right_candidates else len(texto)
    return re.sub(r"\s+", " ", texto[left:right]).strip()[:600]


def _source_segments(texto: str) -> list[str]:
    """Separa trechos no texto original, sem aplicar índices normalizados.

    Pontos usados em numeração (por exemplo, ``8.4.1``) não são fronteiras.
    Uma quebra que apenas continua a frase também permanece no mesmo trecho.
    """

    boundary = re.compile(
        r"(?<=[;!?])\s+|(?<=\.)\s+(?=(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]|\d+(?:\.\d+)*[.)]))|"
        r"\n(?=\s*(?:[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ].*?\b(?:licitante|apresent|dever|comprov)))"
    )
    return [segment.strip()[:600] for segment in boundary.split(texto) if segment.strip()]


def _is_out_of_scope(normalized_evidence: str) -> bool:
    if any(term in normalized_evidence for term in EXCLUDED_TERMS):
        return True
    if "administracao" in normalized_evidence and not any(
        subject in normalized_evidence for subject in ("licitante", "empresa", "participante")
    ):
        return True
    return False


def _source_confidence(origem: str, ocr_confidence: float | None) -> float:
    if origem == "pdf_texto":
        return 0.85
    return ocr_confidence if ocr_confidence is not None else 0.60


def _localizar_exigencias_candidatas(
    *,
    documento: SelectedDocument,
    paginas: list[tuple[PageText, str, float | None]],
) -> list[dict[str, Any]]:
    """Extrai somente trechos textuais com categoria e página verificáveis."""
    entries: list[dict[str, Any]] = []
    deduplicated: set[tuple[str, str]] = set()
    for page, origem, ocr_confidence in paginas:
        original = page.texto
        if not original:
            continue
        for evidence in _source_segments(original):
            normalized_evidence = normalizar_texto(evidence)
            if not normalized_evidence or _is_out_of_scope(normalized_evidence):
                continue
            for category, label, keywords in CATEGORY_RULES:
                if not any(
                    re.search(rf"\b{re.escape(keyword)}\b", normalized_evidence) for keyword in keywords
                ) and not _identificar_documentos(category, normalized_evidence):
                    continue
                decision = avaliar_candidato_documental(evidence, category)
                if not decision.aceito:
                    continue
                # Sem documento concreto reconhecido, mantém o rótulo da categoria
                # e a chave textual, para não fundir exigências diferentes.
                documents = _identificar_documentos(category, normalized_evidence) or [
                    (chave_requisito_documental(category, evidence), label, None)
                ]
                for concept, name, description in documents:
                    key = (category, concept)
                    if key in deduplicated:
                        continue
                    deduplicated.add(key)
                    referenced = any(term in normalized_evidence for term in ("anexo", "conforme item", "conforme modelo"))
                    confidence = min(_source_confidence(origem, ocr_confidence), decision.confianca)
                    if referenced:
                        confidence = min(confidence, 0.65)
                    entries.append(
                        {
                            "chave_documental": concept,
                            "categoria": category,
                            "rotulo": name,
                            "descricao_resumida": description or gerar_descricao_resumida(category, evidence),
                            "filtro_documental": "aceito",
                            "descricao_original": evidence,
                            "documento_id": documento.documento_id,
                            "titulo_documento": documento.titulo,
                            "url_documento": documento.url,
                            "pagina": page.pagina,
                            "evidencia": evidence,
                            "confianca": round(confidence, 2),
                            "origem_texto": origem,
                            "status": "referenciado_em_outro_documento" if referenced else "identificado_no_edital",
                        }
                    )
    return entries


def localizar_exigencias_com_metricas(
    *,
    documento: SelectedDocument,
    paginas: list[tuple[PageText, str, float | None]],
) -> DocumentRequirementFilterResult:
    """Localiza e filtra exigências, preservando o motivo das rejeições."""

    candidatas = _localizar_exigencias_candidatas(documento=documento, paginas=paginas)
    return filtrar_exigencias_documentais(candidatas)


def localizar_exigencias(
    *,
    documento: SelectedDocument,
    paginas: list[tuple[PageText, str, float | None]],
) -> list[dict[str, Any]]:
    """Extrai somente documentos exigidos, com evidência rastreável."""

    return localizar_exigencias_com_metricas(documento=documento, paginas=paginas).exigencias


class EditalAnalysisService:
    """Orquestra download, texto/OCR, regras e cache por hash de documento."""

    def __init__(
        self,
        *,
        downloader: Callable[[str], Awaitable[DownloadedDocument]] = baixar_pdf_pncp,
        ocr_service: TesseractOcrService | OpenAIVisionOcrService | None = None,
    ) -> None:
        self.downloader = downloader
        self.ocr_service = ocr_service or criar_servico_ocr()
        self.cache: TTLCache[str, ResultadoExigencias] = TTLCache(
            maxsize=settings.edital_analysis_cache_maxsize,
            ttl=settings.edital_analysis_cache_ttl_seconds,
        )
        self._inflight: dict[str, asyncio.Task[ResultadoExigencias]] = {}
        self._inflight_forced: dict[str, bool] = {}
        self._inflight_guard = asyncio.Lock()
        self._analysis_slots = asyncio.Semaphore(settings.edital_analysis_concurrency)
        self._queued_analyses = 0
        self.metrics: Counter[str] = Counter()

    async def analisar_contratacao(
        self,
        cnpj: str,
        ano: int,
        sequencial: int,
        *,
        forcar: bool = False,
    ) -> ResultadoExigencias:
        contratacao_key = f"{cnpj}:{ano}:{sequencial}"
        try:
            documents_result = await buscar_documentos_pncp(cnpj, ano, sequencial)
        except (PNCPConnectionError, PNCPResponseError):
            persisted = await self._obter_analise_persistida_desatualizada(contratacao_key)
            if persisted is not None:
                return persisted
            raise

        if documents_result.get("desatualizado"):
            persisted = await self._obter_analise_persistida_desatualizada(contratacao_key)
            if persisted is not None:
                return persisted
        return await self.analisar_documentos(
            documents_result.get("documentos", []),
            contratacao_key=contratacao_key,
            forcar=forcar,
        )

    async def _obter_analise_persistida_desatualizada(
        self,
        contratacao_key: str,
    ) -> ResultadoExigencias | None:
        persisted = await asyncio.to_thread(
            obter_ultima_analise_com_atualizacao,
            contratacao_key,
            settings.edital_analyzer_version,
        )
        if persisted is None:
            return None
        return persisted.resultado.model_copy(
            update={
                "origem": "cache_persistente",
                "desatualizado": True,
                "atualizado_em": persisted.updated_at.isoformat(),
                "mensagem": "Exibindo a última análise conhecida; o PNCP está indisponível no momento.",
            }
        )

    async def analisar_documentos(
        self,
        documentos: list[Any],
        *,
        contratacao_key: str,
        forcar: bool = False,
    ) -> ResultadoExigencias:
        async with self._inflight_guard:
            task = self._inflight.get(contratacao_key)
            if task is not None and task.done():
                self._inflight.pop(contratacao_key, None)
                self._inflight_forced.pop(contratacao_key, None)
                task = None
            if task is not None and forcar and not self._inflight_forced.get(contratacao_key, False):
                # A análise normal termina antes do reprocessamento; a tarefa
                # forçada é compartilhada, mas nunca devolve o resultado antigo.
                task = self._create_analysis_task(
                    contratacao_key,
                    self._rerun_after(task, documentos, contratacao_key),
                    forced=True,
                )
            elif task is None:
                task = self._create_analysis_task(
                    contratacao_key,
                    self._run_with_capacity(documentos, contratacao_key, forcar=forcar),
                    forced=forcar,
                )
        return await asyncio.shield(task)

    def _create_analysis_task(
        self,
        contratacao_key: str,
        coroutine: Awaitable[ResultadoExigencias],
        *,
        forced: bool,
    ) -> asyncio.Task[ResultadoExigencias]:
        capacity = settings.edital_analysis_concurrency + settings.edital_analysis_queue_maxsize
        if self._queued_analyses >= capacity:
            self.metrics["capacity_rejections"] += 1
            raise AnalysisCapacityError("A fila de análises está cheia; tente novamente em instantes.")
        self._queued_analyses += 1
        task = asyncio.create_task(coroutine)
        self._inflight[contratacao_key] = task
        self._inflight_forced[contratacao_key] = forced
        task.add_done_callback(
            lambda completed: asyncio.create_task(self._clear_completed_task(contratacao_key, completed))
        )
        return task

    async def _clear_completed_task(
        self,
        contratacao_key: str,
        task: asyncio.Task[ResultadoExigencias],
    ) -> None:
        try:
            if not task.cancelled():
                task.exception()
        except (asyncio.CancelledError, Exception):
            # Consumir a exceção evita aviso de tarefa abandonada; o solicitante
            # que aguardou a mesma tarefa ainda recebe a exceção normalmente.
            pass
        async with self._inflight_guard:
            if self._inflight.get(contratacao_key) is task:
                self._inflight.pop(contratacao_key, None)
                self._inflight_forced.pop(contratacao_key, None)

    async def _rerun_after(
        self,
        previous: asyncio.Task[ResultadoExigencias],
        documentos: list[Any],
        contratacao_key: str,
    ) -> ResultadoExigencias:
        try:
            await asyncio.shield(previous)
        except Exception:
            # Uma falha anterior não impede a tentativa explicitamente forçada.
            pass
        return await self._run_with_capacity(documentos, contratacao_key, forcar=True)

    async def _run_with_capacity(
        self,
        documentos: list[Any],
        contratacao_key: str,
        *,
        forcar: bool,
    ) -> ResultadoExigencias:
        try:
            async with self._analysis_slots:
                self.metrics["active_analyses"] += 1
                self.metrics["active_analyses_peak"] = max(
                    self.metrics["active_analyses_peak"], self.metrics["active_analyses"]
                )
                try:
                    return await self._analisar_documentos_locked(documentos, contratacao_key, forcar=forcar)
                finally:
                    self.metrics["active_analyses"] -= 1
        finally:
            self._queued_analyses -= 1

    async def _download_document(self, document: SelectedDocument) -> _DownloadedDocument:
        if not document.url:
            return _DownloadedDocument(document, None, "O documento não possui link público para análise.")
        try:
            return _DownloadedDocument(document, await self.downloader(document.url))
        except PdfDownloadError as exc:
            return _DownloadedDocument(document, None, str(exc))

    def _document_hash(self, downloaded: list[_DownloadedDocument]) -> str:
        manifest = [
            {
                "id": item.document.documento_id,
                "titulo": item.document.titulo,
                "url": item.document.url,
                "prioridade": item.document.prioridade,
                "selecionado": item.document.selecionado,
                "estado": "baixado" if item.arquivo is not None else "falha_download",
                "hash": item.arquivo.sha256 if item.arquivo is not None else None,
                "erro": item.error if item.arquivo is None else None,
            }
            for item in downloaded
        ]
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _cache_key(self, contract_key: str, document_hash: str) -> str:
        raw_key = f"{contract_key}|{document_hash}|{settings.edital_analyzer_version}"
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def _analisar_documentos_locked(
        self,
        documentos: list[Any],
        contratacao_key: str,
        *,
        forcar: bool,
    ) -> ResultadoExigencias:
        started_at = time.monotonic()
        selected = selecionar_documentos_para_analise(documentos)
        selected_for_analysis = [item for item in selected if item.selecionado]
        if not selected_for_analysis:
            return self._result_without_documents(selected)
        if len(selected_for_analysis) > settings.edital_analysis_max_documents:
            return self._limit_result(
                selected,
                "A análise excede o limite de documentos selecionados para uma contratação.",
            )

        semaphore = asyncio.Semaphore(max(1, settings.edital_analysis_concurrency))

        async def controlled_download(document: SelectedDocument) -> _DownloadedDocument:
            async with semaphore:
                return await self._download_document(document)

        downloaded = await asyncio.gather(*(controlled_download(item) for item in selected_for_analysis))
        total_bytes = sum(
            sum(len(pdf.content) for pdf in item.pdfs)
            for item in downloaded
        )
        if total_bytes > settings.edital_analysis_max_total_bytes:
            return self._limit_result(
                selected,
                "A análise excede o limite total de bytes dos documentos selecionados.",
            )
        self.metrics["bytes_documents_processed"] += total_bytes
        document_hash = self._document_hash(downloaded)
        cache_key = self._cache_key(contratacao_key, document_hash)
        cached = self.cache.get(cache_key)
        if cached is not None and not forcar:
            self.metrics["cache_hits"] += 1
            return cached.model_copy(deep=True)
        if not forcar:
            persisted = await asyncio.to_thread(
                obter_analise,
                contratacao_key,
                document_hash,
                settings.edital_analyzer_version,
            )
            if persisted is not None:
                self.metrics["persistent_cache_hits"] += 1
                self.cache[cache_key] = persisted.model_copy(deep=True)
                return persisted

        self.metrics["analyses_started"] += 1
        documents_out = [
            {
                "documento_id": item.documento_id,
                "titulo": item.titulo,
                "url": item.url,
                "paginas": 0,
                "paginas_com_ocr": 0,
                "status": "nao_selecionado",
                "mensagem": "Documento complementar não foi selecionado automaticamente para habilitação.",
            }
            for item in selected
            if not item.selecionado
        ]
        entries: list[dict[str, Any]] = []
        failures = 0
        analyzed = 0
        total_pages = 0
        for item in downloaded:
            document_out, document_entries, failed = await self._analisar_pdf(item)
            documents_out.append(document_out)
            entries.extend(document_entries)
            total_pages += int(document_out.get("paginas", 0))
            analyzed += int(document_out["status"] in {"analisado", "analise_parcial"})
            failures += int(failed)
            if total_pages > settings.edital_analysis_max_total_pages:
                failures += 1
                document_out["status"] = "analise_parcial"
                document_out["mensagem"] = "A análise atingiu o limite total de páginas da contratação."
                break

        status, message = self._result_status(analyzed, failures, entries)
        result = ResultadoExigencias(
            status=status,
            mensagem=message,
            total_exigencias=len(entries),
            categorias=dict(Counter(entry["categoria"] for entry in entries)),
            documentos_analisados=documents_out,
            exigencias=entries,
            analisador_versao=settings.edital_analyzer_version,
        )
        self.metrics["documents_selected"] += len(selected_for_analysis)
        # Todos os caminhos de análise devem expor a mesma estrutura. O download
        # de um PDF pode falhar depois que o documento foi selecionado; nesse
        # caso a paginação é zero, mas a métrica ainda precisa ser calculada.
        self.metrics["pages_ocr"] += sum(item.get("paginas_com_ocr", 0) for item in documents_out)
        self.metrics[f"status_{status}"] += 1
        self.metrics["duration_ms"] += round((time.monotonic() - started_at) * 1000)
        logger.info(
            "Análise de edital concluída: status=%s documentos=%s paginas_ocr=%s versao=%s duracao_ms=%s",
            status,
            len(selected_for_analysis),
            sum(item.get("paginas_com_ocr", 0) for item in documents_out),
            settings.edital_analyzer_version,
            round((time.monotonic() - started_at) * 1000),
        )
        if any(item.arquivo is not None for item in downloaded):
            self.cache[cache_key] = result.model_copy(deep=True)
            await asyncio.to_thread(salvar_analise, contratacao_key, document_hash, result)
        return result

    def _limit_result(self, documents: list[SelectedDocument], message: str) -> ResultadoExigencias:
        self.metrics["resource_limit_rejections"] += 1
        return ResultadoExigencias(
            status="erro",
            mensagem=message,
            documentos_analisados=[
                {
                    "documento_id": item.documento_id,
                    "titulo": item.titulo,
                    "url": item.url,
                    "paginas": 0,
                    "paginas_com_ocr": 0,
                    "status": "erro" if item.selecionado else "nao_selecionado",
                    "mensagem": message if item.selecionado else "Documento complementar não selecionado.",
                }
                for item in documents
            ],
            analisador_versao=settings.edital_analyzer_version,
        )

    def _result_without_documents(self, documents: list[SelectedDocument]) -> ResultadoExigencias:
        return ResultadoExigencias(
            status="sem_documento_analisavel",
            mensagem="Não há edital ou anexo de habilitação disponível para análise automática.",
            documentos_analisados=[
                {
                    "documento_id": item.documento_id,
                    "titulo": item.titulo,
                    "url": item.url,
                    "paginas": 0,
                    "paginas_com_ocr": 0,
                    "status": "nao_selecionado",
                    "mensagem": "Documento não identificado como edital ou anexo de habilitação.",
                }
                for item in documents
            ],
            analisador_versao=settings.edital_analyzer_version,
        )

    async def _analisar_pdf(
        self,
        downloaded: _DownloadedDocument,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], bool]:
        """Analisa um PDF único ou todos os PDFs seguros extraídos de um ZIP."""
        document = downloaded.document
        base = {
            "documento_id": document.documento_id,
            "titulo": document.titulo,
            "url": document.url,
            "paginas": 0,
            "paginas_com_ocr": 0,
        }
        if not downloaded.pdfs:
            return ({**base, "status": "erro", "mensagem": downloaded.error}, [], True)

        pages: list[tuple[PageText, str, float | None]] = []
        ocr_pages = 0
        ocr_disabled_pages = False
        failures: list[str] = []
        total_pages = 0
        extracted_pdfs: list[tuple[DownloadedPdf, Any]] = []
        is_zip = isinstance(downloaded.arquivo, DownloadedZip)
        for pdf in downloaded.pdfs:
            try:
                text_result = await asyncio.to_thread(extrair_texto_pdf, pdf.content)
            except (PdfPageLimitError, PdfTextError) as exc:
                failures.append(str(exc))
                continue
            total_pages += text_result.total_paginas
            if is_zip and total_pages > settings.edital_zip_max_total_pages:
                return (
                    {
                        **base,
                        "status": "erro",
                        "mensagem": "O arquivo ZIP excede o limite total de páginas para análise.",
                    },
                    [],
                    True,
                )
            extracted_pdfs.append((pdf, text_result))

        if total_pages == 0:
            return (
                {
                    **base,
                    "status": "erro",
                    "mensagem": failures[0] if failures else "Nenhum PDF pôde ser analisado.",
                },
                [],
                True,
            )

        page_offset = 0
        for pdf, text_result in extracted_pdfs:
            for page in text_result.paginas:
                global_page = page.pagina + page_offset
                if page.status == "texto_suficiente":
                    pages.append(
                        (
                            PageText(
                                pagina=global_page,
                                texto=page.texto,
                                caracteres=page.caracteres,
                                proporcao_imprimivel=page.proporcao_imprimivel,
                                status=page.status,
                                erro=page.erro,
                            ),
                            "pdf_texto",
                            None,
                        )
                    )
                    continue
                if not settings.edital_ocr_enabled:
                    ocr_disabled_pages = True
                    failures.append(
                        "O OCR está desativado por configuração; uma página sem texto digital foi ignorada."
                    )
                    continue
                ocr_pages += 1
                try:
                    image = await asyncio.to_thread(renderizar_pagina_para_ocr, pdf.content, page.pagina)
                    ocr_result = await asyncio.to_thread(self.ocr_service.reconhecer, image, page.pagina)
                except PdfTextError:
                    failures.append("Uma página não pôde ser preparada para OCR.")
                    continue
                if ocr_result.status == "erro":
                    failures.append(ocr_result.erro or "Uma página não pôde ser lida por OCR.")
                    continue
                pages.append(
                    (
                        PageText(
                            pagina=global_page,
                            texto=ocr_result.texto,
                            caracteres=len(ocr_result.texto),
                            proporcao_imprimivel=1.0,
                            status="texto_suficiente",
                        ),
                        "ocr",
                        ocr_result.confianca,
                    )
                )
            page_offset += text_result.total_paginas

        filtered_entries = localizar_exigencias_com_metricas(documento=document, paginas=pages)
        entries = filtered_entries.exigencias
        self.metrics["requirements_candidates"] += filtered_entries.total_candidatas
        self.metrics["requirements_filtered"] += len(filtered_entries.rejeitadas)
        document_status = "analise_parcial" if failures else "analisado"
        message = (
            "Algumas páginas sem texto digital foram ignoradas porque o OCR está desativado."
            if ocr_disabled_pages
            else "Uma ou mais páginas ou PDFs não puderam ser lidos integralmente."
            if failures
            else None
        )
        return (
            {
                **base,
                "paginas": total_pages,
                "paginas_com_ocr": ocr_pages,
                "status": document_status,
                "mensagem": message,
            },
            entries,
            bool(failures),
        )

    @staticmethod
    def _result_status(analyzed: int, failures: int, entries: list[dict[str, Any]]) -> tuple[str, str]:
        if analyzed == 0:
            return "erro", "Não foi possível analisar os documentos selecionados do edital."
        if failures:
            return "sucesso_parcial", "Exigências identificadas no edital; alguns anexos não puderam ser analisados."
        if entries:
            return "sucesso", "Exigências identificadas no edital. A lista não substitui a leitura do documento."
        return "sucesso", "Nenhuma exigência de habilitação foi identificada automaticamente no texto analisado."
