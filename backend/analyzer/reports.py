"""Model Reports (SPEC.md section 9): numbers read from the lab JSON files, never typed here.

Each card also returns ``sources``: for every number shown, the file and key path it came from, so the
test (and a curious reader) can check value == source JSON at that key.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from django.conf import settings

REPORTS_SOURCE_REPO = "applied-data-science-lab"
REPORTS_SOURCE_COMMIT = "lab build of 2026-11-05 (lab_inputs/)"

FILES = {
    "churn": "churn_results.json",
    "recalibration": "churn_recalibration.json",
    "forecast": "forecast_results.json",
}


@cache
def _load(name: str) -> dict[str, Any]:
    path = Path(settings.REPORTS_DATA_DIR) / FILES[name]
    return json.loads(path.read_text())


def get_path(doc: dict[str, Any], path: str) -> Any:
    cur: Any = doc
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


class _Card:
    """Collects values together with their source key paths."""

    def __init__(self, file_key: str) -> None:
        self.file_key = file_key
        self.doc = _load(file_key)
        self.sources: dict[str, str] = {}

    def val(self, out_key: str, path: str, file_key: str | None = None) -> Any:
        fk = file_key or self.file_key
        self.sources[out_key] = f"{FILES[fk]}:{path}"
        return get_path(_load(fk), path)


def churn_card() -> dict[str, Any]:
    c = _Card("churn")
    doc = c.doc
    selected = doc["selected_model"]
    baseline = "recency_rule"
    models = []
    for i, name in enumerate(doc["test_by_model"]):
        models.append(
            {
                "model": name,
                "roc_auc": c.val(f"test_by_model.{i}.roc_auc", f"test_by_model.{name}.roc_auc"),
                "pr_auc": c.val(f"test_by_model.{i}.pr_auc", f"test_by_model.{name}.pr_auc"),
                "selected": name == selected,
                "baseline": name == baseline,
            }
        )
    variants = []
    for i, name in enumerate(_load("recalibration")["variants"]):
        variants.append(
            {
                "variant": name,
                "calibration_error": c.val(
                    f"calibration.variants.{i}.calibration_error", f"variants.{name}.calibration_error", "recalibration"
                ),
                "mean_gap_points": c.val(
                    f"calibration.variants.{i}.mean_gap_points", f"variants.{name}.mean_gap_points", "recalibration"
                ),
            }
        )
    best_recal = min(variants, key=lambda v: v["calibration_error"])
    out = {
        "selected_model": selected,
        "baseline_model": baseline,
        "test_auc": c.val("test_auc", "test_selected.roc_auc"),
        "test_auc_ci": c.val("test_auc_ci", "test_selected.roc_auc_ci"),
        "baseline_auc": c.val("baseline_auc", f"test_by_model.{baseline}.roc_auc"),
        "auc_gain_ci": c.val("auc_gain_ci", "auc_gain_over_recency_ci"),
        "shuffled_score_auc": c.val("shuffled_score_auc", "shuffled_score_auc"),
        "test_by_model": models,
        "targeting": {
            "top20_by_risk_x_value": c.val("targeting.top20_by_risk_x_value", "revenue_at_risk.top20_by_risk_x_value"),
            "top20_by_value_only": c.val("targeting.top20_by_value_only", "revenue_at_risk.top20_by_value_only"),
            "top20_by_risk_only": c.val("targeting.top20_by_risk_only", "revenue_at_risk.top20_by_risk_only"),
            "lapsed_customers": c.val("targeting.lapsed_customers", "revenue_at_risk.lapsed_customers"),
            "share_of_revenue_lapsed": c.val(
                "targeting.share_of_revenue_lapsed", "revenue_at_risk.share_of_all_last_year_revenue"
            ),
        },
        "calibration": {
            "uncalibrated_error": c.val("calibration.uncalibrated_error", "test_selected.calibration_error"),
            "test_churn_rate": c.val("calibration.test_churn_rate", "test_churn_rate", "recalibration"),
            "recent_train_churn_rate": c.val(
                "calibration.recent_train_churn_rate", "recent_train_churn_rate", "recalibration"
            ),
            "variants": variants,
            "recalibration_helped": best_recal["variant"] != "uncalibrated",
        },
    }
    out["known_limits"] = [
        "Recalibration failed: every recalibrated variant had a larger calibration error than the uncalibrated "
        "model, because the test period's churn rate differs from both the same-season and the recent training "
        "periods. Use the scores for ranking, not as probabilities."
        if not out["calibration"]["recalibration_helped"]
        else f"Recalibration helped: {best_recal['variant']} had the lowest calibration error.",
        "One retailer (UCI Online Retail II), one time split; AUC is for ranking customers, not for forecasting "
        "how many will churn.",
    ]
    out["sources"] = c.sources
    return out


def forecasting_card() -> dict[str, Any]:
    c = _Card("forecast")
    methods = [
        {
            "method": name,
            "mase": c.val(f"methods.{i}.mase", f"models.{name}.mase"),
            "mae": c.val(f"methods.{i}.mae", f"models.{name}.mae"),
            "smape": c.val(f"methods.{i}.smape", f"models.{name}.smape"),
        }
        for i, name in enumerate(c.doc["models"])
    ]
    winner = min(methods, key=lambda m: m["mase"])["method"]
    for m in methods:
        m["winner"] = m["method"] == winner
    lgb = c.doc["lightgbm_vs_best_simple"]
    return {
        "backtests": c.val("backtests", "forecasts"),
        "weeks_total": c.val("weeks_total", "weeks_total"),
        "first_week": c.val("first_week", "first_week"),
        "last_week": c.val("last_week", "last_week"),
        "methods": methods,
        "winner": winner,
        "lightgbm_vs_best_simple": {
            "best_simple": c.val("lightgbm_vs_best_simple.best_simple", "lightgbm_vs_best_simple.best_simple"),
            "mae_difference": c.val("lightgbm_vs_best_simple.mae_difference", "lightgbm_vs_best_simple.mae_difference"),
            "ci": c.val("lightgbm_vs_best_simple.ci", "lightgbm_vs_best_simple.ci"),
            "ci_includes_zero": lgb["ci"][0] <= 0 <= lgb["ci"][1],
        },
        "sources": c.sources,
    }


def reports() -> dict[str, Any]:
    return {
        "churn": churn_card(),
        "forecasting": forecasting_card(),
        "source": {"repo": REPORTS_SOURCE_REPO, "commit": REPORTS_SOURCE_COMMIT},
    }
