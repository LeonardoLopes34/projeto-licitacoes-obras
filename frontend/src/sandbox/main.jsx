import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./sandbox.css";
import SandboxApp from "./SandboxApp.jsx";

const rootElement = document.getElementById("sandbox-root");
if (rootElement) {
  createRoot(rootElement).render(
    <StrictMode>
      <SandboxApp />
    </StrictMode>
  );
}
