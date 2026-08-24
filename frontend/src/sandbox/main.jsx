import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./sandbox.css";
import NeitImportsApp from "./NeitImportsApp.jsx";

const rootElement = document.getElementById("sandbox-root");
if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <NeitImportsApp />
    </StrictMode>
  );
}
