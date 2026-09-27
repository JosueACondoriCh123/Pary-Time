// Contexto de la app: qué API usar (núcleo real o ejemplos) y el estado del sidecar.
import { createContext, useCallback, useContext, useEffect, useEffectEvent, useMemo, useState, type ReactNode } from "react";
import { ApiError, httpApi, type Api } from "./api";
import type { SidecarState } from "./bridge";

export const FIXTURES = import.meta.env.VITE_FIXTURES === "1";

interface CoreValue {
  api: Api;
  sidecar: SidecarState;
  ready: boolean;
}

const CoreContext = createContext<CoreValue | null>(null);

async function makeApi(): Promise<Api> {
  if (FIXTURES) {
    const { fixturesApi } = await import("./fixtures"); // eliminado del build de producción
    return fixturesApi();
  }
  return httpApi(async () => (window.nde1 ? window.nde1.connection() : null));
}

export function CoreProvider({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<Api | null>(null);
  const [sidecar, setSidecar] = useState<SidecarState>(
    FIXTURES ? { phase: "ready", baseUrl: "fixtures", version: "ejemplos" } : { phase: "starting" },
  );

  useEffect(() => {
    void makeApi().then(setApi);
    if (FIXTURES || !window.nde1) return;
    void window.nde1.sidecar().then(setSidecar);
    return window.nde1.onSidecar(setSidecar);
  }, []);

  const value = useMemo(
    () => (api ? { api, sidecar, ready: sidecar.phase === "ready" } : null),
    [api, sidecar],
  );
  if (!value) return null;
  return <CoreContext.Provider value={value}>{children}</CoreContext.Provider>;
}

export function useCore(): CoreValue {
  const v = useContext(CoreContext);
  if (!v) throw new Error("useCore fuera de CoreProvider");
  return v;
}

export interface Loaded<T> {
  data: T | undefined;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  setData: (data: T) => void;
}

/** Carga datos de la API cuando el núcleo está listo, y cada `everyMs` si se pide.
 *  `loading` es true mientras no haya respuesta para los `deps` actuales; un `reload` mantiene lo que había. */
export function useLoad<T>(fn: (api: Api) => Promise<T>, deps: unknown[], everyMs?: number): Loaded<T> {
  const { api, ready } = useCore();
  const key = JSON.stringify(deps);
  const [result, setResult] = useState<{ key: string; data?: T; error: ApiError | null } | null>(null);
  const [tick, setTick] = useState(0);
  const load = useEffectEvent(() => fn(api));

  useEffect(() => {
    if (!ready) return;
    let alive = true;
    load()
      .then((data) => alive && setResult({ key, data, error: null }))
      .catch((e: unknown) => alive && setResult((r) => ({ key, data: r?.key === key ? r.data : undefined, error: toApiError(e) })));
    return () => {
      alive = false;
    };
  }, [api, ready, tick, key]);

  useEffect(() => {
    if (!everyMs || !ready) return;
    const id = setInterval(() => setTick((t) => t + 1), everyMs);
    return () => clearInterval(id);
  }, [everyMs, ready]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((data: T) => setResult({ key, data, error: null }), [key]);
  const current = result?.key === key ? result : null;
  return { data: current?.data, error: current?.error ?? null, loading: !current, reload, setData };
}

export function toApiError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError(0, "Algo falló. Probá de nuevo.", String(e));
}

/** Reloj que avanza cada `ms` para cuentas regresivas y "falta x". */
export function useNow(ms = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}
