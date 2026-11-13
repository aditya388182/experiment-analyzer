"""Edge cases from SPEC section 8: each one either fails with its error code or warns, as specified."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import RECORDER

import abkit
from abkit import AnalysisError

rng = np.random.default_rng(7)


def _binary(n: int, p: float) -> np.ndarray:
    return rng.binomial(1, p, n).astype(float)


def _code(**kwargs) -> str:
    with pytest.raises(AnalysisError) as e:
        abkit.analyze(**kwargs)
    return e.value.code


def test_single_arm():
    RECORDER.edge_cases.append("single_arm -> SINGLE_ARM")
    assert _code(arms={"A": _binary(100, 0.1)}, control="A", metric_type="binary") == "SINGLE_ARM"


def test_control_not_found():
    RECORDER.edge_cases.append("control label missing -> CONTROL_NOT_FOUND")
    arms = {"A": _binary(100, 0.1), "B": _binary(100, 0.1)}
    assert _code(arms=arms, control="Z", metric_type="binary") == "CONTROL_NOT_FOUND"


def test_more_than_ten_arms():
    RECORDER.edge_cases.append("more than 10 arms -> TOO_MANY_ARMS")
    arms = {f"arm{i:02d}": _binary(50, 0.2) for i in range(11)}
    assert _code(arms=arms, control="arm00", metric_type="binary") == "TOO_MANY_ARMS"


def test_ten_arms_is_allowed():
    arms = {f"arm{i:02d}": _binary(200, 0.2) for i in range(10)}
    r = abkit.analyze(arms, "arm00", "binary")
    assert len(r["comparisons"]) == 9


def test_constant_metric_in_every_arm():
    RECORDER.edge_cases.append("constant metric in every arm -> CONSTANT_METRIC")
    arms = {"A": np.zeros(100), "B": np.zeros(80)}
    assert _code(arms=arms, control="A", metric_type="binary") == "CONSTANT_METRIC"


def test_zero_variance_in_one_comparison_is_degenerate_not_a_crash():
    RECORDER.edge_cases.append("zero variance in both arms of one comparison -> degenerate + warning")
    arms = {"A": np.zeros(100), "B": np.zeros(100), "C": _binary(100, 0.3)}
    r = abkit.analyze(arms, "A", "binary")
    by = {c["treatment"]: c for c in r["comparisons"]}
    assert by["B"]["degenerate"] and by["B"]["p"] == 1.0 and by["B"]["rel_lift"] is None
    assert not by["C"]["degenerate"]
    assert any("zero variance" in w for w in r["warnings"])


def test_arm_with_one_row():
    RECORDER.edge_cases.append("arm with n < 2 -> ARM_TOO_SMALL")
    arms = {"A": _binary(100, 0.2), "B": np.array([1.0])}
    assert _code(arms=arms, control="A", metric_type="binary") == "ARM_TOO_SMALL"


def test_small_arm_warns_but_succeeds():
    RECORDER.edge_cases.append("arm with n < 30 -> warning only")
    arms = {"A": np.array([0, 1, 0, 1, 1, 0, 0, 0, 1, 0], float), "B": _binary(500, 0.3)}
    r = abkit.analyze(arms, "A", "binary")
    assert any("only 10 rows" in w for w in r["warnings"])
    assert r["comparisons"][0]["treatment"] == "B"


def test_missing_pre_period_rows_are_dropped_and_counted():
    RECORDER.edge_cases.append("missing pre-period values -> rows dropped and counted (null_pre_period)")
    y_a, y_b = _binary(200, 0.2), _binary(200, 0.3)
    x_a, x_b = rng.normal(size=200), rng.normal(size=200)
    x_a[:7] = np.nan
    x_b[:3] = np.nan
    r = abkit.analyze({"A": y_a, "B": y_b}, "A", "binary", pre_period={"A": x_a, "B": x_b})
    assert r["rows"]["dropped"]["null_pre_period"] == 10
    assert r["rows"]["used"] == 390
    assert r["rows"]["read"] == 400
    assert {a["label"]: a["n"] for a in r["arms"]} == {"A": 193, "B": 197}
    assert r["cuped"]["requested"] is True


def test_non_binary_values_in_binary_metric_are_dropped_and_counted():
    RECORDER.edge_cases.append("non-binary values in a binary metric -> dropped and counted (non_binary_value)")
    y_a = np.concatenate([_binary(100, 0.2), [2.0, 0.5, -1.0]])
    y_b = np.concatenate([_binary(100, 0.3), [np.nan]])
    r = abkit.analyze({"A": y_a, "B": y_b}, "A", "binary", rows_read=210, dropped={"null_variant": 6})
    d = r["rows"]["dropped"]
    assert d["non_binary_value"] == 3 and d["non_numeric_metric"] == 1 and d["null_variant"] == 6
    assert r["rows"]["used"] == 200 and r["rows"]["read"] == 210


def test_planned_split_length_mismatch():
    RECORDER.edge_cases.append("planned_split length differs from arm count -> PLANNED_SPLIT_MISMATCH")
    arms = {"A": _binary(100, 0.2), "B": _binary(100, 0.2)}
    code = _code(arms=arms, control="A", metric_type="binary", planned_split=[0.3, 0.3, 0.4])
    assert code == "PLANNED_SPLIT_MISMATCH"


def test_srm_flag_changes_the_verdict():
    RECORDER.edge_cases.append("SRM p < 0.001 -> verdict starts with the do-not-trust sentence")
    arms = {"A": _binary(10_000, 0.1), "B": _binary(8_000, 0.1)}
    r = abkit.analyze(arms, "A", "binary")
    assert r["srm"]["flagged"]
    assert r["verdict"].startswith("Do not trust this result: the traffic split is off (SRM p = ")


def test_planned_split_used_for_srm():
    arms = {"A": _binary(10_000, 0.1), "B": _binary(8_000, 0.1)}
    r = abkit.analyze(arms, "A", "binary", planned_split=[10 / 18, 8 / 18])
    assert not r["srm"]["flagged"] and r["srm"]["p"] > 0.99


def test_zero_control_mean_gives_null_relative_lift():
    RECORDER.edge_cases.append("control mean 0 -> rel_lift null")
    arms = {"A": np.zeros(100), "B": np.concatenate([np.zeros(90), np.ones(10)])}
    r = abkit.analyze(arms, "A", "binary")
    assert r["comparisons"][0]["rel_lift"] is None


def test_result_is_strict_json():
    import json

    arms = {"A": np.zeros(100), "B": np.zeros(100), "C": _binary(100, 0.3)}
    r = abkit.analyze(arms, "A", "binary")
    json.dumps(r, allow_nan=False)
