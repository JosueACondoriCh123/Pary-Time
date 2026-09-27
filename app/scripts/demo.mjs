// La app sobre un data-dir de demo, nunca sobre los datos reales.
//   npm run demo       → <repo>/demo-data  (5 semanas simuladas por core.simulate, marcadas "sintetico")
//   npm run demo:live  → <repo>/demo-live  (bloque en vivo creado por tools/demo_live.py)
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const here = import.meta.dirname;
const repo = process.env.NDE1_REPO ?? resolve(here, "..", "..");
const mode = process.argv[2] === "live" ? "live" : "data";
const dir = join(repo, mode === "live" ? "demo-live" : "demo-data");
const howTo =
  mode === "live"
    ? ".venv\\Scripts\\python tools/demo_live.py --data-dir demo-live --in 2m --arm retrasar_distracciones"
    : ".venv\\Scripts\\python -m core.simulate --out demo-data --weeks 5 --seed 7";

function fail(msg) {
  console.error(`\n${msg}\n\nGeneralo desde la raíz del repo (${repo}):\n  ${howTo}\n`);
  process.exit(1);
}

if (!existsSync(dir)) fail(`No existe ${dir}.`);
const label = existsSync(join(dir, "DATA_LABEL")) ? readFileSync(join(dir, "DATA_LABEL"), "utf8").trim() : "";
if (label !== "sintetico") {
  // Protección: la demo nunca corre sobre un data-dir sin marcar, que podría ser el real.
  fail(`${dir} no tiene el marcador DATA_LABEL = sintetico.`);
}

const run = (cmd, args, env = process.env) =>
  new Promise((ok, ko) =>
    spawn(cmd, args, { stdio: "inherit", shell: process.platform === "win32", env }).on("exit", (code) =>
      code === 0 ? ok() : ko(new Error(`${cmd} ${args.join(" ")} salió con ${code}`)),
    ),
  );

await run("npm", ["run", "build"]);
console.log(`\nPary Time · demo sobre ${dir} (DATOS SINTÉTICOS)\n`);
const electron = (await import("electron")).default;
const env = { ...process.env, NDE1_DATA_DIR: dir, NDE1_REPO: repo };
delete env.VITE_DEV_SERVER_URL;
delete env.VITE_FIXTURES;
spawn(electron, ["."], { stdio: "inherit", env, cwd: resolve(here, "..") }).on("exit", (code) => process.exit(code ?? 0));
