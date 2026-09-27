import { useState, type FormEvent } from "react";
import { INTENTIONS, type AccessMode, type Intention, type LocalProfile } from "../lib/local-profile";
import type { AppView } from "./Welcome";

export function Profile({ profile, mode, onSave, onGuest, navigate }: {
  profile: LocalProfile;
  mode: AccessMode;
  onSave: (profile: LocalProfile) => boolean;
  onGuest: () => void;
  navigate: (view: AppView) => void;
}) {
  const [draft, setDraft] = useState(profile);
  const [feedback, setFeedback] = useState<"saved" | "unavailable" | null>(null);
  const initials = (draft.displayName.trim() || "Invitado").split(/\s+/).slice(0, 2).map((word) => Array.from(word)[0]).join("").toUpperCase();

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = { ...draft, displayName: draft.displayName.trim() };
    setDraft(next);
    setFeedback(onSave(next) ? "saved" : "unavailable");
  }

  return (
    <div className="secondary-view profile-view">
      <header className="secondary-head"><div><p className="eyebrow">UN ESPACIO A TU MEDIDA</p><h1>Mi perfil</h1></div><span className="access-pill"><span aria-hidden="true" />{mode === "guest" ? "Modo invitado" : "Sesión de demo"}</span></header>
      <section className="profile-cover">
        <div className="profile-avatar" aria-hidden="true">{initials}</div>
        <div><p className="eyebrow">HOLA, QUÉ BUENO TENERTE ACÁ</p><h2>{draft.displayName.trim() || "Tu espacio empieza con vos"}</h2><p>Pequeños cambios. Un día a la vez.</p></div>
        <span className="profile-cover-star" aria-hidden="true">✧</span>
      </section>
      <div className="profile-layout">
        <form className="profile-form secondary-panel" onSubmit={submit}>
          <div className="section-heading"><h2>Hacelo tuyo</h2><span className="small muted">Perfil local</span></div>
          <p className="muted">No necesitás una cuenta para personalizar este espacio.</p>
          <label htmlFor="profile-name">¿Cómo te llamamos?<input id="profile-name" autoComplete="nickname" value={draft.displayName} placeholder="Tu nombre o apodo (opcional)" maxLength={40} onChange={(e) => { setDraft({ ...draft, displayName: e.target.value }); setFeedback(null); }} /><span className="small">Se muestra en tu inicio. Podés dejarlo en blanco.</span></label>
          <fieldset className="intention-options"><legend>¿Qué te gustaría hacer más fácil?</legend>{Object.entries(INTENTIONS).map(([id, label], index) => <label key={id} className={draft.intention === id ? "intention-option selected" : "intention-option"}><input type="radio" name="intention" value={id} checked={draft.intention === id} onChange={() => { setDraft({ ...draft, intention: id as Intention }); setFeedback(null); }} /><span className="intention-option-icon" aria-hidden="true">{["↗", "◎", "≈"][index]}</span><span>{label}</span></label>)}</fieldset>
          <p className="small muted">Esta intención personaliza tu inicio; no cambia las reglas ni los resultados del experimento.</p>
          <div className="profile-save"><button type="submit" className="primary">Guardar perfil</button><p role="status" className={feedback === "unavailable" ? "note warn" : "profile-feedback"}>{feedback === "saved" ? "Listo, tu perfil quedó guardado en este dispositivo." : feedback === "unavailable" ? "Cambios aplicados por ahora. Este dispositivo no permitió guardarlos; se perderán al cerrar o recargar." : ""}</p></div>
        </form>
        <aside className="profile-aside">
          <section className="secondary-panel profile-access"><span className="profile-panel-icon" aria-hidden="true">◉</span><h2>{mode === "guest" ? "Entrá a tu manera" : "Estás probando la demo"}</h2><p className="muted">{mode === "guest" ? "Ya tenés acceso a todas las herramientas. Si querés, también podés explorar los formularios de acceso." : "Esta sesión es simulada y termina al recargar o cerrar la app. No hay una cuenta real ni sincronización."}</p>{mode === "guest" ? <><button type="button" onClick={() => navigate("login")}>Probar inicio de sesión</button><button type="button" className="text-button" onClick={() => navigate("signup")}>Crear perfil de demo →</button></> : <button type="button" onClick={onGuest}>Salir de la demo</button>}<span className="profile-access-note">Tus bloques permanecen en esta instalación al cambiar de modo.</span></section>
          <section className="secondary-panel"><span className="profile-panel-icon" aria-hidden="true">◇</span><h2>Vos tenés el control</h2><p className="muted">El nombre y la intención se guardan en este dispositivo. La captura de actividad se controla por separado.</p><button type="button" className="text-button" onClick={() => navigate("settings")}>Revisar ajustes y sensor →</button></section>
        </aside>
      </div>
    </div>
  );
}
