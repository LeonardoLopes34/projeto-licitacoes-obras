from backend.services.ocr_service import verificar_disponibilidade_tesseract
from backend.services.ocr_service import TesseractOcrService


def _synthetic_text_image():
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1800, 360), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 88)
    except OSError:
        font = ImageFont.load_default(size=64)
    draw.text((80, 120), "CONTRATO SOCIAL", fill="black", font=font)
    return image


def test_tesseract_disponibiliza_idioma_portugues():
    availability = verificar_disponibilidade_tesseract()
    assert availability.disponivel, availability.erro
    assert availability.idioma == "por"


def test_tesseract_reconhece_texto_de_imagem_sintetica_com_configuracao_da_aplicacao():
    result = TesseractOcrService().reconhecer(_synthetic_text_image(), pagina=1)

    assert result.status in {"sucesso", "baixa_qualidade"}, result.erro
    assert "contrato social" in result.texto.lower()
