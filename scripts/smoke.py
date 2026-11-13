"""Post-deploy smoke test: health, then the Hillstrom sample analysis end to end through the public entry point.

Usage: python3 scripts/smoke.py BASE_URL [--out results/deploy_smoke.json] [--command "..."]
Standard library only, so it runs on a CI runner or the box without installing anything.
Exit code 0 only if health is 200 and the analysis reaches SUCCEEDED with the expected verdict shape.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import results_meta  # noqa: E402


def call(method: str, url: str, body: dict[str, Any] | None = None, timeout: float = 15) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except json.JSONDecodeError:
            return e.code, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--out")
    ap.add_argument("--command", default="python3 scripts/smoke.py")
    ap.add_argument("--metric", default="visit", choices=["visit", "conversion", "spend"])
    args = ap.parse_args()
    base = args.base.rstrip("/")
    codes: dict[str, int] = {}

    try:
        with urllib.request.urlopen(f"{base}/", timeout=15) as r:  # the SPA's index.html (HTML, not JSON)
            codes["GET /"] = r.status
    except urllib.error.HTTPError as e:
        codes["GET /"] = e.code
    codes["GET /api/health"], health = call("GET", f"{base}/api/health")
    t0 = time.monotonic()
    codes["POST /api/analyses/sample/hillstrom"], created = call(
        "POST", f"{base}/api/analyses/sample/hillstrom", {"metric_col": args.metric}
    )
    analysis_id = (created or {}).get("analysis_id")
    detail: dict[str, Any] = {}
    statuses: list[str] = []
    polls = 0
    while analysis_id and time.monotonic() - t0 < 120:
        code, detail = call("GET", f"{base}/api/analyses/{analysis_id}")
        codes["GET /api/analyses/{id}"] = code
        polls += 1
        if not statuses or statuses[-1] != detail.get("status"):
            statuses.append(detail.get("status"))
        if detail.get("status") in ("SUCCEEDED", "FAILED"):
            break
        time.sleep(0.5)
    elapsed = time.monotonic() - t0

    result = detail.get("result") or {}
    ok = (
        codes["GET /api/health"] == 200
        and detail.get("status") == "SUCCEEDED"
        and "percentage points" in (result.get("verdict") or "")
    )
    payload = {
        "base_url": base,
        "ok": ok,
        "health": health,
        "http_status": codes,
        "analysis_id": analysis_id,
        "statuses_seen": statuses,
        "reused_from": detail.get("reused_from"),
        "submit_to_terminal_seconds": round(elapsed, 3),
        "server_timings_ms": detail.get("timings"),
        "verdict": result.get("verdict"),
        "error": detail.get("error"),
        "git_sha": detail.get("git_sha"),
        "abkit_version": detail.get("abkit_version"),
    }
    print(json.dumps(payload, indent=2))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({**results_meta.meta(args.command), **payload}, indent=2) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
