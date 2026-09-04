# Tasks — Spec 008: Classificador/Filtro de Obras por Palavras-Chave

- [ ] Substituir comparação `in` por regex com word boundary em `backend/services/pncp_service.py:92` (R008-1)
- [ ] Definir dicionários de termos positivos, negativos e pesos (`TERMOS_POSITIVOS`, `TERMOS_NEGATIVOS`) (R008-2)
- [ ] Implementar `pontuar_obra()` e `classificar_obra()` com limiares de aprovado/revisão/rejeitado (R008-2)
- [ ] Adicionar coluna de status (`aprovado`/`revisao_pendente`/`rejeitado`) ao modelo `Obra` (conecta com Spec 007) (R008-4)
- [ ] Criar fixture `tests/fixtures/casos_filtro.json` com casos reais aprovados/rejeitados, incluindo os exemplos do relatório ("hospitalar", "cabo elétrico") (R008-3)
- [ ] Implementar `avaliar_filtro()` calculando precisão/cobertura contra a fixture (R008-5)
- [ ] Escrever teste automatizado de regressão que roda a fixture a cada execução de CI (R008-3, R008-5)
- [ ] Expor endpoint ou flag para listar itens `revisao_pendente` separadamente (conecta com Spec 009) (R008-4)
- [ ] Documentar processo de expansão da base de casos conforme novos falsos positivos/negativos forem identificados em produção (R008-3)
