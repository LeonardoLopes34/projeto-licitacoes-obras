"""Contrato do corpus sintético e linha de base segura da Spec 015."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from backend.services import edital_analysis_service
from backend.services.edital_analysis_service import EditalAnalysisService
from backend.services.pdf_download_service import DownloadedPdf
from backend.services.pdf_text_service import PageText, PdfTextResult


CORPUS_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "corpus_indexacao_015.json"


def _load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def test_corpus_indexacao_015_tem_contrato_reproduzivel_e_citacoes_rastreaveis():
    corpus = _load_corpus()

    assert corpus["schema_version"] == "1.0"
    assert corpus["dados_sinteticos"] is True
    assert corpus["casos"]
    assert corpus["metricas_recomendadas"]["recall_at_k"]["k"] >= 1
    assert corpus["metricas_recomendadas"]["posicao_primeiro_trecho_correto"]["maximo"] >= 1

    case_ids: set[str] = set()
    document_pages: dict[str, dict[int, str]] = {}
    covered_input_types: set[str] = set()
    covered_tags: set[str] = set()
    query_ids: set[str] = set()

    for case in corpus["casos"]:
        assert case["id"] not in case_ids
        case_ids.add(case["id"])
        assert case["tipo_entrada"] in {"pdf_digital", "pdf_digitalizado", "zip_com_pdfs"}
        covered_input_types.add(case["tipo_entrada"])
        covered_tags.update(case["tags"])
        assert case["documentos"]
        assert case["perguntas"]

        for document in case["documentos"]:
            assert document["id"] not in document_pages
            assert document["paginas"]
            pages: dict[int, str] = {}
            for page in document["paginas"]:
                page_number = page["pagina"]
                assert isinstance(page_number, int) and page_number >= 1
                assert page_number not in pages
                assert page["origem_texto_esperada"] in {"pdf_texto", "ocr"}
                assert page["texto"].strip()
                if page["origem_texto_esperada"] == "ocr":
                    assert 0 <= page["confianca_ocr_esperada"] <= 1
                else:
                    assert "confianca_ocr_esperada" not in page
                pages[page_number] = page["texto"]
            document_pages[document["id"]] = pages

        for question in case["perguntas"]:
            assert question["id"] not in query_ids
            query_ids.add(question["id"])
            assert question["consulta"].strip()
            assert question["citacoes_esperadas"]
            for citation in question["citacoes_esperadas"]:
                assert citation["documento_id"] in document_pages
                source_page = document_pages[citation["documento_id"]].get(citation["pagina"])
                assert source_page is not None
                assert citation["trecho"] in source_page

    assert {"pdf_digital", "pdf_digitalizado", "zip_com_pdfs"} <= covered_input_types
    assert {"lista", "tabela"} <= covered_tags

    serialized = json.dumps(corpus, ensure_ascii=False).lower()
    assert "%pdf" not in serialized
    assert "http://" not in serialized and "https://" not in serialized
    assert "api_key" not in serialized and "senha" not in serialized


@pytest.mark.asyncio
async def test_linha_de_base_mantem_pdf_em_memoria_e_nao_o_entrega_ao_repositorio(monkeypatch, tmp_path):
    raw_pdf = b"%PDF-1.7\nCONTEUDO_BRUTO_SINTETICO_NAO_PERSISTIR"
    downloaded = DownloadedPdf(
        content=raw_pdf,
        sha256=hashlib.sha256(raw_pdf).hexdigest(),
        url_final="https://pncp.gov.br/documento-sintetico.pdf",
        content_type="application/pdf",
    )
    persisted: list[tuple[str, str, object]] = []

    async def fake_download(_url: str) -> DownloadedPdf:
        return downloaded

    def fake_extract(_content: bytes) -> PdfTextResult:
        return PdfTextResult(
            paginas=[
                PageText(
                    pagina=1,
                    texto="Documento sintetico para confirmar que a analise reutiliza bytes apenas em memoria.",
                    caracteres=84,
                    proporcao_imprimivel=1.0,
                    status="texto_suficiente",
                )
            ],
            parser="fixture",
        )

    def fake_save(contratacao_key: str, document_hash: str, result: object) -> None:
        persisted.append((contratacao_key, document_hash, result))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(edital_analysis_service, "obter_analise", lambda *args, **kwargs: None)
    monkeypatch.setattr(edital_analysis_service, "salvar_analise", fake_save)
    monkeypatch.setattr(edital_analysis_service, "extrair_texto_pdf", fake_extract)

    result = await EditalAnalysisService(downloader=fake_download).analisar_documentos(
        [{"sequencial_documento": 1, "titulo": "Edital sintetico", "url": downloaded.url_final}],
        contratacao_key="sintetico:2026:15",
    )

    assert result.status == "sucesso"
    assert len(persisted) == 1
    assert list(tmp_path.iterdir()) == []

    persisted_payload = json.dumps(persisted[0][2].model_dump(), ensure_ascii=False)
    assert "CONTEUDO_BRUTO_SINTETICO_NAO_PERSISTIR" not in persisted_payload
    assert raw_pdf.hex() not in persisted_payload
