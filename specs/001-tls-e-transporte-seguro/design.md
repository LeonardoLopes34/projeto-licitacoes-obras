# Design — Spec 001: TLS / Verificação de Certificado

## Abordagem

1. Remover `verify=False` das duas ocorrências conhecidas (`pncp_service.py:414`, `test_pncp.py:24`).
2. Investigar a causa raiz: provavelmente erro de cadeia de certificado (proxy corporativo, certificado autoassinado em ambiente de desenvolvimento, ou biblioteca de CA desatualizada).
3. Resolver a causa raiz sem desativar a verificação:
   - Se o problema é um proxy/CA corporativo: apontar `REQUESTS_CA_BUNDLE` (ou `SSL_CERT_FILE`, dependendo da lib HTTP usada) para o certificado correto via variável de ambiente.
   - Se o problema é `certifi` desatualizado: atualizar a dependência.
4. Tratamento de erro explícito: capturar especificamente `requests.exceptions.SSLError` (ou equivalente em `httpx`) e propagar como falha de conexão com mensagem clara — nunca engolir como retorno vazio (isso se conecta à Spec 003).

## Trecho ilustrativo

```python
# Antes (inseguro)
response = requests.get(url, params=params, verify=False)

# Depois
try:
    response = requests.get(url, params=params, timeout=30)  # verify=True é o padrão
    response.raise_for_status()
except requests.exceptions.SSLError as e:
    logger.error("Falha de verificação de certificado TLS ao acessar PNCP: %s", e)
    raise PNCPConnectionError("Certificado TLS inválido ao acessar a API do PNCP") from e
```

## Guard-rail de CI

Adicionar um passo simples ao pipeline (ou a um `pre-commit` hook) que falha se `verify=False` ou `ssl._create_unverified_context` aparecer em qualquer arquivo `.py` versionado:

```bash
if grep -rn "verify=False\|_create_unverified_context" --include="*.py" .; then
  echo "TLS verification disabled — bloqueado por política de segurança (Spec 001)"
  exit 1
fi
```

## Impacto em outras specs

- Spec 003 (Tratamento de erros): o erro de TLS deve alimentar o mesmo mecanismo de metadados de falha (`paginas_com_erro`, `origem`).
