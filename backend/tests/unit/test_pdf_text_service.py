import io

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfWriter

from backend.services.pdf_text_service import PdfPageLimitError, extrair_texto_pdf, renderizar_pagina_para_ocr
from backend.services import pdf_text_service


def make_text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(output)


def make_blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def make_scanned_pdf() -> bytes:
    image = Image.new("RGB", (500, 160), "white")
    ImageDraw.Draw(image).text((20, 20), "Atestado de capacidade tecnica", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PDF")
    return buffer.getvalue()


def test_pdf_digital_tem_texto_suficiente_sem_ocr(monkeypatch):
    monkeypatch.setattr(pdf_text_service.settings, "edital_text_min_characters", 20)
    result = extrair_texto_pdf(make_text_pdf("Documentos de habilitacao devem conter atestado tecnico."))

    assert result.parser == "pdfplumber"
    assert result.paginas[0].pagina == 1
    assert "habilitacao" in result.paginas[0].texto.lower()
    assert result.paginas[0].status == "texto_suficiente"
    assert result.paginas_para_ocr == []


def test_pagina_sem_texto_e_marcada_exclusivamente_para_ocr():
    result = extrair_texto_pdf(make_scanned_pdf())

    assert result.paginas[0].status == "sem_texto"
    assert result.paginas_para_ocr == [1]


def test_pdf_protegido_retorna_erro_compreensivel():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("segredo")
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(pdf_text_service.PdfTextError, match="protegido por senha"):
        extrair_texto_pdf(buffer.getvalue())


def test_rejeita_pdf_invalido_e_limite_de_paginas(monkeypatch):
    with pytest.raises(pdf_text_service.PdfTextError, match="não é um PDF"):
        extrair_texto_pdf(b"texto comum")

    monkeypatch.setattr(pdf_text_service.settings, "edital_pdf_max_pages", 0)
    with pytest.raises(PdfPageLimitError):
        extrair_texto_pdf(make_blank_pdf())


def test_renderizador_gera_imagem_apenas_da_pagina_solicitada():
    image = renderizar_pagina_para_ocr(make_text_pdf("Edital de habilitacao"), pagina=1)

    assert image.mode == "RGB"
    assert image.width > 0
    assert image.height > 0
