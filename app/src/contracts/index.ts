// GENERADO por scripts/contracts.mjs desde contracts/schemas (contracts@1). No editar a mano.

/**
 * Condición de un bloque. `control` = sin intervención.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Arm".
 */
export type Arm = "control" | "abrir_trabajo" | "primer_paso" | "retrasar_distracciones" | "cuenta_regresiva";
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockStatus".
 */
export type BlockStatus = "planned" | "confirmed" | "running" | "started" | "censored" | "device_off" | "cancelled";
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "TaskKind".
 */
export type TaskKind = "escritura" | "lectura" | "estudio" | "programacion" | "admin" | "otro";
/**
 * categoría de la primera ventana tras planned_start
 */
export type Category = "work" | "distraction" | "other" | "none";
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Category".
 */
export type Category1 = "work" | "distraction" | "other" | "none";

export interface Contracts {
  ActivityHistory?: ActivityHistory;
  ActivitySpan?: ActivitySpan;
  ActivitySummary?: ActivitySummary;
  AppUsage?: AppUsage;
  Arm?: Arm;
  Assignment?: Assignment;
  Block?: Block;
  BlockAbort?: BlockAbort;
  BlockConfirmed?: BlockConfirmed;
  BlockCreate?: BlockCreate;
  BlockOutcome?: BlockOutcome;
  BlockStatus?: BlockStatus;
  BlockUpdate?: BlockUpdate;
  BlockView?: BlockView;
  Category?: Category1;
  ConfirmDay?: ConfirmDay;
  CouncilRun?: CouncilRun;
  DayUsage?: DayUsage;
  ExperimentProgress?: ExperimentProgress;
  ExperimentRecord?: ExperimentRecord;
  FirstStep?: FirstStep;
  Health?: Health;
  HourUsage?: HourUsage;
  Hypothesis?: Hypothesis;
  InterventionEvent?: InterventionEvent;
  JournalVerify?: JournalVerify;
  LedgerEntry?: LedgerEntry;
  Moderator?: Moderator;
  OutcomeFeatures?: OutcomeFeatures;
  OutcomeRules?: OutcomeRules;
  OverlayState?: OverlayState;
  Preregistration?: Preregistration;
  ProposalRecord?: ProposalRecord;
  RedTeamReport?: RedTeamReport;
  Report?: Report;
  Resolution?: Resolution;
  RuntimeStatus?: RuntimeStatus;
  Settings?: Settings;
  SiteUsage?: SiteUsage;
  Target?: Target;
  TaskKind?: TaskKind;
  ToolVerdict?: ToolVerdict;
  VetoRegret?: VetoRegret;
  WorkMatcher?: WorkMatcher;
}
/**
 * Agregados del rango [from_date, to_date] (fechas locales, inclusive). Hasta `retention_days` hacia atrás:
 * los tramos crudos del sensor se borran después (privacidad).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ActivityHistory".
 */
export interface ActivityHistory {
  active_minutes: number;
  /**
   * las 15 con más tiempo activo
   */
  apps: AppUsage[];
  days: DayUsage[];
  distraction_share: number;
  from_date: string;
  generated_ms: number;
  /**
   * 24 franjas, sumadas sobre todos los días del rango
   */
  hours: HourUsage[];
  /**
   * tramo más largo en una misma app sin inactividad
   */
  longest_focus_min: number;
  retention_days: number;
  sites: SiteUsage[];
  /**
   * cambios de app por hora activa
   */
  switches_per_hour: number;
  to_date: string;
  totals: {
    [k: string]: number;
  };
  /**
   * trabajo dentro de bloques declarados / tiempo activo
   */
  work_share: number;
}
/**
 * Por proceso (nombre del ejecutable). Nunca títulos de ventana.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "AppUsage".
 */
export interface AppUsage {
  /**
   * categoría donde más tiempo pasó
   */
  category: "work" | "distraction" | "other" | "idle" | "paused";
  minutes: number;
  process: string;
  /**
   * fracción del tiempo activo del rango
   */
  share: number;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "DayUsage".
 */
export interface DayUsage {
  /**
   * work + distraction + other
   */
  active_minutes: number;
  local_date: string;
  /**
   * claves de UsageCategory
   */
  minutes_by_category: {
    [k: string]: number;
  };
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "HourUsage".
 */
export interface HourUsage {
  /**
   * hora local del día
   */
  hour: number;
  minutes_by_category: {
    [k: string]: number;
  };
}
/**
 * Solo el patrón de distracción que coincidió (p.ej. "youtube"), nunca el título.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "SiteUsage".
 */
export interface SiteUsage {
  minutes: number;
  site: string;
}
/**
 * LOCAL. Tramo continuo con la misma ventana en primer plano y el mismo estado de input.
 * Los huecos sin tramos significan compu apagada o suspendida.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ActivitySpan".
 */
export interface ActivitySpan {
  end_ms: number;
  /**
   * sin input por más de OutcomeRules.idle_max_s
   */
  idle: boolean;
  locked?: boolean;
  process: string;
  start_ms: number;
  title: string;
}
/**
 * Resumen del día para la app. Sin títulos. Claves de minutes_by_category: "distraction",
 * "other", "idle" (sin bloque no se sabe qué es trabajo) y "paused".
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ActivitySummary".
 */
export interface ActivitySummary {
  local_date: string;
  minutes_by_category: {
    [k: string]: number;
  };
  paused_until_ms?: number | null;
  sensor_running: boolean;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Assignment".
 */
export interface Assignment {
  arm: Arm;
  assigned_ms: number;
  block_id: string;
  /**
   * posición en la secuencia sorteada
   */
  draw_index?: number | null;
  /**
   * null = línea base (siempre control)
   */
  experiment_id?: string | null;
}
/**
 * Bloque completo, tal como lo guarda el runtime (LOCAL).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Block".
 */
export interface Block {
  aborted?: boolean;
  block_id: string;
  created_ms: number;
  /**
   * LOCAL.
   */
  first_step?: string | null;
  local_date: string;
  planned_minutes: number;
  planned_start_ms: number;
  status: BlockStatus;
  target: Target;
  task_kind: TaskKind;
  /**
   * LOCAL. Nunca va al journal.
   */
  task_label: string;
  /**
   * @minItems 1
   */
  work_matchers: [WorkMatcher, ...WorkMatcher[]];
}
/**
 * LOCAL. Qué abre la intervención `abrir_trabajo`.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Target".
 */
export interface Target {
  kind: "file" | "app" | "url" | "none";
  value?: string;
}
/**
 * LOCAL. Una ventana cuenta como trabajo si CUALQUIER matcher coincide
 * (subcadena, sin distinguir mayúsculas).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "WorkMatcher".
 */
export interface WorkMatcher {
  field: "process" | "title";
  pattern: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockAbort".
 */
export interface BlockAbort {
  block_id: string;
  ts_ms: number;
}
/**
 * Evento `block_confirmed`: lo mínimo y sin textos del usuario.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockConfirmed".
 */
export interface BlockConfirmed {
  block_id: string;
  local_date: string;
  planned_minutes: number;
  planned_start_ms: number;
  task_kind: TaskKind;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockCreate".
 */
export interface BlockCreate {
  local_date: string;
  planned_minutes: number;
  planned_start_ms: number;
  target: Target;
  task_kind: TaskKind;
  /**
   * LOCAL. Nunca va al journal.
   */
  task_label: string;
  /**
   * @minItems 1
   */
  work_matchers: [WorkMatcher, ...WorkMatcher[]];
}
/**
 * Resultado de un bloque. Lo calcula `core.sensing.outcome.evaluate_block` (Frente A);
 * el runtime (Frente B) lo escribe al journal como evento `outcome` cuando es final.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockOutcome".
 */
export interface BlockOutcome {
  block_id: string;
  censored: boolean;
  computed_ms: number;
  features?: OutcomeFeatures | null;
  /**
   * observada; null si pending/censored/device_off
   */
  latency_s?: number | null;
  rules_version?: "outcome@1";
  status: "pending" | "started" | "censored" | "device_off";
  work_run_start_ms?: number | null;
}
/**
 * Variables derivadas por bloque para el snapshot del consejo. Sin títulos.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "OutcomeFeatures".
 */
export interface OutcomeFeatures {
  distraction_s_before_start: number;
  first_category: Category;
  /**
   * cambios de proceso en primer plano antes del arranque/censura
   */
  pre_start_switches: number;
  /**
   * fracción de la ventana con muestras del sensor
   */
  sensor_coverage: number;
  /**
   * ya estaba trabajando a la hora planeada (latencia recortada a 0)
   */
  started_early: boolean;
}
/**
 * Solo mientras el bloque está `planned`.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockUpdate".
 */
export interface BlockUpdate {
  planned_minutes?: number | null;
  planned_start_ms?: number | null;
  target?: Target | null;
  task_kind?: TaskKind | null;
  task_label?: string | null;
  work_matchers?: WorkMatcher[] | null;
}
/**
 * Lo que la API le muestra a la app. La condición se oculta hasta la hora del bloque.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BlockView".
 */
export interface BlockView {
  aborted?: boolean;
  /**
   * null hasta planned_start_ms (salvo primer_paso)
   */
  arm_revealed?: Arm | null;
  block_id: string;
  created_ms: number;
  experiment_id?: string | null;
  /**
   * LOCAL.
   */
  first_step?: string | null;
  local_date: string;
  /**
   * true si le tocó primer_paso y falta escribirlo
   */
  needs_first_step?: boolean;
  planned_minutes: number;
  planned_start_ms: number;
  status: BlockStatus;
  target: Target;
  task_kind: TaskKind;
  /**
   * LOCAL. Nunca va al journal.
   */
  task_label: string;
  /**
   * @minItems 1
   */
  work_matchers: [WorkMatcher, ...WorkMatcher[]];
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ConfirmDay".
 */
export interface ConfirmDay {
  local_date: string;
}
/**
 * Evento `council_run`: todo lo que el consejo miró, incluido lo que vetó.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "CouncilRun".
 */
export interface CouncilRun {
  chosen_experiment_id: string | null;
  fallback_reason?: string | null;
  llm_used: boolean;
  /**
   * {"scout": "...", "red_team": "..."}
   */
  models?: {
    [k: string]: string;
  };
  n_blocks_in_snapshot: number;
  proposals: ProposalRecord[];
  ran_ms: number;
  run_id: string;
  snapshot_sha256: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProposalRecord".
 */
export interface ProposalRecord {
  hypothesis: Hypothesis;
  red_team: RedTeamReport;
  source: "scout" | "allocator_fallback";
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Hypothesis".
 */
export interface Hypothesis {
  cited_block_ids?: string[];
  /**
   * latencia tratamiento / control esperada
   */
  expected_ratio: number;
  intervention: Arm;
  moderator?: Moderator | null;
  rationale: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Moderator".
 */
export interface Moderator {
  kind: "time_of_day" | "task_kind";
  /**
   * TimeOfDay o TaskKind según kind
   */
  value: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "RedTeamReport".
 */
export interface RedTeamReport {
  /**
   * del LLM; sin poder de veto
   */
  premortem?: string;
  tools: ToolVerdict[];
  verdict: "pass" | "veto";
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ToolVerdict".
 */
export interface ToolVerdict {
  detail: string;
  name: "power" | "confounders" | "multiplicity" | "verifier" | "constitution";
  passed: boolean;
}
/**
 * Vista del experimento en curso. NO incluye el efecto hasta llegar al N (anti-espiar).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ExperimentProgress".
 */
export interface ExperimentProgress {
  created_ms: number;
  experiment_id: string;
  intervention: Arm;
  moderator: Moderator | null;
  n_control_done: number;
  n_per_arm: number;
  n_treatment_done: number;
  status: "running" | "closed";
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ExperimentRecord".
 */
export interface ExperimentRecord {
  preregistration: Preregistration;
  resolution: Resolution | null;
}
/**
 * Evento `preregistration`. Se escribe ANTES del primer sorteo del experimento.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Preregistration".
 */
export interface Preregistration {
  alpha: number;
  /**
   * (control, tratamiento)
   *
   * @minItems 2
   * @maxItems 2
   */
  arms: [unknown, unknown];
  council_version: string;
  created_ms: number;
  experiment_id: string;
  hypothesis: Hypothesis;
  limitations?: string[];
  n_per_arm: number;
  outcome_rules: OutcomeRules;
  primary_metric?: "latency_median_censored";
  randomization?: "permuted_blocks_4@1";
  red_team: RedTeamReport;
  seed_commitment: string;
  source: "scout" | "allocator_fallback" | "exploration_vetoed";
  test?: "permutation_median_diff_one_sided@1" | "permutation_meanlog_diff_stratified@2";
}
/**
 * Reglas de la métrica primaria. Se citan por `rules_version` en cada outcome y preregistro.
 * Cambiarlas es un contrato nuevo (`outcome@2`), nunca una edición silenciosa.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "OutcomeRules".
 */
export interface OutcomeRules {
  censor_s?: number;
  gap_tolerance_s?: number;
  idle_max_s?: number;
  rules_version?: "outcome@1";
  work_run_s?: number;
}
/**
 * Evento `resolution`. Revela la semilla: sha256(seed) debe igualar el compromiso.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Resolution".
 */
export interface Resolution {
  aborted_blocks: number;
  alpha: number;
  censored_control: number;
  censored_treatment: number;
  excluded_device_off: number;
  experiment_id: string;
  median_control_s: number | null;
  median_treatment_s: number | null;
  n_control: number;
  n_treatment: number;
  p_value: number | null;
  ratio: number | null;
  resolved_ms: number;
  seed_revealed: string;
  verdict: "supported" | "not_supported" | "insufficient";
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "FirstStep".
 */
export interface FirstStep {
  text: string;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Health".
 */
export interface Health {
  contracts: string;
  /**
   * `sintetico` si data_dir tiene el marcador DATA_LABEL (demo): la app muestra la franja
   */
  data_label?: "real" | "sintetico";
  journal_seq: number;
  ok: boolean;
  version: string;
}
/**
 * Evento `intervention` del journal. Los hwnd y nombres de ventana quedan en el estado
 * local del runtime, no acá.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "InterventionEvent".
 */
export interface InterventionEvent {
  action: "applied" | "reapplied" | "reverted" | "failed";
  arm: Arm;
  block_id: string;
  n_windows?: number;
  reason:
    | "block_start"
    | "device_wake"
    | "work_run_reached"
    | "censor"
    | "abort"
    | "emergency_release"
    | "recovery"
    | "error";
  ts_ms: number;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "JournalVerify".
 */
export interface JournalVerify {
  error?: string | null;
  n_events: number;
  ok: boolean;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "LedgerEntry".
 */
export interface LedgerEntry {
  /**
   * posterior Beta: 1 + apoyados
   */
  alpha: number;
  /**
   * posterior Beta: 1 + no apoyados
   */
  beta: number;
  intervention: Arm;
  n_resolved: number;
  n_supported: number;
}
/**
 * Lo que la app dibuja en el overlay. La app lo consulta cada ~1 s.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "OverlayState".
 */
export interface OverlayState {
  block_id?: string | null;
  kind?: ("countdown" | "first_step") | null;
  planned_start_ms?: number | null;
  task_label?: string | null;
  text?: string | null;
  visible: boolean;
}
/**
 * Reporte exportable (compartible con un profesional). Sin títulos ni textos del usuario.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Report".
 */
export interface Report {
  disclaimer?: string;
  experiments: ExperimentRecord[];
  generated_ms: number;
  journal: JournalVerify;
  ledger: LedgerEntry[];
  veto_regret: VetoRegret;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "VetoRegret".
 */
export interface VetoRegret {
  items: ExperimentRecord[];
  n_explored: number;
  n_replicated: number;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "RuntimeStatus".
 */
export interface RuntimeStatus {
  active_arm_revealed: Arm | null;
  active_block_id: string | null;
  emergency_released?: boolean;
  interventions_applied: Arm[];
  next_block_start_ms: number | null;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Settings".
 */
export interface Settings {
  browser_processes?: string[];
  distraction_processes?: string[];
  distraction_title_patterns?: string[];
  exploration_fraction?: number;
  family_alpha?: number;
  high_friction_max_fraction?: number;
  ollama_base_url?: string;
  raw_retention_days?: number;
  red_team_model?: string;
  scout_model?: string;
  whitelist_processes?: string[];
}
