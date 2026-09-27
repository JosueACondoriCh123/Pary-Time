import { useEffect, useState, type ReactNode } from "react";
import type { NavTarget } from "./bridge";
import { FIXTURES, useCore, useLoad } from "./core";
import { Experiment } from "./views/Experiment";
import { History } from "./views/History";
import { Planner } from "./views/Planner";
import { ReportView } from "./views/ReportView";
import { Results } from "./views/Results";
import { SettingsView } from "./views/SettingsView";
import { Today } from "./views/Today";

const NAV: { id: NavTarget; label: string }[] = [
  { id: "today", label: "Hoy" },
  { id: "history", label: "Mi tiempo" },
  { id: "planner", label: "Planificar" },
  { id: "experiment", label: "Experimento" },
  { id: "results", label: "Resultados" },
  { id: "report", label: "Reporte" },
  { id: "settings", label: "Ajustes" },
];

const VIEWS: Record<NavTarget, () => ReactNode> = {
  today: () => <Today />,
  history: () => <History />,
  planner: () => <Planner />,
  experiment: () => <Experiment />,
  results: () => <Results />,
  report: () => <ReportView />,
  settings: () => <SettingsView />,
};

/** A la noche se abre en el planificador; de día, en "Hoy". */
function defaultView(now = new Date()): NavTarget {
  const h = now.getHours();
  return h >= 18 || h < 5 ? "planner" : "today";
}

export function App() {
  const [view, setView] = useState<NavTarget>(defaultView);

  useEffect(() => window.nde1?.onNavigate(setView), []);
  const synthetic = useDataLabel() === "sintetico";

  return (
    <div className="shell">
      {FIXTURES ? (
        <div className="fixtures-banner">DATOS DE EJEMPLO</div>
      ) : (
        synthetic && (
          <div className="synthetic-banner" role="status">
            DATOS SINTÉTICOS <span>· generados por el código real con reloj acelerado; no son de una persona</span>
          </div>
        )
      )}
      <nav className="nav" aria-label="Secciones">
        <div className="brand">
          Consejo <span>N-de-1</span>
        </div>
        {NAV.map((n) => (
          <button
            key={n.id}
            type="button"
            className={view === n.id ? "nav-item on" : "nav-item"}
            aria-current={view === n.id ? "page" : undefined}
            onClick={() => setView(n.id)}
          >
            {n.label}
          </button>
        ))}
      </nav>
      <main className="content">
        <SidecarBanner />
        {VIEWS[view]()}
      </main>
    </div>
  );
}

/** `real` o `sintetico`, según el marcador DATA_LABEL del data-dir. Se vuelve a leer si el núcleo se reinicia. */
function useDataLabel(): string | undefined {
  const { sidecar } = useCore();
  const base = sidecar.phase === "ready" ? sidecar.baseUrl : null;
  return useLoad((a) => a.health(), [base]).data?.data_label;
}

function SidecarBanner() {
  const { sidecar } = useCore();
  if (sidecar.phase === "ready") return null;
  if (sidecar.phase === "starting") return <div className="banner">Arrancando el núcleo…</div>;
  if (sidecar.phase === "restarting") {
    return (
      <div className="banner warn">
        El núcleo se cerró. Lo vuelvo a lanzar en {Math.round(sidecar.retryInMs / 1000)} s.
      </div>
    );
  }
  return (
    <div className="banner error" role="alert">
      <p>
        <strong>El núcleo no arranca.</strong> Se cayó varias veces seguidas. Sin él no se mide nada.
      </p>
      {sidecar.stderr && (
        <details>
          <summary>Ver el error</summary>
          <pre>{sidecar.stderr}</pre>
        </details>
      )}
      <button type="button" className="primary" onClick={() => void window.nde1?.retrySidecar()}>
        Reintentar
      </button>
    </div>
  );
}
