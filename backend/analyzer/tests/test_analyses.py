"""Phase 3: analysis jobs in Celery eager mode (the real-broker run is in test_integration.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import requests
from botocore.exceptions import EndpointConnectionError
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.conf import settings

from analyzer import storage, tasks
from analyzer.models import Analysis

pytestmark = pytest.mark.django_db

LAB = json.loads((Path(settings.REPORTS_DATA_DIR) / "exp_results.json").read_text())
HILLSTROM = Path(settings.SAMPLES_DIR) / "hillstrom.csv"


@pytest.fixture
def run(django_capture_on_commit_callbacks):
    """Execute on_commit callbacks (the enqueue) so the eager task runs inside the test."""

    def _run(fn, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return fn(*args, **kwargs)

    return _run


def upload_bytes(api, content: bytes, name: str = "data.csv") -> dict:
    body = api.post("/api/uploads", {"filename": name, "size": len(content)}, format="json").json()
    r = requests.post(body["s3"]["url"], data=body["s3"]["fields"], files={"file": (name, content)}, timeout=30)
    assert r.status_code in (200, 201, 204)
    done = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert done.status_code == 200, done.json()
    return {"upload_id": body["upload_id"], **done.json()}


def mapping(**over):
    m = {
        "variant_col": "group",
        "control_label": "A",
        "metric_col": "y",
        "metric_type": "binary",
        "pre_period_col": None,
        "planned_split": None,
        "alpha": 0.05,
    }
    m.update(over)
    return m


def detail(api, analysis_id):
    return api.get(f"/api/analyses/{analysis_id}").json()


def test_sample_reproduces_lab_numbers(api, seeded, run):
    r = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    assert r.status_code == 202 and r.json()["status"] == "QUEUED"
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "SUCCEEDED", d["error"]
    mens = next(c for c in d["result"]["comparisons"] if c["treatment"] == "Mens E-Mail")
    lab = LAB["effects"]["mens_visit"]
    for k in ("diff", "ci_low", "ci_high"):
        assert abs(mens[k] - lab[k]) <= 1e-9
    assert abs(d["result"]["srm"]["p"] - LAB["validity"]["srm_p"]) <= 1e-9
    assert d["input_sha256"] == "27bab8c5d3669f26ec08ebb50a0a78317542f29501156f2e2af6781fab4cd7e2"
    assert d["abkit_version"] == "0.1.0" and d["attempts"] == 1
    assert set(d["timings"]) >= {"queued_ms", "download_ms", "ingest_ms", "stats_ms", "total_ms"}
    assert d["result"]["cuped"]["helpful"] is False


def test_second_sample_post_is_reused_immediately(api, seeded, run):
    first = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json").json()["analysis_id"]
    r = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    assert r.status_code == 200
    assert r.json()["reused_from"] == first
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "SUCCEEDED" and d["reused_from"] == first and d["result"] == detail(api, first)["result"]


def test_same_file_uploaded_again_is_reused_by_hash_in_worker(api, seeded, run):
    first = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json").json()["analysis_id"]
    up = upload_bytes(api, HILLSTROM.read_bytes(), "my_copy.csv")
    m = {
        "variant_col": "segment",
        "control_label": "No E-Mail",
        "metric_col": "visit",
        "metric_type": "binary",
        "pre_period_col": "history",
        "planned_split": None,
        "alpha": 0.05,
    }
    r = run(api.post, "/api/analyses", {"upload_id": up["upload_id"], "mapping": m}, format="json")
    assert r.status_code == 202
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "SUCCEEDED" and d["reused_from"] == first
    assert "ingest_ms" not in d["timings"]  # no work redone


def test_different_mapping_is_not_reused(api, seeded, run):
    run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    r = run(api.post, "/api/analyses/sample/hillstrom", {"metric_col": "spend"}, format="json")
    assert r.status_code == 202
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "SUCCEEDED" and d["reused_from"] is None
    assert d["result"]["metric_type"] == "continuous"


def _csv(rows: list[str], header: str = "group,y") -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode()


@pytest.mark.parametrize(
    ("content", "m", "code"),
    [
        (_csv(["A,1", "A,0", "A,1"]), {}, "SINGLE_ARM"),
        (_csv(["B,1", "B,0", "C,1", "C,0"]), {}, "CONTROL_NOT_FOUND"),
        (_csv([f"g{i},{i % 2}" for i in range(24)]), {"control_label": "g0"}, "TOO_MANY_ARMS"),
        (_csv(["A,1", "A,1", "B,1", "B,1"]), {}, "CONSTANT_METRIC"),
        (_csv(["A,1", "A,0", "B,1"]), {}, "ARM_TOO_SMALL"),
        (_csv(["A,x", "A,y", "B,z", "B,w"]), {}, "NO_USABLE_ROWS"),
        (_csv(["A,1", "A,0", "B,1", "B,0"]), {"planned_split": [0.2, 0.3, 0.5]}, "PLANNED_SPLIT_MISMATCH"),
    ],
)
def test_bad_data_fails_with_code_and_is_not_retried(api, run, content, m, code):
    up = upload_bytes(api, content)
    r = run(api.post, "/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping(**m)}, format="json")
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "FAILED"
    assert d["error"]["code"] == code, d["error"]
    assert d["attempts"] == 1
    assert d["result"] is None


def test_ragged_csv_beyond_preview_fails_with_bad_csv(api, run):
    rows = [f"{'AB'[i % 2]},{i % 2}" for i in range(40)] + ["A,1,extra"]
    up = upload_bytes(api, _csv(rows))
    r = run(api.post, "/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping()}, format="json")
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "FAILED" and d["error"]["code"] == "BAD_CSV" and d["attempts"] == 1


def test_dropped_rows_are_counted(api, run):
    rows = [f"{'AB'[i % 2]},{i % 3 == 0:d}" for i in range(200)] + [",1", "A,abc", "B,7", "A,"]
    up = upload_bytes(api, _csv(rows))
    r = run(api.post, "/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping()}, format="json")
    res = detail(api, r.json()["analysis_id"])["result"]
    assert res["rows"]["read"] == 204 and res["rows"]["used"] == 200
    assert res["rows"]["dropped"] == {
        "null_variant": 1,
        "non_numeric_metric": 2,
        "non_binary_value": 1,
        "null_pre_period": 0,
    }


def _queued_sample() -> Analysis:
    from analyzer.mapping import canonical, mapping_hash
    from analyzer.views import SAMPLE_MAPPINGS

    m = canonical(SAMPLE_MAPPINGS["visit"])
    return Analysis.objects.create(sample_name="hillstrom", mapping=m, mapping_hash=mapping_hash(m))


def test_transient_s3_errors_are_retried_then_succeed(seeded, monkeypatch):
    """Eager mode raises Retry instead of re-queueing, so each redelivery is driven by hand with its retry count
    (the real broker path is covered by test_integration.py)."""
    real = storage.download_with_sha256
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise EndpointConnectionError(endpoint_url="http://s3")
        return real(*a, **k)

    monkeypatch.setattr(storage, "download_with_sha256", flaky)
    a = _queued_sample()
    for retries in (0, 1):
        with pytest.raises(Retry) as e:
            tasks.run_analysis.apply(args=[str(a.pk)], retries=retries, throw=True)
        assert e.value.when == 2 ** (retries + 1)  # exponential backoff: 2 s, 4 s
        assert Analysis.objects.get(pk=a.pk).status == "RUNNING"
    assert tasks.run_analysis.apply(args=[str(a.pk)], retries=2, throw=True).get() == "SUCCEEDED"
    a.refresh_from_db()
    assert a.status == "SUCCEEDED" and a.attempts == 3 and calls["n"] == 3


def test_transient_errors_give_up_after_three_retries(seeded, monkeypatch):
    def down(*a, **k):
        raise EndpointConnectionError(endpoint_url="http://s3")

    monkeypatch.setattr(storage, "download_with_sha256", down)
    a = _queued_sample()
    assert tasks.run_analysis.apply(args=[str(a.pk)], retries=3, throw=True).get() == "FAILED"
    a.refresh_from_db()
    assert a.status == "FAILED" and a.error_code == "STORAGE_UNAVAILABLE"


def test_access_denied_means_missing_and_is_not_retried(seeded, monkeypatch):
    """Without s3:ListBucket (production IAM), S3 returns 403 for a missing key. Not transient: no retry."""
    from botocore.exceptions import ClientError

    def denied(*a, **k):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "GetObject")

    monkeypatch.setattr(storage, "download_with_sha256", denied)
    a = _queued_sample()
    assert tasks.run_analysis.apply(args=[str(a.pk)], throw=True).get() == "FAILED"
    a.refresh_from_db()
    assert a.error_code == "OBJECT_MISSING" and a.attempts == 1


def test_other_client_errors_are_internal_and_not_retried(seeded, monkeypatch):
    from botocore.exceptions import ClientError

    def bad(*a, **k):
        raise ClientError({"Error": {"Code": "InvalidObjectState", "Message": "archived"}}, "GetObject")

    monkeypatch.setattr(storage, "download_with_sha256", bad)
    a = _queued_sample()
    assert tasks.run_analysis.apply(args=[str(a.pk)], throw=True).get() == "FAILED"
    a.refresh_from_db()
    assert a.error_code == "INTERNAL" and a.attempts == 1


def test_soft_time_limit_records_timeout(api, seeded, run, monkeypatch):
    def slow(*a, **k):
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr(tasks, "ingest", slow)
    r = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    d = detail(api, r.json()["analysis_id"])
    assert d["status"] == "FAILED" and d["error"]["code"] == "TIMEOUT" and d["attempts"] == 1


def test_unexpected_error_is_internal_without_traceback(api, seeded, run, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(tasks, "ingest", boom)
    r = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    d = detail(api, r.json()["analysis_id"])
    assert d["error"]["code"] == "INTERNAL" and "secret" not in json.dumps(d)


def test_task_config_is_safe():
    t = tasks.run_analysis
    assert t.acks_late and t.reject_on_worker_lost
    assert t.soft_time_limit == 120 and t.time_limit == 150 and t.max_retries == 3


def test_duplicate_message_for_finished_job_does_nothing(api, seeded, run):
    aid = run(api.post, "/api/analyses/sample/hillstrom", {}, format="json").json()["analysis_id"]
    before = Analysis.objects.get(pk=aid)
    assert tasks.run_analysis.apply(args=[aid]).get() == "SUCCEEDED"
    after = Analysis.objects.get(pk=aid)
    assert after.attempts == before.attempts and after.finished_at == before.finished_at


def test_redelivered_running_job_is_recomputed(api, seeded):
    """A worker died mid-job: the row says RUNNING and the message comes back. The task finishes it."""
    from analyzer.mapping import canonical, mapping_hash
    from analyzer.views import SAMPLE_MAPPINGS

    m = canonical(SAMPLE_MAPPINGS["visit"])
    a = Analysis.objects.create(sample_name="hillstrom", mapping=m, mapping_hash=mapping_hash(m), status="RUNNING")
    assert tasks.run_analysis.apply(args=[str(a.pk)]).get() == "SUCCEEDED"
    assert Analysis.objects.get(pk=a.pk).result["arms"][0]["n"] == 21306


# ------------------------------------------------------------- request validation


def test_mapping_column_not_in_header_is_422(api):
    up = upload_bytes(api, _csv(["A,1", "B,0"]))
    r = api.post("/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping(metric_col="nope")}, format="json")
    assert r.status_code == 422 and "nope" in r.json()["error"]["message"]


@pytest.mark.parametrize(
    "over",
    [
        {"alpha": 0.3},
        {"alpha": 0},
        {"planned_split": [0.5, 0.6]},
        {"planned_split": [1.0]},
        {"metric_type": "count"},
        {"pre_period_col": "y"},
    ],
)
def test_bad_mapping_is_422(api, over):
    up = upload_bytes(api, _csv(["A,1", "B,0"]))
    r = api.post("/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping(**over)}, format="json")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_upload_404_and_incomplete_upload_409(api):
    r = api.post(
        "/api/analyses", {"upload_id": "00000000-0000-0000-0000-000000000000", "mapping": mapping()}, format="json"
    )
    assert r.status_code == 404
    pending = api.post("/api/uploads", {"filename": "a.csv", "size": 10}, format="json").json()["upload_id"]
    r = api.post("/api/analyses", {"upload_id": pending, "mapping": mapping()}, format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "UPLOAD_NOT_COMPLETE"


def test_unknown_sample_and_bad_metric(api):
    assert api.post("/api/analyses/sample/nope", {}, format="json").status_code == 404
    assert api.post("/api/analyses/sample/hillstrom", {"metric_col": "x"}, format="json").status_code == 422


def test_detail_404(api):
    assert api.get("/api/analyses/00000000-0000-0000-0000-000000000000").status_code == 404


def test_list_returns_recent(api, seeded, run):
    run(api.post, "/api/analyses/sample/hillstrom", {}, format="json")
    run(api.post, "/api/analyses/sample/hillstrom", {"metric_col": "conversion"}, format="json")
    rows = api.get("/api/analyses?limit=1").json()["results"]
    assert len(rows) == 1 and rows[0]["metric_col"] == "conversion" and rows[0]["verdict"].startswith("Mens E-Mail")
    assert len(api.get("/api/analyses").json()["results"]) == 2


def test_rate_limit_429(api, seeded, run, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"analysis_create": "2/hour"})
    for _ in range(2):
        assert run(api.post, "/api/analyses/sample/hillstrom", {}, format="json").status_code in (200, 202)
    r = api.post("/api/analyses/sample/hillstrom", {}, format="json")
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED" and "30 per hour" in r.json()["error"]["message"]
    assert api.get("/api/analyses").status_code == 200  # reads are not throttled


def test_constant_after_dropping_non_binary_values_explains_metric_type(api, run):
    rows = [f"{'AB'[i % 2]},{0 if i % 3 else 12.5}" for i in range(60)]
    up = upload_bytes(api, _csv(rows))
    r = run(api.post, "/api/analyses", {"upload_id": up["upload_id"], "mapping": mapping()}, format="json")
    d = detail(api, r.json()["analysis_id"])
    assert d["error"]["code"] == "CONSTANT_METRIC"
    assert "20 rows were dropped because the metric was not 0/1. Is the metric type right" in d["error"]["message"]
