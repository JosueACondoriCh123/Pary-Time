// Autocompletado de los matchers de trabajo a partir del objetivo del bloque. Siempre editables.
import type { Target, WorkMatcher } from "../contracts";

const PROCESS_BY_EXT: Record<string, string> = {
  doc: "WINWORD.EXE",
  docx: "WINWORD.EXE",
  docm: "WINWORD.EXE",
  rtf: "WINWORD.EXE",
  xls: "EXCEL.EXE",
  xlsx: "EXCEL.EXE",
  xlsm: "EXCEL.EXE",
  csv: "EXCEL.EXE",
  ppt: "POWERPNT.EXE",
  pptx: "POWERPNT.EXE",
  odt: "soffice.bin",
  ods: "soffice.bin",
  odp: "soffice.bin",
  pdf: "Acrobat.exe",
  md: "Code.exe",
  txt: "notepad.exe",
  py: "Code.exe",
  js: "Code.exe",
  ts: "Code.exe",
  tsx: "Code.exe",
  jsx: "Code.exe",
  go: "Code.exe",
  rs: "Code.exe",
  java: "idea64.exe",
  ipynb: "Code.exe",
  tex: "Code.exe",
};

/** Último segmento de una ruta de Windows o POSIX. */
export function basename(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] ?? "";
}

function splitExt(name: string): [string, string] {
  const i = name.lastIndexOf(".");
  return i > 0 ? [name.slice(0, i), name.slice(i + 1).toLowerCase()] : [name, ""];
}

/** Proceso probable para un archivo por su extensión, o null si no hay una app obvia. */
export function probableProcess(filePath: string): string | null {
  return PROCESS_BY_EXT[splitExt(basename(filePath))[1]] ?? null;
}

/** Matchers sugeridos. El título de la ventana casi siempre incluye el nombre del archivo, sin extensión. */
export function suggestMatchers(target: Target): WorkMatcher[] {
  const value = (target.value ?? "").trim();
  if (!value) return [];
  switch (target.kind) {
    case "file": {
      const [stem] = splitExt(basename(value));
      const proc = probableProcess(value);
      const out: WorkMatcher[] = [];
      if (proc) out.push({ field: "process", pattern: proc });
      if (stem) out.push({ field: "title", pattern: stem });
      return out;
    }
    case "app": {
      const exe = basename(value);
      return exe ? [{ field: "process", pattern: /\.exe$/i.test(exe) ? exe : `${exe}.exe` }] : [];
    }
    case "url": {
      const host = hostOf(value);
      if (!host) return [];
      const labels = host.replace(/^www\./, "").split(".");
      const name = labels.length > 1 ? labels[labels.length - 2] : labels[0];
      return name ? [{ field: "title", pattern: name }] : [];
    }
    default:
      return [];
  }
}

function hostOf(value: string): string | null {
  try {
    return new URL(/^[a-z]+:\/\//i.test(value) ? value : `https://${value}`).hostname || null;
  } catch {
    return null;
  }
}

/** Solo los matchers válidos para el contrato (patrón no vacío, sin duplicados). */
export function cleanMatchers(matchers: WorkMatcher[]): WorkMatcher[] {
  const seen = new Set<string>();
  const out: WorkMatcher[] = [];
  for (const m of matchers) {
    const pattern = m.pattern.trim().slice(0, 200);
    const key = `${m.field}:${pattern.toLowerCase()}`;
    if (!pattern || seen.has(key)) continue;
    seen.add(key);
    out.push({ field: m.field, pattern });
  }
  return out;
}
