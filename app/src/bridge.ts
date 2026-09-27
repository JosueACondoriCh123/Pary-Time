// Lo que el preload expone como `window.nde1`. Solo tipos: lo comparten el proceso principal y el renderer.

export type SidecarState =
  | { phase: "starting" }
  | { phase: "ready"; baseUrl: string; version: string }
  | { phase: "restarting"; retryInMs: number; stderr: string }
  | { phase: "failed"; stderr: string };

export interface Connection {
  baseUrl: string;
  /** Vive solo en memoria: nunca va al localStorage ni a la URL. */
  token: string;
}

export interface Prefs {
  openAtLogin: boolean;
}

export type NavTarget = "planner" | "today" | "history" | "experiment" | "results" | "report" | "settings";

export interface Nde1Bridge {
  sidecar(): Promise<SidecarState>;
  connection(): Promise<Connection | null>;
  onSidecar(cb: (state: SidecarState) => void): () => void;
  retrySidecar(): Promise<void>;
  pickFile(): Promise<string | null>;
  saveFile(opts: { defaultName: string; content: string; ext: "html" | "json" }): Promise<boolean>;
  prefs(): Promise<Prefs>;
  setPrefs(prefs: Partial<Prefs>): Promise<Prefs>;
  onNavigate(cb: (to: NavTarget) => void): () => void;
  setOverlayVisible(visible: boolean): void;
}

declare global {
  interface Window {
    nde1?: Nde1Bridge;
  }
}
