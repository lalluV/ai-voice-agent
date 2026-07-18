import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_PROXY_TARGET || "http://127.0.0.1:8080";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/admin": { target, changeOrigin: true, secure: true },
        "/health": { target, changeOrigin: true, secure: true },
        "/metrics": { target, changeOrigin: true, secure: true },
        "/calls": { target, changeOrigin: true, secure: true },
      },
    },
  };
});
