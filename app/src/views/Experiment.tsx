// "Experimento": progreso sin efectos parciales, y "Reunir al consejo ahora".
import { useState } from "react";
import type { CouncilRun, ExperimentProgress } from "../contracts";
import { useCore, useLoad } from "../core";
import { ARM_LABEL, moderatorText } from "../lib/labels";
import { dateTime } from "../lib/time";
import { Card, ErrorNote, useAction } from "../ui";
import { CouncilRunView } from "./Council";

export const ANTI_SPY = "El resultado se muestra al completar el experimento, para que no te engañes espiando.";

export function Experiment() {
  const { api } = useCore();
  const current = useLoad((a) => a.currentExperiment(), [], 30_000);
  const runs = useLoad((a) => a.councilRuns(), []);
  const experiments = useLoad((a) => a.experiments(), []);
  const [fresh, setFresh] = useState<CouncilRun | null>(null);
  const council = useAction();

  const lastRun = fresh ?? [...(runs.data ?? [])].sort((a, b) => b.ran_ms - a.ran_ms)[0] ?? null;

  async function onRun() {
    const run = await council.run(() => api.runCouncil());
    if (run) {
      setFresh(run);
      current.reload();
      runs.reload();
      experiments.reload();
    }
  }

  return (
    <div className="view">
      <header className="view-head">
        <h1>Experimento</h1>
      </header>

      <ErrorNote error={current.error} />
      {current.data ? (
        <Progress exp={current.data} />
      ) : (
        !current.loading &&
        !current.error && (
          <Card className="hero">
            <p className="big-text">No hay un experimento en curso.</p>
            <p className="muted">
              Mientras tanto la compu solo mide: es la línea base. Cuando haya datos suficientes, el consejo propone
              qué probar.
            </p>
          </Card>
        )
      )}

      <Card>
        <div className="row">
          <button type="button" className="primary" disabled={council.busy} onClick={onRun}>
            {council.busy ? "El consejo está deliberando…" : "Reunir al consejo ahora"}
          </button>
          {council.busy ? (
            <span className="muted small">
              El Scout propone, el verificador revisa cada cifra y el Red Team ataca. Con modelos locales tarda 1–2 min.
            </span>
          ) : (
            <span className="muted small">Propone una hipótesis sobre tus datos y la ataca antes de probarla.</span>
          )}
        </div>
        <ErrorNote error={council.error} />
      </Card>

      {lastRun && (
        <CouncilRunView
          run={lastRun}
          prereg={
            experiments.data?.find((e) => e.preregistration.experiment_id === lastRun.chosen_experiment_id)
              ?.preregistration
          }
        />
      )}
    </div>
  );
}

function Progress({ exp }: { exp: ExperimentProgress }) {
  const bar = (done: number) => (
    <div className="bar" aria-hidden>
      <span style={{ width: `${Math.min(100, (done / Math.max(1, exp.n_per_arm)) * 100)}%` }} />
    </div>
  );
  return (
    <Card className="hero">
      <p className="muted small">
        {exp.status === "closed" ? "Experimento cerrado" : "En curso"} desde el {dateTime(exp.created_ms)}
      </p>
      <p className="big-text">{ARM_LABEL[exp.intervention]}</p>
      <p className="muted">Se prueba {moderatorText(exp.moderator)}, contra bloques sin intervención.</p>
      <div className="progress">
        <span>Sin intervención</span>
        {bar(exp.n_control_done)}
        <span>
          {exp.n_control_done}/{exp.n_per_arm}
        </span>
        <span>Con intervención</span>
        {bar(exp.n_treatment_done)}
        <span>
          {exp.n_treatment_done}/{exp.n_per_arm}
        </span>
      </div>
      <p className="disclaimer">{ANTI_SPY}</p>
    </Card>
  );
}
