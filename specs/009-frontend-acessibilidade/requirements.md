# Spec 009 — Robustez e Acessibilidade do Frontend (React + Vite)

**Origem:** erro do backend não exibido (`App.jsx:110`, `StatusBar.jsx:13`); modal sem focus trap (`ObraDetailModal.jsx:7`); `role="button"` com link aninhado (`ObraCard.jsx:38`); `Math.random()` para IDs em render (`ObraCard.jsx:5`); selo de conformidade WCAG 2.2 AA sem auditoria (`AccessibilityFooter.jsx:21`); estatísticas do dashboard inconsistentes com `filteredObras`; filtro de UF só no frontend; `fetch` sem `res.ok`/`URLSearchParams`/proteção contra race condition; arquivos legados sem uso (`App.css`, `hero.png`, SVGs de template, `SandboxApp.jsx`, `mockVendasData.js`).
**Fase:** 4 — Frontend e Acessibilidade · **Bloqueia produção:** Não
**Depende de:** Spec 003 (metadados de erro/parcialidade), Spec 005 (config de API)

## Requisitos

| ID | Requisito |
|---|---|
| R009-1 | QUANDO o backend retornar `parcial: true` ou `origem: "banco_local"` ENTÃO a interface DEVE exibir essa informação de forma visível ao usuário. |
| R009-2 | QUANDO o modal de detalhes da obra abrir ENTÃO o foco DEVE mover-se para dentro do modal e ficar retido nele (focus trap) até o fechamento. |
| R009-3 | O card de obra NÃO DEVE usar `role="button"` contendo um elemento `<a>`/link interativo aninhado. |
| R009-4 | O sistema NÃO DEVE gerar identificadores via `Math.random()` durante a renderização; IDs DEVEM ser estáveis entre re-renders. |
| R009-5 | O sistema NÃO DEVE declarar conformidade WCAG 2.2 AA sem evidência de auditoria documentada. |
| R009-6 | O dashboard DEVE calcular estatísticas de forma consistente com o conjunto de dados exibido (`filteredObras`) quando há busca, filtro de UF ou ordenação aplicados. |
| R009-7 | O filtro de UF DEVE ser aplicado no backend quando o volume de dados justificar. |
| R009-8 | Toda chamada `fetch` DEVE verificar `res.ok`, construir query strings via `URLSearchParams`, e evitar condições de corrida entre requisições concorrentes. |
| R009-9 | O sistema NÃO DEVE manter arquivos legados sem uso comprovado no repositório. |

## Critérios de aceitação

- [ ] Erro/parcialidade do backend visível na UI em cenário de teste manual com falha simulada.
- [ ] Teste de acessibilidade automatizado confirma focus trap funcional no modal.
- [ ] Auditoria de acessibilidade (ferramenta automatizada) roda no CI e resultado é publicado — sem alegação de conformidade sem essa evidência.
- [ ] Estatísticas do dashboard batem com a lista exibida em cenário com filtro + busca + ordenação combinados.
- [ ] Filtro de UF com grande volume de dados é resolvido no backend, validado por teste de integração.
- [ ] Client `fetch` trata `res.ok = false` corretamente e cancela requisição anterior ao disparar nova busca em sequência rápida.
- [ ] Arquivos legados listados removidos do repositório sem quebrar build.
