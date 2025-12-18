import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendHost = process.env.VITE_BACKEND_HOST ?? "127.0.0.1";
const backendPort = process.env.VITE_BACKEND_PORT ?? "8000";
const backendUrl = process.env.VITE_BACKEND_URL ?? `http://${backendHost}:${backendPort}`;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backendUrl,
    },
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
});
