// Smoke: la app empaquetada (dist/) lanza el núcleo real (.venv\Scripts\python -m core) y dibuja el planificador.
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";

let app: ElectronApplication;
let win: Page;
let dataDir: string;

test.beforeAll(async () => {
  dataDir = mkdtempSync(join(tmpdir(), "nde1-e2e-"));
  const env = { ...process.env, NDE1_DATA_DIR: dataDir } as Record<string, string>;
  delete env.VITE_DEV_SERVER_URL;
  delete env.VITE_FIXTURES;
  app = await electron.launch({ args: ["."], cwd: join(import.meta.dirname, ".."), env });
  win = await app.firstWindow();
  // La primera ventana puede ser el overlay: buscamos la principal.
  const pages = () => app.windows().filter((w) => w.url().endsWith("index.html"));
  await expect.poll(() => pages().length, { timeout: 15_000 }).toBeGreaterThan(0);
  win = pages()[0];
});

test.afterAll(async () => {
  await app?.close();
  rmSync(dataDir, { recursive: true, force: true });
});

test("el núcleo arranca y /health responde", async () => {
  const conn = await expect
    .poll(() => win.evaluate(() => window.nde1!.connection()), { timeout: 30_000 })
    .not.toBeNull()
    .then(() => win.evaluate(() => window.nde1!.connection()));
  expect(conn!.baseUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+$/);
  const health = await win.evaluate(async (base) => (await fetch(`${base}/health`)).json(), conn!.baseUrl);
  expect(health).toMatchObject({ ok: true, contracts: "contracts@1" });
  // Sin token, cualquier otra ruta da 401.
  const status = await win.evaluate(async (base) => (await fetch(`${base}/settings`)).status, conn!.baseUrl);
  expect(status).toBe(401);
});

test("el renderer está aislado y el token no queda guardado", async () => {
  const leaks = await win.evaluate(() => ({
    require: typeof (window as unknown as { require?: unknown }).require,
    process: typeof (window as unknown as { process?: unknown }).process,
    storage: JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }),
    url: location.href,
  }));
  const conn = await win.evaluate(() => window.nde1!.connection());
  expect(leaks.require).toBe("undefined");
  expect(leaks.process).toBe("undefined");
  expect(leaks.storage).not.toContain(conn!.token);
  expect(leaks.url).not.toContain(conn!.token);
});

test("si el núcleo muere, Electron lo relanza", async () => {
  const before = (await win.evaluate(() => window.nde1!.connection()))!;
  const port = new URL(before.baseUrl).port;
  // PID del proceso que escucha en ese puerto, y TerminateProcess como en una caída real.
  const netstat = execFileSync("netstat", ["-ano", "-p", "TCP"], { encoding: "utf8" });
  const line = netstat.split(/\r?\n/).find((l) => l.includes(`127.0.0.1:${port} `) && /LISTENING/.test(l));
  expect(line, `nadie escucha en ${port}`).toBeTruthy();
  const pid = line!.trim().split(/\s+/).at(-1)!;
  execFileSync("taskkill", ["/PID", pid, "/F"]);

  await expect
    .poll(async () => (await win.evaluate(() => window.nde1!.connection()))?.baseUrl ?? null, { timeout: 30_000 })
    .not.toBe(before.baseUrl);
  const after = await expect
    .poll(() => win.evaluate(() => window.nde1!.connection()), { timeout: 30_000 })
    .not.toBeNull()
    .then(() => win.evaluate(() => window.nde1!.connection()));
  const health = await win.evaluate(async (base) => (await fetch(`${base}/health`)).json(), after!.baseUrl);
  expect(health.ok).toBe(true);
  expect(after!.token).toBe(before.token); // mismo token de sesión
});

test("dibuja el planificador", async () => {
  await win.getByRole("button", { name: "Planificar" }).click();
  await expect(win.getByRole("heading", { name: /Planificá (mañana|hoy)/ })).toBeVisible();
  await expect(win.getByText("DATOS DE EJEMPLO")).toHaveCount(0);
  await win.screenshot({ path: "test-results/planificador.png" });
});
