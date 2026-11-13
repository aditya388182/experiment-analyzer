"""Power: minimum detectable effect and sample size, normal approximation, two-sided test, equal arms."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def _z(alpha: float, power: float) -> float:
    return float(stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power))


def mde_two_proportions(base_rate: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest absolute lift detectable with the given power (normal approximation). Lab formula."""
    z = stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)
    return float(z * np.sqrt(2 * base_rate * (1 - base_rate) / n_per_arm))


def sample_size_two_proportions(base_rate: float, mde_abs: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Arms size needed to detect an absolute lift of ``mde_abs``: the inverse of ``mde_two_proportions``,
    rounded up, so ``mde_two_proportions(base, n) <= mde_abs < mde_two_proportions(base, n - 1)``."""
    if not 0 < base_rate < 1:
        raise ValueError("base_rate must be in (0, 1)")
    if mde_abs <= 0:
        raise ValueError("mde_abs must be positive")
    z = _z(alpha, power)
    n = math.ceil(2 * base_rate * (1 - base_rate) * (z / mde_abs) ** 2)
    # ceil of a float can land one unit off; settle it against the forward function.
    while n > 1 and mde_two_proportions(base_rate, n - 1, alpha, power) <= mde_abs:
        n -= 1
    while mde_two_proportions(base_rate, n, alpha, power) > mde_abs:
        n += 1
    return n


def mde_two_means(sd: float, n_per_arm: int, alpha: float = 0.05, power: float = 0.8) -> float:
    """MDE for a continuous metric with a common standard deviation ``sd`` (same normal approximation)."""
    return float(_z(alpha, power) * math.sqrt(2 * sd**2 / n_per_arm))
