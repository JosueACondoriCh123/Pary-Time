// Densidad Beta para dibujar la posterior del ledger (sin dependencias).

// Lanczos (g = 7, n = 9): error relativo ~1e-15 para x > 0.
const LANCZOS = [
  0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
  12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
];

export function logGamma(x: number): number {
  if (x < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * x)) - logGamma(1 - x);
  x -= 1;
  let a = LANCZOS[0];
  const t = x + 7.5;
  for (let i = 1; i < 9; i++) a += LANCZOS[i] / (x + i);
  return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
}

export function betaPdf(x: number, a: number, b: number): number {
  if (x <= 0 || x >= 1) return 0;
  const logB = logGamma(a) + logGamma(b) - logGamma(a + b);
  return Math.exp((a - 1) * Math.log(x) + (b - 1) * Math.log(1 - x) - logB);
}

export const betaMean = (a: number, b: number) => a / (a + b);

/** Puntos (x, densidad) en (0, 1) para dibujar la curva. */
export function betaCurve(a: number, b: number, n = 60): [number, number][] {
  const pts: [number, number][] = [];
  for (let i = 1; i < n; i++) {
    const x = i / n;
    pts.push([x, betaPdf(x, a, b)]);
  }
  return pts;
}
