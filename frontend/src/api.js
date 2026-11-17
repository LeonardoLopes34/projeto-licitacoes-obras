import { API_URL } from "./config";

let activeController = null;

export class ApiError extends Error {
  constructor(message, { status, code } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function cancelarBuscaAtual() {
  activeController?.abort();
  activeController = null;
}

function montarQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null && item !== "") query.append(key, String(item));
      });
      return;
    }
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  return query;
}

export async function buscarObras(params) {
  cancelarBuscaAtual();
  activeController = new AbortController();
  const query = montarQuery(params);

  const response = await fetch(`${API_URL}/obras?${query.toString()}`, {
    signal: activeController.signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`;
    let code = null;
    try {
      const body = await response.json();
      const payload = body.detail || body;
      detail = typeof payload === "string" ? payload : payload.mensagem || body.mensagem || detail;
      code = typeof payload === "object" ? payload.code : null;
    } catch {
      // Mantém a mensagem HTTP quando a resposta não for JSON.
    }
    throw new ApiError(detail, { status: response.status, code });
  }

  return response.json();
}

export async function buscarObrasProgressivamente(params, { onProgress, onComplete } = {}) {
  cancelarBuscaAtual();
  activeController = new AbortController();
  const query = montarQuery(params);
  const response = await fetch(`${API_URL}/obras/stream?${query.toString()}`, {
    signal: activeController.signal,
    headers: { Accept: "text/event-stream" },
  });

  if (!response.ok || !response.body) {
    let detail = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail?.mensagem || body.detail || body.mensagem || detail;
    } catch {
      // Mantém a mensagem HTTP quando a resposta não for JSON.
    }
    throw new ApiError(detail, { status: response.status });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatchEvent = (block) => {
    const lines = block.split(/\r?\n/);
    const type = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() || "message";
    const data = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return;
    const payload = JSON.parse(data);
    if (type === "progresso") onProgress?.(payload);
    else if (type === "concluido") onComplete?.(payload);
    else if (type === "erro") throw new ApiError(payload.mensagem || "Falha ao consultar o PNCP.", { status: 502 });
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";
    blocks.forEach(dispatchEvent);
    if (done) break;
  }
  if (buffer.trim()) dispatchEvent(buffer);
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

export async function buscarTipoContratacao({ cnpj, ano, sequencial, modalidade, tipoInstrumento, signal }) {
  const path = [cnpj, ano, sequencial]
    .map((value) => encodeURIComponent(String(value)))
    .join("/");
  const query = new URLSearchParams();
  if (modalidade) query.set("modalidade", modalidade);
  if (tipoInstrumento) query.set("tipo_instrumento", tipoInstrumento);
  const queryString = query.toString() ? `?${query.toString()}` : "";

  const response = await fetch(`${API_URL}/obras/${path}/tipo${queryString}`, {
    signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Erro HTTP ${response.status}`);
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
