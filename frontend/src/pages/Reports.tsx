import { Bar, BarChart, CartesianGrid, Rectangle, ResponsiveContainer, Tooltip, XAxis, YAxis, type BarShapeProps } from "recharts";

import { useReports } from "../api/queries";
import type { ChurnCard, ForecastingCard } from "../api/types";
import { int, pct } from "../lib/format";
import { Card, ErrorMessage, Spinner, Stat } from "../components/ui";

const nice = (s: string) => s.replaceAll("_", " ");

function Churn({ c }: { c: ChurnCard }) {
  return (
    <Card title="Churn model (UCI Online Retail II)">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label={`Test AUC (${nice(c.selected_model)})`} value={c.test_auc.toFixed(2)} hint={`95% CI ${c.test_auc_ci[0].toFixed(3)} to ${c.test_auc_ci[1].toFixed(3)}`} />
        <Stat label={`Baseline (${nice(c.baseline_model)})`} value={c.baseline_auc.toFixed(2)} />
        <Stat label="AUC gain over baseline" value={`${c.auc_gain_ci[0].toFixed(3)} to ${c.auc_gain_ci[1].toFixed(3)}`} hint="95% CI" />
        <Stat label="Shuffled scores" value={c.shuffled_score_auc.toFixed(3)} hint="sanity check: ≈ 0.5" />
      </dl>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="mb-1 text-left text-xs text-stone-500">Test-set scores by model</caption>
          <thead>
            <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wide text-stone-500">
              <th scope="col" className="py-1.5">Model</th>
              <th scope="col" className="py-1.5 text-right">ROC AUC</th>
              <th scope="col" className="py-1.5 text-right">PR AUC</th>
            </tr>
          </thead>
          <tbody>
            {c.test_by_model.map((m) => (
              <tr key={m.model} className={`border-b border-stone-100 ${m.selected ? "bg-teal-50 font-semibold" : ""}`}>
                <th scope="row" className="py-1.5 text-left font-normal">
                  {nice(m.model)}
                  {m.selected ? " (selected)" : m.baseline ? " (baseline)" : ""}
                </th>
                <td className="py-1.5 text-right tabular-nums">{m.roc_auc.toFixed(3)}</td>
                <td className="py-1.5 text-right tabular-nums">{m.pr_auc.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="mt-6 text-sm font-semibold">Who to target: share of lapsed customers' revenue in the top 20%</h3>
      <dl className="mt-2 grid grid-cols-3 gap-4">
        <Stat label="Risk × value" value={pct(c.targeting.top20_by_risk_x_value)} />
        <Stat label="Value only" value={pct(c.targeting.top20_by_value_only)} />
        <Stat label="Risk only" value={pct(c.targeting.top20_by_risk_only)} />
      </dl>
      <p className="mt-1 text-xs text-stone-500">
        {int(c.targeting.lapsed_customers)} customers lapsed, holding {pct(c.targeting.share_of_revenue_lapsed)} of last year's revenue.
      </p>
      <h3 className="mt-6 text-sm font-semibold">Known limits</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-stone-700">
        {c.known_limits.map((l) => <li key={l}>{l}</li>)}
      </ul>
      <table className="mt-3 w-full text-xs">
        <caption className="mb-1 text-left text-stone-500">Calibration error by recalibration method (lower is better)</caption>
        <tbody>
          {c.calibration.variants.map((v) => (
            <tr key={v.variant} className="border-b border-stone-100">
              <th scope="row" className="py-1 text-left font-normal">{nice(v.variant)}</th>
              <td className="py-1 text-right tabular-nums">{pct(v.calibration_error)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function Forecasting({ f }: { f: ForecastingCard }) {
  const data = f.methods.map((m) => ({ name: nice(m.method), mase: m.mase, winner: m.winner }));
  return (
    <Card title="Weekly revenue forecasting">
      <p className="text-sm text-stone-700">
        Mean absolute scaled error (MASE: error divided by the in-sample naive forecast's error; lower is better) across{" "}
        {f.backtests} rolling-origin backtests over {f.weeks_total} weeks;{" "}
        <strong>{nice(f.winner)}</strong> has the lowest error.
      </p>
      <div className="mt-4" style={{ width: "100%", height: 240 }} role="img" aria-label={data.map((d) => `${d.name}: MASE ${d.mase.toFixed(3)}`).join("; ")}>
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 10 }}>
            <CartesianGrid horizontal={false} stroke="#e7e5e4" />
            <XAxis type="number" domain={[0, "auto"]} fontSize={12} />
            <YAxis type="category" dataKey="name" width={130} fontSize={12} />
            <Tooltip formatter={(v) => [Number(v).toFixed(3), "MASE"]} />
            <Bar
              dataKey="mase"
              isAnimationActive={false}
              label={{ position: "right", fontSize: 11, formatter: (v: unknown) => Number(v).toFixed(3) }}
              shape={(props: BarShapeProps) => {
                const winner = (props.payload as { winner?: boolean } | undefined)?.winner === true;
                return <Rectangle {...props} fill={winner ? "#0f766e" : "#a8a29e"} />;
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-sm text-stone-700">
        LightGBM vs {nice(f.lightgbm_vs_best_simple.best_simple)}: LightGBM's MAE is{" "}
        {f.lightgbm_vs_best_simple.mae_difference >= 0 ? "higher" : "lower"} by{" "}
        {int(Math.round(Math.abs(f.lightgbm_vs_best_simple.mae_difference)))} (difference 95% CI {int(Math.round(f.lightgbm_vs_best_simple.ci[0]))} to{" "}
        {int(Math.round(f.lightgbm_vs_best_simple.ci[1]))}){f.lightgbm_vs_best_simple.ci_includes_zero ? ", an interval that includes zero" : ""}.
      </p>
    </Card>
  );
}

export function Reports() {
  const q = useReports();
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Model reports</h1>
      <p className="max-w-2xl text-sm text-stone-700">Results from the lab's churn and forecasting projects, read from their result files.</p>
      {q.isPending ? <Spinner label="Loading reports…" /> : null}
      <ErrorMessage error={q.error} title="Could not load the reports" />
      {q.data ? (
        <>
          <Churn c={q.data.churn} />
          <Forecasting f={q.data.forecasting} />
          <p className="text-xs text-stone-500">
            Source: {q.data.source.repo}, {q.data.source.commit}. Every number above is read from the lab's results JSON; a test checks
            each one against its key.
          </p>
        </>
      ) : null}
    </div>
  );
}
