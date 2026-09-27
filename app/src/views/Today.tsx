// "Hoy": el bloque activo con su condición revelada, cuánto falta para el siguiente, "Hoy no" y salida de emergencia.
import { useEffect, useState } from "react";
import type { BlockView } from "../contracts";
import { useCore, useLoad, useNow } from "../core";
import { ARM_HINT, ARM_LABEL, STATUS_LABEL, TASK_LABEL, visibleArm } from "../lib/labels";
import { clock, dayLabel, duration, today, untilText } from "../lib/time";
import { Card, ErrorNote, useAction } from "../ui";

const LIVE = new Set(["confirmed", "running"]);

/** El bloque en curso: el que el runtime dice activo o, si no responde, el que está `running`. */
export function activeBlock(blocks: BlockView[], activeId: string | null | undefined): BlockView | null {
  return blocks.find((b) => b.block_id === activeId) ?? blocks.find((b) => b.status === "running") ?? null;
}

/** El próximo bloque confirmado que todavía no empezó. */
export function nextBlock(blocks: BlockView[], nowMs: number): BlockView | null {
  return (
    blocks
      .filter((b) => b.status === "confirmed" && b.planned_start_ms > nowMs)
      .sort((a, b) => a.planned_start_ms - b.planned_start_ms)[0] ?? null
  );
}

export function Today() {
  const date = today();
  const now = useNow(1000);
  const blocks = useLoad((a) => a.listBlocks(date), [date], 15_000);
  const status = useLoad((a) => a.runtimeStatus(), [], 5_000);
  const list = (blocks.data ?? []).filter((b) => b.status !== "cancelled");
  const active = activeBlock(list, status.data?.active_block_id);
  const next = nextBlock(list, now);

  const replace = (b: BlockView) => blocks.setData(list.map((x) => (x.block_id === b.block_id ? b : x)));

  return (
    <div className="view">
      <header className="view-head">
        <div>
          <h1>Hoy</h1>
          <p className="muted">{dayLabel(date)}</p>
        </div>
      </header>

      <ErrorNote error={blocks.error} />

      {active ? (
        <ActiveCard block={active} now={now} onChange={replace} />
      ) : (
        <Card className="hero">
          <p className="big-text">{next ? "Todavía no empezó ningún bloque." : "No hay bloques por delante hoy."}</p>
          {!next && !blocks.loading && <p className="muted">Si querés, planificá mañana a la noche.</p>}
        </Card>
      )}

      {next && (
        <Card>
          <p className="muted small">Siguiente</p>
          <p>
            <strong>{clock(next.planned_start_ms)}</strong> · {next.task_label}{" "}
            <span className="muted">({untilText(next.planned_start_ms, now)})</span>
          </p>
          {!active && <AbortButton block={next} onDone={replace} />}
        </Card>
      )}

      <EmergencyCard released={!!status.data?.emergency_released} onDone={status.reload} />
      <SensorCard />

      {list.length > 0 && (
        <Card>
          <h2>El día</h2>
          <ul className="tools">
            {list.map((b) => (
              <li key={b.block_id}>
                <strong>{clock(b.planned_start_ms)}</strong> · {b.task_label}{" "}
                <span className="muted">
                  · {STATUS_LABEL[b.status]}
                  {b.aborted ? " · hoy no" : ""}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ActiveCard({ block, now, onChange }: { block: BlockView; now: number; onChange: (b: BlockView) => void }) {
  const arm = visibleArm(block);
  const elapsed = (now - block.planned_start_ms) / 1000;
  return (
    <Card className="hero">
      <p className="muted small">
        {block.task_kind === "otro" ? "Bloque" : `Bloque de ${TASK_LABEL[block.task_kind].toLowerCase()}`} ·{" "}
        {clock(block.planned_start_ms)} ·{" "}
        {elapsed >= 0 ? `hace ${duration(elapsed)}` : untilText(block.planned_start_ms, now)}
      </p>
      <p className="big-text">{block.task_label}</p>
      {arm ? (
        <>
          <p className="arm-big">{ARM_LABEL[arm]}</p>
          <p className="muted">{ARM_HINT[arm]}</p>
        </>
      ) : (
        <p className="muted">La condición se revela a las {clock(block.planned_start_ms)}.</p>
      )}
      {block.first_step && <p className="first-step">Primer paso: {block.first_step}</p>}
      {block.aborted ? (
        <p className="muted">Marcaste “hoy no”. El bloque igual cuenta en el análisis.</p>
      ) : (
        LIVE.has(block.status) && <AbortButton block={block} onDone={onChange} />
      )}
    </Card>
  );
}

/** "Hoy no" con confirmación de un clic: el primer toque arma el botón por 4 s. */
function AbortButton({ block, onDone }: { block: BlockView; onDone: (b: BlockView) => void }) {
  const { api } = useCore();
  const [armed, setArmed] = useState(false);
  const act = useAction();

  useEffect(() => {
    if (!armed) return;
    const id = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(id);
  }, [armed]);

  if (block.aborted) return null;
  return (
    <div>
      <div className="row">
        <button
          type="button"
          className={armed ? "danger" : ""}
          disabled={act.busy}
          onClick={async () => {
            if (!armed) return setArmed(true);
            setArmed(false);
            const b = await act.run(() => api.abortBlock(block.block_id));
            if (b) onDone(b);
          }}
        >
          {armed ? "Tocá de nuevo para confirmar" : "Hoy no"}
        </button>
        {armed && <span className="muted small">Queda registrado y el bloque sigue contando. Sin culpa.</span>}
      </div>
      <ErrorNote error={act.error} />
    </div>
  );
}

function EmergencyCard({ released, onDone }: { released: boolean; onDone: () => void }) {
  const { api } = useCore();
  const act = useAction();
  const [done, setDone] = useState(false);
  return (
    <Card>
      <div className="row">
        <button
          type="button"
          className="danger"
          disabled={act.busy}
          onClick={async () => {
            if (await act.run(() => api.emergencyRelease())) {
              setDone(true);
              onDone();
            }
          }}
        >
          Salida de emergencia
        </button>
        <span className="muted small">
          {done || released
            ? "Listo: restauré todas las ventanas y no vuelvo a tocarlas en este bloque."
            : "Restaura todas las ventanas al instante."}
        </span>
      </div>
      <ErrorNote error={act.error} />
    </Card>
  );
}

export function SensorCard() {
  const { api } = useCore();
  const summary = useLoad((a) => a.activityToday(), [], 30_000);
  const act = useAction();
  const now = useNow(15_000);
  const s = summary.data;
  if (summary.error?.status === 501) return null; // sensor todavía no mergeado
  if (!s) return <ErrorNote error={summary.error} />;
  const paused = !!s.paused_until_ms && s.paused_until_ms > now;
  const run = async (fn: () => Promise<typeof s>) => {
    const next = await act.run(fn);
    if (next) summary.setData(next);
  };
  return (
    <Card>
      <div className="row">
        <span>
          Sensor:{" "}
          {paused ? `en pausa hasta las ${clock(s.paused_until_ms!)}` : s.sensor_running ? "midiendo" : "apagado"}
        </span>
        {paused ? (
          <button type="button" className="ghost" disabled={act.busy} onClick={() => run(() => api.resumeSensor())}>
            Reanudar
          </button>
        ) : (
          <>
            <button type="button" className="ghost" disabled={act.busy} onClick={() => run(() => api.pauseSensor(30))}>
              Pausar 30 min
            </button>
            <button type="button" className="ghost" disabled={act.busy} onClick={() => run(() => api.pauseSensor(60))}>
              Pausar 60 min
            </button>
          </>
        )}
      </div>
      <ErrorNote error={act.error} />
    </Card>
  );
}
