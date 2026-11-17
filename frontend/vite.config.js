import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "path";

const frontendRoot = resolve(import.meta.dirname || process.cwd());
const projectRoot = resolve(frontendRoot, "..");

// https://vite.dev/config/
export default defineConfig({
  envDir: projectRoot,
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(frontendRoot, "index.html"),
        sandbox: resolve(frontendRoot, "sandbox.html"),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
    css: true,
  },
});
