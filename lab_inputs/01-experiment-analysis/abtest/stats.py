"""Statistics for a randomized experiment. Every function is small enough to explain line by line."""
from __future__ import annotations

import numpy as np
from scipy import stats


def srm_test(counts: list[int], expected_share: list[float]) -> float:
    """Sample ratio mismatch: chi-square test that arm sizes match the planned split.
    A tiny p-value (convention: below 0.001) means assignment is broken and results cannot be trusted."""
    total = sum(counts)
    expected = [total * s for s in expected_share]
    return float(stats.chisquare(counts, expected).pvalue)


def diff_in_means(treat: np.ndarray, ctrl: np.ndarray, alpha: float = 0.05) -> dict:
    """Difference in means with a Welch (unequal variance) confidence interval and p-value."""
    mt, mc = treat.mean(), ctrl.mean()
    vt, vc = treat.var(ddof=1) / len(treat), ctrl.var(ddof=1) / len(ctrl)
    se = np.sqrt(vt + vc)
    df = (vt + vc) ** 2 / (vt ** 2 / (len(treat) - 1) + vc ** 2 / (len(ctrl) - 1))
    t = (mt - mc) / se
    half = stats.t.ppf(1 - alpha / 2, df) * se
    return {"treat": float(mt), "ctrl": float(mc), "diff": float(mt - mc),
            "ci_low": float(mt - mc - half), "ci_high": float(mt - mc + half),
            "rel_lift": float((mt - mc) / mc), "se": float(se),
            "p": float(2 * stats.t.sf(abs(t), df))}


def bootstrap_diff_ci(treat: np.ndarray, ctrl: np.ndarray, reps: int, rng: np.random.Generator,
                      alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap interval. Used for spend, which is about 99% zeros with a long tail."""
    diffs = np.empty(reps)
    for i in range(reps):
        diffs[i] = rng.choice(treat, len(treat)).mean() - rng.choice(ctrl, len(ctrl)).mean()
    return float(np.quantile(diffs, alpha / 2)), float(np.quantile(diffs, 1 - alpha / 2))


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values (controls the chance of any false positive across tests)."""
    m = len(pvalues)
    order = np.argsort(pvalues)
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvalues[idx])
        adjusted[idx] = min(1.0, running)
    return [float(x) for x in adjusted]


def cuped(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float]:
    """CUPED: subtract the part of y predicted by a pre-experiment covariate x.
    Returns the adjusted outcome and the share of variance removed (equals correlation squared)."""
    theta = np.cov(y, x, ddof=1)[0, 1] / x.var(ddof=1)
    y_adj = y - theta * (x - x.mean())
    return y_adj, float(1 - y_adj.var(ddof=1) / y.var(ddof=1))


def regression_adjusted_effect(y: np.ndarray, t: np.ndarray, X: np.ndarray) -> dict:
    """Lin (2013) estimator: regress y on treatment, centered covariates and their interactions.
    The treatment coefficient is the average effect; HC2 robust standard error."""
    Xc = X - X.mean(axis=0)
    design = np.column_stack([np.ones(len(y)), t, Xc, Xc * t[:, None]])
    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ y
    resid = y - design @ beta
    leverage = np.einsum("ij,jk,ik->i", design, xtx_inv, design)
    meat = design.T @ (design * (resid ** 2 / (1 - leverage))[:, None])
    cov = xtx_inv @ meat @ xtx_inv
    return {"diff": float(beta[1]), "se": float(np.sqrt(cov[1, 1]))}


def mde_two_proportions(base_rate: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest absolute lift detectable with the given power (normal approximation)."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * np.sqrt(2 * base_rate * (1 - base_rate) / n_per_arm))


def aa_false_positive_rate(y: np.ndarray, reps: int, rng: np.random.Generator, alpha: float = 0.05) -> float:
    """A/A test: split one arm in two at random many times. With a valid test about alpha of
    the splits should come out 'significant'. Far more than that means the test is broken."""
    hits = 0
    n = len(y)
    for _ in range(reps):
        mask = rng.permutation(n) < n // 2
        hits += diff_in_means(y[mask], y[~mask], alpha)["p"] < alpha
    return hits / reps
