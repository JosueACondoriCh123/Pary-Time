import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";
import type { BlockView, Report } from "../src/contracts";
import { betaMean, betaPdf, logGamma } from "../src/lib/beta";
import { escapeHtml, reportHtml } from "../src/lib/report";
import { hexToBytes, verifySeed } from "../src/lib/seed";
import { fromLines, toLines } from "../src/views/SettingsView";
import { activeBlock, nextBlock } from "../src/views/Today";
import reportExample from "../../contracts/examples/Report.json";
import hidden from "../../contracts/examples/BlockView.hidden.json";

describe("verificación de la semilla", () => {
  it("hashea los bytes de la semilla hex, como core.contracts.seed_commitment", async () => {
    // sha256(bytes.fromhex("00")) en Python
    expect(await verifySeed("00", "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d")).toBe(true);
    const seed = "3f".repeat(32);
    const commitment = createHash("sha256").update(Buffer.from(seed, "hex")).digest("hex");
    expect(await verifySeed(seed, commitment)).toBe(true);
    expect(await verifySeed(seed, commitment.toUpperCase())).toBe(true);
  });

  it("rechaza semillas que no coinciden o no son hex", async () => {
    const commitment = createHash("sha256").update(Buffer.from("aa", "hex")).digest("hex");
    expect(await verifySeed("ab", commitment)).toBe(false);
    // Hashear el texto en vez de los bytes da otro valor: no se acepta.
    const textHash = createHash("sha256").update("aa").digest("hex");
    expect(await verifySeed("aa", textHash)).toBe(false);
    expect(await verifySeed("zz", commitment)).toBe(false);
    expect(await verifySeed("", commitment)).toBe(false);
    expect(hexToBytes("abc")).toBeNull();
  });
});

describe("posterior Beta", () => {
  it("logGamma en valores conocidos", () => {
    expect(logGamma(1)).toBeCloseTo(0, 10);
    expect(logGamma(5)).toBeCloseTo(Math.log(24), 10);
    expect(logGamma(0.5)).toBeCloseTo(Math.log(Math.sqrt(Math.PI)), 10);
  });

  it("Beta(1,1) es uniforme y Beta(2,1) es 2x", () => {
    expect(betaPdf(0.3, 1, 1)).toBeCloseTo(1, 10);
    expect(betaPdf(0.3, 2, 1)).toBeCloseTo(0.6, 10);
    expect(betaMean(2, 1)).toBeCloseTo(2 / 3);
  });

  it("integra a 1", () => {
    const n = 20_000;
    let sum = 0;
    for (let i = 0; i < n; i++) sum += betaPdf((i + 0.5) / n, 3, 5) / n;
    expect(sum).toBeCloseTo(1, 4);
  });
});

describe("reporte HTML", () => {
  const report = reportExample as unknown as Report;

  it("es autocontenido, sin scripts ni recursos externos, y lleva el disclaimer", () => {
    const html = reportHtml(report, { exp_0123456789ab: true });
    expect(html).not.toMatch(/<script|<link|src=|https?:\/\//i);
    expect(html).toContain("No es tratamiento ni consejo médico");
    expect(html).toContain("Semilla verificada</th><td>sí");
  });

  it("escapa todo lo que viene de la API", () => {
    const evil = structuredClone(report);
    evil.experiments[0].preregistration.hypothesis.rationale = '<img src=x onerror="alert(1)">';
    const html = reportHtml(evil);
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;");
    expect(escapeHtml(`&<>"'`)).toBe("&amp;&lt;&gt;&quot;&#39;");
  });

  it("marca la semilla que no coincide", () => {
    expect(reportHtml(report, { exp_0123456789ab: false })).toContain("NO COINCIDE");
  });
});

describe("vista Hoy", () => {
  const base = hidden as BlockView;
  const mk = (id: string, start: number, status: BlockView["status"]): BlockView => ({
    ...base,
    block_id: id,
    planned_start_ms: start,
    status,
  });
  const blocks = [mk("blk_000000000001", 1000, "started"), mk("blk_000000000002", 5000, "running"), mk("blk_000000000003", 9000, "confirmed")];

  it("activo: el que dice el runtime, si no el que está running", () => {
    expect(activeBlock(blocks, "blk_000000000001")?.block_id).toBe("blk_000000000001");
    expect(activeBlock(blocks, null)?.block_id).toBe("blk_000000000002");
    expect(activeBlock([blocks[0]], undefined)).toBeNull();
  });

  it("siguiente: el próximo confirmado en el futuro", () => {
    expect(nextBlock(blocks, 6000)?.block_id).toBe("blk_000000000003");
    expect(nextBlock(blocks, 9500)).toBeNull();
  });
});

it("listas de ajustes: una por línea, sin vacíos ni repetidos", () => {
  expect(fromLines(" Discord.exe \r\n\nSteam.exe\nDiscord.exe")).toEqual(["Discord.exe", "Steam.exe"]);
  expect(toLines(["a", "b"])).toBe("a\nb");
});
