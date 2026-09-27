import { describe, expect, it } from "vitest";
import type { CouncilRun, Preregistration, Resolution } from "../src/contracts";
import { effectSentence, ratioWords } from "../src/lib/effect";
import { chosenIndex, hypothesisText } from "../src/views/Council";
import resolutionExample from "../../contracts/examples/Resolution.json";
import runExample from "../../contracts/examples/CouncilRun.json";
import preregExample from "../../contracts/examples/Preregistration.json";

const res = resolutionExample as unknown as Resolution;

describe("frase del resultado", () => {
  it("ratios redondos en palabras", () => {
    expect(ratioWords(0.52)).toBe("en la mitad de tiempo");
    expect(ratioWords(0.34)).toBe("en un tercio del tiempo");
    expect(ratioWords(0.7)).toBe("un 30% más rápido");
    expect(ratioWords(1.2)).toBe("un 20% más lento");
    expect(ratioWords(1.01)).toBe("prácticamente igual de rápido");
  });

  it("apoyada: p < α", () => {
    expect(effectSentence({ ...res, ratio: 0.5, p_value: 0.01, alpha: 0.024 }, "Retrasar distracciones")).toBe(
      "Con “Retrasar distracciones” arrancaste en la mitad de tiempo (p = 0.010 < α = 0.024): en vos, funciona.",
    );
  });

  it("no apoyada: dice que no alcanza, sin vender el efecto", () => {
    const s = effectSentence({ ...res, verdict: "not_supported", ratio: 0.8, p_value: 0.21, alpha: 0.024 }, "X");
    expect(s).toContain("p = 0.210 > α = 0.024");
    expect(s).toContain("no se puede afirmar");
  });

  it("insuficiente o sin números", () => {
    expect(effectSentence({ ...res, verdict: "insufficient" }, "X")).toMatch(/^Datos insuficientes/);
    expect(effectSentence({ ...res, ratio: null }, "X")).toMatch(/^Datos insuficientes/);
  });
});

describe("consejo", () => {
  it("encuentra la propuesta elegida por su hipótesis preregistrada", () => {
    const run = runExample as unknown as CouncilRun;
    const prereg = preregExample as unknown as Preregistration;
    expect(chosenIndex(run, prereg)).toBe(0);
    expect(chosenIndex({ ...run, chosen_experiment_id: null }, prereg)).toBe(-1);
    expect(chosenIndex(run, null)).toBe(-1);
  });

  it("la hipótesis en una línea", () => {
    expect(hypothesisText((preregExample as unknown as Preregistration).hypothesis)).toBe(
      "Retrasar distracciones, solo a la mañana: espera 40% menos de latencia de arranque",
    );
  });
});
