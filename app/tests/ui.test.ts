import { describe, expect, it } from "vitest";
import type { BlockView, CouncilRun, ProposalRecord, RuntimeStatus } from "../src/contracts";
import { blockTimeline, focusBlock } from "../src/lib/timeline";
import { groupProposals, vetoReason } from "../src/views/Council";
import hidden from "../../contracts/examples/BlockView.hidden.json";
import runExample from "../../contracts/examples/CouncilRun.json";

const P = (hidden as BlockView).planned_start_ms;
const base = { ...(hidden as BlockView), arm_revealed: null } as BlockView;
const status = (over: Partial<RuntimeStatus> = {}): RuntimeStatus => ({
  active_block_id: base.block_id,
  active_arm_revealed: "retrasar_distracciones",
  interventions_applied: ["retrasar_distracciones"],
  next_block_start_ms: null,
  emergency_released: false,
  ...over,
});
const byKey = (b: BlockView, s: RuntimeStatus | undefined, now: number) =>
  Object.fromEntries(blockTimeline(b, s, now).map((st) => [st.key, st]));

describe("línea de tiempo del bloque", () => {
  it("antes de la hora: sellado, cuenta regresiva y condición oculta", () => {
    const t = byKey(base, undefined, P - 60_000);
    expect(t.sealed.state).toBe("done");
    expect(t.hour.state).toBe("now");
    expect(t.intervention.state).toBe("pending");
    expect(t.intervention.title).toBe("Condición oculta hasta la hora");
  });

  it("nunca nombra la intervención si arm_revealed es null, aunque el runtime la tenga aplicada", () => {
    const t = byKey(base, status(), P + 5_000);
    expect(t.intervention.title).toBe("Revelando la condición…");
    expect(JSON.stringify(t)).not.toContain("Retrasar");
  });

  it("revelada y aplicada: la intervención es la etapa actual", () => {
    const b = { ...base, status: "running", arm_revealed: "retrasar_distracciones" } as BlockView;
    const t = byKey(b, status(), P + 5_000);
    expect(t.intervention).toMatchObject({ state: "now", title: "Retrasar distracciones: activa" });
    expect(t.start.state).toBe("pending");
  });

  it("salida de emergencia y hoy no se marcan como aviso", () => {
    const b = { ...base, status: "running", arm_revealed: "retrasar_distracciones" } as BlockView;
    expect(byKey(b, status({ emergency_released: true }), P + 5_000).intervention.title).toBe("Salida de emergencia");
    expect(byKey({ ...b, aborted: true }, status(), P + 5_000).intervention.title).toBe("Hoy no");
  });

  it("control: solo se mide, y el arranque pasa a ser la etapa actual", () => {
    const b = { ...base, status: "running", arm_revealed: "control" } as BlockView;
    const t = byKey(b, status({ interventions_applied: [] }), P + 5_000);
    expect(t.intervention.state).toBe("done");
    expect(t.start.state).toBe("now");
  });

  it("finales", () => {
    const b = { ...base, arm_revealed: "control" } as BlockView;
    expect(byKey({ ...b, status: "started" }, undefined, P + 1e6).start.title).toBe("Arrancaste");
    expect(byKey({ ...b, status: "censored" }, undefined, P + 1e7).start.state).toBe("warn");
    expect(byKey({ ...b, status: "planned" }, undefined, P - 1e6).sealed.state).toBe("pending");
  });

  it("foco: el activo, o el próximo si falta menos de media hora", () => {
    expect(focusBlock(base, null, 0)).toBe(base);
    expect(focusBlock(null, base, P - 10 * 60_000)).toBe(base);
    expect(focusBlock(null, base, P - 45 * 60_000)).toBeNull();
  });
});

describe("consejo compacto", () => {
  const run = runExample as unknown as CouncilRun;
  const prop = run.proposals[0];
  const tools = (fail: ProposalRecord["red_team"]["tools"][number]["name"][]) =>
    prop.red_team.tools.map((t) => ({ ...t, passed: !fail.includes(t.name) }));

  it("el motivo del veto se lee con el verificador primero", () => {
    const vetoed: ProposalRecord = { ...prop, red_team: { ...prop.red_team, verdict: "veto", tools: tools(["power", "verifier"]) } };
    expect(vetoReason(vetoed)?.name).toBe("verifier");
    expect(vetoReason(prop)).toBeNull();
  });

  it("separa lo del Scout de los respaldos, con el índice original", () => {
    const fb: ProposalRecord = { ...prop, source: "allocator_fallback" };
    const g = groupProposals({ ...run, proposals: [prop, fb, prop] });
    expect(g.scout.map((x) => x.i)).toEqual([0, 2]);
    expect(g.fallback.map((x) => x.i)).toEqual([1]);
  });
});
