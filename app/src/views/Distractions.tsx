// "Distracciones": sitios y programas que cuentan como distracción, al estilo de un bloqueador de Chrome.
// Cada cambio se guarda al instante en /settings. Pausar un sitio lo saca de la lista del sensor pero lo deja
// visible acá (la lista de pausados vive en localStorage: es una preferencia de esta pantalla).
import { useState } from "react";
import type { Settings } from "../contracts";
import { useCore, useLoad } from "../core";
import {
  PACKS, addItems, appSuggestions, hasItem, minutesBySite, monogram, normalizeProcess, normalizeSite,
  packCoverage, removeItem, siteLabel, type Pack,
} from "../lib/sites";
import { fmtMinutes, rangeFor } from "../lib/usage";
import { Card, ErrorNote, useAction } from "../ui";

type Kind = "sites" | "apps";
const FIELD: Record<Kind, "distraction_title_patterns" | "distraction_processes"> = {
  sites: "distraction_title_patterns",
  apps: "distraction_processes",
};

const PAUSED_KEY = "pary.distractions.paused.v1";
type Paused = Record<Kind, string[]>;

function readPaused(): Paused {
  try {
    const v = JSON.parse(localStorage.getItem(PAUSED_KEY) ?? "null") as Partial<Paused> | null;
    return { sites: Array.isArray(v?.sites) ? v.sites : [], apps: Array.isArray(v?.apps) ? v.apps : [] };
  } catch {
    return { sites: [], apps: [] };
  }
}

function writePaused(p: Paused) {
  try {
    localStorage.setItem(PAUSED_KEY, JSON.stringify(p));
  } catch {
    /* sin almacenamiento: los pausados valen solo para esta sesión */
  }
}

export function Distractions() {
  const { api } = useCore();
  const settings = useLoad((a) => a.settings(), []);
  const [from, to] = rangeFor("week");
  const history = useLoad((a) => a.activityHistory(from, to), [from, to], 60_000);
  const [paused, setPausedState] = useState<Paused>(readPaused);
  const save = useAction();
  const [flash, setFlash] = useState<string | null>(null);

  const s = settings.data;
  const setPaused = (p: Paused) => {
    setPausedState(p);
    writePaused(p);
  };

  async function commit(next: Settings, msg: string, nextPaused?: Paused) {
    const prev = s;
    settings.setData(next); // optimista: la tarjeta cambia ya
    if (nextPaused) setPaused(nextPaused);
    const saved = await save.run(() => api.putSettings(next));
    if (saved) {
      settings.setData(saved);
      setFlash(msg);
      window.setTimeout(() => setFlash((f) => (f === msg ? null : f)), 2200);
    } else if (prev) {
      settings.setData(prev);
      if (nextPaused) setPaused(paused);
    }
  }

  if (!s) {
    return (
      <div className="view">
        <header className="view-head"><h1>Distracciones</h1></header>
        <ErrorNote error={settings.error} />
      </div>
    );
  }

  const active: Record<Kind, string[]> = { sites: s.distraction_title_patterns ?? [], apps: s.distraction_processes ?? [] };
  // Un pausado que alguien volvió a agregar desde Ajustes o el núcleo deja de figurar como pausado.
  const pausedNow: Paused = {
    sites: paused.sites.filter((x) => !hasItem(active.sites, x)),
    apps: paused.apps.filter((x) => !hasItem(active.apps, x)),
  };

  const add = (kind: Kind, items: string[], msg: string) => {
    const fresh = items.filter((it) => !hasItem(active[kind], it));
    if (fresh.length === 0) return;
    void commit(
      { ...s, [FIELD[kind]]: addItems(active[kind], fresh) },
      msg,
      { ...pausedNow, [kind]: pausedNow[kind].filter((x) => !hasItem(fresh, x)) },
    );
  };
  const toggle = (kind: Kind, item: string, on: boolean) =>
    void commit(
      { ...s, [FIELD[kind]]: on ? addItems(active[kind], [item]) : removeItem(active[kind], item) },
      on ? `${label(kind, item)} vuelve a contar como distracción.` : `${label(kind, item)} en pausa.`,
      { ...pausedNow, [kind]: on ? removeItem(pausedNow[kind], item) : addItems(pausedNow[kind], [item]) },
    );
  const remove = (kind: Kind, item: string) =>
    void commit(
      { ...s, [FIELD[kind]]: removeItem(active[kind], item) },
      `${label(kind, item)} quitado.`,
      { ...pausedNow, [kind]: removeItem(pausedNow[kind], item) },
    );
  const addPack = (p: Pack) => {
    const sites = p.sites.filter((x) => !hasItem(active.sites, x));
    const apps = p.apps.filter((x) => !hasItem(active.apps, x));
    if (sites.length + apps.length === 0) return;
    void commit(
      { ...s, distraction_title_patterns: addItems(active.sites, sites), distraction_processes: addItems(active.apps, apps) },
      `Paquete "${p.label}" agregado.`,
      { sites: pausedNow.sites.filter((x) => !hasItem(sites, x)), apps: pausedNow.apps.filter((x) => !hasItem(apps, x)) },
    );
  };

  const siteMin = minutesBySite(history.data?.sites ?? []);
  const appMin = new Map((history.data?.apps ?? []).map((a) => [a.process.toLowerCase(), a.minutes]));
  const known = [...active.apps, ...pausedNow.apps, ...(s.browser_processes ?? []), ...(s.whitelist_processes ?? [])];
  const suggestions = appSuggestions(history.data?.apps ?? [], known);
  const weekDistraction = history.data?.totals?.distraction ?? 0;

  return (
    <div className="view distractions">
      <header className="view-head">
        <div>
          <h1>Distracciones</h1>
          <p className="muted">
            Agregá una página o un programa y Pary Time lo reconoce solo. En los bloques con "Retrasar distracciones"
            sus ventanas se minimizan; nunca se cierran.
          </p>
        </div>
      </header>

      <div className="kpis">
        <Kpi label="Sitios activos" value={String(active.sites.length)} hint={pausedNow.sites.length ? `${pausedNow.sites.length} en pausa` : "ninguno en pausa"} />
        <Kpi label="Programas activos" value={String(active.apps.length)} hint={pausedNow.apps.length ? `${pausedNow.apps.length} en pausa` : "ninguno en pausa"} />
        <Kpi label="Distracción · 7 días" value={history.data ? fmtMinutes(weekDistraction) : "—"} hint="medido por el sensor" />
      </div>

      <div className="save-state" role="status" aria-live="polite">
        {save.busy ? "Guardando…" : flash}
      </div>
      <ErrorNote error={save.error} />

      <Card className="dx-section">
        <div className="dx-head">
          <h2>Sitios web</h2>
          <AddForm
            placeholder="youtube.com o pegá la dirección"
            button="Agregar sitio"
            parse={(v) => normalizeSite(v)?.pattern ?? null}
            invalid="Escribí un dominio (youtube.com) o un nombre (youtube)."
            onAdd={(p) => add("sites", [p], `${siteLabel(p)} agregado.`)}
            exists={(p) => hasItem(active.sites, p) || hasItem(pausedNow.sites, p)}
          />
        </div>
        <p className="muted small">
          El navegador no comparte la dirección: se reconoce el sitio porque su nombre aparece en el título de la
          pestaña. Funciona en {(s.browser_processes ?? []).map((b) => b.replace(/\.exe$/i, "")).join(", ")}.
        </p>
        <TileGrid
          kind="sites"
          active={active.sites}
          paused={pausedNow.sites}
          minutes={(x) => siteMin.get(x.toLowerCase())}
          onToggle={toggle}
          onRemove={remove}
          empty="Todavía no agregaste sitios. Probá con un paquete de abajo."
        />
      </Card>

      <Card className="dx-section">
        <h2>Paquetes</h2>
        <p className="muted small">Un clic agrega todos los sitios y programas de la categoría. Después podés pausar los que no quieras.</p>
        <ul className="packs">
          {PACKS.map((p) => {
            const total = p.sites.length + p.apps.length;
            const have = packCoverage(p, [...active.sites, ...pausedNow.sites], [...active.apps, ...pausedNow.apps]);
            const full = have === total;
            return (
              <li key={p.id} className={full ? "pack full" : "pack"}>
                <div>
                  <strong>{p.label}</strong>
                  <span className="muted small">{[...p.sites.map(siteLabel), ...p.apps.map((a) => a.replace(/\.exe$/i, ""))].slice(0, 4).join(" · ")}{total > 4 ? " …" : ""}</span>
                </div>
                <button type="button" className={full ? "small" : "primary small"} disabled={full || save.busy} onClick={() => addPack(p)}>
                  {full ? "Agregado" : have ? `Agregar ${total - have} más` : `Agregar ${total}`}
                </button>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card className="dx-section">
        <div className="dx-head">
          <h2>Programas</h2>
          <AddForm
            placeholder="Discord.exe"
            button="Agregar programa"
            parse={normalizeProcess}
            invalid="Escribí el nombre del ejecutable (Discord.exe)."
            onAdd={(p) => add("apps", [p], `${p} agregado.`)}
            exists={(p) => hasItem(active.apps, p) || hasItem(pausedNow.apps, p)}
          />
        </div>
        <TileGrid
          kind="apps"
          active={active.apps}
          paused={pausedNow.apps}
          minutes={(x) => appMin.get(x.toLowerCase())}
          onToggle={toggle}
          onRemove={remove}
          empty="Ningún programa cuenta como distracción."
        />
        {suggestions.length > 0 && (
          <div className="suggest">
            <h3>Tus apps con más tiempo esta semana</h3>
            <p className="muted small">No están en ninguna lista. ¿Alguna te distrae?</p>
            <div className="chips">
              {suggestions.map((c) => (
                <button key={c.process} type="button" className="chip" disabled={save.busy}
                  onClick={() => add("apps", [c.process], `${c.process} agregado.`)}>
                  + {c.process.replace(/\.exe$/i, "")} <span className="muted">· {fmtMinutes(c.minutes)}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </Card>

      <Card className="dx-section">
        <details>
          <summary><h2>Avanzado</h2><span className="muted small">navegadores y lista blanca</span></summary>
          <div className="grid-2 dx-advanced">
            <ChipList
              title="Navegadores"
              hint="Donde se buscan los sitios. ApplicationFrameHost es el de las apps de la Tienda (WhatsApp de escritorio)."
              items={s.browser_processes ?? []}
              onChange={(items, msg) => void commit({ ...s, browser_processes: items }, msg)}
            />
            <ChipList
              title="Lista blanca"
              hint="Nunca cuentan como distracción ni se minimizan. Ej.: Teams.exe"
              items={s.whitelist_processes ?? []}
              onChange={(items, msg) => void commit({ ...s, whitelist_processes: items }, msg)}
            />
          </div>
        </details>
      </Card>
    </div>
  );
}

function label(kind: Kind, item: string) {
  return kind === "sites" ? siteLabel(item) : item;
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <span className="kpi-hint">{hint}</span>
    </div>
  );
}

function AddForm(props: {
  placeholder: string;
  button: string;
  parse: (v: string) => string | null;
  invalid: string;
  exists: (v: string) => boolean;
  onAdd: (v: string) => void;
}) {
  const [value, setValue] = useState("");
  const [note, setNote] = useState<string | null>(null);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    const parsed = props.parse(value);
    if (!parsed) return setNote(props.invalid);
    if (props.exists(parsed)) return setNote("Ya está en la lista.");
    props.onAdd(parsed);
    setValue("");
    setNote(null);
  }
  return (
    <form className="add-site" onSubmit={submit}>
      <input value={value} onChange={(e) => { setValue(e.target.value); setNote(null); }}
        placeholder={props.placeholder} aria-label={props.button} spellCheck={false} />
      <button type="submit" className="primary" disabled={!value.trim()}>{props.button}</button>
      {note && <span className="note error small add-note">{note}</span>}
    </form>
  );
}

function TileGrid(props: {
  kind: Kind;
  active: string[];
  paused: string[];
  minutes: (item: string) => number | undefined;
  onToggle: (kind: Kind, item: string, on: boolean) => void;
  onRemove: (kind: Kind, item: string) => void;
  empty: string;
}) {
  const items = [...props.active.map((x) => ({ x, on: true })), ...props.paused.map((x) => ({ x, on: false }))];
  if (items.length === 0) return <p className="muted dx-empty">{props.empty}</p>;
  return (
    <>
    <p className="muted small tiles-legend">Debajo de cada nombre: tiempo en los últimos 7 días.</p>
    <ul className="tiles">
      {items.map(({ x, on }) => {
        const name = props.kind === "sites" ? siteLabel(x) : x.replace(/\.exe$/i, "");
        const { letter, hue } = monogram(x);
        const min = props.minutes(x);
        return (
          <li key={x} className={on ? "tile" : "tile off"}>
            <span className="tile-icon" style={{ "--h": hue } as React.CSSProperties} aria-hidden="true">{letter}</span>
            <div className="tile-meta" title={props.kind === "sites" ? `Cuenta si el título de la pestaña contiene «${x}»` : x}>
              <strong>{name}</strong>
              <span className="muted small">{!on ? "en pausa" : min ? fmtMinutes(min) : "sin uso"}</span>
            </div>
            <label className="switch" title={on ? "Activo" : "En pausa"}>
              <input type="checkbox" role="switch" checked={on} aria-label={`${name}: ${on ? "activo" : "en pausa"}`}
                onChange={(e) => props.onToggle(props.kind, x, e.target.checked)} />
              <span aria-hidden="true" />
            </label>
            <button type="button" className="ghost tile-x" aria-label={`Quitar ${name}`} onClick={() => props.onRemove(props.kind, x)}>
              ×
            </button>
          </li>
        );
      })}
    </ul>
    </>
  );
}

function ChipList(props: { title: string; hint: string; items: string[]; onChange: (items: string[], msg: string) => void }) {
  return (
    <div className="chiplist">
      <h3>{props.title}</h3>
      <p className="muted small">{props.hint}</p>
      <ul className="chips">
        {props.items.map((it) => (
          <li key={it} className="chip-static">
            {it}
            <button type="button" className="ghost" aria-label={`Quitar ${it}`}
              onClick={() => props.onChange(removeItem(props.items, it), `${it} quitado.`)}>×</button>
          </li>
        ))}
      </ul>
      <AddForm placeholder="programa.exe" button="Agregar" parse={normalizeProcess} invalid="Escribí un ejecutable."
        exists={(p) => hasItem(props.items, p)} onAdd={(p) => props.onChange(addItems(props.items, [p]), `${p} agregado.`)} />
    </div>
  );
}
