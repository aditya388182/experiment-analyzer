"""Recompute the lab's Hillstrom numbers from the CSV with abkit.analyze and compare them to the lab's results.json.

Expected values are READ from backend/reports/data/exp_results.json (a copy of the lab file); none are typed here.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest
from conftest import RECORDER, REPO_ROOT

import abkit

CSV = REPO_ROOT / "backend" / "samples" / "hillstrom.csv"
SOURCE = REPO_ROOT / "backend" / "samples" / "SOURCE.md"
LAB = REPO_ROOT / "backend" / "reports" / "data" / "exp_results.json"
TOL = 1e-9


def _load(path: Path) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    seg = np.array([r["segment"] for r in rows])
    cols = {c: np.array([float(r[c]) for r in rows]) for c in ("visit", "conversion", "spend", "history")}
    return seg, cols


@pytest.fixture(scope="module")
def data():
    want = re.search(r"sha256:\s*([0-9a-f]{64})", SOURCE.read_text()).group(1)
    assert hashlib.sha256(CSV.read_bytes()).hexdigest() == want, "hillstrom.csv does not match SOURCE.md"
    return _load(CSV)


@pytest.fixture(scope="module")
def lab():
    return json.loads(LAB.read_text())


def _run(data, metric, metric_type):
    seg, cols = data
    labels = sorted(set(seg))
    arms = {s: cols[metric][seg == s] for s in labels}
    pre = {s: cols["history"][seg == s] for s in labels}
    return abkit.analyze(arms, "No E-Mail", metric_type, pre_period=pre, metric_name=metric, pre_period_name="history")


def test_mens_visit_matches_lab(data, lab):
    r = _run(data, "visit", "binary")
    mens = next(c for c in r["comparisons"] if c["treatment"] == "Mens E-Mail")
    womens = next(c for c in r["comparisons"] if c["treatment"] == "Womens E-Mail")
    cup = next(c for c in r["cuped"]["by_comparison"] if c["treatment"] == "Mens E-Mail")
    checks = {
        "mens_visit.diff": (mens["diff"], lab["effects"]["mens_visit"]["diff"]),
        "mens_visit.ci_low": (mens["ci_low"], lab["effects"]["mens_visit"]["ci_low"]),
        "mens_visit.ci_high": (mens["ci_high"], lab["effects"]["mens_visit"]["ci_high"]),
        "mens_visit.p": (mens["p"], lab["effects"]["mens_visit"]["p"]),
        "mens_visit.rel_lift": (mens["rel_lift"], lab["effects"]["mens_visit"]["rel_lift"]),
        "womens_visit.diff": (womens["diff"], lab["effects"]["womens_visit"]["diff"]),
        "womens_visit.ci_low": (womens["ci_low"], lab["effects"]["womens_visit"]["ci_low"]),
        "womens_visit.ci_high": (womens["ci_high"], lab["effects"]["womens_visit"]["ci_high"]),
        "srm_p": (r["srm"]["p"], lab["validity"]["srm_p"]),
        "mde_visit_abs": (r["power"]["mde_abs"], lab["power"]["mde_visit_abs"]),
        "mens_visit.cuped_corr": (cup["corr"], lab["variance_reduction"]["mens_visit"]["corr_with_prior_year_spend"]),
        "mens_visit.cuped_variance_removed": (
            cup["variance_removed"],
            lab["variance_reduction"]["mens_visit"]["cuped_variance_removed"],
        ),
    }
    for name, (got, want) in checks.items():
        assert abs(got - want) <= TOL, f"{name}: app {got!r} vs lab {want!r}"
    assert sorted(a["n"] for a in r["arms"]) == sorted(lab["validity"]["arm_counts"])
    assert r["power"]["n_per_arm"] == lab["power"]["n_per_arm"]
    assert r["rows"] == {"read": 64000, "used": 64000, "dropped": {k: 0 for k in abkit.DROP_REASONS}}
    assert r["cuped"]["helpful"] is False

    RECORDER.lab_reproduction = {
        "dataset": "backend/samples/hillstrom.csv",
        "dataset_sha256": hashlib.sha256(CSV.read_bytes()).hexdigest(),
        "lab_file": "backend/reports/data/exp_results.json",
        "abkit_version": abkit.__version__,
        "mapping": {
            "variant_col": "segment",
            "control_label": "No E-Mail",
            "metric_col": "visit",
            "metric_type": "binary",
            "pre_period_col": "history",
            "alpha": 0.05,
        },
        "tolerance": TOL,
        "comparisons": {
            name: {"app": got, "lab": want, "abs_diff": abs(got - want)} for name, (got, want) in checks.items()
        },
        "max_abs_diff": max(abs(g - w) for g, w in checks.values()),
        "arm_counts": {a["label"]: a["n"] for a in r["arms"]},
        "headline": {
            "mens_visit_diff_pts": round(mens["diff"] * 100, 2),
            "mens_visit_ci_pts": [round(mens["ci_low"] * 100, 2), round(mens["ci_high"] * 100, 2)],
            "srm_p": round(r["srm"]["p"], 4),
        },
        "verdict": r["verdict"],
        "cuped_message": r["cuped"]["message"],
    }


@pytest.mark.parametrize(
    ("metric", "metric_type", "key_m", "key_w"),
    [
        ("conversion", "binary", "mens_conversion", "womens_conversion"),
        ("spend", "continuous", "mens_spend", "womens_spend"),
    ],
)
def test_other_metrics_match_lab(data, lab, metric, metric_type, key_m, key_w):
    r = _run(data, metric, metric_type)
    by = {c["treatment"]: c for c in r["comparisons"]}
    for label, key in (("Mens E-Mail", key_m), ("Womens E-Mail", key_w)):
        for f in ("diff", "ci_low", "ci_high", "p"):
            assert abs(by[label][f] - lab["effects"][key][f]) <= TOL, (key, f)
