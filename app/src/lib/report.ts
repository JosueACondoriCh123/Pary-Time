// Reporte exportable: HTML autocontenido (sin scripts ni recursos externos) para compartir con un profesional.
import type { ExperimentRecord, Report } from "../contracts";
import { ARM_LABEL, moderatorText } from "./labels";
import { dateTime, duration } from "./time";

export const DEFAULT_DISCLAIMER =
  "Ajustes de flujo de trabajo medidos sobre vos. No es tratamiento ni consejo médico.";

export const VERDICT_LABEL = {
  supported: "Funcionó en vos",
  not_supported: "No se vio efecto",
  insufficient: "Datos insuficientes",
} as const;

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

const fmtS = (s: number | null) => (s === null ? "—" : duration(s));
const fmtN = (n: number | null, digits = 3) => (n === null ? "—" : n.toFixed(digits));

function experimentHtml(rec: ExperimentRecord, seedOk: boolean | undefined): string {
  const pre = rec.preregistration;
  const res = rec.resolution;
  const h = pre.hypothesis;
  const rows: [string, string][] = [
    ["Preregistrado", dateTime(pre.created_ms)],
    ["N por brazo", String(pre.n_per_arm)],
    ["α asignado", fmtN(pre.alpha)],
    ["Test", pre.test ?? "permutation_median_diff_one_sided@1"],
    ["Compromiso de la semilla", pre.seed_commitment],
  ];
  if (res) {
    rows.push(
      ["Veredicto", VERDICT_LABEL[res.verdict]],
      ["Mediana sin intervención", fmtS(res.median_control_s)],
      ["Mediana con intervención", fmtS(res.median_treatment_s)],
      ["Ratio", fmtN(res.ratio)],
      ["p", fmtN(res.p_value)],
      ["Bloques (control / tratamiento)", `${res.n_control} / ${res.n_treatment}`],
      ["Censurados (control / tratamiento)", `${res.censored_control} / ${res.censored_treatment}`],
      ["Excluidos por compu apagada", String(res.excluded_device_off)],
      ["Abortados (cuentan en su brazo)", String(res.aborted_blocks)],
      ["Semilla revelada", res.seed_revealed],
      ["Semilla verificada", seedOk === undefined ? "sin verificar" : seedOk ? "sí" : "NO COINCIDE"],
    );
  } else {
    rows.push(["Estado", "En curso: sin resultados hasta completar el N"]);
  }
  return `<section><h2>${escapeHtml(ARM_LABEL[h.intervention])} · ${escapeHtml(moderatorText(h.moderator))}</h2>
<p>${escapeHtml(h.rationale)}</p>
<table>${rows.map(([k, v]) => `<tr><th>${escapeHtml(k)}</th><td>${escapeHtml(v)}</td></tr>`).join("")}</table></section>`;
}

/** `seedChecks[experiment_id]` es el resultado de verifySeed, si ya se calculó. */
export function reportHtml(report: Report, seedChecks: Record<string, boolean> = {}): string {
  const disclaimer = report.disclaimer || DEFAULT_DISCLAIMER;
  const ledger = report.ledger
    .map(
      (l) =>
        `<tr><td>${escapeHtml(ARM_LABEL[l.intervention])}</td><td>${l.n_supported} de ${l.n_resolved}</td><td>Beta(${l.alpha}, ${l.beta})</td></tr>`,
    )
    .join("");
  return `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Pary Time · reporte</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<style>
body{font-family:"Segoe UI",system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1a1d23;line-height:1.5}
h1{margin-bottom:.2rem}h2{margin-top:2rem;font-size:1.15rem}
table{border-collapse:collapse;width:100%;margin:.5rem 0}th,td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #e3e6eb;vertical-align:top}
th{font-weight:600;width:45%}td{word-break:break-all}.disclaimer{background:#f4f6f9;border-left:4px solid #5b8def;padding:.6rem .9rem}
.muted{color:#5d6675}
</style></head><body>
<h1>Pary Time · reporte</h1>
<p class="muted">Generado el ${escapeHtml(dateTime(report.generated_ms))}</p>
<p class="disclaimer">${escapeHtml(disclaimer)}</p>
<h2>Integridad del journal</h2>
<p>${report.journal.ok ? "Cadena de hashes verificada" : "La cadena de hashes NO verifica"}: ${report.journal.n_events} eventos.${
    report.journal.error ? ` ${escapeHtml(report.journal.error)}` : ""
  }</p>
<h2>Experimentos</h2>
${report.experiments.length ? report.experiments.map((e) => experimentHtml(e, seedChecks[e.preregistration.experiment_id])).join("\n") : "<p>Todavía no hay experimentos.</p>"}
<h2>Ledger por intervención</h2>
<table><tr><th>Intervención</th><th>Funcionó</th><th>Posterior</th></tr>${ledger}</table>
<h2>Vetos explorados</h2>
<p>${report.veto_regret.n_explored} hipótesis vetadas se probaron igual; ${report.veto_regret.n_replicated} replicaron.</p>
<p class="muted">Sin títulos de ventana ni textos personales. Métrica: latencia de arranque (outcome@1).</p>
</body></html>
`;
}
