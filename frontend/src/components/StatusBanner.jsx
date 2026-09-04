import React from "react";

export default function StatusBanner({ statusInfo }) {
  if (!statusInfo) return null;

  const metadata = statusInfo.metadados || statusInfo;
  const isError = statusInfo.status === "erro";
  const isOffline = metadata.origem === "banco_local";
  const isCache = metadata.origem === "cache";
  const isPartial = Boolean(metadata.parcial);

  if (!isError && !isOffline && !isCache && !isPartial) return null;

  const tone = isError ? "error" : isOffline || isCache || isPartial ? "warning" : "info";
  const message = isError
      ? statusInfo.mensagem
      : isOffline || isCache
        ? "Exibindo dados salvos localmente; o PNCP não respondeu agora."
        : isPartial
        ? statusInfo.mensagem ||
          `Resultado parcial: ${metadata.paginas_com_erro || 0} página(s) falharam durante a busca.`
        : statusInfo.mensagem;

  return (
    <div
      role={isError ? "alert" : "status"}
      aria-live="polite"
      className={`rounded-xl border px-4 py-3 text-sm ${
        tone === "error"
          ? "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-200"
          : tone === "warning"
            ? "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200"
            : "border-blue-500/40 bg-blue-500/10 text-blue-800 dark:text-blue-200"
      }`}
    >
      <strong className="font-semibold">
        {isError ? "Não foi possível concluir a busca." : isOffline || isCache ? "Modo offline" : isPartial ? "Busca parcial" : "Status da busca"}
      </strong>{" "}
      <span>{message}</span>
    </div>
  );
}
