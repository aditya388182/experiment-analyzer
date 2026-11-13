import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useCreateSample, useRecentAnalyses } from "../api/queries";
import { when } from "../lib/format";
import { Button, Card, ErrorMessage, Spinner } from "../components/ui";

type SampleMetric = "visit" | "conversion" | "spend";

const STATUS_STYLE: Record<string, string> = {
  SUCCEEDED: "bg-emerald-100 text-emerald-900",
  FAILED: "bg-red-100 text-red-900",
  RUNNING: "bg-amber-100 text-amber-900",
  QUEUED: "bg-stone-100 text-stone-700",
};

export function Home() {
  const navigate = useNavigate();
  const sample = useCreateSample();
  const recent = useRecentAnalyses();
  const [metric, setMetric] = useState<SampleMetric>("visit");

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900">Did your A/B test actually work?</h1>
        <p className="max-w-2xl text-stone-700">
          Upload a results file and get a correct, plain-English readout: the effect with a confidence interval, whether the
          traffic split was healthy, whether the test had enough data, and whether variance reduction helped.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Button
            onClick={() => {
              sample.mutate(metric, {
                onSuccess: (r) => {
                  void navigate(`/analyses/${r.analysis_id}`);
                },
              });
            }}
            disabled={sample.isPending}
          >
            {sample.isPending ? "Starting…" : "Analyze a real 64,000-customer email test"}
          </Button>
          <div>
            <label htmlFor="sample-metric" className="block text-xs text-stone-600">Outcome</label>
            <select
              id="sample-metric"
              value={metric}
              onChange={(e) => {
                setMetric(e.target.value as SampleMetric);
              }}
              className="mt-1 rounded-md border border-stone-300 bg-white px-2 py-2 text-sm"
            >
              <option value="visit">Site visit (binary)</option>
              <option value="conversion">Purchase (binary)</option>
              <option value="spend">Spend in $ (continuous)</option>
            </select>
          </div>
          <Link
            to="/new"
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600"
          >
            Upload your own
          </Link>
        </div>
        <p className="text-xs text-stone-500">
          Sample: the MineThatData (Hillstrom) email test. 64,000 customers randomized to a men's email, a women's email or no email.
        </p>
        <ErrorMessage error={sample.error} title="Could not start the sample analysis" />
      </section>

      <Card title="Recent analyses">
        {recent.isPending ? <Spinner label="Loading recent analyses…" /> : null}
        <ErrorMessage error={recent.error} title="Could not load recent analyses" />
        {recent.data && recent.data.results.length === 0 ? <p className="text-sm text-stone-600">No analyses yet.</p> : null}
        {recent.data && recent.data.results.length > 0 ? (
          <ul className="divide-y divide-stone-100">
            {recent.data.results.map((a) => (
              <li key={a.id} className="py-3">
                <Link to={`/analyses/${a.id}`} className="group block focus:outline-none focus-visible:ring-2 focus-visible:ring-teal-600">
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[a.status] ?? ""}`}>{a.status}</span>
                    <span className="font-medium text-stone-900 group-hover:underline">
                      {a.sample_name ? `Sample: ${a.sample_name}` : (a.file_name ?? "Upload")} · {a.metric_col}
                    </span>
                    {a.reused_from ? <span className="text-xs text-stone-500">reused</span> : null}
                    <span className="ml-auto text-xs text-stone-500">{when(a.created_at)}</span>
                  </div>
                  {a.verdict ? <p className="mt-1 line-clamp-2 text-sm text-stone-600">{a.verdict}</p> : null}
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </Card>
    </div>
  );
}
