import { defineConfig } from "@playwright/test";

// UI real en navegador y ejemplos de contratos existentes. No arranca sensor ni Electron.
export default defineConfig({
  testDir: "ui-tests",
  timeout: 30_000,
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results/secondary",
  use: {
    baseURL: "http://127.0.0.1:5207",
    channel: process.platform === "win32" ? "msedge" : undefined,
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: "node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5207",
    url: "http://127.0.0.1:5207",
    env: { VITE_FIXTURES: "1" },
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
