// La app empaquetada (release/win-unpacked) lanza el núcleo congelado de A (resources/nde1-core/nde1-core.exe).
// Se saltea si no hay build con sidecar: `npm run dist:dir` después de construir packaging/sidecar.spec.
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { _electron as electron, expect, test, type ElectronApplication, type Page } from "@playwright/test";

const unpacked = join(import.meta.dirname, "..", "release", "win-unpacked");
const exe = join(unpacked, "Consejo N-de-1.exe");
const sidecar = join(unpacked, "resources", "nde1-core", "nde1-core.exe");

test.skip(!existsSync(exe) || !existsSync(sidecar), "sin build empaquetado con sidecar");

let app: ElectronApplication;
let win: Page;
let dataDir: string;

test.beforeAll(async () => {
  dataDir = mkdtempSync(join(tmpdir(), "nde1-pkg-"));
  const env = { ...process.env, NDE1_DATA_DIR: dataDir, NDE1_NO_LOGIN_ITEM: "1", NDE1_USER_DATA: join(dataDir, "_userdata") } as Record<string, string>;
  for (const k of ["VITE_DEV_SERVER_URL", "VITE_FIXTURES", "NDE1_PYTHON", "NDE1_REPO"]) delete env[k];
  app = await electron.launch({ executablePath: exe, env });
  const pages = () => app.windows().filter((w) => w.url().endsWith("index.html"));
  await expect.poll(() => pages().length, { timeout: 20_000 }).toBeGreaterThan(0);
  win = pages()[0];
  await win.bringToFront(); // el chequeo de estabilidad del clic usa requestAnimationFrame
});

test.afterAll(async () => {
  await app?.close();
  rmSync(dataDir, { recursive: true, force: true });
});

test("empaquetada: arranca el núcleo congelado y responde", async () => {
  expect(await app.evaluate(({ app: a }) => a.isPackaged)).toBe(true);
  await expect.poll(() => win.evaluate(() => window.nde1!.connection()), { timeout: 45_000 }).not.toBeNull();
  const conn = (await win.evaluate(() => window.nde1!.connection()))!;
  const health = await win.evaluate(async (base) => (await fetch(`${base}/health`)).json(), conn.baseUrl);
  expect(health).toMatchObject({ ok: true, contracts: expect.stringMatching(/^contracts@1(\.\d+)?$/) });
  // Con token: una ruta real de A (sensor) y la verificación del journal.
  const today = await win.evaluate(
    async ({ base, token }) => (await fetch(`${base}/activity/today`, { headers: { "X-NDE1-Token": token } })).status,
    { base: conn.baseUrl, token: conn.token },
  );
  expect(today).toBe(200);
  const verify = await win.evaluate(
    async ({ base, token }) => (await fetch(`${base}/journal/verify`, { headers: { "X-NDE1-Token": token } })).json(),
    { base: conn.baseUrl, token: conn.token },
  );
  expect(verify.ok).toBe(true);
});

test("empaquetada: la vista Hoy muestra el sensor midiendo", async () => {
  await win.getByRole("button", { name: "Hoy", exact: true }).click();
  await expect(win.getByText(/Sensor: (midiendo|en pausa)/)).toBeVisible({ timeout: 15_000 });
  await win.screenshot({ path: "test-results/empaquetada-hoy.png" });
});
