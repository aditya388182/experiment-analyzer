"""Metadata stamped on every results/*.json file: commit, UTC date, command. Used by the test suites."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def meta(command: str) -> dict[str, Any]:
    """``commit`` is HEAD; ``dirty`` says whether tracked files differed from it when the numbers were produced."""
    dirty_files = [
        line[3:] for line in _git("status", "--porcelain", "--untracked-files=no").splitlines() if line.strip()
    ]
    return {
        "commit": os.environ.get("GIT_SHA_OVERRIDE") or _git("rev-parse", "HEAD") or "unknown",
        "dirty": bool(dirty_files),
        "generated_at_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": command,
    }


def write(name: str, command: str, payload: dict[str, Any]) -> Path:
    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / name
    path.write_text(json.dumps({**meta(command), **payload}, indent=2, sort_keys=False) + "\n")
    return path
