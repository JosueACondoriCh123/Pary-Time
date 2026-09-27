import { describe, expect, it } from "vitest";
import type { BlockView } from "../src/contracts";
import { visibleArm } from "../src/lib/labels";
import { cleanMatchers, suggestMatchers } from "../src/lib/matchers";
import { overlayContent } from "../src/lib/overlay";
import { addDays, clock, duration, localDate, mss, toEpochMs, tomorrow, untilText } from "../src/lib/time";
import hidden from "../../contracts/examples/BlockView.hidden.json";
import firstStep from "../../contracts/examples/BlockView.first_step.json";

describe("tiempos", () => {
  it("fechas locales y cruce de mes y de año", () => {
    expect(localDate(new Date(2026, 8, 30, 23, 59))).toBe("2026-09-30");
    expect(addDays("2026-09-30", 1)).toBe("2026-10-01");
    expect(tomorrow(new Date(2026, 11, 31, 22, 0))).toBe("2027-01-01");
  });

  it("hora local ida y vuelta", () => {
    const ms = toEpochMs("2026-09-29", "08:30");
    expect(new Date(ms).getHours()).toBe(8);
    expect(clock(ms)).toBe("08:30");
  });

  it("m:ss nunca negativo", () => {
    expect(mss(180_000)).toBe("3:00");
    expect(mss(61_400)).toBe("1:01");
    expect(mss(-5000)).toBe("0:00");
  });

  it("duraciones cortas", () => {
    expect(duration(45)).toBe("45 s");
    expect(duration(720)).toBe("12 min");
    expect(duration(3900)).toBe("1 h 05 min");
    expect(untilText(1000, 0)).toBe("ahora");
    expect(untilText(600_000, 0)).toBe("en 10 min");
  });
});

describe("matchers", () => {
  it("archivo de Word: proceso probable y nombre sin extensión", () => {
    expect(suggestMatchers({ kind: "file", value: "C:\\Users\\x\\tesis\\Cap3 final.docx" })).toEqual([
      { field: "process", pattern: "WINWORD.EXE" },
      { field: "title", pattern: "Cap3 final" },
    ]);
  });

  it("archivo sin app obvia: solo el título", () => {
    expect(suggestMatchers({ kind: "file", value: "D:/notas/idea.xyz" })).toEqual([{ field: "title", pattern: "idea" }]);
  });

  it("app y web", () => {
    expect(suggestMatchers({ kind: "app", value: "C:\\Apps\\Obsidian.exe" })).toEqual([
      { field: "process", pattern: "Obsidian.exe" },
    ]);
    expect(suggestMatchers({ kind: "app", value: "obsidian" })).toEqual([{ field: "process", pattern: "obsidian.exe" }]);
    expect(suggestMatchers({ kind: "url", value: "https://www.overleaf.com/project/1" })).toEqual([
      { field: "title", pattern: "overleaf" },
    ]);
    expect(suggestMatchers({ kind: "none", value: "" })).toEqual([]);
  });

  it("cleanMatchers saca vacíos y duplicados", () => {
    expect(
      cleanMatchers([
        { field: "title", pattern: " cap3 " },
        { field: "title", pattern: "CAP3" },
        { field: "process", pattern: "   " },
      ]),
    ).toEqual([{ field: "title", pattern: "cap3" }]);
  });
});

describe("brazo oculto", () => {
  it("con arm_revealed null no se muestra nada, aunque haya experimento", () => {
    const b = hidden as BlockView;
    expect(b.experiment_id).not.toBeNull();
    expect(visibleArm(b)).toBeNull();
  });

  it("no se infiere de needs_first_step", () => {
    const b = { ...(firstStep as BlockView), arm_revealed: null };
    expect(b.needs_first_step).toBe(true);
    expect(visibleArm(b)).toBeNull();
  });

  it("revelado, se muestra tal cual", () => {
    expect(visibleArm(firstStep as BlockView)).toBe("primer_paso");
  });
});

describe("overlay", () => {
  it("solo dibuja si es visible y trae texto", () => {
    expect(overlayContent({ visible: false, text: "x" })).toBeNull();
    expect(overlayContent({ visible: true, text: null })).toBeNull();
    expect(overlayContent({ visible: true, kind: "countdown", text: "Tesis · arrancás en 3:00" })).toEqual({
      caption: "Cuenta regresiva",
      text: "Tesis · arrancás en 3:00",
    });
  });
});
