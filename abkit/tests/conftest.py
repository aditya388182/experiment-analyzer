"""Shared fixtures. With ABKIT_WRITE_RESULTS=1 a passing run writes results/validation.json and
results/lab_reproduction.json from the values the tests measured (never typed by hand)."""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import results_meta  # noqa: E402

COMMAND = os.environ.get("ABKIT_RESULTS_COMMAND", "cd abkit && ABKIT_WRITE_RESULTS=1 uv run pytest")


class Recorder:
    def __init__(self) -> None:
        self.max_abs_diff: dict[str, float] = defaultdict(float)
        self.datasets: Counter[str] = Counter()
        self.tolerance: dict[str, str] = {}
        self.reference: dict[str, str] = {}
        self.kind: dict[str, str] = {}
        self.hypothesis_examples: Counter[str] = Counter()
        self.edge_cases: list[str] = []
        self.lab_reproduction: dict[str, Any] | None = None

    def diff(self, name: str, value: float) -> None:
        self.max_abs_diff[name] = max(self.max_abs_diff[name], float(abs(value)))

    def dataset(self, name: str, reference: str, tolerance: str, kind: str = "absolute") -> None:
        self.datasets[name] += 1
        self.kind[name] = kind
        self.reference[name] = reference
        self.tolerance[name] = tolerance


RECORDER = Recorder()


@pytest.fixture
def recorder() -> Recorder:
    return RECORDER


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("ABKIT_WRITE_RESULTS") != "1" or exitstatus != 0:
        return
    r = RECORDER
    results_meta.write(
        "validation.json",
        COMMAND,
        {
            "equivalence": {
                name: {
                    "reference": r.reference[name],
                    "tolerance": r.tolerance[name],
                    "datasets": r.datasets[name],
                    "difference_kind": r.kind[name],
                    "max_diff": r.max_abs_diff[name],
                }
                for name in sorted(r.datasets)
            },
            "hypothesis": {
                "examples_by_property": dict(sorted(r.hypothesis_examples.items())),
                "total_examples": sum(r.hypothesis_examples.values()),
            },
            "edge_cases_covered": sorted(set(r.edge_cases)),
            "tests_passed": session.testscollected - session.testsfailed,
        },
    )
    if r.lab_reproduction is not None:
        results_meta.write("lab_reproduction.json", COMMAND, r.lab_reproduction)
