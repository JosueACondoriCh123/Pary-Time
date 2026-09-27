import { describe, expect, it } from "vitest";
import type { ActivityHistory } from "../src/contracts";
import { dayLabel, donutArcs, fmtMinutes, pct, rangeFor, sumCats } from "../src/lib/usage";
import example from "../../contracts/examples/ActivityHistory.json";

const history = example as unknown as ActivityHistory;

describe("Mi tiempo: helpers", () => {
  it("formatea minutos en horas humanas", () => {
    expect(fmtMinutes(0)).toBe("0 min");
    expect(fmtMinutes(45)).toBe("45 min");
    expect(fmtMinutes(125)).toBe("2 h 05 min");
    expect(pct(0.3421)).toBe("34%");
  });

  it("rangos inclusivos en fechas locales", () => {
    const now = new Date(2026, 8, 27, 15, 0);
    expect(rangeFor("today", now)).toEqual(["2026-09-27", "2026-09-27"]);
    expect(rangeFor("week", now)).toEqual(["2026-09-21", "2026-09-27"]);
    expect(rangeFor("twoWeeks", now)).toEqual(["2026-09-14", "2026-09-27"]);
    expect(dayLabel("2026-09-21")).toBe("lun 21");
  });

  it("la dona tiene una porción por categoría con tiempo y suma el total", () => {
    const arcs = donutArcs({ work: 30, distraction: 10, other: 0, idle: 20, paused: 0 });
    expect(arcs.map((a) => a.cat)).toEqual(["work", "distraction", "idle"]);
    expect(arcs.every((a) => a.d.startsWith("M ") && a.d.endsWith("Z"))).toBe(true);
    expect(donutArcs({})).toEqual([]);
    expect(donutArcs({ work: 5 })).toHaveLength(1);           // círculo completo sin romper el path
  });

  it("el ejemplo del contrato es coherente: los días suman los totales", () => {
    for (const cat of ["work", "distraction", "other"] as const) {
      const byDays = history.days.reduce((s, d) => s + (d.minutes_by_category[cat] ?? 0), 0);
      expect(Math.abs(byDays - history.totals[cat])).toBeLessThanOrEqual(history.days.length);   // redondeo por día
    }
    expect(sumCats(history.totals, ["work", "distraction", "other"])).toBeGreaterThan(0);
  });
});
