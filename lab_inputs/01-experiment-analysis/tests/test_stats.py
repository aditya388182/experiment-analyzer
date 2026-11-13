"""Checks that the statistics behave correctly on cases where the right answer is known."""
import numpy as np
import pandas as pd

import run
from abtest import stats as st
from abtest import uplift as up

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
    y = 0.6 * x + rng.normal(scale=0.8, size=100_000)       # correlation 0.6
    y_adj, removed = st.cuped(y, x)
    assert abs(removed - np.corrcoef(y, x)[0, 1] ** 2) < 1e-9
    assert abs(y_adj.mean() - y.mean()) < 1e-9


def test_aa_false_positive_rate_is_near_alpha():
    y = rng.binomial(1, 0.1, 20_000).astype(float)
    assert 0.03 < st.aa_false_positive_rate(y, 1000, np.random.default_rng(1)) < 0.07


def test_mde_shrinks_with_sample_size():
    assert st.mde_two_proportions(0.1, 40_000) < st.mde_two_proportions(0.1, 10_000)


def _synthetic(n=40_000):
    x = rng.normal(size=n)
    t = rng.integers(0, 2, n)
    y = rng.binomial(1, np.clip(0.10 + 0.10 * t * (x > 0), 0, 1))   # only x > 0 responds
    return x, t, y


def test_qini_zero_for_random_and_positive_for_true_signal():
    x, t, y = _synthetic()
    assert abs(up.qini_coefficient(rng.normal(size=len(x)), t, y)) < 0.05
    assert up.qini_coefficient(x, t, y) > 0.15
    assert up.capture_at(x, t, y, 0.5) > 0.85          # top half holds nearly all the uplift


def test_t_learner_finds_planted_uplift():
    from sklearn.linear_model import LogisticRegression
    x, t, y = _synthetic()
    X = np.column_stack([x, (x > 0).astype(float)])
    s = up.TLearner(LogisticRegression()).fit(X[:30_000], t[:30_000], y[:30_000]).predict(X[30_000:])
    assert up.qini_coefficient(s, t[30_000:], y[30_000:]) > 0.1


def test_features_do_not_leak_outcomes():
    df = run.load()
    base = run.features(df)
    shuffled = df.copy()
    for col in ["visit", "conversion", "spend", "segment"]:
        shuffled[col] = rng.permutation(shuffled[col].to_numpy())
    assert np.array_equal(base, run.features(shuffled))   # features ignore outcomes and assignment


def test_results_are_reproducible():
    df = run.load()
    a = run.effects(df, np.random.default_rng(run.SEED))
    b = run.effects(df, np.random.default_rng(run.SEED))
    assert a == b
    assert abs(a["mens_visit"]["diff"] - 0.0766) < 0.0005
