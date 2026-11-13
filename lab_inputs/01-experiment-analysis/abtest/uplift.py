"""Uplift modeling: who should get the email? Scored on a holdout with the Qini curve."""
from __future__ import annotations

import numpy as np
from sklearn.base import clone


class TLearner:
    """Two models: one on treated customers, one on control. Uplift = difference of predictions."""

    def __init__(self, base):
        self.base = base

    def fit(self, X, t, y):
        self.m1 = clone(self.base).fit(X[t == 1], y[t == 1])
        self.m0 = clone(self.base).fit(X[t == 0], y[t == 0])
        return self

    def predict(self, X):
        return self.m1.predict_proba(X)[:, 1] - self.m0.predict_proba(X)[:, 1]


class SLearner:
    """One model with treatment as a feature plus treatment-by-feature interactions."""

    def __init__(self, base):
        self.base = base

    @staticmethod
    def _design(X, t):
        return np.column_stack([X, t, X * t[:, None]])

    def fit(self, X, t, y):
        self.m = clone(self.base).fit(self._design(X, t), y)
        return self

    def predict(self, X):
        one, zero = np.ones(len(X)), np.zeros(len(X))
        return (self.m.predict_proba(self._design(X, one))[:, 1]
                - self.m.predict_proba(self._design(X, zero))[:, 1])


def qini_curve(score: np.ndarray, t: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """x = share of customers targeted (highest score first).
    y = incremental responses gained so far, as a share of the total incremental responses
    from emailing everyone. Random targeting is the diagonal y = x."""
    order = np.argsort(-score, kind="stable")
    t, y = t[order], y[order]
    cum_t, cum_c = np.cumsum(t), np.cumsum(1 - t)
    cum_yt, cum_yc = np.cumsum(y * t), np.cumsum(y * (1 - t))
    with np.errstate(divide="ignore", invalid="ignore"):
        gain = cum_yt - np.where(cum_c > 0, cum_yc * cum_t / cum_c, 0.0)
    x = np.arange(1, len(y) + 1) / len(y)
    return np.concatenate([[0.0], x]), np.concatenate([[0.0], gain / gain[-1]])


def qini_coefficient(score, t, y) -> float:
    """Area between the model's Qini curve and the random diagonal. 0 = no better than random."""
    x, g = qini_curve(score, t, y)
    return float(np.trapezoid(g, x) - 0.5)


def capture_at(score, t, y, share: float) -> float:
    """Share of all incremental responses captured by targeting the top `share` of customers."""
    x, g = qini_curve(score, t, y)
    return float(np.interp(share, x, g))


def uplift_by_bucket(score, t, y, buckets: int = 5) -> list[dict]:
    """Observed uplift (treated rate minus control rate) inside each predicted-uplift bucket."""
    order = np.argsort(-score, kind="stable")
    out = []
    for i, idx in enumerate(np.array_split(order, buckets)):
        tt, yy = t[idx], y[idx]
        out.append({"bucket": i + 1, "n": int(len(idx)),
                    "observed_uplift": float(yy[tt == 1].mean() - yy[tt == 0].mean())})
    return out
