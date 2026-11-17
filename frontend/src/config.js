const configuredApiUrl = import.meta.env.VITE_API_URL?.trim();

if (!configuredApiUrl) {
  throw new Error(
    "VITE_API_URL não definida. Configure frontend/.env.development ou frontend/.env.production antes de executar o build.",
  );
}

export const API_URL = configuredApiUrl.replace(/\/$/, "");

export const SANDBOX_URL = import.meta.env.VITE_SANDBOX_URL?.trim() || "/sandbox.html";
