"""Lab tests for the statistics, ported from lab_inputs/01-experiment-analysis/tests/test_stats.py.
Tests of the lab's run.py and uplift.py stay in the lab (DECISIONS.md D4)."""

from __future__ import annotations

import numpy as np

from abkit import power as pw
from abkit import stats as st

rng = np.random.default_rng(0)


def test_srm_passes_even_split_and_catches_broken_split():
    assert st.srm_test([10000, 10050, 9950], [1 / 3] * 3) > 0.05
    assert st.srm_test([10000, 10000, 9000], [1 / 3] * 3) < 0.001


def test_diff_in_means_recovers_known_effect():
    t, c = rng.normal(1.0, 1, 50_000), rng.normal(0.8, 1, 50_000)
    r = st.diff_in_means(t, c)
    assert r["ci_low"] < 0.2 < r["ci_high"] and r["p"] < 1e-6


def test_holm_matches_hand_calculation():
    # sorted p: .01 .02 .03 -> .03, max(.03,.04)=.04, max(.04,.03)=.04
    assert np.allclose(st.holm([0.02, 0.01, 0.03]), [0.04, 0.03, 0.04])


def test_cuped_removes_correlation_squared_and_keeps_the_mean():
    x = rng.normal(size=100_000)
    y = 0.6 * x + rng.normal(scale=0.8, size=100_000)  # correlation 0.6
    y_adj, removed = st.cuped(y, x)
    assert abs(removed - np.corrcoef(y, x)[0, 1] ** 2) < 1e-9
    assert abs(y_adj.mean() - y.mean()) < 1e-9


def test_aa_false_positive_rate_is_near_alpha():
    y = rng.binomial(1, 0.1, 20_000).astype(float)
    assert 0.03 < st.aa_false_positive_rate(y, 1000, np.random.default_rng(1)) < 0.07


def test_mde_shrinks_with_sample_size():
    assert pw.mde_two_proportions(0.1, 40_000) < pw.mde_two_proportions(0.1, 10_000)


def test_bootstrap_ci_brackets_true_difference():
    t, c = rng.normal(1.0, 1, 2_000), rng.normal(0.8, 1, 2_000)
    lo, hi = st.bootstrap_diff_ci(t, c, 500, np.random.default_rng(2))
    assert lo < 0.2 < hi


def test_regression_adjustment_recovers_effect():
    n = 20_000
    x = rng.normal(size=(n, 2))
    t = rng.integers(0, 2, n).astype(float)
    y = 0.3 * t + x @ np.array([1.0, -0.5]) + rng.normal(size=n)
    r = st.regression_adjusted_effect(y, t, x)
    assert abs(r["diff"] - 0.3) < 4 * r["se"]
