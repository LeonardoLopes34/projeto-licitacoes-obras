import json

import pytest

from backend.config import settings
from backend.services.openai_edital_service import (
    AnalysisChunkContext,
    OpenAIBudgetExceededError,
    OpenAIEmbeddingProvider,
    OpenAIRequirementAnalyzer,
    OpenAIServiceError,
)


class StubEmbeddings(OpenAIEmbeddingProvider):
    def __init__(self):
        self.payload = None

    async def _post(self, path, payload):
        self.payload = (path, payload)
        return {
            "data": [
                {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                {"index": 0, "embedding": [1.0, 0.0, 0.0]},
            ],
            "usage": {"input_tokens": 9},
        }


class StubAnalyzer(OpenAIRequirementAnalyzer):
    def __init__(self, response):
        self.response = response
        self.payload = None

    async def _post(self, path, payload):
        self.payload = (path, payload)
        return self.response


def _chunk():
    return AnalysisChunkContext(
        chunk_id=7,
        documento_id=12,
        titulo_documento="Edital",
        url_documento="https://pncp.gov.br/edital.pdf",
        pagina=4,
        texto="A licitante deverá apresentar atestado de capacidade técnica.",
        origem_texto="pdf_texto",
    )


def _valid_item():
    return {
        "categoria": "qualificacao_tecnica",
        "nome_documento": "Atestado de capacidade técnica",
        "resumo": "Comprovação técnica.",
        "chunk_id": 7,
        "documento_id": 12,
        "pagina": 4,
        "evidencia": "apresentar atestado de capacidade técnica",
        "confianca": 0.91,
        "estado": "identificado",
    }


def _completed_rest_response(text: str, *, content: object | None = None) -> dict:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "status": "completed",
                "content": content if content is not None else [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {"input_tokens": 30, "output_tokens": 12},
    }


@pytest.mark.asyncio
async def test_embeddings_ordenam_resposta_e_enviam_configuracao_versionada(monkeypatch):
    monkeypatch.setattr(settings, "openai_embedding_dimensions", 3)
    provider = StubEmbeddings()

    batch = await provider.embed(["primeiro", "segundo"], remaining_budget_usd=1)

    assert batch.vectors == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert batch.input_tokens == 9
    assert provider.payload[0] == "/embeddings"
    assert provider.payload[1]["model"] == settings.openai_embedding_model
    assert provider.payload[1]["dimensions"] == 3


@pytest.mark.asyncio
async def test_analisador_rejeita_evidencia_que_nao_esta_na_fonte_e_delimita_contexto():
    response = _completed_rest_response(
        json.dumps(
            {
                "itens": [
                    _valid_item(),
                    {
                        "categoria": "declaracoes",
                        "nome_documento": "Declaração inventada",
                        "resumo": "Não deve passar.",
                        "chunk_id": 7,
                        "documento_id": 12,
                        "pagina": 4,
                        "evidencia": "texto que não existe",
                        "confianca": 0.99,
                        "estado": "identificado",
                    },
                ]
            }
        )
    )
    analyzer = StubAnalyzer(response)

    result = await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert [item.nome_documento for item in result.accepted] == ["Atestado de capacidade técnica"]
    assert result.rejected_count == 1
    assert analyzer.payload[0] == "/responses"
    assert "DADOS NÃO CONFIÁVEIS" in analyzer.payload[1]["instructions"]
    assert '<trecho_edital chunk_id="7" documento_id="12" pagina="4">' in analyzer.payload[1]["input"]
    assert analyzer.payload[1]["store"] is False
    assert analyzer.payload[1]["text"]["format"]["strict"] is True


@pytest.mark.asyncio
async def test_analisador_aceita_payload_rest_concluido_sem_output_text_na_raiz():
    analyzer = StubAnalyzer(_completed_rest_response(json.dumps({"itens": [_valid_item()]})))

    result = await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert [item.nome_documento for item in result.accepted] == ["Atestado de capacidade técnica"]
    assert result.rejected_count == 0
    assert result.input_tokens == 30
    assert result.output_tokens == 12


@pytest.mark.asyncio
async def test_orcamento_e_desativacao_bloqueiam_chamada_externa(monkeypatch):
    monkeypatch.setattr(settings, "openai_embedding_dimensions", 3)
    provider = StubEmbeddings()
    with pytest.raises(OpenAIBudgetExceededError):
        await provider.embed(["texto suficiente para consumir orçamento"], remaining_budget_usd=0)

    monkeypatch.setattr(settings, "vector_indexing_enabled", False)
    with pytest.raises(OpenAIServiceError, match="desativada"):
        await OpenAIEmbeddingProvider().embed(["texto"], remaining_budget_usd=1)


@pytest.mark.asyncio
async def test_analisador_rejeita_json_invalido_sem_resultado_aceito():
    analyzer = StubAnalyzer(_completed_rest_response("não é JSON"))

    with pytest.raises(OpenAIServiceError, match="estruturada inválida") as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "json_invalido"


@pytest.mark.asyncio
async def test_analisador_classifica_resposta_incompleta_antes_de_tentar_ler_json():
    analyzer = StubAnalyzer(
        {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [],
        }
    )

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "resposta_incompleta"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_code", "retryable"),
    [
        ({"status": "queued"}, "resposta_pendente", True),
        ({"status": "in_progress"}, "resposta_pendente", True),
        ({"status": "failed", "error": {"code": "server_error"}}, "resposta_falhou", True),
        ({"status": "failed", "error": {"code": "invalid_request_error"}}, "resposta_falhou", False),
        ({"status": "cancelled"}, "resposta_cancelada", False),
        ({"status": "desconhecido"}, "resposta_estado_invalido", False),
    ],
)
async def test_analisador_classifica_estados_nao_concluidos_sem_ler_saida(response, expected_code, retryable):
    analyzer = StubAnalyzer(response)

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == expected_code
    assert caught.value.retryable is retryable


@pytest.mark.asyncio
async def test_analisador_classifica_recusa_sem_tratar_como_json_invalido():
    analyzer = StubAnalyzer(
        {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "Não posso concluir esta solicitação."}],
                }
            ],
        }
    )

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "recusa_openai"
    assert "Não posso concluir" not in str(caught.value)


@pytest.mark.asyncio
async def test_analisador_concatena_segmentos_de_texto_da_resposta_rest():
    analyzer = StubAnalyzer(
        _completed_rest_response(
            "",
            content=[
                {"type": "output_text", "text": '{"itens": ['},
                {"type": "output_text", "text": "]}"},
            ],
        )
    )

    result = await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert result.accepted == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        {"status": "completed", "output": None},
        {"status": "completed", "output": [{"type": "message", "content": None}]},
        {"status": "completed", "output": []},
    ],
)
async def test_analisador_classifica_saida_sem_texto_quando_output_ou_content_sao_nulos(response):
    analyzer = StubAnalyzer(response)

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "resposta_sem_texto"


@pytest.mark.asyncio
async def test_analisador_rejeita_json_valido_com_schema_de_item_incompleto():
    analyzer = StubAnalyzer(_completed_rest_response(json.dumps({"itens": [{"categoria": "qualificacao_tecnica"}]})))

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "schema_invalido"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"itens": [], "campo_extra": "não permitido"},
    ],
)
async def test_analisador_rejeita_objeto_vazio_e_campos_extras_no_schema(payload):
    analyzer = StubAnalyzer(_completed_rest_response(json.dumps(payload)))

    with pytest.raises(OpenAIServiceError) as caught:
        await analyzer.analyze([_chunk()], remaining_budget_usd=1)

    assert caught.value.code == "schema_invalido"
