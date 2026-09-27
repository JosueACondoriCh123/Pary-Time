// Etapas de un bloque para la vista "Hoy", derivadas solo de lo que expone la API (bloque + /runtime/status).
// Regla dura: la intervención se nombra solo si `arm_revealed` la trae (visibleArm); nunca se infiere.
import type { BlockView, RuntimeStatus } from "../contracts";
import { ARM_HINT, ARM_LABEL, visibleArm } from "./labels";
import { clock } from "./time";

export type StepState = "done" | "now" | "pending" | "warn";

export interface Step {
  key: "sealed" | "hour" | "intervention" | "start";
  state: StepState;
  title: string;
  sub?: string;
}

export function blockTimeline(b: BlockView, status: RuntimeStatus | undefined, now: number): Step[] {
  const started = now >= b.planned_start_ms;
  const isActive = status?.active_block_id === b.block_id;
  const arm = visibleArm(b);
  const final = b.status === "started" || b.status === "censored" || b.status === "device_off";

  const sealed: Step =
    b.status === "planned"
      ? { key: "sealed", state: "pending", title: "Falta confirmar el día", sub: "Al confirmar se sortea la condición." }
      : { key: "sealed", state: "done", title: "Condición sorteada y sellada", sub: "Nadie la ve antes de la hora, ni vos." };

  const hour: Step = started
    ? { key: "hour", state: "done", title: `Empezó a las ${clock(b.planned_start_ms)}` }
    : { key: "hour", state: "now", title: `Empieza a las ${clock(b.planned_start_ms)}` };

  let intervention: Step;
  if (!started) {
    intervention = { key: "intervention", state: "pending", title: "Condición oculta hasta la hora" };
  } else if (b.aborted) {
    intervention = { key: "intervention", state: "warn", title: "Hoy no", sub: "Sin intervención. El bloque cuenta igual." };
  } else if (isActive && status?.emergency_released) {
    intervention = {
      key: "intervention",
      state: "warn",
      title: "Salida de emergencia",
      sub: "Todo restaurado. En este bloque no se vuelve a minimizar nada.",
    };
  } else if (!arm) {
    intervention = { key: "intervention", state: "now", title: "Revelando la condición…" };
  } else if (arm === "control") {
    intervention = { key: "intervention", state: "done", title: ARM_LABEL.control, sub: "Hoy solo se mide." };
  } else if (isActive && status?.interventions_applied.includes(arm) && !final) {
    intervention = { key: "intervention", state: "now", title: `${ARM_LABEL[arm]}: activa`, sub: ARM_HINT[arm] };
  } else {
    intervention = { key: "intervention", state: "done", title: ARM_LABEL[arm], sub: "Ya se revirtió." };
  }

  let start: Step;
  if (b.status === "started") {
    start = { key: "start", state: "done", title: "Arrancaste", sub: "15 minutos de trabajo real." };
  } else if (b.status === "censored") {
    start = { key: "start", state: "warn", title: "No arrancó en 90 min", sub: "Cuenta igual: también es un dato." };
  } else if (b.status === "device_off") {
    start = { key: "start", state: "warn", title: "La compu estuvo apagada", sub: "Este bloque se excluye." };
  } else {
    start = {
      key: "start",
      state: started && intervention.state !== "now" ? "now" : "pending",
      title: "Esperando que arranques",
      sub: "Cuenta cuando hacés 15 minutos de trabajo real.",
    };
  }
  return [sealed, hour, intervention, start];
}

/** El bloque que ocupa la vista: el activo o, si no hay, el próximo que empieza dentro de `leadMs`. */
export function focusBlock(
  active: BlockView | null,
  next: BlockView | null,
  now: number,
  leadMs = 30 * 60_000,
): BlockView | null {
  if (active) return active;
  return next && next.planned_start_ms - now <= leadMs ? next : null;
}
