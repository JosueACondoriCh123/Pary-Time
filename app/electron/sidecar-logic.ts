// Lógica pura del sidecar (sin Electron), para poder testearla con Vitest.
import { join } from "node:path";

export interface ReadyInfo {
  port: number;
  version: string;
  contracts: string;
}

const READY_PREFIX = "NDE1_READY ";

/** Parsea `NDE1_READY {"port": 51234, ...}`. Devuelve null si la línea no es la de arranque o está mal formada. */
export function parseReadyLine(line: string): ReadyInfo | null {
  const trimmed = line.trim();
  if (!trimmed.startsWith(READY_PREFIX)) return null;
  try {
    const data = JSON.parse(trimmed.slice(READY_PREFIX.length)) as Partial<ReadyInfo>;
    if (!Number.isInteger(data.port) || (data.port as number) <= 0 || (data.port as number) > 65535) return null;
    if (typeof data.version !== "string" || typeof data.contracts !== "string") return null;
    return { port: data.port as number, version: data.version, contracts: data.contracts };
  } catch {
    return null;
  }
}

export const BACKOFF_MS = [1000, 2000, 5000, 10000] as const;
export const CRASH_WINDOW_MS = 5 * 60 * 1000;
export const MAX_CRASHES_IN_WINDOW = 5;

/** Cuánto esperar antes de relanzar, dadas las caídas registradas (epoch ms, incluida la última).
 *  Devuelve null si hubo más de 5 caídas en 5 min: hay que mostrar el error y esperar a "reintentar". */
export function restartDelay(crashTimes: readonly number[], now: number): number | null {
  const recent = crashTimes.filter((t) => now - t <= CRASH_WINDOW_MS);
  if (recent.length > MAX_CRASHES_IN_WINDOW) return null;
  const i = Math.min(Math.max(recent.length - 1, 0), BACKOFF_MS.length - 1);
  return BACKOFF_MS[i];
}

export interface CoreCommand {
  command: string;
  args: string[];
  cwd: string;
}

/** Cómo lanzar el núcleo. En desarrollo usa el Python del venv del repo (o el del repo padre, para los worktrees
 *  anidados); empaquetado, el ejecutable del sidecar en resources/. */
export function coreCommand(opts: {
  packaged: boolean;
  resourcesPath: string;
  repoRoot: string;
  dataDir: string;
  exists: (p: string) => boolean;
  pythonOverride?: string;
}): CoreCommand {
  const args = ["--port", "0", "--data-dir", opts.dataDir];
  if (opts.packaged) {
    const dir = join(opts.resourcesPath, "nde1-core");
    return { command: join(dir, "nde1-core.exe"), args, cwd: dir };
  }
  const candidates = [
    opts.pythonOverride,
    join(opts.repoRoot, ".venv", "Scripts", "python.exe"),
    join(opts.repoRoot, "..", ".venv", "Scripts", "python.exe"),
  ].filter((p): p is string => !!p);
  const python = candidates.find(opts.exists);
  if (!python) {
    throw new Error(`No encontré el Python del núcleo. Probé: ${candidates.join(", ")}. Definí NDE1_PYTHON.`);
  }
  return { command: python, args: ["-m", "core", ...args], cwd: opts.repoRoot };
}

/** Últimas líneas de stderr que se guardan para mostrar si el núcleo no levanta. */
export function appendTail(tail: string, chunk: string, maxChars = 4000): string {
  const next = tail + chunk;
  return next.length > maxChars ? next.slice(next.length - maxChars) : next;
}
