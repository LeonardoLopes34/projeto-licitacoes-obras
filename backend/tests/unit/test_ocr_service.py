import pytesseract

from backend.services.ocr_service import TesseractOcrService, verificar_disponibilidade_tesseract


def test_pre_verificacao_indica_tesseract_e_idioma_configurados(monkeypatch):
    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(pytesseract, "get_languages", lambda: ["eng", "por"])

    result = verificar_disponibilidade_tesseract(language="por", tesseract_cmd="C:/tesseract.exe")

    assert result.disponivel is True
    assert result.status == "disponivel"
    assert result.idioma == "por"
    assert result.versao == "5.5.0"
    assert result.idiomas_disponiveis == ("eng", "por")
    assert result.erro is None


def test_pre_verificacao_indica_binario_ausente(monkeypatch):
    def missing_binary():
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "get_tesseract_version", missing_binary)

    result = verificar_disponibilidade_tesseract(language="por")

    assert result.disponivel is False
    assert result.status == "binario_ausente"
    assert "não está instalado" in result.erro.lower()


def test_pre_verificacao_indica_idioma_ausente(monkeypatch):
    monkeypatch.setattr(pytesseract, "get_tesseract_version", lambda: "5.5.0")
    monkeypatch.setattr(pytesseract, "get_languages", lambda: ["eng"])

    result = TesseractOcrService(language="por").verificar_disponibilidade()

    assert result.disponivel is False
    assert result.status == "idioma_ausente"
    assert result.idiomas_disponiveis == ("eng",)
    assert "por" in result.erro


def test_tesseract_recebe_portugues_e_retorna_confianca(monkeypatch):
    captured = {}

    def fake_image_to_data(image, **kwargs):
        captured.update(kwargs)
        return {"text": ["Atestado", "técnico"], "conf": ["91.5", "88.5"]}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)
    service = TesseractOcrService(language="por", timeout_seconds=7, tesseract_cmd="C:/tesseract.exe")

    result = service.reconhecer(object(), pagina=2)

    assert captured["lang"] == "por"
    assert captured["config"] == "--psm 6"
    assert captured["timeout"] == 7
    assert result.pagina == 2
    assert result.texto == "Atestado técnico"
    assert result.confianca == 0.9
    assert result.status == "sucesso"


def test_tesseract_ausente_ou_sem_texto_retorna_estado_rastreavel(monkeypatch):
    def missing_binary(*args, **kwargs):
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_data", missing_binary)
    missing = TesseractOcrService().reconhecer(object(), pagina=1)

    assert missing.status == "erro"
    assert "não está instalado" in missing.erro.lower()

    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": [""], "conf": ["-1"]},
    )
    empty = TesseractOcrService().reconhecer(object(), pagina=1)

    assert empty.status == "erro"
    assert "não identificou" in empty.erro.lower()


def test_tesseract_marca_texto_de_baixa_confianca_para_revisao(monkeypatch):
    monkeypatch.setattr(
        pytesseract,
        "image_to_data",
        lambda *args, **kwargs: {"text": ["CND"], "conf": ["31"]},
    )

    result = TesseractOcrService().reconhecer(object(), pagina=3)

    assert result.status == "baixa_qualidade"
    assert result.confianca == 0.31


class _FakeImage:
    def save(self, buffer, format, quality):
        buffer.write(b"jpeg")


class _FallbackOcr:
    language = "por"

    def reconhecer(self, image, pagina):
        from backend.services.ocr_service import OcrPageResult

        return OcrPageResult(pagina=pagina, texto="tesseract", confianca=0.5, idioma="por", duracao_ms=1, status="sucesso")


def _openai_response(payload, status_code=200):
    import httpx

    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))


def test_ocr_openai_transcreve_pagina_com_imagem(monkeypatch):
    import httpx

    from backend.services.ocr_service import OpenAIVisionOcrService

    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return _openai_response(
            {"status": "completed", "output": [{"content": [{"type": "output_text", "text": " Atestado técnico \n"}]}]}
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = OpenAIVisionOcrService(fallback=_FallbackOcr()).reconhecer(_FakeImage(), pagina=4)

    assert captured["url"].endswith("/responses")
    content = captured["json"]["input"][0]["content"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/jpeg;base64,")
    assert captured["json"]["store"] is False
    assert result.texto == "Atestado técnico"
    assert result.pagina == 4
    assert result.status == "sucesso"
    assert result.confianca == 0.80


def test_ocr_openai_usa_tesseract_quando_api_falha(monkeypatch):
    import httpx

    from backend.services.ocr_service import OpenAIVisionOcrService

    monkeypatch.setattr(httpx, "post", lambda url, **kwargs: _openai_response({"error": {}}, status_code=429))

    result = OpenAIVisionOcrService(fallback=_FallbackOcr()).reconhecer(_FakeImage(), pagina=1)

    assert result.texto == "tesseract"


def test_ocr_openai_usa_tesseract_quando_pagina_volta_vazia(monkeypatch):
    import httpx

    from backend.services.ocr_service import OpenAIVisionOcrService

    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: _openai_response({"status": "completed", "output_text": "   "}),
    )

    result = OpenAIVisionOcrService(fallback=_FallbackOcr()).reconhecer(_FakeImage(), pagina=1)

    assert result.texto == "tesseract"
