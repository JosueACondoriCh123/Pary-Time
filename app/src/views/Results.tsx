// "Resultados": experimentos resueltos con la semilla verificada, el ledger y el veto regret.
import { useEffect, useState } from "react";
import type { ExperimentRecord, LedgerEntry } from "../contracts";
import { useLoad } from "../core";
import { betaCurve, betaMean } from "../lib/beta";
import { ARM_LABEL, moderatorText } from "../lib/labels";
import { VERDICT_LABEL } from "../lib/report";
import { verifySeed } from "../lib/seed";
import { dateTime, duration } from "../lib/time";
import { Card, Disclaimer, ErrorNote } from "../ui";
import { ANTI_SPY } from "./Experiment";

/** Verifica la semilla de cada experimento resuelto. Clave: experiment_id. */
export function useSeedChecks(records: ExperimentRecord[] | undefined): Record<string, boolean> {
  const [checks, setChecks] = useState<Record<string, boolean>>({});
  useEffect(() => {
    let alive = true;
    const resolved = (records ?? []).filter((r) => r.resolution);
    void Promise.all(
      resolved.map(async (r) => [
        r.preregistration.experiment_id,
        await verifySeed(r.resolution!.seed_revealed, r.preregistration.seed_commitment),
      ]),
    ).then((pairs) => alive && setChecks(Object.fromEntries(pairs)));
    return () => {
      alive = false;
    };
  }, [records]);
  return checks;
}

export function Results() {
  const experiments = useLoad((a) => a.experiments(), []);
  const ledger = useLoad((a) => a.ledger(), []);
  const regret = useLoad((a) => a.vetoRegret(), []);
  const checks = useSeedChecks(experiments.data);
  const records = [...(experiments.data ?? [])].sort(
    (a, b) => b.preregistration.created_ms - a.preregistration.created_ms,
  );

  return (
    <div className="view">
      <header className="view-head">
        <h1>Resultados</h1>
      </header>
      <Disclaimer />

      <ErrorNote error={experiments.error} />
      {experiments.data && records.length === 0 && (
        <Card>
          <p className="muted">Todavía no hay experimentos. Primero corre la línea base.</p>
        </Card>
      )}
      {records.map((r) => (
        <ExperimentCard key={r.preregistration.experiment_id} rec={r} seedOk={checks[r.preregistration.experiment_id]} />
      ))}

      <Card>
        <h2>Qué tan bien te funciona cada intervención</h2>
        <p className="muted small">
          Curva: lo que se sabe hasta ahora (posterior Beta). Más a la derecha y más angosta = funcionó más veces.
        </p>
        <ErrorNote error={ledger.error} />
        <div className="grid-2">
          {(ledger.data ?? []).map((l) => (
            <LedgerCurve key={l.intervention} entry={l} />
          ))}
        </div>
      </Card>

      <Card>
        <h2>Vetos explorados</h2>
        <ErrorNote error={regret.error} />
        {regret.data && (
          <p>
            {regret.data.n_explored === 0
              ? "Todavía no se probó ninguna hipótesis vetada."
              : `${regret.data.n_explored} hipótesis vetadas se probaron igual; ${regret.data.n_replicated} replicaron.`}
          </p>
        )}
        <p className="muted small">
          Una parte chica del presupuesto prueba ideas vetadas por evidencia débil, para medir si el Red Team se
          equivoca.
        </p>
      </Card>
    </div>
  );
}

function ExperimentCard({ rec, seedOk }: { rec: ExperimentRecord; seedOk: boolean | undefined }) {
  const pre = rec.preregistration;
  const res = rec.resolution;
  const h = pre.hypothesis;
  return (
    <Card>
      <p className="muted small">Preregistrado el {dateTime(pre.created_ms)}</p>
      <h2>
        {ARM_LABEL[h.intervention]} <span className="muted">{moderatorText(h.moderator)}</span>
      </h2>
      <p className="muted small">{h.rationale}</p>
      {!res ? (
        <p className="disclaimer">{ANTI_SPY}</p>
      ) : (
        <>
          <p className={`verdict ${res.verdict}`}>{VERDICT_LABEL[res.verdict]}</p>
          <dl className="kv">
            <dt>Mediana sin intervención</dt>
            <dd>{res.median_control_s === null ? "—" : duration(res.median_control_s)}</dd>
            <dt>Mediana con intervención</dt>
            <dd>{res.median_treatment_s === null ? "—" : duration(res.median_treatment_s)}</dd>
            <dt>Ratio</dt>
            <dd>{res.ratio?.toFixed(2) ?? "—"}</dd>
            <dt>p / α</dt>
            <dd>
              {res.p_value?.toFixed(3) ?? "—"} / {res.alpha.toFixed(3)}
            </dd>
            <dt>Bloques</dt>
            <dd>
              {res.n_control} sin, {res.n_treatment} con
            </dd>
            <dt>No arrancaron en 90 min</dt>
            <dd>
              {res.censored_control} sin, {res.censored_treatment} con
            </dd>
            <dt>Excluidos (compu apagada)</dt>
            <dd>{res.excluded_device_off}</dd>
            <dt>“Hoy no” (cuentan igual)</dt>
            <dd>{res.aborted_blocks}</dd>
            <dt>Semilla</dt>
            <dd className={seedOk === false ? "fail" : seedOk ? "pass" : "muted"}>
              {seedOk === undefined
                ? "verificando…"
                : seedOk
                  ? "✓ coincide con el compromiso preregistrado"
                  : "✗ NO coincide con el compromiso"}
            </dd>
          </dl>
        </>
      )}
    </Card>
  );
}

function LedgerCurve({ entry }: { entry: LedgerEntry }) {
  const W = 260;
  const H = 70;
  const pts = betaCurve(entry.alpha, entry.beta);
  // Escala fija (mínimo 3): así la uniforme del principio se ve baja y ancha, no "segura".
  const maxY = Math.max(3, ...pts.map((p) => p[1]));
  const y = (d: number) => (H - (d / maxY) * (H - 4)).toFixed(1);
  const path = [
    `M0,${y(pts[0][1])}`,
    ...pts.map(([x, d]) => `L${(x * W).toFixed(1)},${y(d)}`),
    `L${W},${y(pts[pts.length - 1][1])}`,
  ];
  const mean = betaMean(entry.alpha, entry.beta);
  return (
    <div>
      <p>
        <strong>{ARM_LABEL[entry.intervention]}</strong>{" "}
        <span className="muted small">
          · funcionó {entry.n_supported} de {entry.n_resolved}
        </span>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={`Posterior Beta(${entry.alpha}, ${entry.beta})`}>
        <path d={`${path.join(" ")} L${W},${H} L0,${H} Z`} fill="rgba(91,141,239,0.25)" />
        <path d={path.join(" ")} fill="none" stroke="#5b8def" strokeWidth="2" />
        <line x1={mean * W} x2={mean * W} y1={0} y2={H} stroke="#9aa3b2" strokeDasharray="3 3" />
      </svg>
      <p className="muted small">Promedio: {Math.round(mean * 100)}%</p>
    </div>
  );
}
