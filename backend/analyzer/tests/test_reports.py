"""SPEC section 9: every number the reports API returns equals the value at its key in the lab JSON."""

from __future__ import annotations

import json
import numbers
from pathlib import Path

from django.conf import settings

from analyzer.reports import get_path


def _numbers(obj, prefix=""):
    """Yield (path, value) for every number in the response, skipping the `sources` maps."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k != "sources":
                yield from _numbers(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _numbers(v, f"{prefix}.{i}")
    elif isinstance(obj, numbers.Number) and not isinstance(obj, bool):
        yield prefix, obj


def _source_value(spec: str):
    fname, path = spec.split(":", 1)
    return get_path(json.loads((Path(settings.REPORTS_DATA_DIR) / fname).read_text()), path)


def test_every_number_equals_its_source(api):
    body = api.get("/api/reports").json()
    checked = 0
    for card in ("churn", "forecasting"):
        data, sources = body[card], body[card]["sources"]
        for path, value in _numbers(data):
            # list items such as test_auc_ci.0 are covered by their parent key's source
            key = path if path in sources else path.rsplit(".", 1)[0]
            src = _source_value(sources[key])
            if isinstance(src, list):
                src = src[int(path.rsplit(".", 1)[1])]
            assert value == src, (card, path, value, src)
            checked += 1
    assert checked >= 40


def test_reports_content(api):
    body = api.get("/api/reports").json()
    churn, fc = body["churn"], body["forecasting"]
    assert churn["selected_model"] == "gradient_boosting" and churn["baseline_model"] == "recency_rule"
    assert churn["test_auc"] > churn["baseline_auc"]
    assert churn["calibration"]["recalibration_helped"] is False
    assert churn["known_limits"][0].startswith("Recalibration failed")
    assert fc["winner"] == min(fc["methods"], key=lambda m: m["mase"])["method"]
    assert sum(m["winner"] for m in fc["methods"]) == 1
    assert body["source"] == {"repo": "applied-data-science-lab", "commit": "lab build of 2026-11-05 (lab_inputs/)"}
