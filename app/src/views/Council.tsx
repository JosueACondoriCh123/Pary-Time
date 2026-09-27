// La reunión del consejo contada para quien la ve por primera vez. Primero el flujo de un vistazo; después una fila por
// propuesta con su veredicto (se despliega el detalle), los respaldos agrupados y la elegida completa con su preregistro.
import type { CouncilRun, Hypothesis, Preregistration, ProposalRecord, ToolVerdict } from "../contracts";
import { ARM_LABEL, moderatorText } from "../lib/labels";
import { dateTime } from "../lib/time";
import { Card } from "../ui";

const RED_TEAM_TOOLS: ToolVerdict["name"][] = ["power", "confounders", "multiplicity", "constitution"];

export const TOOL_LABEL: Record<ToolVerdict["name"], string> = {
  verifier: "Verificador de cifras",
  power: "Potencia",
  confounders: "Confusores",
  multiplicity: "Comparaciones múltiples",
  constitution: "Constitución",
};

const TOOL_HINT: Record<ToolVerdict["name"], string> = {
  verifier: "¿Cada número de la justificación está en tus datos?",
  power: "¿Alcanzan tus bloques para detectar el efecto en ~3 semanas?",
  confounders: "¿Hay otra explicación escondida (día, tipo de tarea)?",
  multiplicity: "¿Queda α para probar una hipótesis más?",
  constitution: "¿Respeta los límites de fricción y de un experimento a la vez?",
};

const TEST_LABEL: Record<string, string> = {
  "permutation_median_diff_one_sided@1": "permutación a una cola sobre la mediana",
  "permutation_meanlog_diff_stratified@2": "permutación estratificada, a una cola, sobre el log de la latencia",
};

/** Nombre humano del test preregistrado; si es uno nuevo, se muestra tal cual. */
export function testLabel(test: string | undefined): string {
  return test ? (TEST_LABEL[test] ?? test) : TEST_LABEL["permutation_median_diff_one_sided@1"];
}

const pctLess = (h: Hypothesis) => Math.round((1 - h.expected_ratio) * 100);

export function hypothesisText(h: Hypothesis): string {
  return `${ARM_LABEL[h.intervention]}, ${moderatorText(h.moderator)}: espera ${pctLess(h)}% menos de latencia de arranque`;
}

const same = (a: Hypothesis, b: Hypothesis) =>
  a.intervention === b.intervention &&
  a.expected_ratio === b.expected_ratio &&
  (a.moderator?.kind ?? null) === (b.moderator?.kind ?? null) &&
  (a.moderator?.value ?? null) === (b.moderator?.value ?? null);

/** Índice de la propuesta elegida, comparando con la hipótesis preregistrada. */
export function chosenIndex(run: CouncilRun, prereg: Preregistration | null | undefined): number {
  if (!run.chosen_experiment_id || !prereg) return -1;
  return run.proposals.findIndex((p) => same(p.hypothesis, prereg.hypothesis));
}

/** La primera herramienta que vetó, en el orden en que se lee (verificador primero), o null si pasó. */
export function vetoReason(p: ProposalRecord): ToolVerdict | null {
  if (p.red_team.verdict !== "veto") return null;
  const order: ToolVerdict["name"][] = ["verifier", ...RED_TEAM_TOOLS];
  return order.map((n) => p.red_team.tools.find((t) => t.name === n && !t.passed)).find((t) => !!t) ?? null;
}

type Indexed = { p: ProposalRecord; i: number };

/** Separa lo que propuso el Scout de los respaldos del Allocator, conservando el índice original. */
export function groupProposals(run: CouncilRun): { scout: Indexed[]; fallback: Indexed[] } {
  const all = run.proposals.map((p, i) => ({ p, i }));
  return {
    scout: all.filter((x) => x.p.source !== "allocator_fallback"),
    fallback: all.filter((x) => x.p.source === "allocator_fallback"),
  };
}

export function CouncilRunView({ run, prereg }: { run: CouncilRun; prereg?: Preregistration | null }) {
  const chosen = chosenIndex(run, prereg);
  const { scout, fallback } = groupProposals(run);
  const scoutVetoed = scout.filter((x) => x.p.red_team.verdict === "veto").length;
  const firstCaught = scout.find((x) => vetoReason(x.p)?.name === "verifier")?.i ?? -1;
  const models = run.models ?? {};
  const chosenRec = chosen >= 0 ? run.proposals[chosen] : null;

  return (
    <Card className="council">
      <h2>Reunión del consejo</h2>
      <p className="muted small">
        {dateTime(run.ran_ms)} · {run.n_blocks_in_snapshot} bloques en el resumen, sin títulos de ventana · sellado{" "}
        <code title={run.snapshot_sha256}>{run.snapshot_sha256.slice(0, 12)}…</code>
      </p>
      <p className="muted small">
        {run.llm_used
          ? `${models.scout ?? "Scout"} propone y ${models.red_team ?? "el Red Team"} escribe el pre-mortem, en esta compu. Los vetos son estadística determinista: el modelo no puede aprobar lo que los números rechazan.`
          : "Sin modelos: propuso el Allocator con el efecto mínimo detectable."}
      </p>

      <ol className="flow" aria-label="Flujo de la reunión">
        <li className={scout.length ? "" : "off"}>
          <strong>{scout.length}</strong> {scout.length === 1 ? "idea" : "ideas"} del Scout
        </li>
        <li className={scoutVetoed ? "bad" : "off"}>
          <strong>{scoutVetoed}</strong> {scoutVetoed === 1 ? "vetada" : "vetadas"}
        </li>
        {fallback.length > 0 && (
          <li>
            <strong>{fallback.length}</strong> de respaldo
          </li>
        )}
        <li className={chosenRec ? "good" : "off"}>{chosenRec ? "1 preregistrada" : "ninguna elegida"}</li>
      </ol>

      {scout.length > 0 && (
        <section className="council-section">
          <h3>Lo que propuso el Scout</h3>
          {scout.map(({ p, i }) => (
            <ProposalRow key={i} p={p} label={`Idea ${scout.findIndex((x) => x.i === i) + 1}`} chosen={i === chosen} open={i === firstCaught && i !== chosen} />
          ))}
        </section>
      )}

      {fallback.length > 0 && (
        <section className="council-section">
          <h3>Respaldo del Allocator</h3>
          <details className="row-card">
            <summary>
              <span className="row-tag">Respaldo</span>
              <span className="row-title">
                {scout.length ? "Nada del Scout sobrevivió: " : ""}
                {fallback.length} intervenciones con el efecto mínimo detectable ({pctLess(fallback[0].p.hypothesis)}%
                menos)
              </span>
              <span className="chip ok">✅ {fallback.filter((x) => x.p.red_team.verdict === "pass").length} pasaron</span>
            </summary>
            <div className="row-body">
              {fallback.map(({ p, i }) => (
                <ProposalRow key={i} p={p} label="Respaldo" chosen={i === chosen} nested />
              ))}
            </div>
          </details>
        </section>
      )}

      {chosenRec && (
        <section className="council-section">
          <h3>Elegida</h3>
          <div className="chosen-card">
            <p className="hyp">{hypothesisText(chosenRec.hypothesis)}</p>
            {chosenRec.source !== "allocator_fallback" && (
              <p className="muted small">“{chosenRec.hypothesis.rationale}”</p>
            )}
            <ToolList p={chosenRec} />
            {chosenRec.red_team.premortem && (
              <div className="premortem">
                <span className="row-tag">Pre-mortem</span> <span className="tag">sin poder de veto</span>
                <p className="small">{chosenRec.red_team.premortem}</p>
              </div>
            )}
          </div>
          {prereg && run.chosen_experiment_id === prereg.experiment_id && <PreregCard prereg={prereg} />}
        </section>
      )}

      {run.fallback_reason && (
        <details className="tech">
          <summary className="muted small">Detalle técnico del respaldo</summary>
          <p className="muted small">{run.fallback_reason}</p>
        </details>
      )}
    </Card>
  );
}

function VerdictChip({ p, chosen }: { p: ProposalRecord; chosen: boolean }) {
  if (chosen) return <span className="chip ok">⭐ elegida</span>;
  const why = vetoReason(p);
  if (!why) return <span className="chip ok">✅ pasó</span>;
  return (
    <span className="chip bad" title={why.detail}>
      ❌ {TOOL_LABEL[why.name]}: {why.detail.length > 48 ? `${why.detail.slice(0, 46)}…` : why.detail}
    </span>
  );
}

function ProposalRow(props: { p: ProposalRecord; label: string; chosen: boolean; open?: boolean; nested?: boolean }) {
  const { p } = props;
  const veto = p.red_team.verdict === "veto";
  return (
    <details className={`row-card ${veto ? "vetoed" : ""} ${props.nested ? "nested" : ""}`} open={props.open}>
      <summary>
        <span className="row-tag">{props.label}</span>
        <span className="row-title">
          {ARM_LABEL[p.hypothesis.intervention]}
          <span className="muted"> · {moderatorText(p.hypothesis.moderator)} · −{pctLess(p.hypothesis)}%</span>
        </span>
        <VerdictChip p={p} chosen={props.chosen} />
      </summary>
      <div className="row-body">
        {p.source !== "allocator_fallback" && <p className="muted small">“{p.hypothesis.rationale}”</p>}
        <ToolList p={p} />
      </div>
    </details>
  );
}

function ToolList({ p }: { p: ProposalRecord }) {
  const tools = (["verifier", ...RED_TEAM_TOOLS] as ToolVerdict["name"][])
    .map((name) => p.red_team.tools.find((t) => t.name === name))
    .filter((t): t is ToolVerdict => !!t);
  return (
    <ul className="tools">
      {tools.map((t) => (
        <li key={t.name} className={`tool ${t.passed ? "" : "fail"}`} title={TOOL_HINT[t.name]}>
          <span aria-hidden>{t.passed ? "✅" : "❌"}</span> <strong>{TOOL_LABEL[t.name]}</strong>
          <span className="muted"> · {t.detail}</span>
        </li>
      ))}
    </ul>
  );
}

export function PreregCard({ prereg }: { prereg: Preregistration }) {
  return (
    <div className="prereg">
      <h3>Preregistro</h3>
      <p className="small">
        Quedó sellado en el journal antes del primer sorteo: qué se prueba, con cuántos bloques y con qué test. De la
        semilla del sorteo solo se publica el hash; al final se revela y cualquiera puede comprobar que no se tocó.
      </p>
      <dl className="kv">
        <dt>N por brazo</dt>
        <dd>
          {prereg.n_per_arm} bloques con intervención y {prereg.n_per_arm} sin
        </dd>
        <dt>Test</dt>
        <dd>
          {testLabel(prereg.test)} · α = {prereg.alpha.toFixed(4)}
        </dd>
        <dt>Hash de la semilla</dt>
        <dd>
          <code className="hash short" title="La semilla se revela al terminar el experimento">
            {prereg.seed_commitment.slice(0, 16)}…{prereg.seed_commitment.slice(-8)}
          </code>
          <span className="muted small"> la semilla se revela al terminar</span>
        </dd>
        <dt>Experimento</dt>
        <dd className="muted">{prereg.experiment_id}</dd>
      </dl>
    </div>
  );
}
