# Tasks — Spec 003: Erros Não Devem Virar Sucesso Silencioso

- [ ] Criar schema Pydantic `ResultadoBusca` com campos `obras`, `parcial`, `paginas_consultadas`, `paginas_com_erro`, `origem` (R003-3)
- [ ] Substituir `except Exception` genérico em `backend/main.py:55` por captura específica por tipo de erro (R003-1)
- [ ] Substituir `except Exception` genérico em `backend/services/pncp_service.py:358` e `:467` por captura específica (R003-1)
- [ ] Definir exceção customizada `PNCPConnectionError` (ou reaproveitar a criada na Spec 001) para falhas de conexão com o PNCP (R003-1)
- [ ] Implementar fallback explícito para banco local, marcando `origem="banco_local"` e `parcial=True` (R003-4)
- [ ] Conectar endpoint `/obras` ao novo schema de resposta, retornando sempre o bloco de metadados (R003-3)
- [ ] Adicionar logging estruturado por página com falha (nível WARNING) (R003-2)
- [ ] Escrever teste simulando falha de uma página específica, validando que as demais são coletadas e a falha é contabilizada (R003-2)
- [ ] Escrever teste simulando indisponibilidade total do PNCP, validando fallback local com `origem` e `parcial` corretos (R003-4)
