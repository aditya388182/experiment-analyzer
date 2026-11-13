"""Submit a burst of distinct analyses so the worker HPA has CPU to react to (runs INSIDE the cluster).

Each job is a different synthetic CSV (seeded), so no result is reused and every job does real work.
Usage (in a pod that can reach the api Service and the S3 endpoint the presigned URLs point at):
    python hpa_burst.py http://ea-experiment-analyzer-api:8000 --jobs 20 --rows 800000
Prints one JSON line with per-job timings. Standard library + numpy only (both are in the api image).
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
import uuid
from pathlib import Path

import numpy as np


def call(method: str, url: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    # Host: localhost, because Django's ALLOWED_HOSTS lists the public host plus localhost, not the Service name.
    headers = {"Content-Type": "application/json", "Host": "localhost"}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"null")


def multipart(url: str, fields: dict[str, str], path: Path) -> int:
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="b.csv"\r\n'
                 "Content-Type: text/csv\r\n\r\n".encode())
    body = b"".join(parts) + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.status


def make_csv(path: Path, rows: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    arm = rng.integers(0, 3, rows)
    y = rng.binomial(1, 0.10 + 0.01 * arm)
    pre = rng.gamma(2.0, 50.0, rows).round(2)
    labels = np.array(["control", "variant_b", "variant_c"])[arm]
    with path.open("w") as f:
        f.write("group,converted,prior_spend\n")
        for chunk in range(0, rows, 200_000):
            sl = slice(chunk, chunk + 200_000)
            f.write("".join(f"{g},{v},{p}\n" for g, v, p in zip(labels[sl], y[sl], pre[sl], strict=True)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("api")
    ap.add_argument("--jobs", type=int, default=20)
    ap.add_argument("--rows", type=int, default=800_000)
    args = ap.parse_args()
    api = args.api.rstrip("/")
    prep = time.monotonic()
    # Phase 1: make every file and get it into storage. Phase 2: submit all analyses back to back,
    # so the workers see one concentrated burst.
    uploads = []
    for i in range(args.jobs):
        path = Path(f"/tmp/burst-{i}.csv")
        make_csv(path, args.rows, seed=1000 + i)
        up = call("POST", f"{api}/api/uploads", {"filename": path.name, "size": path.stat().st_size})
        multipart(up["s3"]["url"], up["s3"]["fields"], path)
        call("POST", f"{api}/api/uploads/{up['upload_id']}/complete")
        uploads.append(up["upload_id"])
    mapping = {"variant_col": "group", "control_label": "control", "metric_col": "converted",
               "metric_type": "binary", "pre_period_col": "prior_spend", "planned_split": None, "alpha": 0.05}
    ids = [call("POST", f"{api}/api/analyses", {"upload_id": u, "mapping": mapping})["analysis_id"] for u in uploads]
    submitted = time.monotonic()
    done: dict[str, dict] = {}
    while len(done) < len(ids) and time.monotonic() - submitted < 900:
        for aid in ids:
            if aid not in done:
                d = call("GET", f"{api}/api/analyses/{aid}")
                if d["status"] in ("SUCCEEDED", "FAILED"):
                    done[aid] = {"status": d["status"], "timings": d["timings"]}
        time.sleep(2)
    print(json.dumps({
        "jobs": args.jobs, "rows_per_job": args.rows,
        "prepare_and_upload_seconds": round(submitted - prep, 1),
        "all_terminal_seconds_after_submit": round(time.monotonic() - submitted, 1),
        "succeeded": sum(v["status"] == "SUCCEEDED" for v in done.values()),
        "failed": sum(v["status"] == "FAILED" for v in done.values()),
        "job_total_ms": sorted(v["timings"].get("total_ms", 0) for v in done.values()),
    }))


if __name__ == "__main__":
    main()
