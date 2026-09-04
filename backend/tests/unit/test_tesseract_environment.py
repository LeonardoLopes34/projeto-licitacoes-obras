import shutil

import pytest
import pytesseract


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract não está instalado neste ambiente")
def test_tesseract_disponibiliza_idioma_portugues():
    assert "por" in pytesseract.get_languages(config="")
