import { describe, expect, it } from "vitest";

import { fixtures } from "./server";

// Real API responses must carry exactly the keys src/api/types.ts declares (no silent drift between Python and TS).
const DETAIL_KEYS = ["abkit_version", "attempts", "created_at", "error", "file_name", "finished_at", "git_sha", "id", "input_sha256", "mapping", "result", "reused_from", "sample_name", "started_at", "status", "timings", "upload_id"];
const RESULT_KEYS = ["alpha", "arms", "comparisons", "control_label", "cuped", "metric_col", "metric_type", "power", "rows", "srm", "verdict", "warnings"];
const COMPARISON_KEYS = ["ci_high", "ci_low", "ctrl_mean", "degenerate", "diff", "p", "p_holm", "rel_lift", "se", "significant", "treat_mean", "treatment"];
const CUPED_KEYS = ["adjusted", "by_comparison", "corr", "helpful", "message", "pre_period_col", "requested", "theta", "variance_removed"];
const SRM_KEYS = ["flagged", "observed_split", "p", "planned_split", "threshold"];
const POWER_KEYS = ["alpha", "base_rate", "mde_abs", "n_per_arm", "power", "sd"];

const keys = (o: object) => Object.keys(o).sort();

describe("API fixtures match the TypeScript types", () => {
  it.each([["visit", fixtures.visit], ["spend", fixtures.spend], ["failed", fixtures.failed]])("%s detail", (_name, d) => {
    expect(keys(d)).toEqual(DETAIL_KEYS);
  });
  it.each([["visit", fixtures.visit.result], ["spend", fixtures.spend.result]])("%s result", (_name, r) => {
    expect(keys(r)).toEqual(RESULT_KEYS);
    expect(keys(r.comparisons[0] ?? {})).toEqual(COMPARISON_KEYS);
    expect(keys(r.cuped)).toEqual(CUPED_KEYS);
    expect(keys(r.srm)).toEqual(SRM_KEYS);
    expect(keys(r.power)).toEqual(POWER_KEYS);
    expect(keys(r.rows.dropped)).toEqual(["non_binary_value", "non_numeric_metric", "null_pre_period", "null_variant"]);
  });
});
