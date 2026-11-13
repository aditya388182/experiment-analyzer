"""Write results/tests.json from the JUnit XML files the three suites produce (make results-tests)."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import results_meta  # noqa: E402

SUITES = {"abkit": "junit-abkit.xml", "backend": "junit-backend.xml", "integration": "junit-integration.xml",
          "frontend": "junit-frontend.xml"}


def counts(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for s in suites:
        for k in total:
            total[k] += int(s.get(k, 0) or 0)
    total["passed"] = total["tests"] - total["failures"] - total["errors"] - total["skipped"]
    return total


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else results_meta.REPO_ROOT / "build"
    suites = {}
    for name, fname in SUITES.items():
        p = out_dir / fname
        suites[name] = counts(p) if p.exists() else None
    present = [v for v in suites.values() if v]
    payload = {
        "suites": suites,
        "total": {k: sum(v[k] for v in present) for k in ("tests", "passed", "failures", "errors", "skipped")},
    }
    path = results_meta.write("tests.json", "make results-tests", payload)
    print(f"wrote {path}: {payload['total']}")


if __name__ == "__main__":
    main()
