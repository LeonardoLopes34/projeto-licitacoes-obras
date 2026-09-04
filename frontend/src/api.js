import { API_URL } from "./config";

let activeController = null;

export function cancelarBuscaAtual() {
  activeController?.abort();
  activeController = null;
}

export async function buscarObras(params) {
  cancelarBuscaAtual();
  activeController = new AbortController();
  const query = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });

  const response = await fetch(`${API_URL}/obras?${query.toString()}`, {
    signal: activeController.signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || body.mensagem || detail;
    } catch {
      // Mantém a mensagem HTTP quando a resposta não for JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function buscarDocumentos({ cnpj, ano, sequencial, signal }) {
  const path = [cnpj, ano, sequencial]
    .map((value) => encodeURIComponent(String(value)))
    .join("/");

  const response = await fetch(`${API_URL}/obras/${path}/documentos`, {
    signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || body.mensagem || detail;
    } catch {
      // Mantém a mensagem HTTP quando a resposta não for JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function buscarExigencias({ cnpj, ano, sequencial, signal, forcar = false }) {
  const path = [cnpj, ano, sequencial]
    .map((value) => encodeURIComponent(String(value)))
    .join("/");
  const query = forcar ? "?forcar=true" : "";
  const response = await fetch(`${API_URL}/obras/${path}/exigencias${query}`, {
    signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || body.mensagem || detail;
    } catch {
      // Mantém a mensagem HTTP quando a resposta não for JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}
