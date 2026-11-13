/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In dev, Vite proxies /api to the Django API so the SPA and API share one origin, as they do behind
// nginx/Traefik in the cluster. Override the target with API_PROXY_TARGET.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000", changeOrigin: false } },
  },
  preview: { host: "127.0.0.1", port: 4173 },
  build: { sourcemap: false, chunkSizeWarningLimit: 900 },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    css: false,
    env: { VITE_API_BASE_URL: "http://localhost" },
  },
});
