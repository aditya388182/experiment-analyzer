import type { ReactNode } from "react";

import { Card } from "../components/ui";

const REPO_URL = "https://github.com/aditya388182/experiment-analyzer";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card title={title}>
      <div className="space-y-2 text-sm leading-relaxed text-stone-700">{children}</div>
    </Card>
  );
}

export function Method() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">How the analysis works</h1>
      <p className="max-w-2xl text-sm text-stone-700">
        The statistics live in a small Python package, <code>abkit</code>, tested against SciPy and statsmodels. The web app only calls it.
      </p>
      <Section title="Effect and confidence interval (Welch)">
        <p>
          Each treatment is compared with the control as a difference in means with Welch's t interval, which does not assume the two arms
          have equal variance. For a 0/1 metric the mean is the rate, and at these sample sizes the t interval on 0/1 data matches the usual
          normal interval for a difference in proportions. Binary effects are shown in percentage points.
        </p>
      </Section>
      <Section title="Several treatments (Holm)">
        <p>
          With more than one treatment, p-values are adjusted with Holm's step-down method so the chance of any false positive across the
          comparisons stays at alpha. A result is called significant when the Holm-adjusted p is below alpha.
        </p>
      </Section>
      <Section title="Traffic split (sample ratio mismatch)">
        <p>
          A chi-square test compares the arm sizes with the planned split (equal unless you give one). It is flagged when p &lt; 0.001. A
          strict threshold is used because a real mismatch usually means broken assignment or logging, and false alarms are costly. When it
          fires, the verdict starts with a warning: fix the pipeline before trusting the effects.
        </p>
      </Section>
      <Section title="Power and minimum detectable effect">
        <p>
          The minimum detectable effect is the smallest true lift the test would detect 80% of the time at your alpha, using the normal
          approximation with the smallest arm's size. When a result shows no detectable difference, this tells you whether the test could
          have found an effect of a size you care about.
        </p>
      </Section>
      <Section title="Variance reduction (CUPED)">
        <p>
          If you map a pre-period column, CUPED removes the part of the metric that the pre-period value predicts (theta = cov(y, x) / var(x),
          one theta pooled across arms). The share of variance removed equals the squared correlation. It is reported as helpful only when
          |correlation| ≥ 0.1 and at least 5% of the variance is removed; otherwise the unadjusted results stand and the card says why.
        </p>
      </Section>
      <Section title="Data handling">
        <p>
          Rows with a missing variant, a non-numeric metric, a value other than 0/1 for a binary metric, or a missing pre-period value (when
          one is mapped) are dropped and counted by reason. Results are keyed by the file's sha256 and the mapping, so the same file and
          mapping always return the same stored result.
        </p>
      </Section>
      <p className="text-sm">
        Source code:{" "}
        <a className="text-teal-800 underline" href={REPO_URL}>
          {REPO_URL}
        </a>
      </p>
    </div>
  );
}
