# Tasks — Spec 002: Paginação Completa da API do PNCP

- [ ] Separar `intervalo_dias` de `max_paginas` como parâmetros distintos em `pncp_service.py` (R002-4)
- [ ] Implementar loop de paginação usando `pagina` e `tamanhoPagina` conforme manual oficial do PNCP (R002-1)
- [ ] Continuar buscando páginas enquanto `pagina * tamanho_pagina < total_registros` e `pagina <= max_paginas` (R002-2)
- [ ] Produzir dicionário de metadados (`parcial`, `paginas_consultadas`, `paginas_com_erro`) ao final da busca (R002-3)
- [ ] Conectar metadados de paginação ao schema de resposta da Spec 003 (R002-3)
- [ ] Escrever teste unitário com mock de API retornando múltiplas páginas, validando que todas são coletadas (R002-1, R002-2)
- [ ] Escrever teste unitário com `max_paginas` menor que o necessário, validando `parcial=True` (R002-3)
- [ ] Validar manualmente contra a API real do PNCP que um intervalo de datas conhecido retorna o total esperado (R002-1)
