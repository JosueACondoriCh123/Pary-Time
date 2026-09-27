// Textos de la UI para los enums del contrato, y la regla de revelación del brazo.
import type { Arm, BlockStatus, BlockView, Moderator, TaskKind } from "../contracts";

export const ARM_LABEL: Record<Arm, string> = {
  control: "Sin intervención (control)",
  abrir_trabajo: "Abrir el trabajo solo",
  primer_paso: "Primer paso mínimo",
  retrasar_distracciones: "Retrasar distracciones",
  cuenta_regresiva: "Cuenta regresiva",
};

export const ARM_HINT: Record<Arm, string> = {
  control: "Hoy la compu no hace nada distinto. Arrancá como siempre.",
  abrir_trabajo: "La compu te abre el trabajo a la hora del bloque.",
  primer_paso: "Te muestra el primer paso que escribiste.",
  retrasar_distracciones: "Minimiza las distracciones hasta que arranques. No cierra nada.",
  cuenta_regresiva: "Te muestra una cuenta regresiva antes de la hora.",
};

export const TASK_KINDS: TaskKind[] = ["escritura", "lectura", "estudio", "programacion", "admin", "otro"];

export const TASK_LABEL: Record<TaskKind, string> = {
  escritura: "Escritura",
  lectura: "Lectura",
  estudio: "Estudio",
  programacion: "Programación",
  admin: "Admin",
  otro: "Otro",
};

export const STATUS_LABEL: Record<BlockStatus, string> = {
  planned: "Sin confirmar",
  confirmed: "Confirmado",
  running: "En curso",
  started: "Arrancaste",
  censored: "No arrancó",
  device_off: "Compu apagada",
  cancelled: "Cancelado",
};

const TIME_OF_DAY: Record<string, string> = { morning: "a la mañana", afternoon: "a la tarde", evening: "a la noche" };

export function moderatorText(m: Moderator | null | undefined): string {
  if (!m) return "en todos los bloques";
  if (m.kind === "time_of_day") return `solo ${TIME_OF_DAY[m.value] ?? m.value}`;
  return `solo en tareas de ${TASK_LABEL[m.value as TaskKind]?.toLowerCase() ?? m.value}`;
}

/** El brazo que la UI puede mostrar. Regla dura: solo `arm_revealed` tal como lo manda la API.
 *  Nunca se deduce de `needs_first_step`, del experimento ni de nada más. */
export function visibleArm(block: Pick<BlockView, "arm_revealed">): Arm | null {
  return block.arm_revealed ?? null;
}
