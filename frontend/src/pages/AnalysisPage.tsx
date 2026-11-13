import { Link, useParams } from "react-router";

import { useAnalysis } from "../api/queries";
import { ForestPlot } from "../components/ForestPlot";
import {
  ArmsTable,
  CupedCard,
  FailurePanel,
  MetaPanel,
  PowerCard,
  ShareButtons,
  SrmBanner,
  StatusTimeline,
} from "../components/results";
import { Card, ErrorMessage, Spinner } from "../components/ui";

export function AnalysisPage() {
  const { id = "" } = useParams();
  const q = useAnalysis(id);

  if (q.isPending) return <Spinner label="Loading analysis…" />;
  if (q.isError) {
    return (
      <div className="space-y-4">
        <ErrorMessage error={q.error} title="Could not load this analysis" />
        <Link to="/" className="text-sm text-teal-800 underline">Back to home</Link>
      </div>
    );
  }
  const d = q.data;
  const r = d.result;
  const source = d.sample_name ? `Sample: Hillstrom email test` : (d.file_name ?? "Uploaded file");

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <p className="text-sm text-stone-500">
          {source} · metric <span className="font-mono">{d.mapping.metric_col}</span> ({d.mapping.metric_type}) · variant{" "}
          <span className="font-mono">{d.mapping.variant_col}</span> · control “{d.mapping.control_label}”
        </p>
        <StatusTimeline status={d.status} />
      </header>

      {d.status === "QUEUED" || d.status === "RUNNING" ? (
        <Card>
          <Spinner label={d.status === "QUEUED" ? "Waiting for a worker…" : "Analyzing the file…"} />
          <p className="mt-2 text-xs text-stone-500">This page checks every second and updates on its own.</p>
        </Card>
      ) : null}

      {d.status === "FAILED" && d.error ? <FailurePanel error={d.error} /> : null}

      {d.status === "SUCCEEDED" && r ? (
        <>
          <section aria-labelledby="verdict-h" className="rounded-lg border border-teal-200 bg-teal-50 p-5">
            <h1 id="verdict-h" className="sr-only">Verdict</h1>
            <p className="text-xl font-medium leading-relaxed text-teal-950" data-testid="verdict">{r.verdict}</p>
          </section>
          <SrmBanner srm={r.srm} />
          <Card title="Arms">
            <ArmsTable result={r} />
          </Card>
          <Card title="Effect vs control">
            <ForestPlot comparisons={r.comparisons} metricType={r.metric_type} alpha={r.alpha} />
          </Card>
          <div className="grid gap-6 md:grid-cols-2">
            <PowerCard power={r.power} metricType={r.metric_type} />
            <CupedCard cuped={r.cuped} metricType={r.metric_type} />
          </div>
          {r.warnings.length ? (
            <Card title="Warnings">
              <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
                {r.warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            </Card>
          ) : null}
          <MetaPanel detail={d} result={r} />
          <ShareButtons detail={d} />
        </>
      ) : null}
    </div>
  );
}
