"""Hypothesis property tests. Each property counts its generated examples for results/validation.json."""

from __future__ import annotations

import numpy as np
from conftest import RECORDER
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

import abkit

FINITE = st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False)
SAMPLE = arrays(np.float64, st.integers(2, 300), elements=FINITE)
BINARY = arrays(np.float64, st.integers(2, 300), elements=st.sampled_from([0.0, 1.0]))
ALPHA = st.sampled_from([0.01, 0.05, 0.1, 0.2])
PROFILE = settings(max_examples=300, deadline=None)


def _ok(a: np.ndarray) -> bool:
    return bool(np.var(a) > 1e-9)


@PROFILE
@given(t=st.one_of(SAMPLE, BINARY), c=st.one_of(SAMPLE, BINARY), alpha=ALPHA)
def test_ci_contains_point_estimate(t, c, alpha):
    assume(_ok(t) and _ok(c))
    RECORDER.hypothesis_examples["ci_contains_point_estimate"] += 1
    r = abkit.diff_in_means(t, c, alpha)
    assert r["ci_low"] <= r["diff"] <= r["ci_high"]


@PROFILE
@given(t=st.one_of(SAMPLE, BINARY), c=st.one_of(SAMPLE, BINARY), alpha=ALPHA)
def test_swapping_arms_flips_diff_and_swaps_ci(t, c, alpha):
    assume(_ok(t) and _ok(c))
    RECORDER.hypothesis_examples["swap_flips_sign_and_ci"] += 1
    a = abkit.diff_in_means(t, c, alpha)
    b = abkit.diff_in_means(c, t, alpha)
    scale = 1 + abs(a["diff"]) + (a["ci_high"] - a["ci_low"])
    assert abs(a["diff"] + b["diff"]) <= 1e-12 * scale
    assert abs(a["ci_low"] + b["ci_high"]) <= 1e-12 * scale
    assert abs(a["ci_high"] + b["ci_low"]) <= 1e-12 * scale
    assert abs(a["p"] - b["p"]) <= 1e-12


def test_srm_flags_52_48_split_at_100k():
    RECORDER.hypothesis_examples["srm_52_48_flagged"] += 1
    assert abkit.srm_test([52_000, 48_000], [0.5, 0.5]) < 0.001


def test_srm_does_not_flag_true_50_50_in_99_of_100_seeds():
    passes = 0
    for seed in range(100):
        n_a = int(np.random.default_rng(seed).binomial(100_000, 0.5))
        passes += abkit.srm_test([n_a, 100_000 - n_a], [0.5, 0.5]) >= 0.001
        RECORDER.hypothesis_examples["srm_true_50_50_seeds"] += 1
    assert passes >= 99


@PROFILE
@given(p=st.lists(st.floats(min_value=0, max_value=1, allow_nan=False), min_size=1, max_size=12))
def test_holm_adjusted_at_least_raw_and_order_preserved(p):
    RECORDER.hypothesis_examples["holm_monotone"] += 1
    adj = abkit.holm(p)
    assert all(a >= r for a, r in zip(adj, p, strict=True))
    assert all(0 <= a <= 1 for a in adj)
    order = np.argsort(p, kind="stable")
    sorted_adj = [adj[i] for i in order]
    assert all(x <= y for x, y in zip(sorted_adj, sorted_adj[1:], strict=False))


@PROFILE
@given(
    y=arrays(np.float64, st.integers(3, 300), elements=FINITE),
    noise=st.floats(min_value=-5, max_value=5, allow_nan=False),
    seed=st.integers(0, 2**32 - 1),
)
def test_cuped_variance_removed_in_unit_interval(y, noise, seed):
    rng = np.random.default_rng(seed)
    x = y * noise + rng.normal(size=len(y)) * float(np.std(y) + 1)
    assume(_ok(y) and _ok(x))
    RECORDER.hypothesis_examples["cuped_variance_removed_in_0_1"] += 1
    _, removed = abkit.cuped(y, x)
    # corr^2 computed in floating point can land a hair outside [0, 1]; 1e-12 is rounding, not a formula change.
    assert -1e-12 <= removed <= 1 + 1e-12


@PROFILE
@given(
    base=st.floats(min_value=0.01, max_value=0.9),
    n=st.integers(min_value=50, max_value=1_000_000),
    alpha=ALPHA,
)
def test_mde_sample_size_round_trip(base, n, alpha):
    RECORDER.hypothesis_examples["mde_sample_size_round_trip"] += 1
    mde = abkit.mde_two_proportions(base, n, alpha)
    n_back = abkit.sample_size_two_proportions(base, mde, alpha)
    assert abs(n_back - n) <= 1
