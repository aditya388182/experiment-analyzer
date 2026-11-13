# reports/data: lab results shown in the app

Source: lab build of 2026-11-05 (lab_inputs/). The lab repo (applied-data-science-lab) has not been pushed, so there
is no public URL or commit hash yet. Files are copied unchanged:

| File here | Lab file |
|---|---|
| `exp_results.json` | `01-experiment-analysis/results/results.json` |
| `churn_results.json` | `02-churn-value/results/results.json` |
| `churn_recalibration.json` | `02-churn-value/results/recalibration.json` |
| `forecast_results.json` | `03-forecasting/results/results.json` |

`GET /api/reports` returns `source.repo = "applied-data-science-lab"` and `source.commit = "lab build of 2026-11-05 (lab_inputs/)"`.
When the lab is pushed, update `REPORTS_SOURCE_REPO` / `REPORTS_SOURCE_COMMIT` in `backend/analyzer/reports.py` and this file.
