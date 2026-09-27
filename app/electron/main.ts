// Proceso principal: sidecar, ventana, overlay, bandeja y arranque con Windows.
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { app, BrowserWindow, dialog, ipcMain, Menu, screen, shell, Tray } from "electron";
import type { Connection, NavTarget, Prefs } from "../src/bridge";
import { trayIcon } from "./icon";
import { loadPrefs, savePrefs } from "./prefs";
import { Sidecar } from "./sidecar";
import { coreCommand } from "./sidecar-logic";

const DEV_URL = process.env.VITE_DEV_SERVER_URL;
const REPO_ROOT = process.env.NDE1_REPO ?? resolve(__dirname, "..", "..");
const TOKEN = randomBytes(32).toString("hex"); // solo en la memoria de este proceso y del renderer

let mainWin: BrowserWindow | null = null;
let overlayWin: BrowserWindow | null = null;
let tray: Tray | null = null;
let quitting = false;

// Tests, capturas y GIF usan su propia carpeta de usuario: conviven con la app abierta y no tocan sus preferencias.
if (process.env.NDE1_USER_DATA) app.setPath("userData", process.env.NDE1_USER_DATA);

// Dos núcleos no pueden compartir el data-dir: la segunda instancia solo le pasa el foco a la primera.
const primary = app.requestSingleInstanceLock();
if (!primary) app.exit(0);

const dataDir = process.env.NDE1_DATA_DIR ?? join(app.getPath("userData"), "data");
const prefsPath = join(app.getPath("userData"), "prefs.json");

const sidecar = new Sidecar(
  () =>
    coreCommand({
      packaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      repoRoot: REPO_ROOT,
      dataDir,
      exists: existsSync,
      pythonOverride: process.env.NDE1_PYTHON,
    }),
  TOKEN,
);

function connection(): Connection | null {
  return sidecar.state.phase === "ready" ? { baseUrl: sidecar.state.baseUrl, token: TOKEN } : null;
}

async function callCore(method: string, path: string): Promise<number> {
  const conn = connection();
  if (!conn) return 0;
  try {
    const res = await fetch(conn.baseUrl + path, { method, headers: { "X-NDE1-Token": conn.token } });
    return res.status;
  } catch {
    return 0;
  }
}

function load(win: BrowserWindow, page: "index" | "overlay") {
  if (DEV_URL) void win.loadURL(new URL(page === "index" ? "" : "overlay.html", DEV_URL).toString());
  else void win.loadFile(join(__dirname, "..", "dist", `${page}.html`));
}

const secureWebPrefs = {
  preload: join(__dirname, "preload.cjs"),
  contextIsolation: true,
  nodeIntegration: false,
  sandbox: true,
};

function lockNavigation(win: BrowserWindow) {
  // Links externos al navegador; la app nunca navega fuera de sus páginas.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) void shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (DEV_URL && url.startsWith(DEV_URL)) return;
    e.preventDefault();
  });
}

function createMainWindow() {
  mainWin = new BrowserWindow({
    width: 1100,
    height: 800,
    minWidth: 760,
    minHeight: 560,
    title: "Consejo N-de-1",
    backgroundColor: "#101318",
    icon: trayIcon(64),
    show: !process.argv.includes("--hidden"),
    autoHideMenuBar: true,
    webPreferences: secureWebPrefs,
  });
  lockNavigation(mainWin);
  load(mainWin, "index");
  // Cerrar la ventana la esconde: la app sigue midiendo desde la bandeja.
  mainWin.on("close", (e) => {
    if (!quitting) {
      e.preventDefault();
      mainWin?.hide();
    }
  });
}

function createOverlayWindow() {
  const { workArea } = screen.getPrimaryDisplay();
  const width = 460;
  const height = 160;
  overlayWin = new BrowserWindow({
    width,
    height,
    x: workArea.x + workArea.width - width - 16,
    y: workArea.y + 16,
    frame: false,
    transparent: true,
    resizable: false,
    movable: false,
    focusable: false,
    skipTaskbar: true,
    show: false,
    hasShadow: false,
    alwaysOnTop: true,
    webPreferences: secureWebPrefs,
  });
  overlayWin.setAlwaysOnTop(true, "screen-saver");
  overlayWin.setIgnoreMouseEvents(true, { forward: true });
  lockNavigation(overlayWin);
  load(overlayWin, "overlay");
  // Si Windows o un crash del renderer la destruyen, se suelta la referencia y se rehace.
  overlayWin.on("closed", () => {
    overlayWin = null;
    if (!quitting) createOverlayWindow();
  });
}

function showMain(to?: NavTarget) {
  if (!mainWin || mainWin.isDestroyed()) return;
  if (mainWin.isMinimized()) mainWin.restore();
  mainWin.show();
  mainWin.focus();
  if (to) mainWin.webContents.send("nde1:navigate", to);
}

function notify(title: string, content: string) {
  tray?.displayBalloon({ title, content, iconType: "info" });
}

function statusMessage(status: number, okText: string): string {
  if (status >= 200 && status < 300) return okText;
  if (status === 501) return "Todavía no disponible en esta versión.";
  if (status === 409) return "No se puede ahora: el estado cambió.";
  if (status === 0) return "El núcleo no está listo todavía.";
  return `El núcleo respondió ${status}.`;
}

function createTray() {
  tray = new Tray(trayIcon(32));
  tray.setToolTip("Consejo N-de-1");
  const pause = async (minutes: number) => {
    const status = await callCore("POST", `/activity/pause?minutes=${minutes}`);
    notify("Sensor", statusMessage(status, `Sensor en pausa ${minutes} min.`));
  };
  const emergency = async () => {
    const status = await callCore("POST", "/runtime/emergency_release");
    notify("Salida de emergencia", statusMessage(status, "Listo: restauré todas las ventanas."));
  };
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Abrir", click: () => showMain() },
      { label: "Planificar mañana", click: () => showMain("planner") },
      { type: "separator" },
      { label: "Pausar sensor 30 min", click: () => void pause(30) },
      { label: "Pausar sensor 60 min", click: () => void pause(60) },
      { label: "Salida de emergencia", click: () => void emergency() },
      { type: "separator" },
      {
        label: "Salir",
        click: () => {
          quitting = true;
          app.quit();
        },
      },
    ]),
  );
  tray.on("click", () => showMain());
}

function applyLoginItem(prefs: Prefs) {
  // En desarrollo registraría el electron.exe pelado; en los tests e2e, el exe de release/.
  if (!app.isPackaged || process.env.NDE1_NO_LOGIN_ITEM === "1") return;
  app.setLoginItemSettings({ openAtLogin: prefs.openAtLogin, args: ["--hidden"] });
}

function registerIpc() {
  ipcMain.handle("nde1:sidecar", () => sidecar.state);
  ipcMain.handle("nde1:connection", () => connection());
  ipcMain.handle("nde1:retry", () => sidecar.retry());
  ipcMain.handle("nde1:pick-file", async () => {
    const opts = { properties: ["openFile" as const], title: "Elegí el archivo de trabajo" };
    const r = mainWin ? await dialog.showOpenDialog(mainWin, opts) : await dialog.showOpenDialog(opts);
    return r.canceled ? null : (r.filePaths[0] ?? null);
  });
  ipcMain.handle("nde1:save-file", async (_e, arg: { defaultName: string; content: string; ext: "html" | "json" }) => {
    const opts = { defaultPath: arg.defaultName, filters: [{ name: arg.ext.toUpperCase(), extensions: [arg.ext] }] };
    const r = mainWin ? await dialog.showSaveDialog(mainWin, opts) : await dialog.showSaveDialog(opts);
    if (r.canceled || !r.filePath) return false;
    writeFileSync(r.filePath, arg.content, "utf8");
    return true;
  });
  ipcMain.handle("nde1:prefs", () => loadPrefs(prefsPath));
  ipcMain.handle("nde1:set-prefs", (_e, patch: Partial<Prefs>) => {
    const next = { ...loadPrefs(prefsPath), ...patch };
    savePrefs(prefsPath, next);
    applyLoginItem(next);
    return next;
  });
  ipcMain.on("nde1:overlay-visible", (e, visible: boolean) => {
    if (!overlayWin || overlayWin.isDestroyed() || e.sender !== overlayWin.webContents) return;
    if (visible) {
      // YouTube a pantalla completa se sube después: hay que volver a pedir el tope.
      overlayWin.setAlwaysOnTop(true, "screen-saver");
      if (!overlayWin.isVisible()) overlayWin.showInactive();
    } else if (overlayWin.isVisible()) overlayWin.hide();
  });
}

if (primary) {
  app.on("second-instance", () => showMain());

  void app.whenReady().then(() => {
    mkdirSync(dataDir, { recursive: true });
    registerIpc();
    sidecar.on("state", (state) => {
      for (const win of BrowserWindow.getAllWindows()) {
        if (!win.isDestroyed()) win.webContents.send("nde1:sidecar", state);
      }
    });
    sidecar.start();
    applyLoginItem(loadPrefs(prefsPath));
    createTray();
    createMainWindow();
    createOverlayWindow();
    setInterval(() => {
      if (overlayWin && !overlayWin.isDestroyed() && overlayWin.isVisible()) {
        overlayWin.setAlwaysOnTop(true, "screen-saver");
      }
    }, 1000);
  });

  app.on("before-quit", () => {
    quitting = true;
    sidecar.stop(); // el núcleo restaura las ventanas al volver a arrancar
  });

  // La app vive en la bandeja: no sale al cerrar ventanas.
  app.on("window-all-closed", () => {});
}
