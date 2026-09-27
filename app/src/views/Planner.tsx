// Planificador: la vista principal de la noche. Crear bloques, confirmar el día y escribir el primer paso.
import { useState } from "react";
import type { BlockCreate, BlockView, Target, TaskKind, WorkMatcher } from "../contracts";
import { useCore, useLoad } from "../core";
import { ARM_LABEL, STATUS_LABEL, TASK_KINDS, TASK_LABEL, visibleArm } from "../lib/labels";
import { basename, cleanMatchers, suggestMatchers } from "../lib/matchers";
import { clock, dayLabel, toEpochMs, today, tomorrow } from "../lib/time";
import { Card, Chips, ErrorNote, useAction } from "../ui";

const DURATIONS = [25, 50, 90] as const;
const TARGET_KINDS = ["file", "app", "url", "none"] as const;
const TARGET_LABEL: Record<Target["kind"], string> = { file: "Archivo", app: "App", url: "Web", none: "Nada" };

export function Planner() {
  const { api } = useCore();
  const [date, setDate] = useState(() => tomorrow());
  const blocks = useLoad((a) => a.listBlocks(date), [date]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const confirm = useAction();

  const list = (blocks.data ?? []).filter((b) => b.status !== "cancelled");
  const planned = list.filter((b) => b.status === "planned");
  const isTomorrow = date === tomorrow();
  const showForm = editing === "new" || (!blocks.loading && !blocks.error && list.length === 0 && editing === null);

  const replace = (b: BlockView) =>
    blocks.setData((blocks.data ?? []).map((x) => (x.block_id === b.block_id ? b : x)));

  async function onConfirm() {
    const res = await confirm.run(() => api.confirmDay(date));
    if (res) blocks.setData(res);
  }

  return (
    <div className="view">
      <header className="view-head">
        <div>
          <h1>Planificá {isTomorrow ? "mañana" : "hoy"}</h1>
          <p className="muted">{dayLabel(date)}</p>
        </div>
        <Chips
          name="Día"
          options={[tomorrow(), today()]}
          value={date}
          label={(d) => (d === tomorrow() ? "Mañana" : "Hoy")}
          onChange={(d) => {
            setDate(d);
            setEditing(null);
          }}
        />
      </header>

      <ErrorNote error={blocks.error} />

      <div className="blocks">
        {list.map((b) =>
          editing === b.block_id ? (
            <BlockForm
              key={b.block_id}
              date={date}
              initial={b}
              onDone={(saved) => {
                if (saved) replace(saved);
                setEditing(null);
              }}
            />
          ) : (
            <BlockCard
              key={b.block_id}
              block={b}
              onEdit={() => setEditing(b.block_id)}
              onChange={replace}
              onCancelled={() => blocks.reload()}
            />
          ),
        )}
      </div>

      {showForm ? (
        <BlockForm
          date={date}
          suggestedStart={suggestStart(list)}
          onDone={(saved) => {
            if (saved) blocks.setData([...(blocks.data ?? []), saved].sort(byStart));
            setEditing(null);
          }}
          cancellable={list.length > 0}
        />
      ) : (
        editing === null && (
          <button type="button" className="add" onClick={() => setEditing("new")}>
            + Agregar bloque
          </button>
        )
      )}

      {planned.length > 0 && editing === null && (
        <div className="confirm-zone">
          <button type="button" className="big primary" disabled={confirm.busy} onClick={onConfirm}>
            {confirm.busy ? "Sorteando…" : isTomorrow ? "Confirmar mañana" : "Confirmar hoy"}
          </button>
          <p className="muted small">
            Se sortea la condición de cada bloque y queda sellada. Después ya no se editan, pero siempre podés decir
            “hoy no”.
          </p>
          <ErrorNote error={confirm.error} />
        </div>
      )}
    </div>
  );
}

const byStart = (a: BlockView, b: BlockView) => a.planned_start_ms - b.planned_start_ms;

function suggestStart(list: BlockView[]): string {
  if (list.length === 0) return "09:00";
  const last = [...list].sort(byStart).at(-1)!;
  const end = last.planned_start_ms + last.planned_minutes * 60_000 + 10 * 60_000;
  const d = new Date(Math.ceil(end / 900_000) * 900_000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function BlockCard(props: {
  block: BlockView;
  onEdit: () => void;
  onChange: (b: BlockView) => void;
  onCancelled: () => void;
}) {
  const { api } = useCore();
  const b = props.block;
  const cancel = useAction();
  const arm = visibleArm(b);
  const end = b.planned_start_ms + b.planned_minutes * 60_000;

  return (
    <Card className={`block status-${b.status}`}>
      <div className="block-time">
        <strong>{clock(b.planned_start_ms)}</strong>
        <span className="muted">{clock(end)}</span>
      </div>
      <div className="block-body">
        <div className="block-title">
          <span className="label">{b.task_label || "(sin nombre)"}</span>
          <span className="tag">{TASK_LABEL[b.task_kind]}</span>
          <span className={`badge ${b.status}`}>{STATUS_LABEL[b.status]}</span>
          {b.aborted && <span className="badge aborted">Hoy no</span>}
        </div>
        {b.target.kind !== "none" && (
          <p className="muted small">
            {TARGET_LABEL[b.target.kind]}: {b.target.kind === "file" ? basename(b.target.value ?? "") : b.target.value}
          </p>
        )}
        {arm ? (
          <p className="arm">Condición: {ARM_LABEL[arm]}</p>
        ) : (
          b.status === "confirmed" && (
            <p className="muted small">Condición sellada. Se revela a las {clock(b.planned_start_ms)}.</p>
          )
        )}
        {b.needs_first_step && <FirstStepInput block={b} onSaved={props.onChange} />}
        {b.first_step && <p className="first-step">Primer paso: {b.first_step}</p>}
        <ErrorNote error={cancel.error} />
      </div>
      {b.status === "planned" && (
        <div className="block-actions">
          <button type="button" className="ghost" onClick={props.onEdit}>
            Editar
          </button>
          <button
            type="button"
            className="ghost"
            disabled={cancel.busy}
            onClick={async () => {
              if (await cancel.run(() => api.cancelBlock(b.block_id))) props.onCancelled();
            }}
          >
            Quitar
          </button>
        </div>
      )}
    </Card>
  );
}

function FirstStepInput({ block, onSaved }: { block: BlockView; onSaved: (b: BlockView) => void }) {
  const { api } = useCore();
  const [text, setText] = useState("");
  const save = useAction();
  return (
    <form
      className="first-step-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const b = await save.run(() => api.setFirstStep(block.block_id, text.trim()));
        if (b) onSaved(b);
      }}
    >
      <label htmlFor={`fs-${block.block_id}`}>¿Cuál es el primer paso ridículamente chico?</label>
      <div className="row">
        <input
          id={`fs-${block.block_id}`}
          value={text}
          maxLength={200}
          placeholder="Ej.: abrir el doc y escribir una frase fea"
          onChange={(e) => setText(e.target.value)}
          autoFocus
        />
        <button type="submit" className="primary" disabled={!text.trim() || save.busy}>
          Guardar
        </button>
      </div>
      <ErrorNote error={save.error} />
    </form>
  );
}

function BlockForm(props: {
  date: string;
  initial?: BlockView;
  suggestedStart?: string;
  cancellable?: boolean;
  onDone: (saved: BlockView | null) => void;
}) {
  const { api } = useCore();
  const init = props.initial;
  const [start, setStart] = useState(init ? clock(init.planned_start_ms) : (props.suggestedStart ?? "09:00"));
  const [minutes, setMinutes] = useState(init?.planned_minutes ?? 50);
  const [kind, setKind] = useState<TaskKind>(init?.task_kind ?? "escritura");
  const [label, setLabel] = useState(init?.task_label ?? "");
  const [target, setTarget] = useState<Target>(init?.target ?? { kind: "file", value: "" });
  const [matchers, setMatchers] = useState<WorkMatcher[]>(init?.work_matchers ?? []);
  const [touchedMatchers, setTouchedMatchers] = useState(!!init);
  const save = useAction();

  function changeTarget(next: Target) {
    setTarget(next);
    // Autocompleta mientras la persona no haya tocado los matchers a mano.
    if (!touchedMatchers) setMatchers(suggestMatchers(next));
  }

  async function pickFile() {
    const path = await window.nde1?.pickFile();
    if (path) {
      changeTarget({ kind: "file", value: path });
      if (!label.trim()) setLabel(basename(path).replace(/\.[^.]+$/, "").slice(0, 120));
    }
  }

  const clean = cleanMatchers(matchers);
  const valid = /^\d{2}:\d{2}$/.test(start) && label.trim().length > 0 && clean.length > 0;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    const body: BlockCreate = {
      local_date: props.date,
      planned_start_ms: toEpochMs(props.date, start),
      planned_minutes: minutes,
      task_kind: kind,
      task_label: label.trim().slice(0, 120),
      target: target.kind === "none" ? { kind: "none", value: "" } : { ...target, value: (target.value ?? "").trim() },
      work_matchers: clean as BlockCreate["work_matchers"],
    };
    const saved = await save.run(() => {
      if (!init) return api.createBlock(body);
      const { local_date: _d, ...update } = body;
      return api.updateBlock(init.block_id, update);
    });
    if (saved) props.onDone(saved);
  }

  return (
    <Card className="block-form">
      <form onSubmit={onSubmit}>
        <div className="form-row">
          <label>
            Hora
            <input type="time" value={start} onChange={(e) => setStart(e.target.value)} required />
          </label>
          <div className="field">
            <span>Duración</span>
            <div className="row">
              <Chips
                name="Duración"
                options={DURATIONS.map(String)}
                value={String(minutes)}
                label={(m) => `${m} min`}
                onChange={(m) => setMinutes(Number(m))}
              />
              <input
                type="number"
                className="narrow"
                min={15}
                max={240}
                step={5}
                value={minutes}
                aria-label="Minutos"
                onChange={(e) => setMinutes(Math.min(240, Math.max(15, Number(e.target.value) || 15)))}
              />
            </div>
          </div>
        </div>

        <div className="field">
          <span>Tipo de tarea</span>
          <Chips name="Tipo de tarea" options={TASK_KINDS} value={kind} label={(k) => TASK_LABEL[k]} onChange={setKind} />
        </div>

        <label>
          Qué vas a hacer
          <input
            value={label}
            maxLength={120}
            placeholder="Ej.: Tesis, capítulo 3"
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>

        <div className="field">
          <span>Qué abrir</span>
          <Chips
            name="Objetivo"
            options={TARGET_KINDS}
            value={target.kind}
            label={(k) => TARGET_LABEL[k]}
            onChange={(k) => changeTarget({ kind: k, value: k === target.kind ? target.value : "" })}
          />
          {target.kind === "file" && (
            <div className="row">
              <button type="button" onClick={pickFile} disabled={!window.nde1}>
                Elegir archivo…
              </button>
              <span className="muted small ellipsis">{target.value ? basename(target.value) : "Ninguno"}</span>
            </div>
          )}
          {target.kind === "app" && (
            <input
              value={target.value}
              placeholder="Ej.: Obsidian.exe o la ruta al .exe"
              onChange={(e) => changeTarget({ kind: "app", value: e.target.value })}
            />
          )}
          {target.kind === "url" && (
            <input
              value={target.value}
              placeholder="Ej.: https://www.overleaf.com/project/…"
              onChange={(e) => changeTarget({ kind: "url", value: e.target.value })}
            />
          )}
        </div>

        <MatchersEditor
          matchers={matchers}
          onChange={(m) => {
            setTouchedMatchers(true);
            setMatchers(m);
          }}
        />

        <ErrorNote error={save.error} />
        <div className="row end">
          {(props.initial || props.cancellable) && (
            <button type="button" className="ghost" onClick={() => props.onDone(null)}>
              Cancelar
            </button>
          )}
          <button type="submit" className="primary" disabled={!valid || save.busy}>
            {init ? "Guardar" : "Agregar bloque"}
          </button>
        </div>
      </form>
    </Card>
  );
}

function MatchersEditor({ matchers, onChange }: { matchers: WorkMatcher[]; onChange: (m: WorkMatcher[]) => void }) {
  const set = (i: number, m: WorkMatcher) => onChange(matchers.map((x, j) => (j === i ? m : x)));
  return (
    <div className="field">
      <span>Cuenta como trabajo si…</span>
      {matchers.length === 0 && <p className="muted small">Agregá al menos una regla.</p>}
      {matchers.map((m, i) => (
        <div className="row matcher" key={i}>
          <select
            value={m.field}
            aria-label="Campo"
            onChange={(e) => set(i, { ...m, field: e.target.value as WorkMatcher["field"] })}
          >
            <option value="process">el programa es</option>
            <option value="title">el título contiene</option>
          </select>
          <input
            value={m.pattern}
            maxLength={200}
            aria-label="Patrón"
            onChange={(e) => set(i, { ...m, pattern: e.target.value })}
          />
          <button
            type="button"
            className="ghost"
            aria-label="Quitar regla"
            onClick={() => onChange(matchers.filter((_, j) => j !== i))}
          >
            ×
          </button>
        </div>
      ))}
      <button type="button" className="ghost small" onClick={() => onChange([...matchers, { field: "title", pattern: "" }])}>
        + Regla
      </button>
    </div>
  );
}
