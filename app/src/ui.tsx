// Piezas chicas de UI compartidas por las vistas.
import { useState, type ReactNode } from "react";
import type { ApiError } from "./api";
import { toApiError } from "./core";

export function Chips<T extends string>(props: {
  options: readonly T[];
  value: T | null;
  label: (v: T) => string;
  onChange: (v: T) => void;
  name: string;
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={props.name}>
      {props.options.map((o) => (
        <button
          key={o}
          type="button"
          role="radio"
          aria-checked={props.value === o}
          className={props.value === o ? "chip on" : "chip"}
          onClick={() => props.onChange(o)}
        >
          {props.label(o)}
        </button>
      ))}
    </div>
  );
}

export function ErrorNote({ error }: { error: ApiError | null | undefined }) {
  if (!error) return null;
  return (
    <p className={error.status === 501 ? "note soon" : "note error"} role="alert">
      {error.human}
    </p>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{children}</section>;
}

/** Ejecuta una acción async mostrando "ocupado" y el error humano si falla. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(toApiError(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run, clear: () => setError(null) };
}

export const DISCLAIMER = "Ajustes de flujo de trabajo medidos sobre vos. No es tratamiento ni consejo médico.";

export function Disclaimer({ text = DISCLAIMER }: { text?: string }) {
  return <p className="disclaimer">{text}</p>;
}
