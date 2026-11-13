"""Sequential testing with the mixture sequential probability ratio test (mSPRT).

A fixed-horizon test is only valid if you look once, at the planned sample size. Looking
early and stopping when p < 0.05 inflates false positives. The mSPRT gives a p-value that
stays valid no matter how often you look (Johari, Pekelis, Walsh: "Always Valid Inference").
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def msprt_pvalues(diff: np.ndarray, n: np.ndarray, var: float, tau2: float) -> np.ndarray:
    """Always-valid p-values at each look.

    diff : treatment mean minus control mean after n customers per arm
    var  : outcome variance of one observation (for a rate p, var = p * (1 - p))
    tau2 : variance of the normal prior on the true effect (how big an effect we expect)

    Likelihood ratio of "effect ~ N(0, tau2)" against "effect = 0":
        L_n = sqrt(2 var / (2 var + n tau2)) * exp(n^2 tau2 diff^2 / (4 var (2 var + n tau2)))
    The p-value is the running minimum of 1 / L_n, so it can only go down.
    """
    v = 2 * var
    log_l = 0.5 * np.log(v / (v + n * tau2)) + (n ** 2) * tau2 * diff ** 2 / (2 * v * (v + n * tau2))
    return np.minimum.accumulate(np.minimum(1.0, np.exp(-log_l)), axis=-1)


def naive_pvalues(diff: np.ndarray, n: np.ndarray, var: float) -> np.ndarray:
    """Ordinary two-sample z-test p-value at each look (valid only if you look once)."""
    z = diff / np.sqrt(2 * var / n)
    return 2 * stats.norm.sf(np.abs(z))


def simulate(p_ctrl: float, p_treat: float, n_max: int, look_every: int, reps: int,
             rng: np.random.Generator, tau2: float, alpha: float = 0.05) -> dict:
    """Simulate many experiments with a look every `look_every` customers per arm."""
    looks = np.arange(look_every, n_max + 1, look_every)
    # successes between looks are binomial; cumulative sums give the running means
    c = rng.binomial(look_every, p_ctrl, size=(reps, len(looks))).cumsum(axis=1)
    t = rng.binomial(look_every, p_treat, size=(reps, len(looks))).cumsum(axis=1)
    diff = (t - c) / looks
    pooled = (t + c) / (2 * looks)
    var = np.clip(pooled * (1 - pooled), 1e-9, None)          # plug-in variance at each look
    v = 2 * var
    log_l = 0.5 * np.log(v / (v + looks * tau2)) + (looks ** 2) * tau2 * diff ** 2 / (2 * v * (v + looks * tau2))
    p_seq = np.minimum.accumulate(np.minimum(1.0, np.exp(-log_l)), axis=1)
    p_naive = 2 * stats.norm.sf(np.abs(diff / np.sqrt(v / looks)))
    seq_hit = p_seq < alpha
    stopped = seq_hit.any(axis=1)
    stop_n = np.where(stopped, looks[seq_hit.argmax(axis=1)], n_max)
    return {"looks": int(len(looks)),
            "msprt_reject_rate": float(stopped.mean()),
            "naive_peeking_reject_rate": float((p_naive < alpha).any(axis=1).mean()),
            "fixed_horizon_reject_rate": float((p_naive[:, -1] < alpha).mean()),
            "msprt_mean_sample_per_arm": float(stop_n.mean()),
            "msprt_median_sample_per_arm": float(np.median(stop_n)),
            "sample_saving_vs_fixed": float(1 - stop_n.mean() / n_max)}
