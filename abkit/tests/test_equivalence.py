"""Every abkit function against an independent reference (SciPy / statsmodels / numpy), 20 seeded datasets each."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats as sps
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.power import NormalIndPower

import abkit

SEEDS = range(20)


def _pair(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Even seeds: binary outcomes; odd seeds: continuous (skewed). Arm sizes always differ."""
    rng = np.random.default_rng(seed)
    n_t, n_c = 40 + 97 * seed, 55 + 61 * seed
    if seed % 2 == 0:
        p = 0.05 + 0.02 * seed
        return rng.binomial(1, p + 0.03, n_t).astype(float), rng.binomial(1, p, n_c).astype(float)
    return rng.lognormal(0.2, 0.9, n_t) + 0.1, rng.lognormal(0.0, 1.1, n_c)


@pytest.mark.parametrize("seed", SEEDS)
def test_diff_in_means_matches_scipy_welch(seed, recorder):
    t, c = _pair(seed)
    for alpha in (0.05, 0.1):
        ours = abkit.diff_in_means(t, c, alpha)
        ref = sps.ttest_ind(t, c, equal_var=False)
        ci = ref.confidence_interval(confidence_level=1 - alpha)
        for got, want in (
            (ours["p"], ref.pvalue),
            (ours["ci_low"], ci.low),
            (ours["ci_high"], ci.high),
            (ours["diff"], t.mean() - c.mean()),
        ):
            assert abs(got - want) <= 1e-9
            recorder.diff("diff_in_means", got - want)
    recorder.dataset(
        "diff_in_means", "scipy.stats.ttest_ind(equal_var=False) p-value and .confidence_interval()", "1e-9"
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_srm_matches_scipy_chisquare(seed, recorder):
    rng = np.random.default_rng(100 + seed)
    k = 2 + seed % 5
    share = rng.dirichlet(np.ones(k) * 5)
    counts = [int(x) for x in rng.multinomial(1000 + 500 * seed, share)]
    got = abkit.srm_test(counts, list(share))
    want = sps.chisquare(counts, np.sum(counts) * share).pvalue
    assert abs(got - want) <= 1e-12
    recorder.diff("srm_test", got - want)
    recorder.dataset("srm_test", "scipy.stats.chisquare", "1e-12")


@pytest.mark.parametrize("seed", SEEDS)
def test_holm_matches_statsmodels(seed, recorder):
    rng = np.random.default_rng(200 + seed)
    m = 2 + seed % 9
    p = rng.uniform(0, 0.2, m) ** (1 + seed % 3)
    got = np.array(abkit.holm(list(p)))
    want = multipletests(p, method="holm")[1]
    assert np.max(np.abs(got - want)) <= 1e-12
    recorder.diff("holm", float(np.max(np.abs(got - want))))
    recorder.dataset("holm", "statsmodels.stats.multitest.multipletests(method='holm')", "1e-12")


@pytest.mark.parametrize("seed", SEEDS)
def test_cuped_theta_is_ols_slope_and_variance_removed_is_corr_squared(seed, recorder):
    rng = np.random.default_rng(300 + seed)
    n = 200 + 150 * seed
    x = rng.normal(5, 2, n) if seed % 2 else rng.exponential(3, n)
    noise = rng.normal(0, 1, n)
    y = (rng.binomial(1, 0.3, n) + 0.05 * x).astype(float) if seed % 2 == 0 else 0.3 * x + noise
    theta = abkit.cuped_theta(y, x)
    slope_polyfit = np.polyfit(x, y, 1)[0]
    slope_ols = OLS(y, np.column_stack([np.ones(n), x])).fit().params[1]
    _, removed = abkit.cuped(y, x)
    corr2 = np.corrcoef(y, x)[0, 1] ** 2
    for got, want in ((theta, slope_polyfit), (theta, slope_ols), (removed, corr2)):
        assert abs(got - want) <= 1e-9
        recorder.diff("cuped", got - want)
    recorder.dataset("cuped", "theta vs numpy.polyfit and statsmodels OLS slope; variance removed vs corr^2", "1e-9")


@pytest.mark.parametrize("seed", SEEDS)
def test_mde_matches_statsmodels_normal_ind_power(seed, recorder):
    """statsmodels' power curve at our MDE must equal the target power plus the far-tail term it also counts
    (exact to 1e-9), and its MDE must be within 1e-4 relative after converging the solve properly.

    ``NormalIndPower().solve_power`` alone stops early (it returns power 0.79990 for a 0.8 target on some
    seeds, a 1.3e-4 relative MDE error), so its raw output is checked at 1e-3 and the converged value at 1e-4.
    See DECISIONS.md D5.
    """
    from scipy.optimize import brentq

    rng = np.random.default_rng(400 + seed)
    base = float(rng.uniform(0.01, 0.5))
    n = int(rng.integers(500, 100_000))
    alpha = (0.01, 0.05, 0.1)[seed % 3]
    power = (0.8, 0.9)[seed % 2]
    got = abkit.mde_two_proportions(base, n, alpha, power)
    sd = np.sqrt(base * (1 - base))
    sm = NormalIndPower()
    # 1. statsmodels power at our MDE = target + far tail.
    d = got / sd
    far_tail = sps.norm.cdf(-sps.norm.ppf(1 - alpha / 2) - d * np.sqrt(n / 2))
    assert abs(sm.power(d, n, alpha, ratio=1.0) - (power + far_tail)) <= 1e-9
    # 2. statsmodels' MDE, solved to full precision on its own power function.
    d_ref = brentq(lambda e: sm.power(e, n, alpha, ratio=1.0) - power, 1e-8, 10, xtol=1e-15, rtol=1e-15)
    rel = abs(got - d_ref * sd) / (d_ref * sd)
    assert rel <= 1e-4
    recorder.diff("mde_two_proportions", rel)
    # 3. statsmodels' own solver, as shipped.
    d_solve = sm.solve_power(effect_size=None, nobs1=n, alpha=alpha, power=power, ratio=1.0, alternative="two-sided")
    assert abs(got - d_solve * sd) / (d_solve * sd) <= 1e-3
    recorder.diff("mde_two_proportions_vs_solve_power_raw", abs(got - d_solve * sd) / (d_solve * sd))
    recorder.dataset(
        "mde_two_proportions",
        "statsmodels NormalIndPower power curve, solved with brentq to 1e-15, x sqrt(p(1-p)) "
        "(statsmodels also counts the far tail)",
        "1e-4 relative",
        kind="relative",
    )
    recorder.dataset(
        "mde_two_proportions_vs_solve_power_raw",
        "statsmodels NormalIndPower().solve_power as shipped (its root-finder stops early)",
        "1e-3 relative",
        kind="relative",
    )


@pytest.mark.parametrize("seed", SEEDS)
def test_sample_size_round_trips_and_matches_statsmodels(seed, recorder):
    rng = np.random.default_rng(500 + seed)
    base = float(rng.uniform(0.02, 0.5))
    mde = float(base * rng.uniform(0.02, 0.3))
    n = abkit.sample_size_two_proportions(base, mde)
    assert abkit.mde_two_proportions(base, n) <= mde < abkit.mde_two_proportions(base, n - 1)
    # Smallest n at which statsmodels' power curve reaches 0.8 (searched exactly, not via solve_power).
    d = mde / np.sqrt(base * (1 - base))
    sm = NormalIndPower()
    n_ref = n
    while sm.power(d, n_ref - 1, 0.05, ratio=1.0) >= 0.8:
        n_ref -= 1
    assert sm.power(d, n_ref, 0.05, ratio=1.0) >= 0.8
    # statsmodels also counts the far tail, so its n can be slightly smaller at very large n (2 of 817,099).
    assert abs(n - n_ref) <= max(1, 1e-5 * n)
    recorder.diff("sample_size_two_proportions", abs(n - n_ref) / n)
    recorder.dataset(
        "sample_size_two_proportions",
        "round trip through mde_two_proportions; smallest n where statsmodels NormalIndPower power >= 0.8",
        "round trip exact (1 unit); vs statsmodels within max(1 unit, 1e-5 relative)",
        kind="relative (n vs statsmodels n)",
    )
