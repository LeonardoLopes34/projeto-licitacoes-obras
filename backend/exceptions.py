class PNCPError(RuntimeError):
    """Erro base da integração com o PNCP."""


class PNCPConnectionError(PNCPError):
    """Falha de transporte, TLS ou timeout ao acessar o PNCP."""


class PNCPResponseError(PNCPError):
    """Resposta HTTP ou payload inválido retornado pelo PNCP."""


class DatabaseServiceError(RuntimeError):
    """Falha ao consultar ou persistir dados locais."""
