import hashlib
import io
import zipfile

import pytest

from backend.services import pdf_download_service
from backend.services.pdf_download_service import (
    DownloadedZip,
    PdfDownloadError,
    baixar_pdf_pncp,
    extrair_pdfs_zip,
    validar_url_documento,
)


class FakeResponse:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {"content-type": "application/pdf"}
        self.chunks = chunks or []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def aiter_bytes(self):
        for chunk in self.chunks:
            yield chunk


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def stream(self, method, url, **kwargs):
        self.urls.append(url)
        return self.responses.pop(0)


def make_zip(entries: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_valida_apenas_hosts_https_autorizados():
    assert validar_url_documento("https://arquivos.pncp.gov.br/edital.pdf") == "https://arquivos.pncp.gov.br/edital.pdf"

    for unsafe_url in (
        "http://pncp.gov.br/edital.pdf",
        "https://localhost/edital.pdf",
        "https://127.0.0.1/edital.pdf",
        "https://pncp.gov.br:8443/edital.pdf",
        "https://pncp.gov.br.evil.example/edital.pdf",
        "https://user:secret@pncp.gov.br/edital.pdf",
    ):
        with pytest.raises(PdfDownloadError):
            validar_url_documento(unsafe_url)


@pytest.mark.asyncio
async def test_baixa_pdf_com_hash_e_limite_de_stream(monkeypatch):
    content = b"%PDF-1.7\nconteudo de edital"
    client = FakeClient(
        [
            FakeResponse(
                headers={"content-type": "application/pdf", "content-length": str(len(content))},
                chunks=[content[:8], content[8:]],
            )
        ]
    )
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: client)

    result = await baixar_pdf_pncp("https://pncp.gov.br/edital.pdf")

    assert result.content == content
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert client.urls == ["https://pncp.gov.br/edital.pdf"]


@pytest.mark.asyncio
async def test_rejeita_redirect_para_host_externo(monkeypatch):
    client = FakeClient([FakeResponse(302, headers={"location": "https://evil.example/arquivo.pdf"})])
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(PdfDownloadError, match="não é autorizada"):
        await baixar_pdf_pncp("https://pncp.gov.br/edital.pdf")

    assert client.urls == ["https://pncp.gov.br/edital.pdf"]


@pytest.mark.asyncio
async def test_rejeita_tipo_assinatura_e_tamanho_invalidos(monkeypatch):
    too_large = FakeClient([FakeResponse(headers={"content-type": "application/pdf", "content-length": "999"})])
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: too_large)
    monkeypatch.setattr(pdf_download_service.settings, "edital_pdf_max_bytes", 20)
    with pytest.raises(PdfDownloadError, match="excede"):
        await baixar_pdf_pncp("https://pncp.gov.br/grande.pdf")

    invalid = FakeClient([FakeResponse(headers={"content-type": "text/html"}, chunks=[b"<html>"])])
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: invalid)
    with pytest.raises(PdfDownloadError, match="não é um PDF"):
        await baixar_pdf_pncp("https://pncp.gov.br/invalido.pdf")


@pytest.mark.asyncio
async def test_rejeita_resposta_http_indisponivel(monkeypatch):
    client = FakeClient([FakeResponse(404)])
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: client)

    with pytest.raises(PdfDownloadError, match="HTTP 404"):
        await baixar_pdf_pncp("https://pncp.gov.br/ausente.pdf")


@pytest.mark.asyncio
async def test_baixa_zip_e_extrai_todos_os_pdfs(monkeypatch):
    first_pdf = b"%PDF-1.7\nprimeiro edital"
    second_pdf = b"%PDF-1.7\nsegundo anexo"
    content = make_zip(
        {
            "edital/edital-principal.pdf": first_pdf,
            "edital/anexo.pdf": second_pdf,
            "edital/leiame.txt": b"arquivo complementar",
        }
    )
    client = FakeClient(
        [
            FakeResponse(
                headers={"content-type": "application/zip", "content-length": str(len(content))},
                chunks=[content],
            )
        ]
    )
    monkeypatch.setattr(pdf_download_service.httpx, "AsyncClient", lambda **kwargs: client)

    result = await baixar_pdf_pncp("https://pncp.gov.br/edital.zip")

    assert isinstance(result, DownloadedZip)
    assert [pdf.content for pdf in result.pdfs] == [first_pdf, second_pdf]
    assert result.sha256 == hashlib.sha256(content).hexdigest()


def test_rejeita_zip_com_caminho_inseguro_ou_sem_pdf():
    traversal = make_zip({"../edital.pdf": b"%PDF-1.7\nconteudo"})
    with pytest.raises(PdfDownloadError, match="caminho"):
        extrair_pdfs_zip(
            traversal,
            url_final="https://pncp.gov.br/edital.zip",
            content_type="application/zip",
        )

    without_pdf = make_zip({"edital/leiame.txt": b"sem documento"})
    with pytest.raises(PdfDownloadError, match="não contém PDFs"):
        extrair_pdfs_zip(
            without_pdf,
            url_final="https://pncp.gov.br/edital.zip",
            content_type="application/zip",
        )


def test_rejeita_zip_bomb_por_taxa_ou_total_descompactado(monkeypatch):
    highly_compressed = make_zip({"edital.pdf": b"%PDF-1.7\n" + b"A" * 10_000})
    monkeypatch.setattr(pdf_download_service.settings, "edital_zip_max_compression_ratio", 2)
    with pytest.raises(PdfDownloadError, match="taxa de compressão"):
        extrair_pdfs_zip(
            highly_compressed,
            url_final="https://pncp.gov.br/edital.zip",
            content_type="application/zip",
        )

    regular_zip = make_zip({"edital.pdf": b"%PDF-1.7\nconteudo suficiente"})
    monkeypatch.setattr(pdf_download_service.settings, "edital_zip_max_compression_ratio", 100)
    monkeypatch.setattr(pdf_download_service.settings, "edital_zip_max_uncompressed_bytes", 10)
    with pytest.raises(PdfDownloadError, match="limite descompactado"):
        extrair_pdfs_zip(
            regular_zip,
            url_final="https://pncp.gov.br/edital.zip",
            content_type="application/zip",
        )
