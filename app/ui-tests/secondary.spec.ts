import { expect, test, type Page } from "@playwright/test";

const PROFILE_KEY = "nde1.local-profile.v1";
const demoEmail = "demo@example.com";
const demoPassword = "inventada-solo-demo-27";
const nav = (page: Page) => page.getByRole("navigation", { name: "Secciones" });

test.beforeEach(async ({ page }) => { await page.goto("/"); });

test("invitado puede abrir todas las herramientas sin pasar por autenticación", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Inicio", exact: true })).toBeVisible();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
  for (const section of ["Hoy", "Mi tiempo", "Planificar", "Experimento", "Resultados", "Reporte", "Ajustes"]) {
    await nav(page).getByRole("button", { name: section, exact: true }).click();
    await expect(nav(page).getByRole("button", { name: section, exact: true })).toHaveAttribute("aria-current", "page");
    await expect(page.locator("main h1")).toHaveCount(1);
    await expect(page.locator(".access-form")).toHaveCount(0);
  }
});

test("login y registro permiten entrar como invitado con formularios vacíos", async ({ page }) => {
  await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByText("ACCESO DE DEMOSTRACIÓN")).toBeVisible();
  await page.getByRole("button", { name: "Continuar como invitado" }).click();
  await expect(page.getByRole("heading", { name: "Inicio", exact: true })).toBeVisible();
  await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByRole("button", { name: "Crear perfil", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Creá tu espacio" })).toBeVisible();
  await page.getByRole("button", { name: "Continuar como invitado" }).click();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
});

test("perfil de invitado persiste en este dispositivo y personaliza inicio", async ({ page }) => {
  await nav(page).getByRole("button", { name: "Mi perfil" }).click();
  await page.getByLabel("¿Cómo te llamamos?").fill("  Alex  ");
  await page.getByRole("radio", { name: "Encontrar un ritmo sostenible" }).check();
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await expect(page.getByRole("status")).toContainText("guardado en este dispositivo");
  await page.reload();
  await expect(page.getByText("HOLA, Alex", { exact: true })).toBeVisible();
  await expect(page.getByText("Encontrar un ritmo sostenible", { exact: true })).toBeVisible();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
  await nav(page).getByRole("button", { name: "Mi perfil" }).click();
  await page.getByLabel("¿Cómo te llamamos?").fill("");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  await page.reload();
  await expect(page.getByText("UN NUEVO PUNTO DE PARTIDA")).toBeVisible();
});

test("demo de registro no transmite ni conserva credenciales; salir mantiene acceso", async ({ page }) => {
  const credentialRequests: string[] = [];
  page.on("request", (request) => {
    const contents = request.url() + (request.postData() ?? "");
    if (contents.includes(demoEmail) || contents.includes(demoPassword)) credentialRequests.push(request.method());
  });
  await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByRole("button", { name: "Crear perfil", exact: true }).click();
  await page.getByLabel("Nombre o apodo").fill("Luz Demo");
  await page.getByLabel("Correo de ejemplo").fill(demoEmail);
  await page.getByLabel("Contraseña de ejemplo", { exact: true }).fill(demoPassword);
  await page.getByRole("button", { name: "Crear perfil de demo", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mi perfil", exact: true })).toBeVisible();
  await expect(page.locator(".access-pill")).toHaveText("Sesión de demo");
  await page.getByRole("button", { name: "Guardar perfil" }).click();
  const stored = await page.evaluate(() => JSON.stringify({ local: { ...localStorage }, session: { ...sessionStorage } }));
  expect(stored).not.toContain(demoEmail);
  expect(stored).not.toContain(demoPassword);
  expect(credentialRequests).toEqual([]);
  await page.getByRole("main").getByRole("button", { name: "Salir de la demo" }).click();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
  await page.reload();
  await expect(page.getByText("HOLA, Luz Demo", { exact: true })).toBeVisible();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
});

test("login valida campos, permite mostrar contraseña y olvida la sesión al recargar", async ({ page }) => {
  await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByRole("button", { name: "Entrar a la demo" }).click();
  await expect(page.getByRole("heading", { name: "Qué bueno verte" })).toBeVisible();
  await page.getByLabel("Correo de ejemplo").fill(demoEmail);
  const password = page.getByLabel("Contraseña de ejemplo", { exact: true });
  await password.fill(demoPassword);
  await page.getByRole("button", { name: "Mostrar contraseña" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Ocultar contraseña" }).click();
  await expect(password).toHaveAttribute("type", "password");
  await page.getByRole("button", { name: "Entrar a la demo" }).click();
  await expect(page.locator(".access-pill")).toHaveText("Sesión de demo");
  await page.reload();
  await expect(page.locator(".access-pill")).toHaveText("Modo invitado");
  await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page.getByLabel("Correo de ejemplo")).toHaveValue("");
  await expect(page.getByLabel("Contraseña de ejemplo", { exact: true })).toHaveValue("");
});

test("perfil corrupto recupera inicio sin bloquear invitado", async ({ page }) => {
  await page.evaluate((key) => localStorage.setItem(key, "{incompleto"), PROFILE_KEY);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Inicio", exact: true })).toBeVisible();
  await page.evaluate((key) => localStorage.setItem(key, JSON.stringify({ displayName: 42, intention: "toString" })), PROFILE_KEY);
  await page.reload();
  await expect(page.getByText("Que empezar sea más fácil", { exact: true })).toBeVisible();
});

for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 740 }]) {
  test(`pantallas navegables sin desbordamiento a ${viewport.width}px`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize(viewport);
    const capture = async (name: string) => {
      await expect(page.locator("main h1")).toBeVisible();
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      if (viewport.width < 680) expect((await nav(page).boundingBox())!.height).toBeLessThan(130);
      if (name === "inicio") await expect(page.getByText("2 bloques planificados", { exact: true })).toBeVisible();
      await page.screenshot({ path: testInfo.outputPath(`${name}.png`), fullPage: true });
    };
    await capture("inicio");
    await nav(page).getByRole("button", { name: "Mi perfil" }).click();
    await capture("perfil");
    await nav(page).getByRole("button", { name: "Iniciar sesión" }).click();
    await capture("login");
    await page.getByRole("button", { name: "Crear perfil", exact: true }).click();
    await capture("signup");
    expect(errors).toEqual([]);
  });
}
