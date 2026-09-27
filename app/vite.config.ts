import { resolve } from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";

// CSP solo en el build: en desarrollo, el refresh de React necesita un script inline.
const CSP =
  "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; " +
  "connect-src http://127.0.0.1:*; img-src 'self' data:; object-src 'none'; base-uri 'none'";
const cspPlugin: Plugin = {
  name: "nde1-csp",
  apply: "build",
  transformIndexHtml: () => [{ tag: "meta", attrs: { "http-equiv": "Content-Security-Policy", content: CSP }, injectTo: "head-prepend" }],
};

export default defineConfig(({ command }) => {
  if (command === "build" && process.env.VITE_FIXTURES === "1") {
    throw new Error("VITE_FIXTURES=1 es solo para desarrollo: nunca se empaqueta el modo ejemplos.");
  }
  return {
    base: "./",
    plugins: [react(), cspPlugin],
    server: { port: 5199, strictPort: true, fs: { allow: [resolve(import.meta.dirname, "..")] } },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      rollupOptions: {
        input: { main: resolve(import.meta.dirname, "index.html"), overlay: resolve(import.meta.dirname, "overlay.html") },
      },
    },
    test: { include: ["tests/**/*.test.ts"], environment: "node" },
  };
});
