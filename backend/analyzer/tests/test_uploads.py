"""Phase 2: upload creation (presigned POST), completion (HEAD + ranged GET preview), health and error format."""

from __future__ import annotations

import base64
import json
import uuid

import pytest
import requests
from django.conf import settings

from analyzer import storage
from analyzer.models import Upload

pytestmark = pytest.mark.django_db

GOOD_CSV = b"user_id,group,converted,revenue\n" + b"".join(
    f"{i},{'A' if i % 2 else 'B'},{i % 3 == 0:d},{i * 1.5}\n".encode() for i in range(50)
)


def _create(api, filename="test.csv", size=None):
    return api.post("/api/uploads", {"filename": filename, "size": size or len(GOOD_CSV)}, format="json")


def _post_to_s3(body: dict, content: bytes, filename: str = "test.csv") -> requests.Response:
    return requests.post(body["s3"]["url"], data=body["s3"]["fields"], files={"file": (filename, content)}, timeout=10)


def test_create_returns_201_with_presigned_post(api):
    r = _create(api)
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"upload_id", "s3", "max_bytes", "expires_in"}
    assert body["max_bytes"] == 52_428_800 and body["expires_in"] == 600
    up = Upload.objects.get(pk=body["upload_id"])
    assert up.status == "PENDING" and up.s3_key == f"uploads/{up.id}.csv"
    assert body["s3"]["fields"]["key"] == up.s3_key


def test_presigned_policy_enforces_size_range_and_exact_key(api):
    body = _create(api).json()
    policy = json.loads(base64.b64decode(body["s3"]["fields"]["policy"]))
    conditions = policy["conditions"]
    assert ["content-length-range", 1, 52_428_800] in conditions
    assert {"key": body["s3"]["fields"]["key"]} in conditions
    assert {"bucket": settings.S3_BUCKET} in conditions


def test_create_rejects_oversize_with_413(api):
    r = _create(api, size=52_428_801)
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert Upload.objects.count() == 0


def test_create_rejects_non_csv_with_415(api):
    r = _create(api, filename="data.xlsx")
    assert r.status_code == 415
    assert r.json() == {"error": {"code": "UNSUPPORTED_FILE_TYPE", "message": "Only .csv files can be analyzed."}}


@pytest.mark.parametrize(
    "payload", [{}, {"filename": "a.csv"}, {"filename": "a.csv", "size": 0}, {"filename": "a.csv", "size": "big"}]
)
def test_create_rejects_bad_payload_with_422(api, payload):
    r = api.post("/api/uploads", payload, format="json")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_full_upload_flow_returns_preview(api):
    body = _create(api).json()
    assert _post_to_s3(body, GOOD_CSV).status_code in (200, 201, 204)
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 200
    out = r.json()
    assert out["columns"] == ["user_id", "group", "converted", "revenue"]
    assert out["size_bytes"] == len(GOOD_CSV)
    assert len(out["preview"]) == 20 and out["preview"][0] == ["0", "B", "1", "0.0"]
    up = Upload.objects.get(pk=body["upload_id"])
    assert up.status == "UPLOADED" and up.columns == out["columns"] and up.size_bytes == len(GOOD_CSV)


def test_complete_unknown_upload_is_404(api):
    r = api.post(f"/api/uploads/{uuid.uuid4()}/complete")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_complete_without_object_is_409(api):
    body = _create(api).json()
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "OBJECT_MISSING"


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        (b"a,b\n\xff\xfe\x00bad,\x80\n", "not UTF-8"),
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00", "UTF-8"),
        (b"onlyonecolumn\n1\n2\n", "at least 2 columns"),
        (b"a,b\n1,2,3\n", "Row 2 has 3 fields"),
        (b"a,b\n", "no data rows"),
        (b"a,a\n1,2\n", "unique"),
    ],
)
def test_complete_with_bad_csv_is_422(api, content, fragment):
    body = _create(api, size=len(content)).json()
    _post_to_s3(body, content)
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "BAD_CSV"
    assert fragment in r.json()["error"]["message"]


def test_complete_rejects_stored_object_over_limit_with_413(api, settings):
    body = _create(api).json()
    settings.UPLOAD_MAX_BYTES = 100  # moto ignores the POST policy (BLOCKERS.md B1), so the API re-checks HEAD size
    storage.client().put_object(Bucket=settings.S3_BUCKET, Key=Upload.objects.get().s3_key, Body=GOOD_CSV)
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_large_file_preview_uses_a_ranged_get(api):
    big = b"variant,metric\n" + b"".join(f"{'AB'[i % 2]},{i % 7}\n".encode() for i in range(80_000))
    assert len(big) > 256 * 1024
    body = _create(api, size=len(big)).json()
    _post_to_s3(body, big)
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 200
    assert r.json()["size_bytes"] == len(big) and len(r.json()["preview"]) == 20


def test_health_ok(api):
    r = api.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": True, "broker": True}


def test_health_503_when_broker_down(api, settings):
    settings.CELERY_BROKER_URL = "amqp://nobody:nothing@127.0.0.1:1//"
    r = api.get("/api/health")
    assert r.status_code == 503
    assert r.json()["broker"] is False and r.json()["db"] is True


def test_unknown_route_is_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_bad_json_body(api):
    r = api.post("/api/uploads", data="{not json", content_type="application/json")
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "BAD_JSON"


def test_cors_preflight_for_dev_origin(client):
    r = client.options("/api/uploads", HTTP_ORIGIN="http://localhost:5173", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert r.status_code == 204
    assert r["Access-Control-Allow-Origin"] == "http://localhost:5173"
    r = client.options("/api/uploads", HTTP_ORIGIN="http://evil.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert "Access-Control-Allow-Origin" not in r


def test_complete_is_409_when_s3_answers_403_for_a_missing_key(api, monkeypatch):
    """Production S3 without s3:ListBucket returns 403 (not 404) for a key that does not exist."""
    from botocore.exceptions import ClientError

    body = _create(api).json()

    def forbidden(**kwargs):
        raise ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject")

    monkeypatch.setattr(storage.client(), "head_object", forbidden)
    r = api.post(f"/api/uploads/{body['upload_id']}/complete")
    assert r.status_code == 409 and r.json()["error"]["code"] == "OBJECT_MISSING"
