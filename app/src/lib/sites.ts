// "Distracciones": helpers puros para la lista de sitios y programas, al estilo de un bloqueador de Chrome.
// El sensor no ve URLs: reconoce un sitio porque su nombre aparece en el título de la ventana del navegador.
// Por eso cada sitio se guarda como un patrón de título ("youtube"), no como dominio.

/** Sitios cuyo título no contiene el nombre del dominio tal cual. */
const TITLE_ALIASES: Record<string, string> = {
  primevideo: "prime video",
  disneyplus: "disney+",
  mercadolibre: "mercado libre",
  hbomax: "max",
  "web.whatsapp": "whatsapp",
};

const SECOND_LEVEL = new Set(["com", "co", "net", "org", "gob", "gov", "edu", "ac"]);

export interface SiteInput {
  /** Lo que se guarda en `distraction_title_patterns`. */
  pattern: string;
  /** Dominio para mostrar, si se escribió uno. */
  domain: string | null;
}

/** "https://www.youtube.com/watch?v=1" → { pattern: "youtube", domain: "youtube.com" }. null si no sirve. */
export function normalizeSite(raw: string): SiteInput | null {
  let s = raw.trim().toLowerCase();
  if (!s) return null;
  s = s.replace(/^[a-z]+:\/\//, "").replace(/^www\./, "");
  s = s.split(/[/?#]/)[0].split(":")[0];
  if (!s || /\s/.test(s) && s.includes(".")) return null;
  if (!s.includes(".")) {
    const word = s.replace(/\s+/g, " ").trim();
    return word.length >= 2 ? { pattern: TITLE_ALIASES[word] ?? word, domain: null } : null;
  }
  const labels = s.split(".").filter(Boolean);
  if (labels.length < 2) return null;
  const n = labels.length;
  const twoLevel = n >= 3 && labels[n - 1].length === 2 && SECOND_LEVEL.has(labels[n - 2]);
  const mainIdx = twoLevel ? n - 3 : n - 2;
  const main = labels[mainIdx];
  const host = labels.join(".");
  const sub = labels.slice(0, mainIdx).join(".");
  const alias = TITLE_ALIASES[sub ? `${sub}.${main}` : main] ?? TITLE_ALIASES[main];
  // "x.com": el nombre solo ("x") coincidiría con casi cualquier título.
  const pattern = alias ?? (main.length <= 2 ? host : main);
  return { pattern, domain: host };
}

/** "youtube" → "Youtube"; "x.com" queda igual; "prime video" → "Prime Video". */
export function siteLabel(pattern: string): string {
  if (pattern.includes(".")) return pattern;
  return pattern.replace(/(^|\s)\S/g, (c) => c.toUpperCase());
}

/** Letra y tono estables para el ícono de cada sitio (no se descargan favicons: no sale nada de la compu). */
export function monogram(name: string): { letter: string; hue: number } {
  const clean = name.replace(/\.exe$/i, "");
  let h = 0;
  for (const ch of clean.toLowerCase()) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return { letter: (Array.from(clean)[0] ?? "?").toUpperCase(), hue: h };
}

/** "discord" → "Discord.exe"; respeta lo que ya termina en .exe. */
export function normalizeProcess(raw: string): string | null {
  const s = raw.trim().split(/[\\/]/).pop() ?? "";
  if (!s || /\s{2,}/.test(s)) return null;
  return /\.exe$/i.test(s) ? s : `${s}.exe`;
}

export const hasItem = (list: readonly string[], item: string) =>
  list.some((x) => x.toLowerCase() === item.toLowerCase());

export const addItems = (list: readonly string[], items: readonly string[]) =>
  items.reduce<string[]>((acc, it) => (hasItem(acc, it) ? acc : [...acc, it]), [...list]);

export const removeItem = (list: readonly string[], item: string) =>
  list.filter((x) => x.toLowerCase() !== item.toLowerCase());

export interface Pack {
  id: string;
  label: string;
  sites: string[];
  apps: string[];
}

/** Paquetes de un clic, como las categorías de los bloqueadores. */
export const PACKS: Pack[] = [
  { id: "social", label: "Redes sociales", sites: ["instagram", "facebook", "tiktok", "x.com", "twitter", "reddit", "linkedin", "pinterest"], apps: [] },
  { id: "video", label: "Video y streaming", sites: ["youtube", "netflix", "twitch", "prime video", "disney+", "kick"], apps: [] },
  { id: "chat", label: "Mensajería", sites: ["whatsapp", "telegram", "discord", "messenger"], apps: ["WhatsApp.exe", "Telegram.exe", "Discord.exe"] },
  { id: "games", label: "Juegos", sites: ["poki", "chess.com", "roblox"], apps: ["Steam.exe", "EpicGamesLauncher.exe", "RobloxPlayerBeta.exe", "Battle.net.exe"] },
  { id: "shopping", label: "Compras", sites: ["mercado libre", "amazon", "aliexpress", "temu", "shein"], apps: [] },
  { id: "news", label: "Noticias", sites: ["infobae", "clarin", "la nacion", "bbc", "cnn"], apps: [] },
];

/** Cuántos elementos del paquete ya están en las listas (activos o pausados). */
export function packCoverage(pack: Pack, sites: readonly string[], apps: readonly string[]): number {
  return pack.sites.filter((s) => hasItem(sites, s)).length + pack.apps.filter((a) => hasItem(apps, a)).length;
}

export interface AppCandidate {
  process: string;
  minutes: number;
}

/** Procesos de Windows y de la propia app: nunca se sugieren. */
const SYSTEM_PROCESSES = [
  "explorer.exe", "applicationframehost.exe", "searchhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
  "lockapp.exe", "textinputhost.exe", "systemsettings.exe", "taskmgr.exe", "pary time.exe", "consejo n-de-1.exe",
  "electron.exe", "nde1-core.exe",
];

/** Las apps con más tiempo que todavía no están en ninguna lista: candidatas a marcar como distracción. */
export function appSuggestions(
  apps: readonly { process: string; minutes: number; category: string }[],
  known: readonly string[],
  limit = 5,
): AppCandidate[] {
  return apps
    .filter((a) => a.category !== "work" && a.minutes > 0 && !hasItem(known, a.process) && !hasItem(SYSTEM_PROCESSES, a.process))
    .sort((a, b) => b.minutes - a.minutes)
    .slice(0, limit)
    .map(({ process, minutes }) => ({ process, minutes }));
}

/** Minutos por patrón a partir de `ActivityHistory.sites`, sin distinguir mayúsculas. */
export function minutesBySite(sites: readonly { site: string; minutes: number }[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const s of sites) m.set(s.site.toLowerCase(), (m.get(s.site.toLowerCase()) ?? 0) + s.minutes);
  return m;
}
