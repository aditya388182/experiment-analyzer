"""Check that a real S3 bucket enforces the presigned POST policy (BLOCKERS.md B1; moto does not).

Run with credentials that may PutObject on uploads/*:
    cd backend && S3_BUCKET=<bucket> AWS_REGION=<region> uv run python ../scripts/s3_policy_check.py
Posts three objects with the same policy the API uses (content-length-range 1..50 MB, exact key):
  1. 1 KB               -> expect 204
  2. 50 MB + 1 byte     -> expect 400 EntityTooLarge
  3. 1 KB, different key -> expect 403 (policy key mismatch)
Writes results/s3_policy_check.json. Leaves only the 1 KB object in uploads/ (the 7-day lifecycle rule removes it).
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import boto3
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import results_meta  # noqa: E402

MAX = 52_428_800


def post(bucket: str, key: str, body: bytes, override_key: str | None = None) -> tuple[int, str]:
    s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    p = s3.generate_presigned_post(bucket, key, Conditions=[["content-length-range", 1, MAX]], ExpiresIn=300)
    fields = dict(p["fields"])
    if override_key:
        fields["key"] = override_key
    r = requests.post(p["url"], data=fields, files={"file": ("x.csv", body)}, timeout=300)
    code = ""
    if "<Code>" in r.text:
        code = r.text.split("<Code>", 1)[1].split("</Code>", 1)[0]
    return r.status_code, code


def main() -> int:
    bucket = os.environ["S3_BUCKET"]
    run = uuid.uuid4().hex[:8]
    small = post(bucket, f"uploads/policy-check-{run}.csv", b"a,b\n" + b"1,2\n" * 256)
    big = post(bucket, f"uploads/policy-check-{run}-big.csv", b"x" * (MAX + 1))
    wrong = post(bucket, f"uploads/policy-check-{run}-k.csv", b"a,b\n1,2\n", override_key=f"uploads/other-{run}.csv")
    checks = {
        "small_upload": {"status": small[0], "code": small[1], "expected": 204, "ok": small[0] == 204},
        "oversize_upload": {"status": big[0], "code": big[1], "expected": "400 EntityTooLarge",
                            "ok": big[0] == 400 and big[1] == "EntityTooLarge"},
        "wrong_key": {"status": wrong[0], "code": wrong[1], "expected": 403, "ok": wrong[0] == 403},
    }
    ok = all(c["ok"] for c in checks.values())
    results_meta.write("s3_policy_check.json", "scripts/s3_policy_check.py", {"bucket": bucket, "ok": ok,
                                                                               "checks": checks})
    for name, c in checks.items():
        print(f"{name}: HTTP {c['status']} {c['code']} (expected {c['expected']}) -> {'OK' if c['ok'] else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
