import { useEffect, useRef, useState, type ReactNode } from "react";
import type { NavTarget } from "./bridge";
import { FIXTURES, useCore, useLoad } from "./core";
import { readProfile, saveProfile, type AccessMode, type LocalProfile } from "./lib/local-profile";
import { Access } from "./views/Access";
import { Experiment } from "./views/Experiment";
import { History } from "./views/History";
import { Planner } from "./views/Planner";
import { Profile } from "./views/Profile";
import { ReportView } from "./views/ReportView";
import { Results } from "./views/Results";
import { SettingsView } from "./views/SettingsView";
import { Today } from "./views/Today";
import { Welcome, type AppView } from "./views/Welcome";
import "./secondary.css";

const NAV: { id: AppView; label: string }[] = [
  { id: "home", label: "Inicio" },
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

export function App() {
  const [view, setView] = useState<AppView>("home");
  const [profile, setProfile] = useState(readProfile);
  const [mode, setMode] = useState<AccessMode>("guest");
  const contentRef = useRef<HTMLElement>(null);

  useEffect(() => window.nde1?.onNavigate(setView), []);
  useEffect(() => {
    contentRef.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [view]);
  const synthetic = useDataLabel() === "sintetico";
  const isSecondary = ["home", "profile", "login", "signup"].includes(view);
  function guest() { setMode("guest"); setView("home"); }
  function updateProfile(next: LocalProfile) { setProfile(next); return saveProfile(next); }
  const content = view === "home" ? <Welcome profile={profile} mode={mode} navigate={setView} />
    : view === "profile" ? <Profile profile={profile} mode={mode} onSave={updateProfile} onGuest={guest} navigate={setView} />
    : view === "login" || view === "signup" ? <Access key={view} kind={view}
      onSwitch={() => setView(view === "login" ? "signup" : "login")}
      onGuest={guest} onHome={() => setView("home")}
      onComplete={(displayName) => {
        if (displayName) setProfile((p) => ({ ...p, displayName }));
        setMode("demo"); setView("profile");
      }} />
    : VIEWS[view]();

  return (
    <div className="shell secondary-shell">
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
        <div className="nav-account">
          <button type="button" className={view === "profile" ? "nav-item on profile-nav" : "nav-item profile-nav"}
            aria-current={view === "profile" ? "page" : undefined} onClick={() => setView("profile")}>
            <span className="nav-avatar" aria-hidden="true">{Array.from(profile.displayName || "I")[0].toUpperCase()}</span>
            <span>Mi perfil<small>{mode === "guest" ? "Modo invitado" : "Sesión de demo"}</small></span>
          </button>
          {mode === "guest" ? <button type="button" className="nav-login" aria-current={view === "login" ? "page" : undefined} onClick={() => setView("login")}>Iniciar sesión <span aria-hidden="true">↗</span></button>
            : <button type="button" className="nav-login" onClick={guest}>Salir de la demo</button>}
        </div>
      </nav>
      <main ref={contentRef} tabIndex={-1} className={isSecondary ? "content secondary-content" : "content"}>
        <SidecarBanner />
        {content}
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
