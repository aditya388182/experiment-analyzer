# lab_inputs: files reused from applied-data-science-lab

These are finished inputs copied from the lab. The experiment-analyzer project reuses them; nothing here gets built.

| Path | Used for |
|---|---|
| `01-experiment-analysis/abtest/` and `tests/` | starting code and tests for the `abkit` package (SPEC.md section 8) |
| `01-experiment-analysis/data/hillstrom.csv` and `SOURCE.md` | the one-click sample dataset (64,000 customers). The sha256 is in SOURCE.md. |
| `01-experiment-analysis/results/results.json` | expected values for the lab-reproduction test. Copy it to `backend/reports/data/exp_results.json`. |
| `02-churn-value/results/*.json`, `03-forecasting/results/results.json` | Model Reports page data (SPEC.md section 9) |

**Origin:** applied-data-science-lab, as built and delivered on 2026-11-05. It has not been pushed to GitHub, so there is no commit hash. Write "lab build of 2026-11-05 (lab_inputs/)" as the source in `reports/data/SOURCE.md`.
