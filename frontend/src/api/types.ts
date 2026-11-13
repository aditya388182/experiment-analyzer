// API types. They mirror the result schema in SPEC.md section 7, plus the additions listed in DECISIONS.md D7.
// tests/fixtures holds real API responses; tests/types.test.ts checks their keys match these types exactly.

export type MetricType = "binary" | "continuous";
export type AnalysisStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface Mapping {
  variant_col: string;
  control_label: string;
  metric_col: string;
  metric_type: MetricType;
  pre_period_col: string | null;
  planned_split: number[] | null;
  alpha: number;
}

export interface Arm {
  label: string;
  n: number;
  mean: number;
  sd: number;
  is_control: boolean;
}

export interface DroppedRows {
  null_variant: number;
  non_numeric_metric: number;
  non_binary_value: number;
  null_pre_period: number;
}

export interface Rows {
  read: number;
  used: number;
  dropped: DroppedRows;
}

export interface Srm {
  p: number;
  flagged: boolean;
  planned_split: number[];
  observed_split: number[];
  threshold: number;
}

export interface Comparison {
  treatment: string;
  treat_mean: number;
  ctrl_mean: number;
  diff: number;
  ci_low: number;
  ci_high: number;
  se: number;
  rel_lift: number | null;
  p: number;
  p_holm: number;
  significant: boolean;
  degenerate: boolean;
}

export interface Power {
  base_rate: number | null;
  sd: number;
  n_per_arm: number;
  alpha: number;
  power: number;
  mde_abs: number | null;
}

export interface CupedPair {
  treatment: string;
  corr: number | null;
  variance_removed: number | null;
}

export interface Cuped {
  requested: boolean;
  pre_period_col: string | null;
  theta: number | null;
  corr: number | null;
  variance_removed: number | null;
  helpful: boolean;
  message: string;
  adjusted: Comparison[] | null;
  by_comparison: CupedPair[];
}

export interface AnalysisResult {
  metric_col: string;
  metric_type: MetricType;
  control_label: string;
  alpha: number;
  arms: Arm[];
  rows: Rows;
  srm: Srm;
  comparisons: Comparison[];
  power: Power;
  cuped: Cuped;
  warnings: string[];
  verdict: string;
}

export interface Timings {
  queued_ms?: number;
  download_ms?: number;
  ingest_ms?: number;
  stats_ms?: number;
  total_ms?: number;
}

export interface AnalysisDetail {
  id: string;
  status: AnalysisStatus;
  mapping: Mapping;
  sample_name: string | null;
  upload_id: string | null;
  file_name: string | null;
  result: AnalysisResult | null;
  error: { code: string; message: string } | null;
  input_sha256: string | null;
  abkit_version: string | null;
  git_sha: string | null;
  reused_from: string | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  timings: Timings | null;
}

export interface AnalysisSummary {
  id: string;
  created_at: string;
  status: AnalysisStatus;
  metric_col: string;
  metric_type: MetricType;
  sample_name: string | null;
  file_name: string | null;
  verdict: string | null;
  reused_from: string | null;
}

export interface AnalysisList {
  results: AnalysisSummary[];
}

export interface CreateAnalysisResponse {
  analysis_id: string;
  status: AnalysisStatus;
  reused_from?: string;
}

export interface CreateUploadResponse {
  upload_id: string;
  s3: { url: string; fields: Record<string, string> };
  max_bytes: number;
  expires_in: number;
}

export interface CompleteUploadResponse {
  upload_id: string;
  size_bytes: number;
  columns: string[];
  preview: string[][];
}

export interface SampleSizeRequest {
  base_rate: number;
  alpha: number;
  power: number;
  mde_abs?: number;
  n_per_arm?: number;
}

export interface SampleSizeResponse {
  solved_for: "n_per_arm" | "mde_abs";
  n_per_arm: number;
  mde_abs: number;
  base_rate: number;
  alpha: number;
  power: number;
  curve: { n_per_arm: number; mde_abs: number }[];
}

export interface ChurnModelRow {
  model: string;
  roc_auc: number;
  pr_auc: number;
  selected: boolean;
  baseline: boolean;
}

export interface ChurnCard {
  selected_model: string;
  baseline_model: string;
  test_auc: number;
  test_auc_ci: [number, number];
  baseline_auc: number;
  auc_gain_ci: [number, number];
  shuffled_score_auc: number;
  test_by_model: ChurnModelRow[];
  targeting: {
    top20_by_risk_x_value: number;
    top20_by_value_only: number;
    top20_by_risk_only: number;
    lapsed_customers: number;
    share_of_revenue_lapsed: number;
  };
  calibration: {
    uncalibrated_error: number;
    test_churn_rate: number;
    recent_train_churn_rate: number;
    variants: { variant: string; calibration_error: number; mean_gap_points: number }[];
    recalibration_helped: boolean;
  };
  known_limits: string[];
  sources: Record<string, string>;
}

export interface ForecastMethod {
  method: string;
  mase: number;
  mae: number;
  smape: number;
  winner: boolean;
}

export interface ForecastingCard {
  backtests: number;
  weeks_total: number;
  first_week: string;
  last_week: string;
  methods: ForecastMethod[];
  winner: string;
  lightgbm_vs_best_simple: { best_simple: string; mae_difference: number; ci: [number, number]; ci_includes_zero: boolean };
  sources: Record<string, string>;
}

export interface Reports {
  churn: ChurnCard;
  forecasting: ForecastingCard;
  source: { repo: string; commit: string };
}

export interface Health {
  status: "ok" | "degraded";
  db: boolean;
  broker: boolean;
}

export const TERMINAL: readonly AnalysisStatus[] = ["SUCCEEDED", "FAILED"];

export function isTerminal(d: Pick<AnalysisDetail, "status"> | undefined): boolean {
  return d !== undefined && TERMINAL.includes(d.status);
}
