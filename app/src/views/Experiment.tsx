// "Experimento": progreso sin efectos parciales, y "Reunir al consejo ahora".
import { useState } from "react";
import type { CouncilRun, ExperimentProgress, ProposalRecord } from "../contracts";
import { useCore, useLoad } from "../core";
import { ARM_LABEL, moderatorText } from "../lib/labels";
import { dateTime } from "../lib/time";
import { Card, ErrorNote, useAction } from "../ui";

export const ANTI_SPY = "El resultado se muestra al completar el experimento, para que no te engañes espiando.";

const TOOL_LABEL: Record<string, string> = {
  power: "Potencia",
  confounders: "Confusores",
  multiplicity: "Comparaciones múltiples",
  verifier: "Verificador de citas",
  constitution: "Constitución",
};

export function Experiment() {
  const { api } = useCore();
  const current = useLoad((a) => a.currentExperiment(), [], 30_000);
  const runs = useLoad((a) => a.councilRuns(), []);
  const [fresh, setFresh] = useState<CouncilRun | null>(null);
  const council = useAction();

  const lastRun = fresh ?? [...(runs.data ?? [])].sort((a, b) => b.ran_ms - a.ran_ms)[0] ?? null;

  async function onRun() {
    const run = await council.run(() => api.runCouncil());
    if (run) {
      setFresh(run);
      current.reload();
      runs.reload();
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
          {council.busy && <span className="muted small">Con los modelos locales puede tardar unos minutos.</span>}
        </div>
        <ErrorNote error={council.error} />
      </Card>

      {lastRun && <RunSummary run={lastRun} />}
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

function RunSummary({ run }: { run: CouncilRun }) {
  const vetoed = run.proposals.filter((p) => p.red_team.verdict === "veto").length;
  return (
    <Card>
      <h2>Última reunión del consejo</h2>
      <p className="muted small">
        {dateTime(run.ran_ms)} · {run.n_blocks_in_snapshot} bloques en el resumen ·{" "}
        {run.llm_used ? `modelos: ${Object.values(run.models ?? {}).join(" y ")}` : "sin modelos (respaldo del Allocator)"}
      </p>
      {run.fallback_reason && <p className="muted small">Motivo del respaldo: {run.fallback_reason}</p>}
      <p>
        {run.proposals.length} {run.proposals.length === 1 ? "propuesta" : "propuestas"}, {vetoed}{" "}
        {vetoed === 1 ? "vetada" : "vetadas"}.{" "}
        {run.chosen_experiment_id ? (
          <strong>Eligió un experimento nuevo y lo preregistró.</strong>
        ) : (
          <span className="muted">No eligió ninguno.</span>
        )}
      </p>
      {run.proposals.map((p, i) => (
        <Proposal key={i} p={p} />
      ))}
    </Card>
  );
}

function Proposal({ p }: { p: ProposalRecord }) {
  const h = p.hypothesis;
  const veto = p.red_team.verdict === "veto";
  return (
    <div className="proposal">
      <p>
        <strong>{ARM_LABEL[h.intervention]}</strong> {moderatorText(h.moderator)} ·{" "}
        <span className="muted">
          espera {Math.round((1 - h.expected_ratio) * 100)}% menos de latencia
          {p.source === "allocator_fallback" ? " · propuesta del Allocator" : ""}
        </span>
      </p>
      <p className="muted small">{h.rationale}</p>
      <p className={veto ? "fail" : "pass"}>{veto ? "Vetada por el Red Team" : "Pasó el Red Team"}</p>
      <ul className="tools">
        {p.red_team.tools.map((t) => (
          <li key={t.name} className={t.passed ? "" : "fail"}>
            {t.passed ? "✓" : "✗"} {TOOL_LABEL[t.name] ?? t.name}: <span className="muted">{t.detail}</span>
          </li>
        ))}
      </ul>
      {p.red_team.premortem && <p className="muted small">Pre-mortem: {p.red_team.premortem}</p>}
    </div>
  );
}
