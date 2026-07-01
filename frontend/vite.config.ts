import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:6000", changeOrigin: true },
      "/ws":  { target: "ws://localhost:6000",  ws: true, changeOrigin: true },
      "/static": { target: "http://localhost:6000", changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});