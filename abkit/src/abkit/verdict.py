"""The plain-English verdict. Pure string templates over the result dict, so every sentence is unit-tested."""

from __future__ import annotations

import math
from typing import Any


def fmt_p(p: float) -> str:
    """p-values: 3 decimals down to 0.001, scientific notation below that."""
    if p >= 0.001:
        return f"{p:.3f}"
    return f"{p:.1e}"


def _conf(alpha: float) -> str:
    level = (1 - alpha) * 100
    return f"{level:.0f}%" if math.isclose(level, round(level)) else f"{level:.1f}%"


def _decimals(width: float) -> int:
    """Enough decimals to show a number of this size with about 3 significant figures."""
    if width <= 0 or not math.isfinite(width):
        return 2
    return max(0, min(6, 2 - math.floor(math.log10(width))))


def _metric_label(result: dict[str, Any]) -> str:
    name = str(result.get("metric_col", "metric"))
    if result["metric_type"] == "binary" and not name.lower().endswith("rate"):
        return f"{name} rate"
    return name


def _sentence(c: dict[str, Any], result: dict[str, Any], n_comparisons: int) -> str:
    binary = result["metric_type"] == "binary"
    control = result["control_label"]
    metric = _metric_label(result)
    conf = _conf(result["alpha"])
    t = c["treatment"]
    excludes_zero = c["ci_low"] > 0 or c["ci_high"] < 0
    mde = result["power"]["mde_abs"]

    if binary:

        def num(x: float) -> str:
            return f"{x * 100:.2f}"

        unit = " percentage points"
    else:
        d = _decimals(max(c["ci_high"] - c["ci_low"], abs(c["diff"])))

        def num(x: float) -> str:
            return f"{x:.{d}f}"

        unit = ""

    if excludes_zero:
        direction = "increased" if c["diff"] > 0 else "decreased"
        ci = f"{conf} CI {num(c['ci_low'])} to {num(c['ci_high'])}"
        if binary:
            s = f"{t} {direction} {metric} by {num(abs(c['diff']))}{unit} ({ci}) vs {control}."
        else:
            rel = c.get("rel_lift")
            rel_txt = f"; {rel * 100:+.1f}% relative" if rel is not None else ""
            s = f"{t} {direction} {metric} by {num(abs(c['diff']))} ({ci}{rel_txt}) vs {control}."
        if not c["significant"]:
            s += (
                f" This is not significant after the Holm correction across {n_comparisons} comparisons "
                f"(adjusted p = {fmt_p(c['p_holm'])})."
            )
        return s

    s = (
        f"{t}: no detectable difference in {metric} vs {control} "
        f"({conf} CI {num(c['ci_low'])} to {num(c['ci_high'])}{unit})."
    )
    if mde is not None:
        if binary:
            s += f" This test could detect differences of {num(mde)} percentage points or more."
        else:
            dm = _decimals(mde)
            s += f" This test could detect differences of {mde:.{dm}f} or more."
    return s


def verdict(result: dict[str, Any]) -> str:
    """Build the verdict sentence(s) for a result produced by ``analyze``."""
    parts: list[str] = []
    srm = result["srm"]
    if srm["flagged"]:
        parts.append(f"Do not trust this result: the traffic split is off (SRM p = {fmt_p(srm['p'])}).")
    comps = result["comparisons"]
    parts.extend(_sentence(c, result, len(comps)) for c in comps)
    cuped = result.get("cuped") or {}
    if cuped.get("helpful") and cuped.get("adjusted"):
        adjusted = [_sentence(c, result, len(cuped["adjusted"])) for c in cuped["adjusted"]]
        parts.append(f"With CUPED on {cuped.get('pre_period_col') or 'the pre-period column'}: " + " ".join(adjusted))
    return " ".join(parts)
