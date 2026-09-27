// Capturas para el README y el video: la app (build actual) sobre <repo>/demo-data → docs/hackathon/img/*.png.
//   npm run shots            (hace el build antes)
// Requiere demo-data generado por core.simulate y marcado "sintetico".
import { existsSync, mkdirSync, mkdtempSync, cpSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
/* global window -- código que corre en el renderer vía evaluate */
import { _electron as electron } from "@playwright/test";

const here = import.meta.dirname;
const repo = process.env.NDE1_REPO ?? resolve(here, "..", "..");
const source = process.env.NDE1_SHOTS_DATA ?? join(repo, "demo-data");
const out = process.env.NDE1_SHOTS_OUT ?? join(repo, "docs", "hackathon", "img");

if (!existsSync(join(source, "DATA_LABEL")) || readFileSync(join(source, "DATA_LABEL"), "utf8").trim() !== "sintetico") {
  console.error(`Falta ${source} marcado como sintetico. Generalo con:\n  .venv\\Scripts\\python -m core.simulate --out demo-data --weeks 5 --seed 7`);
  process.exit(1);
}
mkdirSync(out, { recursive: true });

// Copia descartable: las capturas no escriben en demo-data (el sensor y el scheduler corren igual).
const dataDir = mkdtempSync(join(tmpdir(), "nde1-shots-"));
cpSync(source, dataDir, { recursive: true });

const env = { ...process.env, NDE1_DATA_DIR: dataDir, NDE1_REPO: repo, NDE1_USER_DATA: join(dataDir, "_userdata") };
for (const k of ["VITE_DEV_SERVER_URL", "VITE_FIXTURES"]) delete env[k];
const app = await electron.launch({ args: ["."], cwd: resolve(here, ".."), env });
try {
  let win;
  for (let i = 0; i < 100 && !win; i++) {
    win = app.windows().find((w) => w.url().endsWith("index.html"));
    if (!win) await new Promise((r) => setTimeout(r, 200));
  }
  await win.bringToFront();
  for (let i = 0; i < 150; i++) {
    if (await win.evaluate(() => window.nde1?.connection().then((c) => !!c))) break;
    await win.waitForTimeout(200);
  }
  await win.getByText("DATOS SINTÉTICOS").waitFor({ timeout: 15_000 });

  const size = () =>
    app.evaluate(({ BrowserWindow }) => {
      for (const w of BrowserWindow.getAllWindows()) if (w.isVisible()) w.setContentSize(1280, 860);
    });
  // [nav, archivo, página completa]: las vistas largas se capturan enteras.
  const shots = [
    ["Planificar", "planificador", false],
    ["Hoy", "hoy", false],
    ["Mi tiempo", "mi-tiempo", true],
    ["Reporte", "reporte", false],
    ["Experimento", "consejo", true],
    ["Resultados", "resultados", true],
  ];
  for (const [nav, name, full] of shots) {
    await size();
    await win.getByRole("button", { name: nav, exact: true }).click();
    await win.locator(".nav-item.on", { hasText: nav }).waitFor();
    await win.mouse.move(1270, 850); // sin hover sobre la barra lateral
    await win.waitForTimeout(2000);
    await win.evaluate(() => window.getSelection()?.removeAllRanges());
    await win.screenshot({ path: join(out, `${name}.png`), fullPage: full });
    console.log(join(out, `${name}.png`));
  }
} finally {
  await app.close();
  rmSync(dataDir, { recursive: true, force: true });
}
