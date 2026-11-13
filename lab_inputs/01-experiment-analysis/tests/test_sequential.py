import numpy as np

from abtest import sequential as sq


def test_always_valid_pvalue_never_increases():
    n = np.arange(100, 5001, 100)
    diff = np.random.default_rng(0).normal(0, 0.01, len(n))
    p = sq.msprt_pvalues(diff, n, 0.09, 0.01 ** 2)
    assert np.all(np.diff(p) <= 0) and p.max() <= 1


def test_msprt_controls_false_positives_while_peeking_does_not():
    r = sq.simulate(0.10, 0.10, 20_000, 500, 2000, np.random.default_rng(1), 0.01 ** 2)
    assert r["msprt_reject_rate"] <= 0.05
    assert r["naive_peeking_reject_rate"] > 0.20
    assert 0.03 < r["fixed_horizon_reject_rate"] < 0.07


def test_msprt_stops_early_on_a_large_effect():
    r = sq.simulate(0.10, 0.18, 20_000, 500, 500, np.random.default_rng(2), 0.01 ** 2)
    assert r["msprt_reject_rate"] == 1.0 and r["sample_saving_vs_fixed"] > 0.8
