// El resultado de un experimento resuelto en una frase que entiende cualquiera. Solo con la `resolution`:
// nunca hay efectos parciales antes de llegar al N.
import type { Resolution } from "../contracts";

const fmt = (x: number) => x.toFixed(3);

/** "en la mitad de tiempo", "un 30% más rápido", "un 20% más lento". */
export function ratioWords(r: number): string {
  if (Math.abs(r - 0.5) < 0.06) return "en la mitad de tiempo";
  if (Math.abs(r - 1 / 3) < 0.04) return "en un tercio del tiempo";
  if (Math.abs(r - 0.25) < 0.03) return "en un cuarto del tiempo";
  if (Math.abs(r - 1) < 0.03) return "prácticamente igual de rápido";
  return r < 1 ? `un ${Math.round((1 - r) * 100)}% más rápido` : `un ${Math.round((r - 1) * 100)}% más lento`;
}

export function effectSentence(res: Resolution, armLabel: string): string {
  if (res.verdict === "insufficient" || res.ratio === null || res.p_value === null) {
    return `Datos insuficientes para concluir algo sobre “${armLabel}”.`;
  }
  const what = `Con “${armLabel}” arrancaste ${ratioWords(res.ratio)}`;
  if (res.verdict === "supported") {
    return `${what} (p = ${fmt(res.p_value)} < α = ${fmt(res.alpha)}): en vos, funciona.`;
  }
  return `${what}, pero no alcanza (p = ${fmt(res.p_value)} > α = ${fmt(res.alpha)}): no se puede afirmar que funcione en vos.`;
}
