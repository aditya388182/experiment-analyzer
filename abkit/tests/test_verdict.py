"""Exact verdict strings for hand-built results (the template, not the statistics, is under test)."""

from __future__ import annotations

from abkit.verdict import fmt_p, verdict


def _result(comparisons, metric_type="binary", srm_p=0.5, mde=0.0084, cuped=None, alpha=0.05, metric="visit"):
    return {
        "metric_col": metric,
        "metric_type": metric_type,
        "control_label": "Control",
        "alpha": alpha,
        "srm": {"p": srm_p, "flagged": srm_p < 0.001},
        "comparisons": comparisons,
        "power": {"mde_abs": mde},
        "cuped": cuped or {"helpful": False, "adjusted": None},
    }


def _cmp(diff, lo, hi, treatment="B", significant=True, p_holm=1e-5, rel=0.5):
    return {
        "treatment": treatment,
        "diff": diff,
        "ci_low": lo,
        "ci_high": hi,
        "significant": significant,
        "p_holm": p_holm,
        "rel_lift": rel,
    }


def test_binary_increase():
    # Made-up inputs: this tests the template, not the lab result (that lives in test_lab_reproduction.py).
    r = _result([_cmp(0.04321, 0.03456, 0.05187, treatment="Email A")])
    r["control_label"] = "No email"
    assert verdict(r) == "Email A increased visit rate by 4.32 percentage points (95% CI 3.46 to 5.19) vs No email."


def test_binary_decrease():
    r = _result([_cmp(-0.02, -0.03, -0.01)])
    assert verdict(r) == "B decreased visit rate by 2.00 percentage points (95% CI -3.00 to -1.00) vs Control."


def test_binary_no_difference_mentions_mde():
    r = _result([_cmp(0.001, -0.004, 0.006, significant=False, p_holm=0.7)])
    assert verdict(r) == (
        "B: no detectable difference in visit rate vs Control (95% CI -0.40 to 0.60 percentage "
        "points). This test could detect differences of 0.84 percentage points or more."
    )


def test_metric_already_named_rate_is_not_doubled():
    r = _result([_cmp(0.02, 0.01, 0.03)], metric="conversion_rate")
    assert "increased conversion_rate by" in verdict(r)


def test_continuous_increase_with_relative_lift():
    r = _result([_cmp(0.7698, 0.4851, 1.0546, rel=1.1793)], metric_type="continuous", metric="spend")
    assert verdict(r) == "B increased spend by 0.770 (95% CI 0.485 to 1.055; +117.9% relative) vs Control."


def test_continuous_no_difference():
    r = _result(
        [_cmp(3.0, -12.0, 18.0, significant=False, p_holm=0.7)], metric_type="continuous", metric="revenue", mde=21.5
    )
    assert verdict(r) == (
        "B: no detectable difference in revenue vs Control (95% CI -12.0 to 18.0). "
        "This test could detect differences of 21.5 or more."
    )


def test_significant_ci_but_not_after_holm():
    r = _result([_cmp(0.02, 0.001, 0.039, significant=False, p_holm=0.08), _cmp(0.0, -0.01, 0.01, "C", False, 1.0)])
    assert verdict(r).startswith(
        "B increased visit rate by 2.00 percentage points (95% CI 0.10 to 3.90) vs Control. "
        "This is not significant after the Holm correction across 2 comparisons (adjusted p = 0.080). C: "
    )


def test_srm_prefix():
    r = _result([_cmp(0.02, 0.01, 0.03)], srm_p=2.3e-8)
    assert verdict(r).startswith("Do not trust this result: the traffic split is off (SRM p = 2.3e-08). B increased")


def test_cuped_helpful_is_mentioned():
    adj = [_cmp(0.021, 0.015, 0.027)]
    r = _result([_cmp(0.02, 0.01, 0.03)], cuped={"helpful": True, "adjusted": adj, "pre_period_col": "history"})
    assert verdict(r).endswith(
        "With CUPED on history: B increased visit rate by 2.10 percentage points (95% CI 1.50 to 2.70) vs Control."
    )


def test_alpha_changes_confidence_level():
    r = _result([_cmp(0.02, 0.01, 0.03)], alpha=0.1)
    assert "(90% CI 1.00 to 3.00)" in verdict(r)


def test_fmt_p():
    assert fmt_p(0.9036929) == "0.904"
    assert fmt_p(0.0001) == "1.0e-04"
