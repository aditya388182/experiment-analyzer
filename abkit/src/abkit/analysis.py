"""``analyze``: turn per-arm arrays into the result JSON the app stores (SPEC.md section 7)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import numpy as np

from . import config
from .power import mde_two_means, mde_two_proportions
from .stats import cuped, cuped_theta, diff_in_means, holm, srm_test
from .verdict import verdict

MetricType = Literal["binary", "continuous"]
DROP_REASONS = ("null_variant", "non_numeric_metric", "non_binary_value", "null_pre_period")


class AnalysisError(Exception):
    """A data problem the user must fix. Never retried. ``code`` is shown in the UI."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _clean(
    arms: Mapping[str, Any],
    metric_type: MetricType,
    pre_period: Mapping[str, Any] | None,
    dropped: dict[str, int],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray] | None]:
    ys: dict[str, np.ndarray] = {}
    xs: dict[str, np.ndarray] | None = {} if pre_period is not None else None
    for label, raw in arms.items():
        y = np.asarray(raw, dtype=np.float64)
        keep = ~np.isnan(y)
        dropped["non_numeric_metric"] += int((~keep).sum())
        if metric_type == "binary":
            bad = keep & (y != 0) & (y != 1)
            dropped["non_binary_value"] += int(bad.sum())
            keep &= ~bad
        if pre_period is not None and xs is not None:
            if label not in pre_period:
                raise ValueError(f"pre_period has no array for arm {label!r}")
            x = np.asarray(pre_period[label], dtype=np.float64)
            if x.shape != y.shape:
                raise ValueError(f"pre_period array for arm {label!r} has a different length")
            bad = keep & np.isnan(x)
            dropped["null_pre_period"] += int(bad.sum())
            keep &= ~bad
            xs[label] = x[keep]
        ys[label] = y[keep]
    return ys, xs


def _validate(ys: Mapping[str, np.ndarray], control: str) -> None:
    labels = list(ys)
    if len(labels) < 2:
        raise AnalysisError(
            "SINGLE_ARM",
            f"Found {len(labels)} arm(s) in the variant column; an experiment needs at least 2.",
        )
    if control not in ys:
        shown = ", ".join(repr(x) for x in sorted(labels)[:10])
        raise AnalysisError(
            "CONTROL_NOT_FOUND", f"Control label {control!r} is not in the variant column. Found: {shown}."
        )
    if len(labels) > config.MAX_ARMS:
        raise AnalysisError(
            "TOO_MANY_ARMS",
            f"Found {len(labels)} arms; the maximum is {config.MAX_ARMS}. Is this the right column?",
        )
    small = [label for label in labels if len(ys[label]) < config.MIN_ARM_N]
    if small:
        raise AnalysisError(
            "ARM_TOO_SMALL",
            f"Arm(s) {', '.join(repr(s) for s in small)} have fewer than {config.MIN_ARM_N} usable rows.",
        )
    if all(float(np.var(ys[label])) == 0.0 for label in labels):
        raise AnalysisError(
            "CONSTANT_METRIC",
            "The metric has the same value in every row of every arm, so there is nothing to compare.",
        )


def _compare(t: np.ndarray, c: np.ndarray, alpha: float) -> dict[str, Any]:
    """Welch comparison, with the degenerate zero-variance case handled instead of dividing by zero."""
    if float(np.var(t)) == 0.0 and float(np.var(c)) == 0.0:
        d = float(t.mean() - c.mean())
        mc = float(c.mean())
        return {
            "treat": float(t.mean()),
            "ctrl": mc,
            "diff": d,
            "ci_low": d,
            "ci_high": d,
            "rel_lift": d / mc if mc != 0 else None,
            "se": 0.0,
            "p": 1.0 if d == 0 else 0.0,
            "degenerate": True,
        }
    with np.errstate(divide="ignore", invalid="ignore"):  # rel_lift when the control mean is 0
        r = dict(diff_in_means(t, c, alpha))
    if float(c.mean()) == 0.0:
        r["rel_lift"] = None
    r["degenerate"] = False
    return r


def _comparisons(order: list[str], ys: Mapping[str, np.ndarray], control: str, alpha: float) -> list[dict[str, Any]]:
    raw = [(label, _compare(ys[label], ys[control], alpha)) for label in order if label != control]
    p_holm = holm([r["p"] for _, r in raw])
    out = []
    for (label, r), ph in zip(raw, p_holm, strict=True):
        out.append(
            {
                "treatment": label,
                "treat_mean": r["treat"],
                "ctrl_mean": r["ctrl"],
                "diff": r["diff"],
                "ci_low": r["ci_low"],
                "ci_high": r["ci_high"],
                "se": r["se"],
                "rel_lift": r["rel_lift"],
                "p": r["p"],
                "p_holm": ph,
                "significant": ph < alpha,
                "degenerate": r["degenerate"],
            }
        )
    return out


def _fmt_corr(x: float) -> str:
    return f"{x:.2f}"


def _cuped(
    order: list[str],
    ys: Mapping[str, np.ndarray],
    xs: Mapping[str, np.ndarray] | None,
    control: str,
    alpha: float,
    pre_period_name: str | None,
) -> dict[str, Any]:
    if xs is None:
        return {
            "requested": False,
            "pre_period_col": None,
            "theta": None,
            "corr": None,
            "variance_removed": None,
            "helpful": False,
            "adjusted": None,
            "by_comparison": [],
            "message": "No pre-period column was mapped, so CUPED was not run.",
        }
    y = np.concatenate([ys[label] for label in order])
    x = np.concatenate([xs[label] for label in order])
    base = {"requested": True, "pre_period_col": pre_period_name, "adjusted": None, "helpful": False}
    if float(np.var(x)) == 0.0 or float(np.var(y)) == 0.0:
        return {
            **base,
            "theta": None,
            "corr": None,
            "variance_removed": None,
            "by_comparison": [],
            "message": "CUPED not helpful here (the pre-period column or the metric is constant).",
        }
    theta = cuped_theta(y, x)
    x_mean = float(x.mean())
    y_adj = y - theta * (x - x_mean)
    variance_removed = float(1 - y_adj.var(ddof=1) / y.var(ddof=1))
    corr = float(np.corrcoef(y, x)[0, 1])
    helpful = abs(corr) >= config.CUPED_MIN_ABS_CORR and variance_removed >= config.CUPED_MIN_VARIANCE_REMOVED
    summary = f"correlation {_fmt_corr(corr)}, variance removed {variance_removed * 100:.1f}%"
    # The lab measured CUPED per treatment-vs-control pair; report that view too (informational).
    by_comparison = []
    for label in order:
        if label == control:
            continue
        yp = np.concatenate([ys[label], ys[control]])
        xp = np.concatenate([xs[label], xs[control]])
        if float(np.var(xp)) == 0.0 or float(np.var(yp)) == 0.0:
            by_comparison.append({"treatment": label, "corr": None, "variance_removed": None})
            continue
        _, vr = cuped(yp, xp)
        by_comparison.append({"treatment": label, "corr": float(np.corrcoef(yp, xp)[0, 1]), "variance_removed": vr})
    out = {
        **base,
        "theta": theta,
        "corr": corr,
        "variance_removed": variance_removed,
        "helpful": helpful,
        "by_comparison": by_comparison,
    }
    if not helpful:
        out["message"] = f"CUPED not helpful here ({summary})"
        return out
    adj = {label: ys[label] - theta * (xs[label] - x_mean) for label in order}
    out["adjusted"] = _comparisons(order, adj, control, alpha)
    out["message"] = f"CUPED helpful ({summary}); adjusted intervals are shown."
    return out


def analyze(
    arms: Mapping[str, Any],
    control: str,
    metric_type: MetricType,
    pre_period: Mapping[str, Any] | None = None,
    planned_split: Sequence[float] | None = None,
    alpha: float = 0.05,
    power: float = config.DEFAULT_POWER,
    *,
    metric_name: str = "metric",
    pre_period_name: str | None = None,
    rows_read: int | None = None,
    dropped: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Analyze an experiment.

    ``arms`` maps each variant label to its metric values. ``pre_period`` (optional) maps each label to the
    pre-period covariate, aligned row by row. ``planned_split`` lists expected shares with the control first and
    the other arms in ascending label order (the order arms appear in the result). ``dropped`` carries row
    counts already dropped upstream (by the CSV reader); rows dropped here are added to it.
    """
    if metric_type not in ("binary", "continuous"):
        raise ValueError("metric_type must be 'binary' or 'continuous'")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    drops = {k: 0 for k in DROP_REASONS}
    for k, v in (dropped or {}).items():
        drops[k] = drops.get(k, 0) + int(v)

    ys, xs = _clean(arms, metric_type, pre_period, drops)
    _validate(ys, control)
    order = [control] + sorted(label for label in ys if label != control)

    counts = [len(ys[label]) for label in order]
    if planned_split is None:
        expected = [1 / len(order)] * len(order)
    else:
        expected = [float(s) for s in planned_split]
        if len(expected) != len(order):
            raise AnalysisError(
                "PLANNED_SPLIT_MISMATCH",
                f"planned_split has {len(expected)} values but the data has {len(order)} arms "
                f"(order: {', '.join(order)}).",
            )
        if any(s <= 0 for s in expected) or not math.isclose(sum(expected), 1.0, abs_tol=1e-6):
            raise AnalysisError("BAD_PLANNED_SPLIT", "planned_split values must be positive and sum to 1.")
    srm_p = srm_test(counts, expected)
    srm = {
        "p": srm_p,
        "flagged": srm_p < config.SRM_THRESHOLD,
        "planned_split": expected,
        "observed_split": [c / sum(counts) for c in counts],
        "threshold": config.SRM_THRESHOLD,
    }

    arms_out = [
        {
            "label": label,
            "n": len(ys[label]),
            "mean": float(ys[label].mean()),
            "sd": float(ys[label].std(ddof=1)),
            "is_control": label == control,
        }
        for label in order
    ]

    comparisons = _comparisons(order, ys, control, alpha)

    ctrl = ys[control]
    n_min = min(counts)
    base_rate = float(ctrl.mean()) if metric_type == "binary" else None
    ctrl_sd = float(ctrl.std(ddof=1))
    if metric_type == "binary":
        assert base_rate is not None
        mde = mde_two_proportions(base_rate, n_min, alpha, power) if 0 < base_rate < 1 else None
    else:
        mde = mde_two_means(ctrl_sd, n_min, alpha, power) if ctrl_sd > 0 else None
    power_out = {
        "base_rate": base_rate,
        "sd": ctrl_sd,
        "n_per_arm": n_min,
        "alpha": alpha,
        "power": power,
        "mde_abs": mde,
    }

    cuped_out = _cuped(order, ys, xs, control, alpha, pre_period_name)

    warnings: list[str] = []
    for a in arms_out:
        if a["n"] < config.SMALL_ARM_WARNING_N:
            warnings.append(
                f"Arm {a['label']!r} has only {a['n']} rows (under {config.SMALL_ARM_WARNING_N}); "
                "the normal approximation behind the interval may be poor."
            )
    for c in comparisons:
        if c["degenerate"]:
            warnings.append(
                f"{c['treatment']!r} and the control both have zero variance; the interval and p-value are degenerate."
            )
    total_dropped = sum(drops.values())
    used = sum(counts)
    if total_dropped:
        detail = ", ".join(f"{k} {v}" for k, v in drops.items() if v)
        warnings.append(f"{total_dropped} row(s) were dropped ({detail}).")
    if srm["flagged"]:
        warnings.append("Sample ratio mismatch: arm sizes do not match the planned split.")

    result: dict[str, Any] = {
        "metric_col": metric_name,
        "metric_type": metric_type,
        "control_label": control,
        "alpha": alpha,
        "arms": arms_out,
        "rows": {
            "read": rows_read if rows_read is not None else used + total_dropped,
            "used": used,
            "dropped": drops,
        },
        "srm": srm,
        "comparisons": comparisons,
        "power": power_out,
        "cuped": cuped_out,
        "warnings": warnings,
    }
    result["verdict"] = verdict(result)
    return result
