// La reunión del consejo contada para quien la ve por primera vez:
// propuesta → verificador → Red Team → veredicto, y lo elegido con su preregistro (hash de la semilla).
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

export function hypothesisText(h: Hypothesis): string {
  return `${ARM_LABEL[h.intervention]}, ${moderatorText(h.moderator)}: espera ${Math.round(
    (1 - h.expected_ratio) * 100,
  )}% menos de latencia de arranque`;
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

export function CouncilRunView({ run, prereg }: { run: CouncilRun; prereg?: Preregistration | null }) {
  const chosen = chosenIndex(run, prereg);
  const vetoed = run.proposals.filter((p) => p.red_team.verdict === "veto").length;
  const models = run.models ?? {};
  return (
    <Card className="council">
      <h2>Reunión del consejo</h2>
      <p className="muted small">
        {dateTime(run.ran_ms)} · {run.n_blocks_in_snapshot} bloques en el resumen (sin títulos de ventana) · resumen
        sellado <code title={run.snapshot_sha256}>{run.snapshot_sha256.slice(0, 12)}…</code>
      </p>
      <p className="muted small">
        {run.llm_used
          ? `Modelos locales: ${models.scout ?? "Scout"} propone · ${models.red_team ?? "Red Team"} escribe el pre-mortem. Las herramientas con veto son estadística determinista, no un LLM.`
          : "Sin modelos: eligió el Allocator directamente."}
        {run.fallback_reason ? ` Respaldo: ${run.fallback_reason}.` : ""}
      </p>

      <div className="council-summary">
        <span>
          <strong>{run.proposals.length}</strong> {run.proposals.length === 1 ? "propuesta" : "propuestas"}
        </span>
        <span className={vetoed ? "fail" : "muted"}>
          <strong>{vetoed}</strong> {vetoed === 1 ? "vetada" : "vetadas"}
        </span>
        <span className={run.chosen_experiment_id ? "pass" : "muted"}>
          {run.chosen_experiment_id ? "1 preregistrada" : "ninguna elegida"}
        </span>
      </div>

      <ol className="proposals">
        {run.proposals.map((p, i) => (
          <ProposalSteps key={i} n={i + 1} p={p} chosen={i === chosen} />
        ))}
      </ol>

      {prereg && run.chosen_experiment_id === prereg.experiment_id && <PreregCard prereg={prereg} />}
    </Card>
  );
}

function ProposalSteps({ n, p, chosen }: { n: number; p: ProposalRecord; chosen: boolean }) {
  const veto = p.red_team.verdict === "veto";
  const verifier = p.red_team.tools.find((t) => t.name === "verifier");
  const tools = RED_TEAM_TOOLS.map((name) => p.red_team.tools.find((t) => t.name === name)).filter(
    (t): t is ToolVerdict => !!t,
  );
  const blockers = p.red_team.tools.filter((t) => !t.passed).map((t) => TOOL_LABEL[t.name].toLowerCase());
  return (
    <li className={`proposal-steps ${veto ? "vetoed" : ""} ${chosen ? "chosen" : ""}`}>
      <div className="step">
        <span className="step-tag">{p.source === "allocator_fallback" ? "Respaldo" : `Scout · ${n}`}</span>
        <div>
          <p className="hyp">{hypothesisText(p.hypothesis)}</p>
          <p className="muted small">
            {p.source === "allocator_fallback"
              ? "Nada del Scout sobrevivió: el Allocator propone el efecto mínimo detectable con tus datos."
              : `“${p.hypothesis.rationale}”`}
          </p>
        </div>
      </div>
      {verifier && (
        <div className="step">
          <span className="step-tag">Verificador</span>
          <Tool t={verifier} />
        </div>
      )}
      <div className="step">
        <span className="step-tag">Red Team</span>
        <ul className="tools">
          {tools.map((t) => (
            <li key={t.name}>
              <Tool t={t} />
            </li>
          ))}
        </ul>
      </div>
      <div className="step">
        <span className="step-tag">Veredicto</span>
        <p className={`verdict-line ${veto ? "fail" : "pass"}`}>
          {veto ? `❌ Vetada por ${blockers.join(" y ")}` : chosen ? "✅ Pasó y fue elegida" : "✅ Pasó el Red Team"}
        </p>
      </div>
      {chosen && p.red_team.premortem && (
        <div className="step">
          <span className="step-tag">Pre-mortem</span>
          <p className="small premortem">
            {p.red_team.premortem} <span className="tag">sin poder de veto</span>
          </p>
        </div>
      )}
    </li>
  );
}

function Tool({ t }: { t: ToolVerdict }) {
  return (
    <p className={`tool ${t.passed ? "" : "fail"}`} title={TOOL_HINT[t.name]}>
      <span aria-hidden>{t.passed ? "✅" : "❌"}</span> <strong>{TOOL_LABEL[t.name]}</strong>
      <span className="muted"> · {t.detail}</span>
    </p>
  );
}

export function PreregCard({ prereg }: { prereg: Preregistration }) {
  return (
    <div className="prereg">
      <h3>Preregistro</h3>
      <p className="small">
        Antes del primer sorteo quedó sellado en el journal: qué se prueba, con cuántos bloques y con qué test. La
        semilla del sorteo queda guardada y solo se publica su hash. Al final se revela y cualquiera puede comprobar
        que el sorteo no se tocó.
      </p>
      <dl className="kv">
        <dt>Experimento</dt>
        <dd>{prereg.experiment_id}</dd>
        <dt>Hipótesis</dt>
        <dd>{hypothesisText(prereg.hypothesis)}</dd>
        <dt>N por brazo</dt>
        <dd>{prereg.n_per_arm} bloques con intervención y {prereg.n_per_arm} sin</dd>
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
      </dl>
    </div>
  );
}
