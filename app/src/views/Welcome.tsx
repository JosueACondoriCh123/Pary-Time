import type { NavTarget } from "../bridge";
import { useLoad } from "../core";
import { INTENTIONS, type AccessMode, type LocalProfile } from "../lib/local-profile";
import { today } from "../lib/time";

export type SecondaryView = "home" | "profile" | "login" | "signup";
export type AppView = NavTarget | SecondaryView;

export function Welcome({ profile, mode, navigate }: {
  profile: LocalProfile;
  mode: AccessMode;
  navigate: (view: AppView) => void;
}) {
  const date = today();
  const blocks = useLoad((api) => api.listBlocks(date), [date]);
  const planned = blocks.data?.filter((b) => b.status !== "cancelled").length;
  const dateLabel = new Intl.DateTimeFormat("es", { weekday: "long", day: "numeric", month: "long" }).format(new Date());

  return (
    <div className="secondary-view welcome-view">
      <header className="secondary-head">
        <div><p className="eyebrow">TU ESPACIO PERSONAL</p><h1>Inicio</h1></div>
        <span className="access-pill"><span aria-hidden="true" />{mode === "guest" ? "Modo invitado" : "Sesión de demo"}</span>
      </header>

      <section className="welcome-hero">
        <div className="welcome-copy">
          <p className="eyebrow">{profile.displayName ? `HOLA, ${profile.displayName}` : "UN NUEVO PUNTO DE PARTIDA"}</p>
          <h2>Un paso pequeño.<br /><span>Un ritmo más tuyo.</span></h2>
          <p>No hace falta resolver todo hoy. Elegí una tarea y descubrí qué te ayuda a empezar.</p>
          <div className="secondary-actions">
            <button type="button" className="primary" onClick={() => navigate("planner")}>Planificar un bloque <span aria-hidden="true">↗</span></button>
            <button type="button" className="quiet-button" onClick={() => navigate("today")}>Ver mi día <span aria-hidden="true">→</span></button>
          </div>
          <p className="hero-footnote">A tu ritmo. Sin una cuenta obligatoria.</p>
        </div>
        <div className="focus-art" aria-hidden="true">
          <div className="focus-orbit orbit-one" /><div className="focus-orbit orbit-two" />
          <div className="focus-spark spark-one">✦</div><div className="focus-spark spark-two">✦</div>
          <div className="focus-note"><span className="focus-note-label">TU PRÓXIMO PASO</span><span className="focus-note-check">✓</span><strong>Solo empezar.</strong><span>Lo demás, de a poco.</span><div className="focus-note-line" /></div>
          <div className="focus-caption">menos presión · más intención</div>
        </div>
      </section>

      <div className="welcome-summary">
        <div><span className="summary-symbol" aria-hidden="true">◷</span><div><p className="eyebrow">TU DÍA, A MANO</p><p className="welcome-date">{dateLabel}</p></div></div>
        <p>{blocks.error ? "Consultá tus bloques en Hoy." : planned !== undefined ? `${planned} ${planned === 1 ? "bloque planificado" : "bloques planificados"}` : "Consultando tus bloques…"}</p>
        <button type="button" className="quiet-button" onClick={() => navigate("today")}>Abrir Hoy <span aria-hidden="true">→</span></button>
      </div>

      <section aria-labelledby="welcome-path-title">
        <div className="section-heading"><h2 id="welcome-path-title">Hacé lugar a lo que importa</h2><span className="muted small">Un experimento a la vez</span></div>
        <div className="welcome-paths">
          <button type="button" className="path-card" onClick={() => navigate("planner")}><span className="path-number">01 <span aria-hidden="true">↗</span></span><strong>Prepará el primer paso</strong><span>Una tarea concreta, un horario y algo sencillo por donde empezar.</span><span className="path-link">Ir al planificador →</span></button>
          <button type="button" className="path-card" onClick={() => navigate("experiment")}><span className="path-number">02 <span aria-hidden="true">↗</span></span><strong>Probá qué te ayuda</strong><span>Conocé el experimento y las condiciones que vas a comparar.</span><span className="path-link">Ver experimento →</span></button>
          <button type="button" className="path-card" onClick={() => navigate("results")}><span className="path-number">03 <span aria-hidden="true">↗</span></span><strong>Aprendé de tus días</strong><span>Revisá los resultados cuando haya datos suficientes. Sin sacar conclusiones antes.</span><span className="path-link">Explorar resultados →</span></button>
        </div>
      </section>

      <section className="intention-strip">
        <span className="intention-star" aria-hidden="true">✧</span><div><p className="eyebrow">TU INTENCIÓN</p><p>{INTENTIONS[profile.intention]}</p></div>
        <button type="button" className="quiet-button" onClick={() => navigate("profile")}>Personalizar mi perfil →</button>
      </section>
    </div>
  );
}
