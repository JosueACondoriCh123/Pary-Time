// GIF del runtime en vivo para el README: overlay → minimiza distracciones → reabrir → se re-minimiza → emergencia.
// ¡Mueve ventanas reales! Graba el escritorio completo: antes, dejá en pantalla solo lo que se puede publicar.
//   npm run gif      (hace el build antes; salida en docs/hackathon/img/demo-live.gif)
import { spawn, execFileSync } from "node:child_process";
import { mkdirSync, rmSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { _electron as electron } from "@playwright/test";

const here = import.meta.dirname;
const repo = process.env.NDE1_REPO ?? resolve(here, "..", "..");
const python = join(repo, existsSync(join(repo, ".venv")) ? ".venv" : "../.venv", "Scripts", "python.exe");
const dataDir = join(repo, "demo-live");
const out = process.env.NDE1_GIF_OUT ?? join(repo, "docs", "hackathon", "img", "demo-live.gif");
const video = join(tmpdir(), `nde1-demo-${Date.now()}.mp4`);
const LEAD_S = 45; // el bloque empieza 45 s después de preparar el directorio
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Reabre las ventanas minimizadas por la intervención, como haría la persona.
const REOPEN = `
from core.runtime.interventions import default_window_ops, select_distractions
from core.sensing.categorize import categorize
from core.contracts import Settings
ops = default_window_ops()
n = 0
for w in select_distractions(ops.windows(), Settings(), categorize):
    if ops.is_minimized(w.hwnd):
        ops.restore(w.hwnd, w.pid); n += 1
print(n)
`;

rmSync(dataDir, { recursive: true, force: true });
execFileSync(python, ["tools/demo_live.py", "--data-dir", dataDir, "--in", `${LEAD_S}s`, "--arm", "retrasar_distracciones"], {
  cwd: repo,
  stdio: "inherit",
});
const startAt = Date.now() + LEAD_S * 1000;

const env = { ...process.env, NDE1_DATA_DIR: dataDir, NDE1_REPO: repo };
for (const k of ["VITE_DEV_SERVER_URL", "VITE_FIXTURES"]) delete env[k];
const app = await electron.launch({ args: ["."], cwd: resolve(here, ".."), env });
let ffmpeg;
let ffmpegDone = Promise.resolve();
let crop;
try {
  let win;
  for (let i = 0; i < 100 && !win; i++) {
    win = app.windows().find((w) => w.url().endsWith("index.html"));
    if (!win) await sleep(200);
  }
  await win.getByRole("button", { name: "Hoy", exact: true }).click();
  // Recorte: desde el borde izquierdo de la app hasta la derecha de la pantalla (app + overlay + barra de tareas),
  // para no publicar lo que haya a la izquierda del escritorio.
  crop = await app.evaluate(({ BrowserWindow, screen }) => {
    const main = BrowserWindow.getAllWindows().find((w) => w.isVisible() && w.isFocusable());
    const d = screen.getPrimaryDisplay();
    const x = Math.max(0, Math.round(((main?.getBounds().x ?? 0) - d.bounds.x) * d.scaleFactor));
    const width = Math.round(d.bounds.width * d.scaleFactor) - x;
    return { x, width: width - (width % 2) };
  });

  // Graba desde 15 s antes de la hora del bloque.
  await sleep(Math.max(0, startAt - 15_000 - Date.now()));
  ffmpeg = spawn("ffmpeg", ["-y", "-f", "gdigrab", "-framerate", "10", "-i", "desktop", "-pix_fmt", "yuv420p", video], {
    stdio: ["pipe", "ignore", "ignore"],
  });
  ffmpegDone = new Promise((r) => ffmpeg.on("exit", r)); // escuchar desde ya: puede salir antes de esperarlo
  await sleep(Math.max(0, startAt + 8_000 - Date.now())); // minimizado a la hora
  const reopened = execFileSync(python, ["-c", REOPEN], { cwd: repo, encoding: "utf8" }).trim();
  console.log(`reabiertas: ${reopened}`);
  await sleep(7_000); // se vuelven a minimizar
  await win.getByRole("button", { name: "Salida de emergencia" }).first().click();
  await sleep(5_000);
} finally {
  // Pase lo que pase, las ventanas de la persona vuelven a su lugar.
  try {
    execFileSync(python, ["-c", REOPEN], { cwd: repo });
  } catch {
    /* sin ventanas para restaurar */
  }
  ffmpeg?.stdin.write("q");
  await ffmpegDone;
  await app.close();
}

mkdirSync(resolve(out, ".."), { recursive: true });
const cropFilter = crop ? `crop=${crop.width}:ih:${crop.x}:0,` : "";
execFileSync("ffmpeg", [
  "-y", "-i", video,
  "-vf", cropFilter + "fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer",
  out,
], { stdio: "ignore" });
rmSync(video, { force: true });
console.log(out);
