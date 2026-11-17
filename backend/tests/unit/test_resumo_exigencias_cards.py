from backend.schemas import ExecucaoBusca
from backend.services import pncp_service


def test_resultado_de_obras_anexa_resumo_persistido_sem_disparar_ocr(monkeypatch):
    requested_keys = []

    def fake_summaries(keys):
        requested_keys.extend(keys)
        return {
            "12345678901234:2026:7": {
                "status": "sucesso",
                "total_exigencias": 3,
                "categorias": {"qualificacao_tecnica": 2, "declaracoes": 1},
                "analisador_versao": "ocr-edital-v1",
            }
        }

    monkeypatch.setattr(pncp_service, "obter_resumos_contratacoes", fake_summaries)
    result = pncp_service._result(
        status="sucesso_real",
        mensagem="Consulta realizada.",
        dados=[
            {
                "id_pncp": "12345678901234-1-000007/2026",
                "cnpj": "12345678901234",
                "ano": 2026,
                "sequencial": 7,
                "orgao": "Prefeitura",
                "uf": "RS",
                "objeto": "Obra de pavimentação",
                "data_publicacao": "2026-09-03T12:00:00+00:00",
            }
        ],
        metadados=ExecucaoBusca(),
    )

    assert requested_keys == ["12345678901234:2026:7"]
    assert result["dados"][0]["resumo_exigencias"]["total_exigencias"] == 3
