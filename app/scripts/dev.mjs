// Desarrollo: servidor de Vite + Electron apuntando a él. `--fixtures` activa el modo ejemplos.
import { spawn } from "node:child_process";
import { createServer } from "vite";

const fixtures = process.argv.includes("--fixtures");
if (fixtures) process.env.VITE_FIXTURES = "1";

await import("./build-electron.mjs");
const server = await createServer({ configFile: "vite.config.ts" });
await server.listen();
const url = server.resolvedUrls.local[0];
console.log(`renderer en ${url}${fixtures ? " (DATOS DE EJEMPLO)" : ""}`);

const electronBin = (await import("electron")).default;
const child = spawn(electronBin, ["."], {
  stdio: "inherit",
  env: { ...process.env, VITE_DEV_SERVER_URL: url },
});
child.on("exit", async (code) => {
  await server.close();
  process.exit(code ?? 0);
});
