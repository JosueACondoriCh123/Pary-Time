import type { OverlayState } from "../contracts";

/** Lo que el overlay dibuja: nada, salvo que la API diga `visible` y mande texto. */
export function overlayContent(state: OverlayState): { caption: string; text: string } | null {
  if (!state.visible || !state.text) return null;
  return { caption: state.kind === "first_step" ? "Primer paso" : "Cuenta regresiva", text: state.text };
}
