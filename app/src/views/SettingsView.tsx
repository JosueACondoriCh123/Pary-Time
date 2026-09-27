// "Ajustes": listas del sensor, retención, modelos de Ollama, arranque con Windows y pausa del sensor.
import { useEffect, useState } from "react";
import type { Prefs } from "../bridge";
import type { Settings } from "../contracts";
import { useCore, useLoad } from "../core";
import { Card, ErrorNote, useAction } from "../ui";
import { SensorCard } from "./Today";

type ListKey = "distraction_processes" | "distraction_title_patterns" | "browser_processes" | "whitelist_processes";

const LISTS: { key: ListKey; label: string; hint: string }[] = [
  { key: "distraction_processes", label: "Programas que distraen", hint: "Uno por línea. Ej.: Discord.exe" },
  { key: "distraction_title_patterns", label: "Sitios que distraen", hint: "Texto del título del navegador. Ej.: youtube" },
  { key: "browser_processes", label: "Navegadores", hint: "Para buscar sitios que distraen en sus títulos." },
  { key: "whitelist_processes", label: "Lista blanca", hint: "Nunca se minimizan. Ej.: Teams.exe" },
];

export const toLines = (xs: string[] | undefined) => (xs ?? []).join("\n");
export const fromLines = (s: string) => [...new Set(s.split(/\r?\n/).map((x) => x.trim()).filter(Boolean))];

export function SettingsView() {
  const { api } = useCore();
  const settings = useLoad((a) => a.settings(), []);
  const [draft, setDraft] = useState<Settings | null>(null);
  const [lists, setLists] = useState<Record<ListKey, string> | null>(null);
  const save = useAction();
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const base = draft ?? settings.data ?? null;
  const texts =
    lists ?? (base ? (Object.fromEntries(LISTS.map((l) => [l.key, toLines(base[l.key])])) as Record<ListKey, string>) : null);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    if (!base || !texts) return;
    const body: Settings = { ...base };
    for (const l of LISTS) body[l.key] = fromLines(texts[l.key]);
    const next = await save.run(() => api.putSettings(body));
    if (next) {
      settings.setData(next);
      setDraft(null);
      setLists(null);
      setSavedAt(Date.now());
    }
  }

  return (
    <div className="view">
      <header className="view-head">
        <h1>Ajustes</h1>
      </header>

      <StartupCard />
      <SensorCard />

      <ErrorNote error={settings.error} />
      {base && texts && (
        <form onSubmit={onSave} className="view">
          <Card className="list-edit">
            <h2>Distracciones</h2>
            <div className="grid-2">
              {LISTS.map((l) => (
                <label key={l.key}>
                  {l.label}
                  <textarea
                    value={texts[l.key]}
                    onChange={(e) => setLists({ ...texts, [l.key]: e.target.value })}
                    spellCheck={false}
                  />
                  <span className="small">{l.hint}</span>
                </label>
              ))}
            </div>
          </Card>

          <Card>
            <h2>Privacidad y modelos</h2>
            <div className="grid-2">
              <label>
                Días que se guardan los títulos crudos
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={base.raw_retention_days ?? 14}
                  onChange={(e) => setDraft({ ...base, raw_retention_days: Number(e.target.value) || 1 })}
                />
              </label>
              <label>
                Ollama
                <input
                  value={base.ollama_base_url ?? ""}
                  onChange={(e) => setDraft({ ...base, ollama_base_url: e.target.value })}
                />
              </label>
              <label>
                Modelo del Scout
                <input value={base.scout_model ?? ""} onChange={(e) => setDraft({ ...base, scout_model: e.target.value })} />
              </label>
              <label>
                Modelo del Red Team (otra familia)
                <input
                  value={base.red_team_model ?? ""}
                  onChange={(e) => setDraft({ ...base, red_team_model: e.target.value })}
                />
              </label>
            </div>
            <p className="muted small">
              Fijos por diseño: α de la familia {base.family_alpha ?? 0.05}, exploración{" "}
              {Math.round((base.exploration_fraction ?? 0.1) * 100)}%, tope de alta fricción{" "}
              {Math.round((base.high_friction_max_fraction ?? 0.5) * 100)}%.
            </p>
          </Card>

          <div className="row">
            <button type="submit" className="primary" disabled={save.busy || (!draft && !lists)}>
              Guardar ajustes
            </button>
            {savedAt && !draft && !lists && <span className="pass small">Guardado.</span>}
          </div>
          <ErrorNote error={save.error} />
        </form>
      )}
    </div>
  );
}

function StartupCard() {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  useEffect(() => {
    void window.nde1?.prefs().then(setPrefs);
  }, []);
  if (!window.nde1 || !prefs) return null;
  return (
    <Card>
      <label className="check">
        <input
          type="checkbox"
          checked={prefs.openAtLogin}
          onChange={async (e) => setPrefs(await window.nde1!.setPrefs({ openAtLogin: e.target.checked }))}
        />
        Arrancar con Windows
      </label>
      <p className="muted small">Sin esto no se miden las mañanas. Arranca escondida en la bandeja.</p>
    </Card>
  );
}
