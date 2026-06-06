import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// In dev, Vite serves the UI on :5173 and proxies API + WebSocket to the Core
// Service on :8080. In production, `vite build` emits ./dist, which the Core
// Service serves itself (see core/homecontrol/app.py) so a unit runs one process.
export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
      "/ws": { target: "ws://localhost:8080", ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
