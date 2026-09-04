# Spec 001 — TLS / Verificação de Certificado

**Origem:** `backend/services/pncp_service.py:414`, `test_pncp.py:24` (`verify=False`)
**Fase:** 1 — Segurança e Infraestrutura · **Bloqueia produção:** Sim

## Contexto

O backend e o script de teste desativam a verificação de certificado TLS ao chamar a API do PNCP (`verify=False`), permitindo conexão HTTPS sem validar o certificado do servidor — uma falha crítica de segurança (exposição a man-in-the-middle).

## Requisitos

| ID | Requisito |
|---|---|
| R001-1 | O sistema DEVE realizar todas as chamadas HTTPS ao PNCP com verificação de certificado ativa (`verify=True`, padrão do `requests`/`httpx`). |
| R001-2 | SE a verificação de certificado falhar ENTÃO o sistema DEVE registrar o erro (log) e retornar falha explícita, nunca dado parcial silencioso. |
| R001-3 | O sistema NÃO DEVE conter `verify=False` em nenhum arquivo de produção ou teste. |

## Critérios de aceitação

- [ ] Nenhuma ocorrência de `verify=False` no repositório (`grep -r "verify=False"` retorna vazio).
- [ ] Chamada real ao PNCP funciona com verificação de certificado ativa.
- [ ] Falha de verificação de certificado é logada e propagada como erro explícito, não como lista vazia/sucesso parcial silencioso.
- [ ] Teste automatizado (lint/CI) impede reintrodução de `verify=False`.
