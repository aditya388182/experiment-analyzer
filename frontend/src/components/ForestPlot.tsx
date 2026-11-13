import { Bar, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";

import type { Comparison, MetricType } from "../api/types";
import { effect } from "../lib/format";
import { niceTicks } from "../lib/ticks";

interface Row {
  treatment: string;
  ci: [number, number];
  diff: number;
  label: string;
}

/** One row per treatment: a line for the CI, a dot for the difference, and a dashed zero line. */
export function ForestPlot({ comparisons, metricType, alpha }: { comparisons: Comparison[]; metricType: MetricType; alpha: number }) {
  const scale = metricType === "binary" ? 100 : 1;
  const rows: Row[] = comparisons.map((c) => ({
    treatment: c.treatment,
    ci: [c.ci_low * scale, c.ci_high * scale],
    diff: c.diff * scale,
    label: `${effect(c.diff, metricType)} (CI ${effect(c.ci_low, metricType)} to ${effect(c.ci_high, metricType)})`,
  }));
  const ticks = niceTicks(Math.min(0, ...rows.map((r) => r.ci[0])), Math.max(0, ...rows.map((r) => r.ci[1])));
  const digits = Math.max(0, -Math.floor(Math.log10((ticks[1] ?? 1) - (ticks[0] ?? 0))) + 1);
  const unit = metricType === "binary" ? "percentage points" : "metric units";
  const level = Math.round((1 - alpha) * 100);
  return (
    <figure>
      <figcaption className="mb-2 text-sm text-stone-600">
        Difference vs control with {level}% confidence intervals, in {unit}. Intervals that cross the dashed zero line are not
        distinguishable from no effect.
      </figcaption>
      <div style={{ width: "100%", height: 70 + rows.length * 56 }} role="img" aria-label={rows.map((r) => `${r.treatment}: ${r.label}`).join("; ")}>
        <ResponsiveContainer>
          <ComposedChart layout="vertical" data={rows} margin={{ top: 10, right: 24, bottom: 20, left: 8 }}>
            <CartesianGrid horizontal={false} stroke="#e7e5e4" />
            <XAxis
              type="number"
              domain={[ticks[0] ?? 0, ticks[ticks.length - 1] ?? 1]}
              ticks={ticks}
              tickFormatter={(v: number) => v.toFixed(Math.min(digits, 4))}
              label={{ value: unit, position: "insideBottom", offset: -12, fontSize: 12 }}
              fontSize={12}
            />
            <YAxis type="category" dataKey="treatment" width={130} fontSize={12} />
            <Tooltip formatter={(_v, _n, item) => [(item.payload as Row).label, "Effect"]} />
            <ReferenceLine x={0} stroke="#57534e" strokeDasharray="4 4" />
            <Bar dataKey="ci" barSize={4} fill="#0f766e" isAnimationActive={false} />
            <Scatter dataKey="diff" fill="#134e4a" shape="circle" isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
