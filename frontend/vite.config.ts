import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    // The Python package serves the built app (spec-web.md §3.2).
    outDir: fileURLToPath(new URL("../src/avideo/server/static", import.meta.url)),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // During development, API and WebSocket calls go to `avideo serve`.
      "/api": { target: "http://127.0.0.1:8765", ws: true },
    },
  },
});
