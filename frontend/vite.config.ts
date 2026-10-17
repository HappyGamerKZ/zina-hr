import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В dev-режиме Vite проксирует API на Django, как nginx в docker compose: один origin, cookie работают.
const backend = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // В docker-compose.dev.yml: изменения файлов с Windows доходят до контейнера только опросом
    watch: process.env.VITE_USE_POLLING ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      "/api": backend,
      "/admin": backend,
      "/static": backend,
    },
  },
});
