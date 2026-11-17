# Tasks — Spec 001: TLS / Verificação de Certificado

- [ ] Remover `verify=False` de `backend/services/pncp_service.py:414` (R001-1, R001-3)
- [ ] Remover `verify=False` de `test_pncp.py:24` (R001-1, R001-3)
- [ ] Investigar e documentar a causa original do `verify=False` (proxy? certificado corporativo? certifi desatualizado?) (R001-1)
- [ ] Se necessário, configurar `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` via variável de ambiente para resolver a causa raiz sem desativar verificação (R001-1)
- [ ] Adicionar captura específica de erro de SSL/TLS com log e exceção customizada (`PNCPConnectionError`) (R001-2)
- [ ] Adicionar verificação `grep`/pre-commit/CI que bloqueia reintrodução de `verify=False` (R001-3)
- [ ] Testar chamada real (ou contra ambiente de homologação) ao PNCP com verificação ativa e confirmar sucesso (R001-1)
- [ ] Testar cenário de falha de certificado (ex. via mock) e confirmar que o erro é logado e propagado, não silenciado (R001-2)
