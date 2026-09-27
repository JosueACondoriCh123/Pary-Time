// "Mi tiempo": helpers puros para los gráficos del historial de uso (sin dependencias de gráficos).
import { addDays, today } from "./time";

export const CATEGORIES = ["work", "distraction", "other", "idle", "paused"] as const;
export type UsageCat = (typeof CATEGORIES)[number];

export const CAT_LABEL: Record<UsageCat, string> = {
  work: "Trabajo en bloques",
  distraction: "Distracción",
  other: "Otras apps",
  idle: "Inactivo",
  paused: "Pausa",
};

/** Variables CSS de styles.css: un color por categoría, igual en todos los gráficos. */
export const CAT_COLOR: Record<UsageCat, string> = {
  work: "var(--cat-work)",
  distraction: "var(--cat-distraction)",
  other: "var(--cat-other)",
  idle: "var(--cat-idle)",
  paused: "var(--cat-paused)",
};

export type RangeKind = "today" | "week" | "twoWeeks";
export const RANGE_LABEL: Record<RangeKind, string> = { today: "Hoy", week: "7 días", twoWeeks: "14 días" };

/** [desde, hasta] en fechas locales, inclusive. */
export function rangeFor(kind: RangeKind, now = new Date()): [string, string] {
  const end = today(now);
  const days = kind === "today" ? 1 : kind === "week" ? 7 : 14;
  return [addDays(end, -(days - 1)), end];
}

/** "2 h 05 min", "45 min", "0 min". */
export function fmtMinutes(min: number): string {
  const m = Math.max(0, Math.round(min));
  if (m < 60) return `${m} min`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

export function pct(share: number): string {
  return `${Math.round(share * 100)}%`;
}

/** "lun 21" para el eje de días. */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  const wd = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"][new Date(y, m - 1, d).getDay()];
  return `${wd} ${d}`;
}

export function sumCats(byCat: Record<string, number>, cats: readonly UsageCat[] = CATEGORIES): number {
  return cats.reduce((s, c) => s + (byCat[c] ?? 0), 0);
}

export interface Arc {
  cat: UsageCat;
  minutes: number;
  d: string;
}

/** Porciones de una dona (SVG path) centrada en (0,0), radio exterior r y ancho w. Omite categorías en 0. */
export function donutArcs(byCat: Record<string, number>, r = 60, w = 18,
                          cats: readonly UsageCat[] = CATEGORIES): Arc[] {
  const total = sumCats(byCat, cats);
  if (total <= 0) return [];
  const arcs: Arc[] = [];
  let a0 = -Math.PI / 2;
  for (const cat of cats) {
    const minutes = byCat[cat] ?? 0;
    if (minutes <= 0) continue;
    const frac = minutes / total;
    const a1 = a0 + frac * 2 * Math.PI - (frac === 1 ? 1e-6 : 0);
    const ri = r - w;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const p = (rad: number, a: number) => `${(rad * Math.cos(a)).toFixed(2)} ${(rad * Math.sin(a)).toFixed(2)}`;
    const d = `M ${p(r, a0)} A ${r} ${r} 0 ${large} 1 ${p(r, a1)} L ${p(ri, a1)} A ${ri} ${ri} 0 ${large} 0 ${p(ri, a0)} Z`;
    arcs.push({ cat, minutes, d });
    a0 = a1;
  }
  return arcs;
}
