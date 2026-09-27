import { useState, type FormEvent } from "react";

export function Access({ kind, onSwitch, onGuest, onHome, onComplete }: {
  kind: "login" | "signup";
  onSwitch: () => void;
  onGuest: () => void;
  onHome: () => void;
  onComplete: (displayName?: string) => void;
}) {
  const signup = kind === "signup";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (signup && !name.trim()) {
      setError("Elegí un nombre o apodo para tu perfil de demo.");
      return;
    }
    // Simulación explícita: no hay petición de autenticación ni persistencia de credenciales.
    setEmail("");
    setPassword("");
    onComplete(signup ? name.trim() : undefined);
  }

  return (
    <div className="secondary-view access-view">
      <button type="button" className="quiet-button back-link" onClick={onHome}>← Volver al inicio</button>
      <div className="access-layout">
        <section className="access-story">
          <span className="access-monogram" aria-hidden="true">n<span>1</span></span>
          <p className="eyebrow">CONSEJO N-DE-1</p>
          <h2>Tu espacio.<br />Tu ritmo.<br /><span>Tu manera.</span></h2>
          <p>Un lugar para probar pequeños cambios y entender qué te ayuda a arrancar.</p>
          <div className="access-story-note"><span aria-hidden="true">✧</span><p>Podés usar todas las herramientas como invitado. Crear una cuenta es opcional.</p></div>
          <div className="access-story-orbit" aria-hidden="true"><span>UN PASO A LA VEZ</span></div>
        </section>

        <section className="access-panel" aria-labelledby="access-title">
          <span className="demo-badge">ACCESO DE DEMOSTRACIÓN</span>
          <h1 id="access-title">{signup ? "Creá tu espacio" : "Qué bueno verte"}</h1>
          <p className="muted">{signup ? "Probá cómo sería crear tu perfil." : "Probá el inicio de sesión de la app."}</p>
          <p className="demo-explanation" id="demo-explanation">Usá datos inventados. Este formulario es una simulación: no crea cuentas ni envía o guarda el correo y la contraseña.</p>

          <button type="button" className="guest-entry" onClick={onGuest}>Continuar como invitado <span aria-hidden="true">→</span></button>
          <p className="guest-entry-caption">Sin registro · acceso a todas las herramientas</p>
          <div className="access-divider"><span>o probá la demo con un perfil</span></div>

          <form className="access-form" onSubmit={submit} aria-describedby="demo-explanation">
            {signup && <label htmlFor="demo-name">Nombre o apodo<input id="demo-name" name="demo-name" autoComplete="off" value={name} maxLength={40} required placeholder="¿Cómo te gustaría que te llamemos?" onChange={(e) => { setName(e.target.value); setError(""); }} /></label>}
            <label htmlFor="demo-email">Correo de ejemplo<input id="demo-email" name="demo-email" type="email" autoComplete="off" spellCheck={false} value={email} maxLength={254} required placeholder="demo@example.com" onChange={(e) => setEmail(e.target.value)} /></label>
            <label htmlFor="demo-password">Contraseña de ejemplo</label>
            <div className="password-field"><input id="demo-password" name="demo-password" type={showPassword ? "text" : "password"} autoComplete="off" value={password} minLength={8} maxLength={128} required aria-describedby="password-hint" placeholder="Al menos 8 caracteres inventados" onChange={(e) => setPassword(e.target.value)} /><button type="button" className="password-toggle" aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"} aria-pressed={showPassword} onClick={() => setShowPassword((shown) => !shown)}>{showPassword ? "Ocultar" : "Mostrar"}</button></div>
            <p className="small muted password-hint" id="password-hint">Solo para probar. No uses una contraseña real.</p>
            {error && <p className="note error" role="alert">{error}</p>}
            <button type="submit" className="primary access-submit">{signup ? "Crear perfil de demo" : "Entrar a la demo"} <span aria-hidden="true">→</span></button>
          </form>
          <p className="access-switch">{signup ? "¿Ya tenés un perfil de demo?" : "¿Primera vez por acá?"} <button type="button" className="text-button" onClick={onSwitch}>{signup ? "Iniciar sesión" : "Crear perfil"}</button></p>
          <p className="access-footer">Una cuenta nunca es un requisito para empezar.</p>
        </section>
      </div>
    </div>
  );
}
