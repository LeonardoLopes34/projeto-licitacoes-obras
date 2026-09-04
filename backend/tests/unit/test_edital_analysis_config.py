import pytest
from pydantic import ValidationError

from backend.config import Settings


def test_configuracoes_do_pipeline_rejeitam_limites_inseguros():
    with pytest.raises(ValidationError):
        Settings(edital_pdf_max_pages=0)

    with pytest.raises(ValidationError):
        Settings(edital_ocr_dpi=90)

    with pytest.raises(ValidationError):
        Settings(edital_zip_max_total_pages=0)
