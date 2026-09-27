// Idioma de la UI: inglés por defecto, español como opción. Cada texto se escribe en los dos idiomas en el
// mismo lugar: t("Today", "Hoy"). Sin claves ni diccionarios aparte.
//
// El idioma vive en localStorage (renderer) y en las preferencias de Electron (para la bandeja). En Electron las
// preferencias mandan: al arrancar, `syncLangFromPrefs` adopta lo que diga prefs.json.
import { useSyncExternalStore } from "react";

export type Lang = "en" | "es";
export const LANGS: Lang[] = ["en", "es"];
export const LANG_NAME: Record<Lang, string> = { en: "English", es: "Español" };

const KEY = "pary.lang";
const listeners = new Set<() => void>();

function readStored(): Lang {
  try {
    const v = localStorage.getItem(KEY);
    return v === "es" || v === "en" ? v : "en";
  } catch {
    return "en";
  }
}

let current: Lang = typeof localStorage === "undefined" ? "en" : readStored();
applyDocumentLang();

function applyDocumentLang() {
  if (typeof document !== "undefined") document.documentElement.lang = current;
}

export const lang = (): Lang => current;

/** El texto en el idioma actual. */
export function t(en: string, es: string): string {
  return current === "es" ? es : en;
}

/** Locale para Intl (fechas, números). */
export const locale = (): string => (current === "es" ? "es" : "en-US");

/** Cambia el idioma, lo guarda y avisa a la app (y a la bandeja, vía prefs). */
export function setLang(next: Lang, { persistPrefs = true } = {}) {
  if (next === current) return;
  current = next;
  try {
    localStorage.setItem(KEY, next);
  } catch {
    /* sin almacenamiento: vale para esta sesión */
  }
  applyDocumentLang();
  if (persistPrefs) void window.nde1?.setPrefs({ language: next });
  listeners.forEach((l) => l());
}

/** En Electron, prefs.json es la fuente de verdad (la bandeja también la lee). */
export async function syncLangFromPrefs() {
  const prefs = await window.nde1?.prefs();
  if (prefs?.language === "en" || prefs?.language === "es") setLang(prefs.language, { persistPrefs: false });
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Re-renderiza el componente cuando cambia el idioma. Usarlo en la raíz de cada ventana. */
export function useLang(): Lang {
  return useSyncExternalStore(subscribe, () => current, () => current);
}

/** Tabla de textos por clave que responde en el idioma actual: bi({ a: ["A", "A-es"] }).a */
export function bi<K extends string>(m: Record<K, readonly [string, string]>): Record<K, string> {
  const o = {} as Record<K, string>;
  for (const k of Object.keys(m) as K[]) {
    Object.defineProperty(o, k, { get: () => t(m[k][0], m[k][1]), enumerable: true });
  }
  return o;
}

/** Solo para tests. */
export function __setLangForTests(next: Lang) {
  current = next;
}
