// Modo ejemplos (VITE_FIXTURES=1): la UI lee contracts/examples/*.json en lugar del núcleo.
// Solo para desarrollo. vite.config.ts se niega a empaquetarlo y la franja "DATOS DE EJEMPLO" queda fija.
import type { Api } from "./api";
import { ApiError, humanError } from "./api";
import type { BlockView, CouncilRun, ExperimentRecord, LedgerEntry, Report, Settings } from "./contracts";
import { toEpochMs, clock } from "./lib/time";

const files = import.meta.glob<{ default: unknown }>("../../contracts/examples/*.json", { eager: true });

function example<T>(name: string): T {
  const hit = Object.entries(files).find(([path]) => path.endsWith(`/${name}.json`));
  if (!hit) throw new Error(`falta contracts/examples/${name}.json`);
  return structuredClone(hit[1].default) as T;
}

const delay = <T>(value: T, ms = 120) => new Promise<T>((r) => setTimeout(() => r(structuredClone(value)), ms));

function moveToDate(block: BlockView, date: string): BlockView {
  return { ...block, local_date: date, planned_start_ms: toEpochMs(date, clock(block.planned_start_ms)) };
}

export function fixturesApi(): Api {
  const byDate = new Map<string, BlockView[]>();
  let settings = example<Settings>("Settings");
  let seq = 0;

  const blocksFor = (date: string) => {
    if (!byDate.has(date)) {
      byDate.set(date, [
        moveToDate(example<BlockView>("BlockView.hidden"), date),
        moveToDate(example<BlockView>("BlockView.first_step"), date),
      ]);
    }
    return byDate.get(date)!;
  };
  const find = (id: string) => {
    for (const list of byDate.values()) {
      const b = list.find((x) => x.block_id === id);
      if (b) return b;
    }
    throw new ApiError(404, humanError(404));
  };
  const editable = (b: BlockView) => {
    if (b.status !== "planned") throw new ApiError(409, humanError(409));
  };

  return {
    fixtures: true,
    health: () => delay(example("Health")),
    listBlocks: (date) => delay([...blocksFor(date)].sort((a, b) => a.planned_start_ms - b.planned_start_ms)),
    createBlock: (body) => {
      const b: BlockView = {
        ...body,
        block_id: `blk_${(0xe0000000000 + ++seq).toString(16).padStart(12, "0")}`,
        status: "planned",
        created_ms: Date.now(),
        first_step: null,
        aborted: false,
        arm_revealed: null,
        needs_first_step: false,
        experiment_id: null,
      };
      blocksFor(body.local_date).push(b);
      return delay(b);
    },
    updateBlock: (id, body) => {
      const b = find(id);
      editable(b);
      for (const [k, v] of Object.entries(body)) if (v !== null && v !== undefined) Object.assign(b, { [k]: v });
      return delay(b);
    },
    cancelBlock: (id) => {
      const b = find(id);
      editable(b);
      b.status = "cancelled";
      return delay(b);
    },
    confirmDay: (date) => {
      // En ejemplos no hay sorteo: la condición queda oculta, como en la API real antes de la hora.
      for (const b of blocksFor(date)) if (b.status === "planned") b.status = "confirmed";
      return delay(blocksFor(date));
    },
    setFirstStep: (id, text) => {
      const b = find(id);
      if (b.arm_revealed !== "primer_paso") throw new ApiError(409, humanError(409));
      b.first_step = text;
      b.needs_first_step = false;
      return delay(b);
    },
    abortBlock: (id) => {
      const b = find(id);
      b.aborted = true;
      return delay(b);
    },
    overlay: () => delay(example("OverlayState")),
    runtimeStatus: () => delay(example("RuntimeStatus")),
    emergencyRelease: () => delay({ ...example<object>("RuntimeStatus"), emergency_released: true } as never),
    currentExperiment: () => delay(example("ExperimentProgress")),
    experiments: () => delay([example<ExperimentRecord>("ExperimentRecord")]),
    runCouncil: () => delay(example<CouncilRun>("CouncilRun"), 900),
    councilRuns: () => delay([example<CouncilRun>("CouncilRun")]),
    ledger: () => delay(example<LedgerEntry[]>("LedgerEntry.list")),
    vetoRegret: () => delay(example("VetoRegret")),
    report: () => delay(example<Report>("Report")),
    verifyJournal: () => delay(example<Report>("Report").journal),
    settings: () => delay(settings),
    putSettings: (body) => {
      settings = body;
      return delay(settings);
    },
    activityToday: () => delay(example("ActivitySummary")),
    pauseSensor: (minutes) =>
      delay({ ...example<object>("ActivitySummary"), paused_until_ms: Date.now() + minutes * 60_000 } as never),
    resumeSensor: () => delay(example("ActivitySummary")),
  };
}
