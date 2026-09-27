// Preferencias de la app que no son del núcleo: arrancar con Windows e idioma.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import type { Prefs } from "../src/bridge";

const DEFAULTS: Prefs = { openAtLogin: true, language: "en" };

export function loadPrefs(path: string): Prefs {
  if (!existsSync(path)) return { ...DEFAULTS };
  try {
    return { ...DEFAULTS, ...(JSON.parse(readFileSync(path, "utf8")) as Partial<Prefs>) };
  } catch {
    return { ...DEFAULTS };
  }
}

export function savePrefs(path: string, prefs: Prefs): void {
  writeFileSync(path, JSON.stringify(prefs, null, 2));
}
