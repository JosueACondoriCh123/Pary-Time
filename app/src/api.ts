// Cliente de la API del núcleo, tipado con los contratos generados. El token viaja solo en el header.
import type {
  ActivitySummary,
  BlockCreate,
  BlockUpdate,
  BlockView,
  CouncilRun,
  ExperimentProgress,
  ExperimentRecord,
  Health,
  JournalVerify,
  LedgerEntry,
  OverlayState,
  Report,
  RuntimeStatus,
  Settings,
  VetoRegret,
} from "./contracts";
import type { Connection } from "./bridge";

export const TOKEN_HEADER = "X-NDE1-Token";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly human: string,
    readonly detail?: string,
  ) {
    super(human);
  }
}

/** El mensaje que ve la persona. 409 y 501 tienen texto propio; el resto, uno corto y sin culpa. */
export function humanError(status: number, detail?: string): string {
  switch (status) {
    case 0:
      return "El núcleo no responde. Si sigue así, reiniciá la app.";
    case 401:
      return "El núcleo rechazó la sesión. Reiniciá la app.";
    case 404:
      return "Eso ya no existe. Recargá la vista.";
    case 409:
      return detail ? `No se puede ahora: ${detail}` : "No se puede ahora: el bloque ya no está editable.";
    case 422:
      return "Algún dato no es válido. Revisá el formulario.";
    case 501:
      return "Todavía no disponible en esta versión.";
    default:
      return status >= 500 ? "El núcleo tuvo un error. Probá de nuevo en un rato." : `Error ${status}.`;
  }
}

export interface Api {
  readonly fixtures: boolean;
  health(): Promise<Health>;
  listBlocks(date: string): Promise<BlockView[]>;
  createBlock(body: BlockCreate): Promise<BlockView>;
  updateBlock(id: string, body: BlockUpdate): Promise<BlockView>;
  cancelBlock(id: string): Promise<BlockView>;
  confirmDay(date: string): Promise<BlockView[]>;
  setFirstStep(id: string, text: string): Promise<BlockView>;
  abortBlock(id: string): Promise<BlockView>;
  overlay(): Promise<OverlayState>;
  runtimeStatus(): Promise<RuntimeStatus>;
  emergencyRelease(): Promise<RuntimeStatus>;
  currentExperiment(): Promise<ExperimentProgress | null>;
  experiments(): Promise<ExperimentRecord[]>;
  runCouncil(): Promise<CouncilRun>;
  councilRuns(): Promise<CouncilRun[]>;
  ledger(): Promise<LedgerEntry[]>;
  vetoRegret(): Promise<VetoRegret>;
  report(): Promise<Report>;
  verifyJournal(): Promise<JournalVerify>;
  settings(): Promise<Settings>;
  putSettings(body: Settings): Promise<Settings>;
  activityToday(): Promise<ActivitySummary>;
  pauseSensor(minutes: number): Promise<ActivitySummary>;
  resumeSensor(): Promise<ActivitySummary>;
}

type GetConnection = () => Promise<Connection | null>;

export function httpApi(getConnection: GetConnection, fetchImpl: typeof fetch = fetch): Api {
  async function call<T>(method: string, path: string, body?: unknown, auth = true): Promise<T> {
    const conn = await getConnection();
    if (!conn) throw new ApiError(0, "El núcleo está arrancando. Un segundo…");
    const headers: Record<string, string> = {};
    if (auth) headers[TOKEN_HEADER] = conn.token;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    let res: Response;
    try {
      res = await fetchImpl(conn.baseUrl + path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, humanError(0));
    }
    if (!res.ok) {
      let detail: string | undefined;
      try {
        const data = (await res.json()) as { detail?: unknown };
        if (typeof data.detail === "string") detail = data.detail;
      } catch {
        /* sin cuerpo JSON */
      }
      throw new ApiError(res.status, humanError(res.status, detail), detail);
    }
    return (await res.json()) as T;
  }

  const q = encodeURIComponent;
  return {
    fixtures: false,
    health: () => call("GET", "/health", undefined, false),
    listBlocks: (date) => call("GET", `/blocks?date=${q(date)}`),
    createBlock: (body) => call("POST", "/blocks", body),
    updateBlock: (id, body) => call("PATCH", `/blocks/${q(id)}`, body),
    cancelBlock: (id) => call("DELETE", `/blocks/${q(id)}`),
    confirmDay: (date) => call("POST", "/blocks/confirm", { local_date: date }),
    setFirstStep: (id, text) => call("POST", `/blocks/${q(id)}/first_step`, { text }),
    abortBlock: (id) => call("POST", `/blocks/${q(id)}/abort`),
    overlay: () => call("GET", "/runtime/overlay"),
    runtimeStatus: () => call("GET", "/runtime/status"),
    emergencyRelease: () => call("POST", "/runtime/emergency_release"),
    currentExperiment: () => call("GET", "/experiments/current"),
    experiments: () => call("GET", "/experiments"),
    runCouncil: () => call("POST", "/council/run"),
    councilRuns: () => call("GET", "/council/runs"),
    ledger: () => call("GET", "/ledger"),
    vetoRegret: () => call("GET", "/veto_regret"),
    report: () => call("GET", "/report"),
    verifyJournal: () => call("GET", "/journal/verify"),
    settings: () => call("GET", "/settings"),
    putSettings: (body) => call("PUT", "/settings", body),
    activityToday: () => call("GET", "/activity/today"),
    pauseSensor: (minutes) => call("POST", `/activity/pause?minutes=${minutes}`),
    resumeSensor: () => call("POST", "/activity/resume"),
  };
}
