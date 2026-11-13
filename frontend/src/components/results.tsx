import { useState } from "react";
import { Link } from "react-router";

import type { AnalysisDetail, AnalysisResult, AnalysisStatus, Cuped, Power, Srm } from "../api/types";
import { effect, int, mean, pValue, pct, shortSha } from "../lib/format";
import { Button, Card, Stat } from "./ui";

const STEPS: { status: AnalysisStatus; label: string }[] = [
  { status: "QUEUED", label: "Queued" },
  { status: "RUNNING", label: "Running" },
  { status: "SUCCEEDED", label: "Done" },
];

export function StatusTimeline({ status }: { status: AnalysisStatus }) {
  const current = status === "FAILED" ? 2 : STEPS.findIndex((s) => s.status === status);
  return (
    <ol aria-label="Analysis progress" className="flex items-center gap-2 text-sm">
      {STEPS.map((s, i) => {
        const done = i < current || status === "SUCCEEDED";
        const active = i === current && !done;
        const label = i === 2 && status === "FAILED" ? "Failed" : s.label;
        return (
          <li key={s.status} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold ${
                status === "FAILED" && i === 2
                  ? "border-red-600 bg-red-600 text-white"
                  : done
                    ? "border-teal-700 bg-teal-700 text-white"
                    : active
                      ? "animate-pulse border-teal-700 text-teal-800"
                      : "border-stone-300 text-stone-400"
              }`}
            >
              {i + 1}
            </span>
            <span className={done || active ? "font-medium text-stone-900" : "text-stone-500"}>{label}</span>
            {i < STEPS.length - 1 ? <span className="mx-1 h-px w-8 bg-stone-300" aria-hidden="true" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

export function SrmBanner({ srm }: { srm: Srm }) {
  if (srm.flagged) {
    return (
      <div role="alert" className="flex items-start gap-3 rounded-md border border-red-300 bg-red-50 p-4 text-red-900">
        <span aria-hidden="true" className="text-lg">✕</span>
        <div>
          <p className="font-semibold">Traffic split check failed (sample ratio mismatch)</p>
          <p className="text-sm">
            SRM p = {pValue(srm.p)}, below the {srm.threshold} threshold. Arm sizes do not match the planned split, so
            assignment or logging is probably broken. Do not trust the effects below until that is fixed.
          </p>
        </div>
      </div>
    );
  }
  return (
    <div role="status" className="flex items-start gap-3 rounded-md border border-emerald-300 bg-emerald-50 p-4 text-emerald-900">
      <span aria-hidden="true" className="text-lg">✓</span>
      <div>
        <p className="font-semibold">Traffic split looks healthy</p>
        <p className="text-sm">
          SRM p = {pValue(srm.p)} (flagged only below {srm.threshold}). Observed split{" "}
          {srm.observed_split.map((s) => pct(s)).join(" / ")} vs planned {srm.planned_split.map((s) => pct(s)).join(" / ")}.
        </p>
      </div>
    </div>
  );
}

export function ArmsTable({ result }: { result: AnalysisResult }) {
  const byT = new Map(result.comparisons.map((c) => [c.treatment, c]));
  const unit = result.metric_type === "binary" ? "rate" : "mean";
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Arms and comparisons with the control</caption>
        <thead>
          <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wide text-stone-500">
            <th scope="col" className="py-2 pr-4">Arm</th>
            <th scope="col" className="py-2 pr-4 text-right">Rows</th>
            <th scope="col" className="py-2 pr-4 text-right">{result.metric_col} {unit}</th>
            <th scope="col" className="py-2 pr-4 text-right">Difference vs control</th>
            <th scope="col" className="py-2 pr-4 text-right">{Math.round((1 - result.alpha) * 100)}% CI</th>
            <th scope="col" className="py-2 pr-4 text-right">Relative</th>
            <th scope="col" className="py-2 text-right">p (Holm)</th>
          </tr>
        </thead>
        <tbody>
          {result.arms.map((a) => {
            const c = byT.get(a.label);
            return (
              <tr key={a.label} className="border-b border-stone-100">
                <th scope="row" className="py-2 pr-4 text-left font-medium">
                  {a.label}
                  {a.is_control ? <span className="ml-2 rounded bg-stone-100 px-1.5 py-0.5 text-xs text-stone-600">control</span> : null}
                </th>
                <td className="py-2 pr-4 text-right tabular-nums">{int(a.n)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{mean(a.mean, result.metric_type)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{c ? (c.diff >= 0 ? "+" : "") + effect(c.diff, result.metric_type) : "—"}</td>
                <td className="py-2 pr-4 text-right tabular-nums">
                  {c ? `${effect(c.ci_low, result.metric_type)} to ${effect(c.ci_high, result.metric_type)}` : "—"}
                </td>
                <td className="py-2 pr-4 text-right tabular-nums">{c?.rel_lift != null ? `${c.rel_lift >= 0 ? "+" : ""}${pct(c.rel_lift)}` : "—"}</td>
                <td className="py-2 text-right tabular-nums">
                  {c ? (
                    <span className={c.significant ? "font-semibold text-teal-800" : ""}>
                      {pValue(c.p_holm)}
                      {c.significant ? <span className="sr-only"> (significant)</span> : null}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PowerCard({ power, metricType }: { power: Power; metricType: AnalysisResult["metric_type"] }) {
  return (
    <Card title="Could this test detect a meaningful effect?">
      {power.mde_abs == null ? (
        <p className="text-sm text-stone-600">The minimum detectable effect is undefined here (the control metric does not vary).</p>
      ) : (
        <p className="text-sm text-stone-700">
          This test could detect differences of <strong className="tabular-nums">{effect(power.mde_abs, metricType)}</strong> or more
          {metricType === "binary" ? " (percentage points)" : ""}, with {pct(power.power, 0)} power at α = {power.alpha}.
        </p>
      )}
      <dl className="mt-3 grid grid-cols-2 gap-3">
        <Stat label="Rows per arm (smallest)" value={int(power.n_per_arm)} />
        {power.base_rate != null ? (
          <Stat label="Control rate" value={pct(power.base_rate, 2)} />
        ) : (
          <Stat label="Control SD" value={power.sd.toFixed(3)} />
        )}
      </dl>
    </Card>
  );
}

export function CupedCard({ cuped, metricType }: { cuped: Cuped; metricType: AnalysisResult["metric_type"] }) {
  return (
    <Card title="Variance reduction (CUPED)">
      <p className={`text-sm ${cuped.helpful ? "text-teal-800" : "text-stone-700"}`} data-testid="cuped-message">
        {cuped.message}
      </p>
      {cuped.requested && cuped.corr != null && cuped.variance_removed != null ? (
        <dl className="mt-3 grid grid-cols-2 gap-3">
          <Stat label={`Correlation with ${cuped.pre_period_col ?? "pre-period"}`} value={cuped.corr.toFixed(3)} />
          <Stat label="Variance removed" value={pct(cuped.variance_removed, 2)} hint="needs ≥ 5% and |corr| ≥ 0.1" />
        </dl>
      ) : null}
      {cuped.helpful && cuped.adjusted ? (
        <ul className="mt-3 space-y-1 text-sm">
          {cuped.adjusted.map((c) => (
            <li key={c.treatment}>
              {c.treatment}: {effect(c.diff, metricType)} (CI {effect(c.ci_low, metricType)} to {effect(c.ci_high, metricType)})
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="ml-2 rounded border border-stone-300 px-1.5 text-xs text-stone-700 hover:bg-stone-100"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          window.setTimeout(() => {
            setCopied(false);
          }, 1500);
        });
      }}
      aria-label={label}
    >
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function MetaPanel({ detail, result }: { detail: AnalysisDetail; result: AnalysisResult }) {
  const d = result.rows.dropped;
  const dropped = (Object.entries(d) as [string, number][]).filter(([, v]) => v > 0);
  return (
    <Card title="Data and provenance">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
        <Stat label="Rows read" value={int(result.rows.read)} />
        <Stat label="Rows used" value={int(result.rows.used)} />
        <Stat
          label="Rows dropped"
          value={int(result.rows.read - result.rows.used)}
          hint={dropped.length ? dropped.map(([k, v]) => `${k.replaceAll("_", " ")}: ${int(v)}`).join(", ") : "none"}
        />
        <div>
          <dt className="text-xs uppercase tracking-wide text-stone-500">Input sha256</dt>
          <dd className="mt-0.5 font-mono text-sm" title={detail.input_sha256 ?? ""}>
            {shortSha(detail.input_sha256)}…
            {detail.input_sha256 ? <CopyButton text={detail.input_sha256} label="Copy full sha256" /> : null}
          </dd>
        </div>
        <Stat label="abkit version" value={<span className="font-mono text-sm">{detail.abkit_version ?? "—"}</span>} />
        <Stat label="Commit" value={<span className="font-mono text-sm">{shortSha(detail.git_sha, 10)}</span>} />
        {detail.reused_from ? (
          <div className="col-span-2">
            <dt className="text-xs uppercase tracking-wide text-stone-500">Reused from</dt>
            <dd className="mt-0.5 text-sm">
              Same file and mapping as{" "}
              <Link className="font-mono text-teal-800 underline" to={`/analyses/${detail.reused_from}`}>
                {detail.reused_from.slice(0, 8)}
              </Link>
              ; nothing was recomputed.
            </dd>
          </div>
        ) : null}
        {detail.timings?.total_ms != null ? (
          <Stat label="Time to result" value={`${(detail.timings.total_ms / 1000).toFixed(2)} s`} />
        ) : null}
      </dl>
    </Card>
  );
}

export function ShareButtons({ detail }: { detail: AnalysisDetail }) {
  const [copied, setCopied] = useState(false);
  const download = () => {
    const blob = new Blob([JSON.stringify(detail, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `analysis-${detail.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="secondary"
        onClick={() => {
          void navigator.clipboard.writeText(window.location.href).then(() => {
            setCopied(true);
            window.setTimeout(() => {
              setCopied(false);
            }, 1500);
          });
        }}
      >
        {copied ? "Link copied" : "Copy link"}
      </Button>
      <Button variant="secondary" onClick={download}>
        Download JSON
      </Button>
    </div>
  );
}

const FIXES: Record<string, string> = {
  SINGLE_ARM: "Check that the variant column is the one that holds the A/B assignment and that the file has every arm.",
  CONTROL_NOT_FOUND: "Type the control label exactly as it appears in the variant column (it is case-sensitive).",
  TOO_MANY_ARMS: "The variant column has more than 10 values. Pick the column with the assignment, not an ID.",
  CONSTANT_METRIC: "The metric never changes. Pick a different metric column.",
  ARM_TOO_SMALL: "Every arm needs at least 2 usable rows.",
  NO_USABLE_ROWS: "No row had both a variant and a numeric metric. Check the metric column and the metric type.",
  BAD_CSV: "Save the file as UTF-8 CSV with one header row and the same number of fields on every row.",
  PLANNED_SPLIT_MISMATCH: "Give one planned share per arm, control first, then the others in A→Z order.",
  MAPPING_COLUMN_MISSING: "Re-upload the file or pick columns that exist in its header.",
  OBJECT_MISSING: "Uploads expire after 7 days. Upload the file again.",
  STORAGE_UNAVAILABLE: "Storage was unreachable. Try again in a minute.",
  TIMEOUT: "The file took too long to analyze. Try a smaller file.",
  INTERNAL: "This is a bug on our side, not a problem with your file. Try again later.",
};

export function FailurePanel({ error }: { error: { code: string; message: string } }) {
  return (
    <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-5 text-red-900">
      <p className="text-lg font-semibold">The analysis could not run</p>
      <p className="mt-1">
        {error.message} <span className="font-mono text-xs">({error.code})</span>
      </p>
      {FIXES[error.code] ? (
        <p className="mt-3 text-sm">
          <strong>What to fix:</strong> {FIXES[error.code]}
        </p>
      ) : null}
      <Link to="/new" className="mt-4 inline-block text-sm font-medium text-red-900 underline">
        Upload a corrected file
      </Link>
    </div>
  );
}
