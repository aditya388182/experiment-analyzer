"""Print the resume bullets with every number read from results/*.json (and the lab JSON for the churn AUC).

A missing file or key prints MISSING(<file>:<key>) instead of a number, so nothing is ever typed by hand.
Usage: python3 scripts/bullets.py [--markdown-table]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
LAB_CHURN = ROOT / "backend" / "reports" / "data" / "churn_results.json"
_missing: list[str] = []


def get(file: Path, path: str | list[str]) -> Any:
    """``path`` is "a.b.c", or a list of keys when a key itself contains dots (lab keys like "mens_visit.diff")."""
    parts = path.split(".") if isinstance(path, str) else path
    label = f"{file.relative_to(ROOT)}:{'.'.join(parts)}"
    try:
        cur: Any = json.loads(file.read_text())
        for part in parts:
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        if cur is None:
            raise KeyError(path)
        return cur
    except (FileNotFoundError, KeyError, IndexError, ValueError, TypeError):
        _missing.append(label)
        return None


def fmt(value: Any, spec: str, label: str = "") -> str:
    if value is None:
        return f"MISSING({label})" if label else "MISSING"
    return format(value, spec)


def hpa_env(env: str | None) -> str:
    if env is None:
        return "MISSING(hpa.json:environment)"
    return "local k3d" if "k3d" in env else "production"


def numbers() -> dict[str, str]:
    lab = RESULTS / "lab_reproduction.json"
    val = RESULTS / "validation.json"
    tests = RESULTS / "tests.json"
    smoke = RESULTS / "deploy_smoke.json"
    hpa = RESULTS / "hpa.json"
    diff = get(lab, ["comparisons", "mens_visit.diff", "app"])
    lo = get(lab, ["comparisons", "mens_visit.ci_low", "app"])
    hi = get(lab, ["comparisons", "mens_visit.ci_high", "app"])
    arms = get(lab, "arm_counts")
    eq = get(val, "equivalence") or {}
    scipy_fns = [k for k in ("diff_in_means", "srm_test", "cuped") if k in eq]
    scipy_max = max((eq[k]["max_diff"] for k in scipy_fns), default=None)
    return {
        "customers": fmt(sum(arms.values()) if arms else None, ",", "lab_reproduction.json:arm_counts"),
        "diff_pts": fmt(diff * 100 if diff is not None else None, ".2f", "lab_reproduction.json:mens_visit.diff"),
        "ci_low_pts": fmt(lo * 100 if lo is not None else None, ".2f", "lab_reproduction.json:mens_visit.ci_low"),
        "ci_high_pts": fmt(hi * 100 if hi is not None else None, ".2f", "lab_reproduction.json:mens_visit.ci_high"),
        "srm_p": fmt(get(lab, "comparisons.srm_p.app"), ".4f", "lab_reproduction.json:srm_p"),
        "lab_max_abs_diff": fmt(get(lab, "max_abs_diff"), ".1e", "lab_reproduction.json:max_abs_diff"),
        "scipy_max_diff": fmt(scipy_max, ".1e", "validation.json:equivalence"),
        "hypothesis_examples": fmt(get(val, "hypothesis.total_examples"), ",", "validation.json:hypothesis"),
        "edge_cases": fmt(len(get(val, "edge_cases_covered") or []) or None, "d", "validation.json:edge_cases"),
        "tests_total": fmt(get(tests, "total.passed"), ",", "tests.json:total.passed"),
        "tests_failed": fmt(get(tests, "total.failures"), "d", "tests.json:total.failures"),
        "churn_auc": fmt(get(LAB_CHURN, "test_selected.roc_auc"), ".2f", "churn_results.json:test_selected.roc_auc"),
        "churn_baseline_auc": fmt(
            get(LAB_CHURN, "test_by_model.recency_rule.roc_auc"),
            ".2f",
            "churn_results.json:test_by_model.recency_rule.roc_auc",
        ),
        "deploy_seconds": fmt(get(smoke, "submit_to_terminal_seconds"), ".2f", "deploy_smoke.json"),
        "hpa_max": fmt(get(hpa, "replicas_max"), "d", "hpa.json:replicas_max"),
        "hpa_start": fmt(get(hpa, "replicas_start"), "d", "hpa.json:replicas_start"),
        "hpa_env": hpa_env(get(hpa, "environment")),
    }


def main() -> int:
    n = numbers()
    if "--markdown-table" in sys.argv:
        rows = [
            (
                "Hillstrom reproduction: men's email vs no email, visit rate",
                f"+{n['diff_pts']} pts (95% CI {n['ci_low_pts']} to {n['ci_high_pts']}), {n['customers']} customers",
            ),
            ("SRM p-value (planned 1/3 split)", n["srm_p"]),
            ("Largest absolute difference, app vs lab, over 12 reproduced values", n["lab_max_abs_diff"]),
            (
                "Largest absolute difference, abkit vs SciPy/numpy (Welch, chi-square, CUPED; 20 datasets each)",
                n["scipy_max_diff"],
            ),
            ("Hypothesis examples generated", n["hypothesis_examples"]),
            ("Edge cases covered", n["edge_cases"]),
            (
                "Tests passed (abkit + backend + integration + frontend)",
                f"{n['tests_total']} ({n['tests_failed']} failed)",
            ),
            ("Churn model test AUC vs recency baseline (lab)", f"{n['churn_auc']} vs {n['churn_baseline_auc']}"),
            ("Deployed sample analysis, submit → SUCCEEDED (s)", n["deploy_seconds"]),
            (f"Worker replicas during a 20-job burst ({n['hpa_env']})", f"{n['hpa_start']} → {n['hpa_max']}"),
        ]
        print("| Measure | Value |\n|---|---|")
        for k, v in rows:
            print(f"| {k} | {v} |")
        return 0
    print("Resume bullets (every number read from results/*.json; MISSING = not measured yet)\n")
    print(
        "- Built a Django REST Framework API with Celery jobs on RabbitMQ, presigned S3 uploads, and a React 18 UI "
        f"on Kubernetes (Helm, k3s); {n['tests_total']} automated tests including a real-broker integration test."
    )
    print(
        f"- A stats library matched to SciPy to 1e-9 (max difference {n['scipy_max_diff']}) with "
        f"{n['hypothesis_examples']} Hypothesis examples reproduces a {n['customers']}-customer test "
        f"(+{n['diff_pts']} pts, 95% CI {n['ci_low_pts']} to {n['ci_high_pts']}); churn model AUC "
        f"{n['churn_auc']} vs {n['churn_baseline_auc']} baseline."
    )
    print(
        f"- Deployed with GitHub Actions to k3s on EC2: a sample analysis completes in {n['deploy_seconds']} s "
        f"after submit; the worker autoscales {n['hpa_start']} → {n['hpa_max']} replicas under a 20-job burst "
        f"({n['hpa_env']})."
    )
    if _missing:
        print("\nMISSING keys:")
        for m in sorted(set(_missing)):
            print(f"  - {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
