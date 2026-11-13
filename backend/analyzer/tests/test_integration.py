"""Integration: real API (gunicorn) -> real RabbitMQ -> real Celery worker -> Postgres, S3 on moto.

Run with `make test-integration`, which starts the API and worker against a fresh database. Talks HTTP only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration

API = os.environ.get("INTEGRATION_API", "http://127.0.0.1:8001")
ROOT = Path(__file__).resolve().parents[2]
LAB = json.loads((ROOT / "reports" / "data" / "exp_results.json").read_text())
HILLSTROM = ROOT / "samples" / "hillstrom.csv"


def poll(analysis_id: str, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        d = requests.get(f"{API}/api/analyses/{analysis_id}", timeout=5).json()
        if not seen or seen[-1] != d["status"]:
            seen.append(d["status"])
        if d["status"] in ("SUCCEEDED", "FAILED"):
            d["_statuses_seen"] = seen
            return d
        time.sleep(0.2)
    raise AssertionError(f"analysis {analysis_id} did not finish; statuses seen {seen}")


def upload(content: bytes, name: str) -> str:
    c = requests.post(f"{API}/api/uploads", json={"filename": name, "size": len(content)}, timeout=5).json()
    r = requests.post(c["s3"]["url"], data=c["s3"]["fields"], files={"file": (name, content)}, timeout=30)
    assert r.status_code == 204
    assert requests.post(f"{API}/api/uploads/{c['upload_id']}/complete", timeout=10).status_code == 200
    return c["upload_id"]


def test_health_sees_db_and_broker():
    assert requests.get(f"{API}/api/health", timeout=5).json() == {"status": "ok", "db": True, "broker": True}


def test_sample_runs_on_worker_and_reproduces_lab():
    t0 = time.monotonic()
    r = requests.post(f"{API}/api/analyses/sample/hillstrom", json={}, timeout=5)
    assert r.status_code == 202, r.text
    d = poll(r.json()["analysis_id"])
    elapsed = time.monotonic() - t0
    assert d["status"] == "SUCCEEDED", d["error"]
    mens = next(c for c in d["result"]["comparisons"] if c["treatment"] == "Mens E-Mail")
    for k in ("diff", "ci_low", "ci_high"):
        assert abs(mens[k] - LAB["effects"]["mens_visit"][k]) <= 1e-9
    assert abs(d["result"]["srm"]["p"] - LAB["validity"]["srm_p"]) <= 1e-9
    assert d["attempts"] == 1 and d["reused_from"] is None
    print(f"\nsample: {d['_statuses_seen']} in {elapsed:.2f}s; timings {d['timings']}")
    print(f"verdict: {d['result']['verdict']}")
    print(f"mens visit diff {mens['diff']!r} CI [{mens['ci_low']!r}, {mens['ci_high']!r}]")
    print(f"SRM p {d['result']['srm']['p']!r}")


def test_second_post_of_same_sample_returns_reused_from():
    r = requests.post(f"{API}/api/analyses/sample/hillstrom", json={}, timeout=5)
    assert r.status_code == 200, r.text
    d = requests.get(f"{API}/api/analyses/{r.json()['analysis_id']}", timeout=5).json()
    assert d["status"] == "SUCCEEDED" and d["reused_from"] == r.json()["reused_from"]
    print(f"\nsecond POST: HTTP 200, reused_from {d['reused_from']}")


def test_same_file_uploaded_is_reused_by_hash_on_worker():
    up = upload(HILLSTROM.read_bytes(), "hillstrom_copy.csv")
    m = {"variant_col": "segment", "control_label": "No E-Mail", "metric_col": "visit", "metric_type": "binary",
         "pre_period_col": "history", "planned_split": None, "alpha": 0.05}
    r = requests.post(f"{API}/api/analyses", json={"upload_id": up, "mapping": m}, timeout=5)
    assert r.status_code == 202
    d = poll(r.json()["analysis_id"])
    assert d["status"] == "SUCCEEDED" and d["reused_from"] is not None and "ingest_ms" not in d["timings"]
    print(f"\nre-uploaded file: worker matched sha256 {d['input_sha256'][:12]}..., reused_from {d['reused_from']}")


def test_bad_data_fails_with_code_and_is_not_retried():
    rows = "group,y\n" + "".join(f"A,{i % 2}\n" for i in range(50))
    up = upload(rows.encode(), "one_arm.csv")
    m = {"variant_col": "group", "control_label": "A", "metric_col": "y", "metric_type": "binary"}
    r = requests.post(f"{API}/api/analyses", json={"upload_id": up, "mapping": m}, timeout=5)
    d = poll(r.json()["analysis_id"])
    assert d["status"] == "FAILED" and d["error"]["code"] == "SINGLE_ARM"
    time.sleep(3)  # a retry would have re-run by now (first backoff is 2 s)
    d2 = requests.get(f"{API}/api/analyses/{d['id']}", timeout=5).json()
    assert d2["attempts"] == 1 and d2["status"] == "FAILED"
    print(f"\nbad data: {d['error']['code']}: {d['error']['message']} (attempts {d2['attempts']})")
