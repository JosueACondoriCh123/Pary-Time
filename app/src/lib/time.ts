// Fechas y tiempos. La API usa epoch ms UTC; `local_date` y las horas se muestran en el reloj local.

const pad = (n: number) => String(n).padStart(2, "0");

/** YYYY-MM-DD en hora local. */
export function localDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function addDays(date: string, days: number): string {
  const [y, m, d] = date.split("-").map(Number);
  return localDate(new Date(y, m - 1, d + days));
}

export function today(now = new Date()): string {
  return localDate(now);
}

export function tomorrow(now = new Date()): string {
  return addDays(localDate(now), 1);
}

/** Epoch ms de una hora "HH:MM" en la fecha local dada. */
export function toEpochMs(date: string, hhmm: string): number {
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = hhmm.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm).getTime();
}

/** "HH:MM" local de un epoch ms. */
export function clock(ms: number): string {
  const d = new Date(ms);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** "m:ss" para cuentas regresivas; nunca negativo. */
export function mss(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${pad(s % 60)}`;
}

/** Duración humana corta: "45 s", "12 min", "1 h 05 min". */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} s`;
  const min = Math.round(s / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${pad(min % 60)} min`;
}

/** "en 2 h 10 min" / "en 5 min" / "ahora". */
export function untilText(targetMs: number, nowMs: number): string {
  const diff = targetMs - nowMs;
  if (diff <= 30_000) return "ahora";
  return `en ${duration(diff / 1000)}`;
}

const WEEKDAYS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** "martes 29 sep". */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return `${WEEKDAYS[dt.getDay()]} ${d} ${MONTHS[m - 1]}`;
}

export function dateTime(ms: number): string {
  const d = new Date(ms);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${clock(ms)}`;
}
