/** Preferencias de presentación locales. No son identidad ni credenciales. */
export const PROFILE_KEY = "nde1.local-profile.v1";
export const INTENTIONS = {
  start: "Que empezar sea más fácil",
  focus: "Hacer espacio para concentrarme",
  balance: "Encontrar un ritmo sostenible",
} as const;
export type Intention = keyof typeof INTENTIONS;
export interface LocalProfile {
  displayName: string;
  intention: Intention;
}
export type AccessMode = "guest" | "demo";
export const EMPTY_PROFILE: LocalProfile = { displayName: "", intention: "start" };

export function readProfile(): LocalProfile {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(PROFILE_KEY) ?? "null");
    if (!value || typeof value !== "object") return { ...EMPTY_PROFILE };
    const p = value as Record<string, unknown>;
    return {
      displayName: typeof p.displayName === "string" ? p.displayName.trim().slice(0, 40) : "",
      intention: typeof p.intention === "string" && Object.hasOwn(INTENTIONS, p.intention) ? p.intention as Intention : "start",
    };
  } catch {
    return { ...EMPTY_PROFILE };
  }
}

export function saveProfile(profile: LocalProfile): boolean {
  try {
    // Lista explícita: jamás persistir campos del formulario de acceso.
    localStorage.setItem(PROFILE_KEY, JSON.stringify({
      displayName: profile.displayName.trim().slice(0, 40),
      intention: profile.intention,
    }));
    return true;
  } catch {
    return false;
  }
}
