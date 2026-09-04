# Design — Spec 009: Robustez e Acessibilidade do Frontend (React + Vite)

## StatusBanner (R009-1)

```jsx
function StatusBanner({ statusInfo }) {
  if (!statusInfo) return null;
  if (statusInfo.origem === "banco_local") {
    return <div role="status" className="banner banner-warning">
      Exibindo dados do último cache local — não foi possível consultar o PNCP agora.
    </div>;
  }
  if (statusInfo.parcial) {
    return <div role="status" className="banner banner-info">
      Resultado parcial: {statusInfo.paginas_com_erro} página(s) falharam durante a busca.
    </div>;
  }
  return null;
}
```
Renderizado a partir do `statusInfo` já armazenado em `App.jsx` (hoje calculado mas não exibido).

## Focus trap no modal (R009-2)

```jsx
function ObraDetailModal({ obra, onClose }) {
  const modalRef = useRef(null);
  const previouslyFocused = useRef(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement;
    modalRef.current?.focus();
    return () => previouslyFocused.current?.focus();
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") onClose();
    if (e.key === "Tab") {
      const focusables = modalRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const [first, last] = [focusables[0], focusables[focusables.length - 1]];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };

  return (
    <div role="dialog" aria-modal="true" ref={modalRef} tabIndex={-1} onKeyDown={handleKeyDown}>
      {/* conteúdo do modal */}
    </div>
  );
}
```
(Alternativa: usar a lib `focus-trap-react` em vez de implementação manual.)

## Card sem role/link aninhado (R009-3)

```jsx
// Antes: <div role="button" onClick={...}><a href={link}>...</a></div>
// Depois: escolher UM elemento interativo
<article className="obra-card">
  <h3>{obra.titulo}</h3>
  <a href={obra.link} className="obra-card-link">Ver detalhes</a>
</article>
```

## IDs estáveis (R009-4)

```jsx
// Antes: key={Math.random()}
// Depois: usar o identificador natural do dado
{obras.map((obra) => (
  <ObraCard key={obra.numeroControlePNCP} obra={obra} />
))}
```

## Selo de acessibilidade (R009-5)

Remover a alegação fixa de conformidade WCAG 2.2 AA do rodapé, ou substituí-la por um resultado real de auditoria (`axe-core`/Lighthouse) versionado e datado, ex.: "Última auditoria automatizada de acessibilidade: 2026-08-20 — ver relatório".

## Estatísticas consistentes (R009-6)

```jsx
// Antes: estatísticas calculadas sobre `obras` (todas), volume/contagem sobre `filteredObras`
// Depois: uma única fonte
const stats = useMemo(() => calcularEstatisticas(filteredObras), [filteredObras]);
```

## Filtro de UF no backend (R009-7)

```jsx
fetch(`${API_URL}/obras?${new URLSearchParams({ uf: ufSelecionada })}`);
```
```python
@router.get("/obras")
async def listar_obras(uf: str | None = None, ...):
    query = query.filter(Obra.uf == uf) if uf else query
```

## Client fetch centralizado (R009-8)

```js
// src/api.js
let controladorAtual;

export async function buscarObras(params) {
  controladorAtual?.abort();
  controladorAtual = new AbortController();
  const query = new URLSearchParams(params);
  const res = await fetch(`${API_URL}/obras?${query}`, { signal: controladorAtual.signal });
  if (!res.ok) throw new Error(`Erro ${res.status} ao buscar obras`);
  return res.json();
}
```

## Limpeza de legados (R009-9)

```bash
for f in App.css hero.png SandboxApp.jsx mockVendasData.js; do
  grep -rl "$f" --include="*.jsx" --include="*.js" src/ || echo "$f: sem referências, candidato à remoção"
done
```
