"""Download controlado de PDFs e arquivos ZIP publicados pelo PNCP.

O serviço recebe somente URLs já retornadas pela API de documentos do PNCP,
mas ainda as valida antes de cada redirecionamento. Isso impede que um arquivo
publicado com URL maliciosa seja usado como ponte para recursos internos.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import ssl
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import urljoin, urlparse

import httpx

from backend.config import settings


MAX_REDIRECTS: Final = 3
PDF_CONTENT_TYPES: Final = {"application/pdf", "application/octet-stream"}
ZIP_CONTENT_TYPES: Final = {
    "application/zip",
    "application/x-zip-compressed",
    "application/x-zip",
    "multipart/x-zip",
    "application/octet-stream",
}
ALLOWED_CONTENT_TYPES: Final = PDF_CONTENT_TYPES | ZIP_CONTENT_TYPES
_ZIP_READ_CHUNK_SIZE: Final = 64 * 1024


class PdfDownloadError(RuntimeError):
    """Erro seguro para exibição quando um PDF público não pode ser obtido."""


@dataclass(frozen=True)
class DownloadedPdf:
    content: bytes
    sha256: str
    url_final: str
    content_type: str


@dataclass(frozen=True)
class DownloadedZip:
    """Arquivo ZIP validado, representado somente pelos PDFs seguros que continha.

    O ZIP bruto não é persistido nem extraído em disco. Dessa forma, nomes de
    arquivos do pacote não podem escrever fora de um diretório de trabalho.
    """

    pdfs: tuple[DownloadedPdf, ...]
    sha256: str
    url_final: str
    content_type: str


DownloadedDocument = DownloadedPdf | DownloadedZip


def _host_is_allowed(host: str, allowed_hosts: list[str]) -> bool:
    host = host.rstrip(".").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)


def validar_url_documento(url: str, *, allowed_hosts: list[str] | None = None) -> str:
    """Valida a origem remota antes de abrir qualquer conexão."""
    raw_url = str(url or "").strip()
    parsed = urlparse(raw_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise PdfDownloadError("O arquivo não possui uma URL HTTPS autorizada.")
    if parsed.username or parsed.password:
        raise PdfDownloadError("A URL do arquivo possui credenciais inválidas.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise PdfDownloadError("A URL do arquivo possui uma porta inválida.") from exc
    if port not in (None, 443):
        raise PdfDownloadError("A URL do arquivo usa uma porta não autorizada.")

    host = parsed.hostname.rstrip(".").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PdfDownloadError("A URL do arquivo não pode apontar para um endereço IP.")

    permitted = [item.rstrip(".").lower() for item in (allowed_hosts or settings.pncp_document_hosts)]
    if not _host_is_allowed(host, permitted):
        raise PdfDownloadError("A origem do arquivo não é autorizada pelo PNCP.")
    return raw_url


def _content_length(headers: httpx.Headers) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        size = int(value)
    except ValueError as exc:
        raise PdfDownloadError("O tamanho informado do arquivo é inválido.") from exc
    if size < 0:
        raise PdfDownloadError("O tamanho informado do arquivo é inválido.")
    return size


def _tls_verify() -> bool | ssl.SSLContext:
    if settings.pncp_ca_bundle:
        return ssl.create_default_context(cafile=settings.pncp_ca_bundle)
    return True


def _normalizar_nome_zip(name: str) -> PurePosixPath:
    """Valida nomes do ZIP mesmo sem extrair arquivos ao sistema de arquivos."""
    normalized_name = str(name or "").replace("\\", "/")
    path = PurePosixPath(normalized_name)
    if (
        not normalized_name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or (path.parts and path.parts[0].endswith(":"))
    ):
        raise PdfDownloadError("O arquivo ZIP contém um caminho de arquivo inválido.")
    return path


def _validar_entrada_zip(info: zipfile.ZipInfo) -> None:
    _normalizar_nome_zip(info.filename)
    if info.flag_bits & 0x1:
        raise PdfDownloadError("O arquivo ZIP contém um item protegido por senha.")
    if info.file_size < 0 or info.compress_size < 0:
        raise PdfDownloadError("O arquivo ZIP contém um item com tamanho inválido.")
    if info.file_size > settings.edital_pdf_max_bytes:
        raise PdfDownloadError("Um PDF do arquivo ZIP excede o limite permitido para análise.")
    if info.file_size and not info.compress_size:
        raise PdfDownloadError("O arquivo ZIP possui uma taxa de compressão inválida.")
    if info.file_size and info.file_size / max(info.compress_size, 1) > settings.edital_zip_max_compression_ratio:
        raise PdfDownloadError("O arquivo ZIP excede a taxa de compressão permitida.")


def _read_zip_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo, *, remaining: int) -> bytes:
    """Lê uma entrada em blocos, limitando o tamanho real descompactado."""
    chunks: list[bytes] = []
    total = 0
    try:
        with archive.open(info, "r") as item:
            while True:
                chunk = item.read(_ZIP_READ_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.edital_pdf_max_bytes or total > remaining:
                    raise PdfDownloadError("O conteúdo descompactado excede o limite permitido para análise.")
                chunks.append(chunk)
    except PdfDownloadError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PdfDownloadError("Não foi possível extrair um PDF do arquivo ZIP.") from exc
    return b"".join(chunks)


def extrair_pdfs_zip(
    content: bytes,
    *,
    url_final: str,
    content_type: str,
) -> DownloadedZip:
    """Extrai PDFs de um ZIP sem escrever em disco e com limites anti-zip-bomb."""
    if not zipfile.is_zipfile(io.BytesIO(content)):
        raise PdfDownloadError("O conteúdo recebido não é um arquivo ZIP válido.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > settings.edital_zip_max_entries:
                raise PdfDownloadError("O arquivo ZIP contém itens demais para análise segura.")

            pdf_entries: list[zipfile.ZipInfo] = []
            declared_total = 0
            for info in entries:
                path = _normalizar_nome_zip(info.filename)
                if info.is_dir():
                    continue
                _validar_entrada_zip(info)
                declared_total += info.file_size
                if declared_total > settings.edital_zip_max_uncompressed_bytes:
                    raise PdfDownloadError("O arquivo ZIP excede o limite descompactado permitido.")
                if path.suffix.lower() == ".pdf":
                    pdf_entries.append(info)

            if not pdf_entries:
                raise PdfDownloadError("O arquivo ZIP não contém PDFs para análise.")
            if len(pdf_entries) > settings.edital_zip_max_pdfs:
                raise PdfDownloadError("O arquivo ZIP contém PDFs demais para análise segura.")

            pdfs: list[DownloadedPdf] = []
            extracted_total = 0
            for info in pdf_entries:
                remaining = settings.edital_zip_max_uncompressed_bytes - extracted_total
                pdf_content = _read_zip_entry(archive, info, remaining=remaining)
                extracted_total += len(pdf_content)
                if not pdf_content.startswith(b"%PDF-"):
                    raise PdfDownloadError("O arquivo ZIP contém um item PDF inválido.")
                pdfs.append(
                    DownloadedPdf(
                        content=pdf_content,
                        sha256=hashlib.sha256(pdf_content).hexdigest(),
                        url_final=url_final,
                        content_type="application/pdf",
                    )
                )
    except PdfDownloadError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise PdfDownloadError("Não foi possível abrir o arquivo ZIP publicado no PNCP.") from exc

    return DownloadedZip(
        pdfs=tuple(pdfs),
        sha256=hashlib.sha256(content).hexdigest(),
        url_final=url_final,
        content_type=content_type,
    )


async def baixar_pdf_pncp(url: str) -> DownloadedDocument:
    """Baixa um PDF ou ZIP permitido, com validação de origem e tamanho."""
    current_url = validar_url_documento(url)
    timeout = httpx.Timeout(
        settings.edital_download_timeout_seconds,
        connect=settings.edital_download_connect_timeout_seconds,
    )
    headers = {
        "User-Agent": "licitacoes-obras/1.0",
        "Accept": "application/pdf, application/zip, application/octet-stream",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, verify=_tls_verify()) as client:
            for _redirect in range(MAX_REDIRECTS + 1):
                async with client.stream("GET", current_url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise PdfDownloadError("O arquivo redirecionou sem informar o destino.")
                        current_url = validar_url_documento(urljoin(current_url, location))
                        continue
                    if response.status_code != 200:
                        raise PdfDownloadError(
                            f"O PNCP não disponibilizou o arquivo (HTTP {response.status_code})."
                        )

                    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type not in ALLOWED_CONTENT_TYPES:
                        raise PdfDownloadError("O arquivo informado pelo PNCP não é um PDF ou ZIP.")
                    declared_size = _content_length(response.headers)
                    if declared_size is not None and declared_size > settings.edital_pdf_max_bytes:
                        raise PdfDownloadError("O arquivo excede o limite permitido para análise.")

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > settings.edital_pdf_max_bytes:
                            raise PdfDownloadError("O arquivo excede o limite permitido para análise.")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    if content.startswith(b"%PDF-"):
                        return DownloadedPdf(
                            content=content,
                            sha256=hashlib.sha256(content).hexdigest(),
                            url_final=current_url,
                            content_type=content_type,
                        )
                    if zipfile.is_zipfile(io.BytesIO(content)):
                        return extrair_pdfs_zip(
                            content,
                            url_final=current_url,
                            content_type=content_type,
                        )
                    raise PdfDownloadError("O conteúdo recebido não é um PDF ou ZIP válido.")
    except PdfDownloadError:
        raise
    except httpx.TimeoutException as exc:
        raise PdfDownloadError("O download do arquivo excedeu o tempo limite.") from exc
    except httpx.HTTPError as exc:
        raise PdfDownloadError("Não foi possível baixar o arquivo publicado no PNCP.") from exc

    raise PdfDownloadError("O arquivo excedeu o limite de redirecionamentos seguros.")
